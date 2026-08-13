"""Donati (demir) planindan cap/adet/aralik okuyup kg metraji uretir.

Kalip planinin yaninda bir donati plani verildiginde beton hacmi uzerinden
katsayi esasli yaklasik demirin yerine, etiketlerden okunan cap/adet/aralik
degerleri eleman geometrisiyle birlestirilerek kg hesabi yapilir.

Kabul edilen notasyon:
  - "4Ø18"  -> 4 adet Ø18 boyuna donati
  - "5Φ20"  -> 5 adet Φ20
  - "Ø8/20" -> Ø8 etriye, 20 cm ara ile
  - "d10/15"-> d10, 15 cm ara (mesh)
  - "2Ø12+3Ø14" -> birlesik (iki boyuna kalem)

Uzunluklar eleman tipine gore standart kabullerle hesaplanir; tum sonuclar
YAKLASIK isaretlenir ve kenetlenme/bindirme/acilim detaylari icin donati
paftasinin kontrolu istenir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from hakedis.config import Ayarlar
from hakedis.geometry import alan
from hakedis.model import Eleman, ElemanTipi, HamVarlik, KirikOlcuSatiri, Nokta

# Aralikli (etriye/mesh): "Ø8/20" veya "d10/15"
_ARALIK = re.compile(
    r"([ØΦϕ∅⌀d])\s*(\d{1,2})\s*[/]\s*(\d{1,3})", re.IGNORECASE
)
# Adet + cap: "4Ø18"
_ADET = re.compile(r"(\d{1,2})\s*[ØΦϕ∅⌀]\s*(\d{1,2})", re.IGNORECASE)
# Yalniz cap: "Ø16" (aralikli olarak okunmamissa 1 adet)
_CAP_YALNIZ = re.compile(
    r"(?<![\dØΦϕ∅⌀/])([ØΦϕ∅⌀])\s*(\d{1,2})(?!\s*/\s*\d)", re.IGNORECASE
)
_DONATI_IPUCU = re.compile(
    r"[ØΦϕ∅⌀]|\b\d{1,2}\s*[ØΦϕ∅⌀]|\bd\s*\d{1,2}\s*/\s*\d", re.IGNORECASE
)


@dataclass
class DonatiKalem:
    """Tek bir cap grubu: boyuna (adet) veya etriye/mesh (aralik)."""

    cap_mm: int
    adet: int | None = None
    aralik_cm: float | None = None

    @property
    def birim_agirlik(self) -> float:
        """Capa gore kg/m: w = d^2 x 0.00617 (d mm)."""
        return round(self.cap_mm**2 * 0.00617, 4)


@dataclass
class DonatiOkuma:
    """Cizimden okunan tek donati etiketi ve kendisine atanan eleman."""

    metin: str
    konum: Nokta
    katman: str = ""
    kalemler: list[DonatiKalem] = field(default_factory=list)
    eleman: Eleman | None = None


def _cap_isareti(metin: str) -> str:
    return metin.replace("Φ", "Ø").replace("ϕ", "Ø").replace("∅", "Ø").replace("⌀", "Ø")


def donati_kalemleri(metin: str, ayarlar: Ayarlar) -> list[DonatiKalem]:
    """Bir metindeki donati kalemlerini ayristirir.

    Donati isaretli hicbir bilgi yoksa bos liste doner (donati etiketi
    degildir).
    """
    temiz = _cap_isareti(" ".join(metin.replace("\n", " ").split()))
    if not _DONATI_IPUCU.search(temiz):
        return []

    kalemler: list[DonatiKalem] = []
    for m in _ARALIK.finditer(temiz):
        kalemler.append(
            DonatiKalem(cap_mm=int(m.group(2)), aralik_cm=float(m.group(3)))
        )
    for m in _ADET.finditer(temiz):
        kalemler.append(
            DonatiKalem(cap_mm=int(m.group(2)), adet=int(m.group(1)))
        )
    for m in _CAP_YALNIZ.finditer(temiz):
        cap = int(m.group(2))
        if not any(k.cap_mm == cap for k in kalemler):
            kalemler.append(DonatiKalem(cap_mm=cap, adet=1))
    return _temizle(kalemler)


def _temizle(kalemler: list[DonatiKalem]) -> list[DonatiKalem]:
    sonuc: list[DonatiKalem] = []
    for k in kalemler:
        if k.adet is None and k.aralik_cm is None:
            continue
        if k.adet is not None and k.adet <= 0:
            continue
        if k.aralik_cm is not None and k.aralik_cm <= 0:
            continue
        sonuc.append(k)
    return sonuc


def donati_okumalari(
    varliklar: list[HamVarlik], ayarlar: Ayarlar
) -> list[DonatiOkuma]:
    """Cizimdeki yazilardan donati kalemi icerenleri toplar."""
    okumalar: list[DonatiOkuma] = []
    for v in varliklar:
        if v.tur != "metin" or not v.metin.strip():
            continue
        kalemler = donati_kalemleri(v.metin, ayarlar)
        if not kalemler:
            continue
        konum = v.noktalar[0] if v.noktalar else Nokta(0.0, 0.0)
        okumalar.append(
            DonatiOkuma(
                metin=v.metin, konum=konum, katman=v.katman, kalemler=kalemler
            )
        )
    return okumalar


def _kapalilar(eleman: Eleman) -> list[Nokta]:
    return eleman.cevre or [s.orta for s in eleman.segmentler]


def donati_elemana_ata(okumalar: list[DonatiOkuma], elemanlar: list[Eleman]) -> None:
    """Her okumayi konumuna en yakin uygun elemana atar."""
    hedefler = [
        e
        for e in elemanlar
        if e.tip
        in (ElemanTipi.KOLON, ElemanTipi.PERDE, ElemanTipi.KIRIS,
            ElemanTipi.DOSEME, ElemanTipi.MERDIVEN)
    ]
    for oku in okumalar:
        en_iyi = None
        en_mesafe = float("inf")
        for e in hedefler:
            d = oku.konum.mesafe(e.merkez)
            if d < en_mesafe:
                en_mesafe = d
                en_iyi = e
        oku.eleman = en_iyi


def _boyuna_kg(oku: DonatiOkuma, boy: float, ayarlar: Ayarlar) -> float:
    katsayi = float(ayarlar.al("donati.boy_katsayisi", 1.0) or 1.0)
    toplam = 0.0
    for k in oku.kalemler:
        if k.adet is None:
            continue
        toplam += k.adet * (boy * katsayi) * k.birim_agirlik
    return toplam


def _kesit_cevresi(b: float, h: float, pas: float, kanca: float) -> float:
    """Tek etriye uzunlugu: 2*(b+h) - 8*pas + kanca."""
    return max(2 * (b + h) - 8 * pas + kanca, 0.5)


def donati_kg(
    oku: DonatiOkuma, ayarlar: Ayarlar, net_yukseklik: float
) -> float:
    """Okumayi elemana gore kg'ye cevirir."""
    e = oku.eleman
    if e is None:
        return 0.0
    pas = float(ayarlar.al("donati.pas_payi", 0.03) or 0.03)
    kanca = float(ayarlar.al("donati.etriye_kanca", 0.15) or 0.15)
    b = float(e.olculer.get("b", 0.0) or 0.0)
    h = float(e.olculer.get("h", 0.0) or 0.0)
    eksen = float(e.olculer.get("eksen_uzunlugu", 0.0) or 0.0)
    net = float(e.olculer.get("net_uzunluk", eksen) or eksen)

    if e.tip == ElemanTipi.KOLON:
        boy = net_yukseklik
        cevre = _kesit_cevresi(b, h, pas, kanca)
        etriye = 0.0
        for k in oku.kalemler:
            if k.aralik_cm is None:
                continue
            n = int(net_yukseklik / (k.aralik_cm / 100.0)) + 1
            etriye += n * cevre * k.birim_agirlik
        return _boyuna_kg(oku, boy, ayarlar) + etriye

    if e.tip == ElemanTipi.KIRIS:
        boy = net if net > 0 else eksen
        cevre = _kesit_cevresi(b, h, pas, kanca)
        etriye = 0.0
        for k in oku.kalemler:
            if k.aralik_cm is None:
                continue
            n = int(boy / (k.aralik_cm / 100.0)) + 1
            etriye += n * cevre * k.birim_agirlik
        return _boyuna_kg(oku, boy, ayarlar) + etriye

    if e.tip == ElemanTipi.PERDE:
        boy = net if net > 0 else eksen
        yatay = 0.0
        for k in oku.kalemler:
            if k.aralik_cm is None:
                continue
            n = int(net_yukseklik / (k.aralik_cm / 100.0)) + 1
            yatay += n * boy * k.birim_agirlik
        return _boyuna_kg(oku, net_yukseklik, ayarlar) + yatay

    if e.tip in (ElemanTipi.DOSEME, ElemanTipi.MERDIVEN):
        pts = _kapalilar(e)
        a = alan(pts) if len(pts) >= 3 else 0.0
        mesh = 0.0
        iki_yon = bool(ayarlar.al("donati.mesh_iki_yon", True))
        for k in oku.kalemler:
            if k.aralik_cm is None:
                continue
            ara_m = float(k.aralik_cm) / 100.0
            m2 = a * (1.0 / ara_m) * k.birim_agirlik
            if iki_yon:
                m2 *= 2.0
            mesh += m2
        return _boyuna_kg(oku, max(net, eksen, 1.0), ayarlar) + mesh
    return 0.0


def donati_satirlari(
    okumalar: list[DonatiOkuma],
    elemanlar: list[Eleman],
    ayarlar: Ayarlar,
    net_yukseklik: float,
) -> list[KirikOlcuSatiri]:
    """Okumalari elemanlara atar ve kg metraj satirlarini uretir.

    Ayni elemana birden fazla okuma atandiginda tek satirda toplanir; cap
    dagilimi detaya yazilir. Kg uretmeyen okumalar atlanir.
    """
    donati_elemana_ata(okumalar, elemanlar)
    gruplar: dict[str, list[DonatiOkuma]] = {}
    for oku in okumalar:
        if oku.eleman is None:
            continue
        anahtar = f"{oku.eleman.tip.value}|{oku.eleman.ad}"
        gruplar.setdefault(anahtar, []).append(oku)

    satirlar: list[KirikOlcuSatiri] = []
    for anahtar, grp in gruplar.items():
        tip, ad = anahtar.split("|", 1)
        e = grp[0].eleman
        toplam = sum(donati_kg(o, ayarlar, net_yukseklik) for o in grp)
        if toplam <= 1e-9:
            continue
        cap_dagilim = []
        for g in grp:
            for k in g.kalemler:
                if k.adet is not None:
                    cap_dagilim.append(f"Ø{k.cap_mm} x {k.adet}")
                else:
                    cap_dagilim.append(f"Ø{k.cap_mm}/{k.aralik_cm:g}")
        satirlar.append(
            KirikOlcuSatiri(
                poz=ayarlar.poz("demir"),
                eleman_adi=ad,
                tip=e.tip,
                tanim=f"Donati ({tip}) - DONATI PLANINDAN OKUNDU",
                benzer=1,
                kg=round(toplam, 2),
                birim="kg",
                formul=f"{len(grp)} etiket, toplam {toplam:.2f} kg",
                kat=ayarlar.kat_adi,
                detay=[
                    f"Cap dagilimi: {', '.join(cap_dagilim)}",
                    "YAKLASIK: donati planindan okunan cap/adet/aralik "
                    "degerleri standart kabullerle kg'ye cevrildi; kenetlenme, "
                    "bindirme ve acilim detaylari icin donati paftasini "
                    "kontrol edin.",
                ],
            )
        )
    return satirlar
