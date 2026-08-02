"""Otomatik katman keşfi.

Katman adları her ofiste, hatta her projede farklıdır: "KOLON", "S-KOL",
"BETONARME-DIKME", "A$C-COL"... Bunları kullanıcıya sordurmak yerine
çizimin KENDİSİNDEN çıkarırız.

Yöntem: her katmandaki geometrinin imzasına bakılır.
  - 0.20-2.00 m kenarlı, tıknaz kapalı kesitler        -> kolon
  - 0.15-1.00 m kalınlıkta, narin veya L/T/U kesitler  -> perde
  - 0.15-1.00 m aralıkla paralel çizgi çiftleri        -> kiriş
  - çizimin en büyük kapalı alanı                      -> döşeme
  - döşemenin içinde kalan, kolon olamayacak kadar
    büyük tıknaz kapalı alanlar                        -> boşluk
  - eşleşmeyen, uzun ve çifti olmayan çizgiler         -> aks/ölçü (yoksay)

Bu sınıflandırma katman adına hiç bakmaz; adı ne olursa olsun çalışır.
Sonuç `hakedis kesfet` ile rapor edilir ve istenirse doğrudan
yapılandırma dosyası olarak yazılır.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median

from hakedis.config import Ayarlar
from hakedis.geometry import (
    alan,
    dogrusallari_sadelestir,
    kenarlar,
    min_donmus_dikdortgen,
    nokta_icinde_mi,
    ortogonale_yasla,
    paralel_cift_eksenleri,
    poligondan_eksen,
    tekrarlari_temizle,
)
from hakedis.model import Cizim, HamVarlik, Nokta, Segment

# Sinifin adi -> yapilandirmadaki katman grubu
GRUPLAR = ("kolon", "perde", "kiris", "doseme", "bosluk", "metin", "yoksay")


@dataclass
class KatmanImzasi:
    """Bir katmanin geometrik parmak izi ve buradan cikan tip onerisi."""

    katman: str
    varlik_sayisi: int = 0
    kapali_sayisi: int = 0
    cizgi_sayisi: int = 0
    metin_sayisi: int = 0
    alanlar: list[float] = field(default_factory=list)
    en_degerleri: list[float] = field(default_factory=list)
    narinlikler: list[float] = field(default_factory=list)
    cift_sayisi: int = 0
    cift_araligi: float = 0.0
    onerilen_tip: str | None = None
    gerekce: str = ""
    guven: float = 0.0

    @property
    def en_buyuk_alan(self) -> float:
        return max(self.alanlar) if self.alanlar else 0.0

    @property
    def ortanca_en(self) -> float:
        return median(self.en_degerleri) if self.en_degerleri else 0.0

    @property
    def ortanca_narinlik(self) -> float:
        return median(self.narinlikler) if self.narinlikler else 0.0


def _kapali_poligonlar(varliklar: list[HamVarlik]) -> list[list[Nokta]]:
    out: list[list[Nokta]] = []
    for v in varliklar:
        if v.tur in ("poligon", "tarama") and v.kapali and len(v.noktalar) >= 3:
            pts = dogrusallari_sadelestir(
                ortogonale_yasla(tekrarlari_temizle(v.noktalar))
            )
            if len(pts) >= 3:
                out.append(pts)
    return out


def _imza_topla(katman: str, varliklar: list[HamVarlik], ayarlar: Ayarlar) -> KatmanImzasi:
    imza = KatmanImzasi(katman=katman, varlik_sayisi=len(varliklar))
    cizgiler: list[Segment] = []

    for v in varliklar:
        if v.tur == "metin":
            imza.metin_sayisi += 1
        elif v.tur in ("poligon", "tarama") and v.kapali:
            imza.kapali_sayisi += 1
        elif v.tur in ("cizgi", "yay"):
            imza.cizgi_sayisi += 1
            cizgiler.extend(kenarlar(v.noktalar, kapali=False))

    per_min = float(ayarlar.al("sezgisel.perde_min_kalinlik", 0.15))
    per_max = float(ayarlar.al("sezgisel.perde_max_kalinlik", 1.00))

    for cevre in _kapali_poligonlar(varliklar):
        a = alan(cevre)
        if a <= 1e-6:
            continue
        imza.alanlar.append(a)
        dik = min_donmus_dikdortgen(cevre)
        if dik is None:
            continue
        dolgu = a / dik.alan if dik.alan > 1e-9 else 1.0
        if dolgu < 0.85:
            # L/T/U kesit: sinir dikdortgeninin kisa kenari kalinlik DEGILDIR
            # (L'nin kollari acildigi icin). Gercek kalinligi karsilikli yuz
            # eslemesiyle buluruz.
            eksenler, kalinlik = poligondan_eksen(cevre, per_min, per_max)
            if eksenler and kalinlik > 0:
                eksen_boyu = sum(s.uzunluk for s in eksenler)
                imza.en_degerleri.append(kalinlik)
                imza.narinlikler.append(
                    eksen_boyu / kalinlik if kalinlik > 1e-9 else 99.0
                )
                continue
            # Eksen cikarilamadi: yine de tikiz olmadigi icin perde tarafina cek
            imza.en_degerleri.append(dik.en)
            imza.narinlikler.append(max(dik.narinlik, 5.0))
            continue
        imza.en_degerleri.append(dik.en)
        imza.narinlikler.append(dik.narinlik)

    if cizgiler:
        ciftler = paralel_cift_eksenleri(
            cizgiler,
            float(ayarlar.al("sezgisel.kiris_min_genislik", 0.15)),
            float(ayarlar.al("sezgisel.kiris_max_genislik", 1.00)),
            min_uzunluk=float(ayarlar.al("sezgisel.kiris_min_uzunluk", 0.50)),
        )
        imza.cift_sayisi = len(ciftler)
        if ciftler:
            imza.cift_araligi = median([g for _, g in ciftler])
    return imza


def _doseme_icinde_mi(
    poligonlar: list[list[Nokta]], doseme_cevreleri: list[list[Nokta]]
) -> bool:
    """Katmandaki kapali alanlarin cogu bir dosemenin icinde mi?"""
    if not poligonlar or not doseme_cevreleri:
        return False
    icerde = 0
    for p in poligonlar:
        merkez = Nokta(
            sum(n.x for n in p) / len(p), sum(n.y for n in p) / len(p)
        )
        if any(nokta_icinde_mi(merkez, d) for d in doseme_cevreleri):
            icerde += 1
    return icerde >= 0.6 * len(poligonlar)


def _tip_ata(
    imza: KatmanImzasi,
    ayarlar: Ayarlar,
    poligonlar: list[list[Nokta]],
    doseme_cevreleri: list[list[Nokta]],
    en_buyuk_alan: float,
) -> None:
    """Imzadan eleman tipi cikarir; imzayi yerinde gunceller."""
    s = ayarlar.al("sezgisel", {}) or {}
    kol_min = float(s.get("kolon_min_kenar", 0.20))
    kol_max = float(s.get("kolon_max_kenar", 2.00))
    per_min = float(s.get("perde_min_kalinlik", 0.15))
    per_max = float(s.get("perde_max_kalinlik", 1.00))
    narin_esik = float(s.get("perde_narinlik_esigi", 4.0))
    doseme_min = float(s.get("doseme_min_alan", 1.00))

    # 1. Agirlikli olarak yazi iceren katman
    if imza.metin_sayisi and imza.metin_sayisi >= 0.6 * imza.varlik_sayisi:
        imza.onerilen_tip = "metin"
        imza.gerekce = f"{imza.metin_sayisi} yazı nesnesi"
        imza.guven = 0.9
        return

    # 2. Kapali poligonlar: doseme / bosluk / perde / kolon
    if imza.kapali_sayisi and imza.alanlar:
        buyuk = imza.en_buyuk_alan
        if buyuk >= max(doseme_min, 0.35 * en_buyuk_alan) and buyuk >= 5.0:
            imza.onerilen_tip = "doseme"
            imza.gerekce = f"en büyük kapalı alan {buyuk:.1f} m²"
            imza.guven = 0.85
            return

        en = imza.ortanca_en
        narinlik = imza.ortanca_narinlik

        # Kolon icin fazla buyuk, dosemenin icinde kalan tikiz alanlar
        if (
            en > kol_max
            and narinlik < narin_esik
            and _doseme_icinde_mi(poligonlar, doseme_cevreleri)
        ):
            imza.onerilen_tip = "bosluk"
            imza.gerekce = (
                f"döşeme içinde, ortanca kenar {en:.2f} m (kolon için fazla büyük)"
            )
            imza.guven = 0.55
            return

        if per_min <= en <= per_max and narinlik >= narin_esik:
            imza.onerilen_tip = "perde"
            imza.gerekce = (
                f"{imza.kapali_sayisi} kapalı kesit, ortanca kalınlık "
                f"{en:.2f} m, narinlik {narinlik:.1f}"
            )
            imza.guven = 0.8
            return

        if kol_min <= en <= kol_max:
            imza.onerilen_tip = "kolon"
            imza.gerekce = (
                f"{imza.kapali_sayisi} kapalı kesit, ortanca kenar {en:.2f} m, "
                f"narinlik {narinlik:.1f}"
            )
            imza.guven = 0.8
            return

    # 3. Paralel cizgi ciftleri -> kiris
    if imza.cift_sayisi and imza.cizgi_sayisi:
        kapsam = (imza.cift_sayisi * 2) / max(imza.cizgi_sayisi, 1)
        if kapsam >= 0.4:
            imza.onerilen_tip = "kiris"
            imza.gerekce = (
                f"{imza.cift_sayisi} paralel çizgi çifti, ortanca açıklık "
                f"{imza.cift_araligi:.2f} m"
            )
            imza.guven = 0.75 if kapsam >= 0.8 else 0.6
            return

    # 4. Cifti olmayan uzun cizgiler -> aks/olculendirme
    if imza.cizgi_sayisi and not imza.cift_sayisi and not imza.kapali_sayisi:
        imza.onerilen_tip = "yoksay"
        imza.gerekce = (
            f"{imza.cizgi_sayisi} bağımsız çizgi, eşleşen çift yok "
            f"(aks/ölçülendirme olabilir)"
        )
        imza.guven = 0.5
        return

    imza.gerekce = "geometrik imza hiçbir eleman tipine uymadı"
    imza.guven = 0.0


def imzalari_cikar(cizim: Cizim, ayarlar: Ayarlar) -> list[KatmanImzasi]:
    """Cizimdeki her katman icin geometrik imza ve tip onerisi uretir."""
    gruplar: dict[str, list[HamVarlik]] = {}
    for v in cizim.varliklar:
        gruplar.setdefault(v.katman, []).append(v)

    imzalar = [_imza_topla(ad, vs, ayarlar) for ad, vs in gruplar.items()]
    en_buyuk = max((i.en_buyuk_alan for i in imzalar), default=0.0)

    katman_poligonlari = {
        ad: _kapali_poligonlar(vs) for ad, vs in gruplar.items()
    }

    # Once doseme adaylarini belirle ki bosluk kontrolu yapilabilsin
    doseme_cevreleri: list[list[Nokta]] = []
    for imza in imzalar:
        if imza.en_buyuk_alan >= max(5.0, 0.35 * en_buyuk):
            doseme_cevreleri.extend(katman_poligonlari[imza.katman])

    for imza in imzalar:
        _tip_ata(
            imza,
            ayarlar,
            katman_poligonlari[imza.katman],
            doseme_cevreleri,
            en_buyuk,
        )

    _bosluklari_ayikla(imzalar, katman_poligonlari, doseme_cevreleri, gruplar, ayarlar)
    imzalar.sort(key=lambda i: (-i.guven, -i.varlik_sayisi))
    return imzalar


def _bosluklari_ayikla(
    imzalar: list[KatmanImzasi],
    katman_poligonlari: dict[str, list[list[Nokta]]],
    doseme_cevreleri: list[list[Nokta]],
    gruplar: dict[str, list[HamVarlik]],
    ayarlar: Ayarlar,
) -> None:
    """Kolon sanilan doseme bosluklarini ayirir.

    Plan gorunusunde 80/100'luk bir sant boslugu ile 80/100'luk bir kolon
    ayni sekilde gorunur. Ayirt edici isaret tasiyici sistemdedir: kolonlar
    kirislerin bittigi/kesistigi yerdedir, bosluklarin cevresinde kiris
    ucu yoktur. Buna gore, hicbir kiris eksenine degmeyen ve dosemenin
    icinde kalan "kolon"lar bosluk adayi sayilir.
    """
    if not doseme_cevreleri:
        return

    kiris_eksenleri: list[Segment] = []
    for imza in imzalar:
        if imza.onerilen_tip != "kiris":
            continue
        cizgiler: list[Segment] = []
        for v in gruplar[imza.katman]:
            if v.tur in ("cizgi", "yay"):
                cizgiler.extend(kenarlar(v.noktalar, kapali=False))
        for eksen, _ in paralel_cift_eksenleri(
            cizgiler,
            float(ayarlar.al("sezgisel.kiris_min_genislik", 0.15)),
            float(ayarlar.al("sezgisel.kiris_max_genislik", 1.00)),
            min_uzunluk=float(ayarlar.al("sezgisel.kiris_min_uzunluk", 0.50)),
        ):
            kiris_eksenleri.append(eksen)
    if not kiris_eksenleri:
        return

    for imza in imzalar:
        if imza.onerilen_tip != "kolon":
            continue
        poligonlar = katman_poligonlari[imza.katman]
        if not poligonlar or not _doseme_icinde_mi(poligonlar, doseme_cevreleri):
            continue
        degen = 0
        for p in poligonlar:
            if any(_eksen_poligona_degiyor_mu(s, p) for s in kiris_eksenleri):
                degen += 1
        if degen == 0:
            imza.onerilen_tip = "bosluk"
            imza.gerekce = (
                f"döşeme içinde, çevresinde kiriş ucu yok "
                f"({len(poligonlar)} kapalı alan) — kolon değil boşluk olmalı"
            )
            imza.guven = 0.6


def _eksen_poligona_degiyor_mu(
    eksen: Segment, poligon: list[Nokta], tol: float = 0.05
) -> bool:
    """Kiris ekseni poligonun icinden geciyor veya ucuna dayaniyor mu?"""
    adim = max(int(eksen.uzunluk / 0.05), 8)
    for i in range(adim + 1):
        t = i / adim
        p = Nokta(
            eksen.baslangic.x + (eksen.bitis.x - eksen.baslangic.x) * t,
            eksen.baslangic.y + (eksen.bitis.y - eksen.baslangic.y) * t,
        )
        if nokta_icinde_mi(p, poligon):
            return True
    return False


def katman_onerileri(cizim: Cizim, ayarlar: Ayarlar) -> dict[str, str]:
    """Katman adı -> eleman tipi eşlemesi (yalnızca güvenli öneriler)."""
    return {
        i.katman: i.onerilen_tip
        for i in imzalari_cikar(cizim, ayarlar)
        if i.onerilen_tip and i.guven >= 0.5
    }


def yapilandirma_metni(imzalar: list[KatmanImzasi]) -> str:
    """Keşif sonucunu, doğrudan kullanılabilir YAML parçası olarak yazar."""
    import re as _re

    gruplandirilmis: dict[str, list[str]] = {}
    for i in imzalar:
        if i.onerilen_tip and i.guven >= 0.5:
            gruplandirilmis.setdefault(i.onerilen_tip, []).append(i.katman)

    satirlar = [
        "# hakedis kesfet tarafindan uretildi.",
        "# Bu dosya cizimdeki KATMAN ADLARINA gore olusturulmustur; baska bir",
        "# projede katman adlari farkliysa kesfeti yeniden calistirin.",
        "katmanlar:",
    ]
    for grup in GRUPLAR:
        adlar = gruplandirilmis.get(grup)
        if not adlar:
            continue
        satirlar.append(f"  {grup}:")
        for ad in sorted(adlar):
            satirlar.append(f"    - '^{_re.escape(ad)}$'")
    return "\n".join(satirlar) + "\n"
