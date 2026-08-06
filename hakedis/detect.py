"""Eleman tespiti: kalip planindaki cizgilerden kolon/perde/kiris/doseme cikarimi.

Iki asamali calisir:
  1. Katman esleme  - katman adi yapilandirmadaki desenlerle eslesiyorsa tip kesin.
  2. Geometrik sezgisel - katman yoksa/eslesmezse bicimden tahmin edilir
     (narinlik, alan, paralel cizgi cifti ...).

Her elemanin kirik olcu zinciri (segmentler) burada olusturulur.
"""

from __future__ import annotations

from collections import defaultdict

from hakedis.config import Ayarlar
from hakedis.geometry import (
    alan,
    dogrusallari_sadelestir,
    kenarlar,
    min_donmus_dikdortgen,
    nokta_icinde_mi,
    ortogonale_yasla,
    paralel_cift_eksenleri,
    poligon_icinde_mi,
    poligondan_eksen,
    segmenti_poligonlarla_kirp,
    sinir_kutusu,
    tekrarlari_temizle,
    zincirle,
)
from hakedis.labels import Etiket, en_uygun_etiket, etiketi_uygula, etiketleri_topla
from hakedis.model import Cizim, Eleman, ElemanTipi, HamVarlik, Nokta, Segment

TIP_ESLEME: dict[str, ElemanTipi] = {
    "kolon": ElemanTipi.KOLON,
    "perde": ElemanTipi.PERDE,
    "kiris": ElemanTipi.KIRIS,
    "doseme": ElemanTipi.DOSEME,
    "merdiven": ElemanTipi.MERDIVEN,
    "bosluk": ElemanTipi.BOSLUK,
}


# ---------------------------------------------------------------------------
# Poligon toplama
# ---------------------------------------------------------------------------


def _cizgilerden_poligonlar(
    cizgiler: list[HamVarlik], min_alan: float
) -> list[list[Nokta]]:
    """Ayri cizgiler halinde cizilmis kapali bolgeleri poligona cevirir.

    Kolonlar cogu projede kapali polyline degil, 4 ayri LINE olarak cizilir;
    bu fonksiyon onlari yakalar.
    """
    if not cizgiler:
        return []
    try:
        from shapely.geometry import LineString
        from shapely.ops import polygonize, unary_union
    except ImportError:  # pragma: no cover
        return []

    parcalar = []
    for c in cizgiler:
        if len(c.noktalar) < 2:
            continue
        koord = [(p.x, p.y) for p in c.noktalar]
        try:
            ls = LineString(koord)
            if ls.length > 0:
                parcalar.append(ls)
        except Exception:  # pragma: no cover
            continue
    if not parcalar:
        return []
    try:
        birlesik = unary_union(parcalar)
        halkalar = list(polygonize(birlesik))
    except Exception:  # pragma: no cover
        return []

    cikti: list[list[Nokta]] = []
    for poly in halkalar:
        if poly.area < min_alan:
            continue
        pts = [Nokta(x, y) for x, y in poly.exterior.coords[:-1]]
        if len(pts) >= 3:
            cikti.append(pts)
    return cikti


def _poligonlari_topla(
    varliklar: list[HamVarlik], ayarlar: Ayarlar
) -> list[tuple[list[Nokta], str]]:
    """Bir varlik grubundan (cevre, katman) ciftleri uretir."""
    min_alan = float(ayarlar.al("sezgisel.min_poligon_alani", 0.02))
    cikti: list[tuple[list[Nokta], str]] = []
    acik_cizgiler: list[HamVarlik] = []

    for v in varliklar:
        if v.tur in ("poligon", "tarama") and v.kapali and len(v.noktalar) >= 3:
            pts = dogrusallari_sadelestir(ortogonale_yasla(tekrarlari_temizle(v.noktalar)))
            if len(pts) >= 3 and alan(pts) >= min_alan:
                cikti.append((pts, v.katman))
        elif v.tur in ("cizgi", "yay"):
            acik_cizgiler.append(v)

    for pts in _cizgilerden_poligonlar(acik_cizgiler, min_alan):
        pts = dogrusallari_sadelestir(ortogonale_yasla(pts))
        if len(pts) >= 3:
            katman = acik_cizgiler[0].katman if acik_cizgiler else ""
            cikti.append((pts, katman))

    # Ayni bolgeyi tarif eden yinelenen poligonlari at (tarama + sinir cizgisi)
    benzersiz: list[tuple[list[Nokta], str]] = []
    for pts, katman in cikti:
        kutu = sinir_kutusu(pts)
        a = alan(pts)
        yineleme = False
        for mevcut, _ in benzersiz:
            m_kutu = sinir_kutusu(mevcut)
            if (
                abs(alan(mevcut) - a) <= max(a * 0.02, 1e-4)
                and all(abs(kutu[i] - m_kutu[i]) < 0.02 for i in range(4))
            ):
                yineleme = True
                break
        if not yineleme:
            benzersiz.append((pts, katman))
    return benzersiz


# ---------------------------------------------------------------------------
# Tip kararlari
# ---------------------------------------------------------------------------


def _kolon_mu_perde_mi(cevre: list[Nokta], ayarlar: Ayarlar) -> ElemanTipi:
    """Kapali bir kesitin kolon mu perde mi oldugunu narinliktan karar verir."""
    dik = min_donmus_dikdortgen(cevre)
    if dik is None:
        return ElemanTipi.BILINMEYEN
    esik = float(ayarlar.al("sezgisel.perde_narinlik_esigi", 4.0))
    # Dikdortgen olmayan (L/U/T) kesitler pratikte perdedir
    dolgu_orani = alan(cevre) / dik.alan if dik.alan > 1e-9 else 1.0
    if dolgu_orani < 0.85:
        return ElemanTipi.PERDE
    return ElemanTipi.PERDE if dik.narinlik >= esik else ElemanTipi.KOLON


def _kolon_olculeri(cevre: list[Nokta], ayarlar: Ayarlar) -> dict[str, float]:
    dik = min_donmus_dikdortgen(cevre)
    if dik is None:
        return {}
    return {
        "b": round(dik.en, 4),
        "h": round(dik.boy, 4),
        "aci": round(dik.aci, 2),
        "kesit_alani": round(alan(cevre), 5),
        "cevre_uzunlugu": round(
            sum(k.uzunluk for k in kenarlar(cevre, kapali=True)), 4
        ),
    }


# ---------------------------------------------------------------------------
# Eleman uretimi
# ---------------------------------------------------------------------------


def _kolon_elemani(cevre: list[Nokta], katman: str, ayarlar: Ayarlar) -> Eleman:
    e = Eleman(ad="", tip=ElemanTipi.KOLON, cevre=cevre, kaynak_katman=katman)
    e.olculer.update(_kolon_olculeri(cevre, ayarlar))
    # Kolonun kirik olcusu: kesit cevresinin kenarlari (kalip cevresi bunlardan)
    e.segmentler = kenarlar(cevre, kapali=True)
    return e


def _perde_elemani(cevre: list[Nokta], katman: str, ayarlar: Ayarlar) -> Eleman:
    e = Eleman(ad="", tip=ElemanTipi.PERDE, cevre=cevre, kaynak_katman=katman)
    min_k = float(ayarlar.al("sezgisel.perde_min_kalinlik", 0.15))
    max_k = float(ayarlar.al("sezgisel.perde_max_kalinlik", 1.00))
    eksenler, kalinlik = poligondan_eksen(cevre, min_k, max_k)
    if eksenler:
        e.segmentler = zincirle(eksenler)
        e.olculer["t"] = round(kalinlik, 4)
    else:
        # Eksen cikarilamadi: minimum dikdortgene dus
        dik = min_donmus_dikdortgen(cevre)
        if dik is not None:
            e.olculer["t"] = round(dik.en, 4)
            e.segmentler = [
                Segment(
                    Nokta(
                        dik.merkez.x
                        - dik.boy / 2 * _cos(dik.aci),
                        dik.merkez.y - dik.boy / 2 * _sin(dik.aci),
                    ),
                    Nokta(
                        dik.merkez.x + dik.boy / 2 * _cos(dik.aci),
                        dik.merkez.y + dik.boy / 2 * _sin(dik.aci),
                    ),
                )
            ]
            e.guven = 0.6
            e.not_ekle(
                "Perde orta ekseni kenar eslemesiyle cikarilamadi; en kucuk "
                "cevreleyen dikdortgenden yaklasik alindi."
            )
    e.olculer["kesit_alani"] = round(alan(cevre), 5)
    e.olculer["eksen_uzunlugu"] = round(e.toplam_uzunluk, 4)
    # Serbest uc sayisi (bas kalibi icin): zincirin kopuk uclari
    e.olculer["serbest_uc"] = float(_serbest_uc_sayisi(e.segmentler))
    return e


def _cos(derece: float) -> float:
    import math

    return math.cos(math.radians(derece))


def _sin(derece: float) -> float:
    import math

    return math.sin(math.radians(derece))


def _serbest_uc_sayisi(segmentler: list[Segment], tol: float = 1e-3) -> int:
    """Eksen zincirinin baska parcaya baglanmayan uc sayisi."""
    if not segmentler:
        return 0
    uclar: list[Nokta] = []
    for s in segmentler:
        uclar.extend([s.baslangic, s.bitis])
    serbest = 0
    for i, p in enumerate(uclar):
        komsu = sum(1 for j, q in enumerate(uclar) if i != j and p.mesafe(q) <= tol)
        if komsu == 0:
            serbest += 1
    return serbest


def _kiris_elemani(
    eksen: Segment, genislik: float, katman: str, ayarlar: Ayarlar
) -> Eleman:
    e = Eleman(ad="", tip=ElemanTipi.KIRIS, kaynak_katman=katman)
    e.segmentler = [eksen]
    e.olculer["b"] = round(genislik, 4)
    e.olculer["h"] = float(ayarlar.al("kat.kiris_yuksekligi", 0.50))
    e.olculer["eksen_uzunlugu"] = round(eksen.uzunluk, 4)
    return e


def _duvar_elemanlari(varliklar: list[HamVarlik], ayarlar: Ayarlar) -> list[Eleman]:
    """Mimari planda cift paralel cizgi olarak cizilmis bolme duvarlarini bulur.

    Kapali poligon duvarlar da kenarlarina ayrilir; paralel cizgi eslestirme
    ikisini de kapsar. Duvar yuksekligi kattan kata tasiyici olmadigi icin
    dogrudan tahmin edilemez; bu yuzden eleman guveni dusuk isaretlenir.
    """
    cizgiler: list[Segment] = []
    for v in varliklar:
        for k in kenarlar(v.noktalar, kapali=v.kapali):
            cizgiler.append(k)
    if not cizgiler:
        return []

    ciftler = paralel_cift_eksenleri(
        cizgiler,
        float(ayarlar.al("duvar.min_genislik", 0.10)),
        float(ayarlar.al("duvar.max_genislik", 0.50)),
        min_uzunluk=float(ayarlar.al("duvar.min_uzunluk", 0.30)),
    )
    katman = varliklar[0].katman
    elemanlar: list[Eleman] = []
    for eksen, genislik in ciftler:
        e = Eleman(ad="", tip=ElemanTipi.DUVAR, kaynak_katman=katman)
        e.segmentler = [eksen]
        e.olculer["b"] = round(genislik, 4)
        e.olculer["eksen_uzunlugu"] = round(eksen.uzunluk, 4)
        e.guven = 0.6
        elemanlar.append(e)
    return elemanlar


def _doseme_elemani(
    cevre: list[Nokta], katman: str, ayarlar: Ayarlar
) -> Eleman:
    e = Eleman(ad="", tip=ElemanTipi.DOSEME, cevre=cevre, kaynak_katman=katman)
    e.segmentler = kenarlar(cevre, kapali=True)
    e.olculer["t"] = float(ayarlar.al("kat.doseme_kalinligi", 0.15))
    e.olculer["brut_alan"] = round(alan(cevre), 4)
    return e


# ---------------------------------------------------------------------------
# Ana tespit akisi
# ---------------------------------------------------------------------------


def elemanlari_tespit_et(
    cizim: Cizim, ayarlar: Ayarlar
) -> tuple[list[Eleman], list[str]]:
    """Cizimden eleman listesi cikarir. Dondurur: (elemanlar, uyarilar)."""
    uyarilar: list[str] = list(cizim.notlar)
    gruplar: dict[str, list[HamVarlik]] = defaultdict(list)
    eslenmemis: list[HamVarlik] = []

    for v in cizim.varliklar:
        tip = ayarlar.katman_tipi(v.katman)
        if tip == "yoksay":
            continue
        if tip == "metin" or v.tur == "metin":
            gruplar["metin"].append(v)
            continue
        if tip is None:
            eslenmemis.append(v)
        else:
            gruplar[tip].append(v)

    etiketler = etiketleri_topla(gruplar["metin"] + eslenmemis, ayarlar)

    sezgisel_aktif = bool(ayarlar.al("sezgisel.aktif", True))
    if eslenmemis and sezgisel_aktif and not any(
        gruplar.get(t) for t in ("kolon", "perde", "kiris", "doseme")
    ):
        uyarilar.append(
            f"Hicbir katman adi yapilandirmayla eslesmedi ({len(eslenmemis)} varlik). "
            f"Sezgisel mod devreye girdi; sonuclari kontrol paftasindan mutlaka "
            f"dogrulayin. Katman adlarinizi gormek icin: hakedis katmanlar <dosya>"
        )
        # Sezgisel modda tum eslenmemis varliklar tek havuza girer
        gruplar["sezgisel"] = eslenmemis
    elif eslenmemis:
        adlar = sorted({v.katman for v in eslenmemis})[:12]
        uyarilar.append(
            f"{len(eslenmemis)} varlik hicbir katman desenine uymadigi icin "
            f"metraja girmedi. Eslenmeyen katmanlar: {', '.join(adlar)}"
        )

    elemanlar: list[Eleman] = []

    # --- Kolon ve perde --------------------------------------------------
    for anahtar, zorla in (("kolon", ElemanTipi.KOLON), ("perde", ElemanTipi.PERDE)):
        for cevre, katman in _poligonlari_topla(gruplar.get(anahtar, []), ayarlar):
            karar = _kolon_mu_perde_mi(cevre, ayarlar)
            # Katman adi acikca soyluyorsa ona guven, ama narinlik cok
            # baskinsa uyari dus.
            tip = zorla
            if karar != zorla and karar != ElemanTipi.BILINMEYEN:
                if zorla == ElemanTipi.KOLON and karar == ElemanTipi.PERDE:
                    tip = ElemanTipi.PERDE
            if tip == ElemanTipi.KOLON:
                e = _kolon_elemani(cevre, katman, ayarlar)
            else:
                e = _perde_elemani(cevre, katman, ayarlar)
                if zorla == ElemanTipi.KOLON:
                    e.not_ekle(
                        "Kolon katmaninda cizilmis, narinligi yuksek oldugu icin "
                        "perde olarak metraja alindi."
                    )
            elemanlar.append(e)

    # --- Kiris ------------------------------------------------------------
    kiris_varliklari = gruplar.get("kiris", [])
    kapali_kirisler = [
        v for v in kiris_varliklari if v.tur in ("poligon", "tarama") and v.kapali
    ]
    acik_kirisler = [v for v in kiris_varliklari if v.tur in ("cizgi", "yay")]

    for cevre, katman in _poligonlari_topla(kapali_kirisler, ayarlar):
        eksenler, genislik = poligondan_eksen(
            cevre,
            float(ayarlar.al("sezgisel.kiris_min_genislik", 0.15)),
            float(ayarlar.al("sezgisel.kiris_max_genislik", 1.00)),
        )
        for eksen in zincirle(eksenler) or []:
            e = _kiris_elemani(eksen, genislik, katman, ayarlar)
            e.cevre = cevre
            elemanlar.append(e)

    if acik_kirisler:
        cizgiler: list[Segment] = []
        for v in acik_kirisler:
            for k in kenarlar(v.noktalar, kapali=v.kapali):
                cizgiler.append(k)
        ciftler = paralel_cift_eksenleri(
            cizgiler,
            float(ayarlar.al("sezgisel.kiris_min_genislik", 0.15)),
            float(ayarlar.al("sezgisel.kiris_max_genislik", 1.00)),
            min_uzunluk=float(ayarlar.al("sezgisel.kiris_min_uzunluk", 0.50)),
        )
        katman = acik_kirisler[0].katman
        for eksen, genislik in ciftler:
            elemanlar.append(_kiris_elemani(eksen, genislik, katman, ayarlar))

    # --- Duvar (bolme) ---------------------------------------------------
    duvar_varliklari = gruplar.get("duvar", [])
    if duvar_varliklari:
        duvar_aktif = bool(ayarlar.al("duvar.aktif", False))
        if duvar_aktif:
            elemanlar.extend(_duvar_elemanlari(duvar_varliklari, ayarlar))
        else:
            uyarilar.append(
                f"{len(duvar_varliklari)} duvar katmaninda varlik bulundu ancak "
                f"'duvar.aktif' kapali oldugu icin metraja alinmadi."
            )

    # --- Doseme -----------------------------------------------------------
    doseme_min = float(ayarlar.al("sezgisel.doseme_min_alan", 1.0))
    doseme_cevreleri = [
        (c, k)
        for c, k in _poligonlari_topla(gruplar.get("doseme", []), ayarlar)
        if alan(c) >= doseme_min
    ]
    bosluk_cevreleri = [
        c for c, _ in _poligonlari_topla(gruplar.get("bosluk", []), ayarlar)
    ]

    for cevre, katman in doseme_cevreleri:
        e = _doseme_elemani(cevre, katman, ayarlar)
        for b in bosluk_cevreleri:
            if poligon_icinde_mi(b, cevre):
                e.bosluklar.append(b)
        elemanlar.append(e)

    # --- Merdiven ---------------------------------------------------------
    for cevre, katman in _poligonlari_topla(gruplar.get("merdiven", []), ayarlar):
        e = Eleman(
            ad="", tip=ElemanTipi.MERDIVEN, cevre=cevre, kaynak_katman=katman
        )
        e.segmentler = kenarlar(cevre, kapali=True)
        e.olculer["brut_alan"] = round(alan(cevre), 4)
        e.olculer["t"] = float(
            ayarlar.al("merdiven.kalinlik", 0.14) or ayarlar.doseme_kalinligi
        )
        e.not_ekle(
            "Merdiven metraji plan izdusumunden hesaplanir; egim katsayisi "
            "yapilandirmadaki 'merdiven' bolumune gore uygulanir. Kesit "
            "bilgisiyle elle kontrol edin."
        )
        e.guven = 0.5
        elemanlar.append(e)

    # --- Sezgisel havuz ---------------------------------------------------
    if "sezgisel" in gruplar:
        sadece_doseme = bool(
            cizim.nitelikler.get("sta4cad_sadece_doseme")
            or cizim.nitelikler.get("asmolen_sadece_doseme")
        )
        if sadece_doseme:
            uyarilar.append(
                "Sta4CAD dolgu deseni: kirmizi/yesil hatch yoksayildi ve "
                "kolon-perde sezgisel tespiti guvenilmez oldugu icin "
                "yalnizca doseme (buyuk kapali alan) metraji uretildi. "
                "Kolon/kiris detaylari icin DWG dosyasini veya Eslestirme "
                "sekmesindeki renk eslemesini kullanin."
            )
        elemanlar.extend(_sezgisel_tespit(gruplar["sezgisel"], ayarlar, sadece_doseme))

    # --- Kirislerin net acikligi -----------------------------------------
    if bool(ayarlar.al("metraj.kiris_net_aciklik", True)):
        _kirisleri_mesnetlerde_kir(elemanlar, uyarilar)

    # --- Etiket eslestirme -----------------------------------------------
    _dogrular_tespit(etiketler, ayarlar, elemanlar)
    _etiketleri_bagla(elemanlar, etiketler, ayarlar)
    _adlari_tamamla(elemanlar)
    _kesitleri_etiketten_guncelle(elemanlar, ayarlar)

    if not elemanlar:
        uyarilar.append(
            "Hicbir tasiyici eleman tespit edilemedi. Once "
            "`hakedis katmanlar <dosya>` ile katman adlarini gorup "
            "yapilandirmadaki 'katmanlar' bolumunu duzenleyin."
        )

    return elemanlar, uyarilar


def _dogrular_tespit(etiketler: list[Etiket], ayarlar: Ayarlar, elemanlar: list) -> None:
    """Kapi/pencere dogrulama etiketlerini (KD101, 90x220, P12) elemana cevirir."""
    if not bool(ayarlar.al("kapi.aktif", True) or ayarlar.al("pencere.aktif", True)):
        return
    on_ekler = {
        "kapi": str(ayarlar.al("kapi.on_ekler", "KD")),
        "pencere": str(ayarlar.al("pencere.on_ekler", "P")),
    }
    birim = str(ayarlar.al("etiket.kesit_birimi", "cm"))
    from hakedis.config import birim_carpani
    import re as _re

    yeni: list[Eleman] = []
    for et in etiketler:
        if not et.dogrulama or et.kullanildi:
            continue
        # Kalinligi okunmus etiket yapisal (perde/doseme) etikettir
        if et.t is not None:
            continue
        tip = ElemanTipi.PENCERE
        on = (et.ad or "")
        if on.startswith(tuple(c for c in on_ekler["kapi"].split(",") if c)) or "KAP" in on:
            tip = ElemanTipi.KAPI
        elif on.startswith(tuple(c for c in on_ekler["pencere"].split(",") if c)):
            tip = ElemanTipi.PENCERE
        if not bool(ayarlar.al(f"{'kapi' if tip == ElemanTipi.KAPI else 'pencere'}.aktif", True)):
            continue

        e = Eleman(ad=on or "?", tip=tip, cevre=[], kaynak_katman=et.katman)
        e.etiket_metni = et.metin
        # Plan konumunda kucuk bir isaretci (svg/toplu pafta icin)
        p = et.konum
        e.cevre = [
            Nokta(p.x - 0.06, p.y - 0.06),
            Nokta(p.x + 0.06, p.y - 0.06),
            Nokta(p.x + 0.06, p.y + 0.06),
            Nokta(p.x - 0.06, p.y + 0.06),
        ]
        e.olculer["en"] = 0.9
        e.olculer["boy"] = 2.2
        # "90x220" gibi olcu iceren dogrulama etiketlerini coz
        om = _re.search(r"(\d{1,3})\s*[xX*×]\s*(\d{1,3})", et.metin)
        if om:
            e.olculer["en"] = float(om.group(1)) * birim_carpani(birim)
            e.olculer["boy"] = float(om.group(2)) * birim_carpani(birim)
        if not e.ad or e.ad == "?":
            e.ad = f"{e.olculer['en'] * 100:.0f}x{e.olculer['boy'] * 100:.0f}"
        e.guven = 0.6
        e.not_ekle(
            "Dogrulama etiketinden okundu; dograma listesi metraj cetvelinde "
            "adet olarak gorunur. Fiziksel olcekle dogrulayin."
        )
        et.kullanildi = True
        yeni.append(e)

    elemanlar.extend(yeni)


def _sezgisel_tespit(
    varliklar: list[HamVarlik], ayarlar: Ayarlar, sadece_doseme: bool = False
) -> list[Eleman]:
    """Katman bilgisi olmadan bicimden eleman cikarimi (PDF ve duzensiz DXF)."""
    elemanlar: list[Eleman] = []
    min_kenar = float(ayarlar.al("sezgisel.kolon_min_kenar", 0.20))
    max_kenar = float(ayarlar.al("sezgisel.kolon_max_kenar", 2.00))
    doseme_min = float(ayarlar.al("sezgisel.doseme_min_alan", 1.0))

    poligonlar = _poligonlari_topla(varliklar, ayarlar)
    for cevre, katman in poligonlar:
        dik = min_donmus_dikdortgen(cevre)
        if dik is None:
            continue
        a = alan(cevre)
        if a >= doseme_min and dik.en > max_kenar:
            e = _doseme_elemani(cevre, katman, ayarlar)
            e.guven = 0.5
            e.not_ekle("Sezgisel tespit: buyuk kapali alan doseme sayildi.")
            elemanlar.append(e)
        elif not sadece_doseme and min_kenar <= dik.en <= max_kenar:
            tip = _kolon_mu_perde_mi(cevre, ayarlar)
            e = (
                _kolon_elemani(cevre, katman, ayarlar)
                if tip == ElemanTipi.KOLON
                else _perde_elemani(cevre, katman, ayarlar)
            )
            e.guven = min(e.guven, 0.6)
            e.not_ekle("Sezgisel tespit: kesit olculerinden siniflandirildi.")
            elemanlar.append(e)
    return elemanlar


def _kirisleri_mesnetlerde_kir(elemanlar: list[Eleman], uyarilar: list[str]) -> None:
    """Kiris eksenlerinden kolon/perde icinde kalan kisimlari duser.

    Kirik olcunun temel kurali: kiris boyu aks-aks degil, mesnet yuzunden
    mesnet yuzune (net aciklik) olculur. Her aciklik ayri bir olcu satiri olur.
    """
    mesnetler = [
        e.cevre
        for e in elemanlar
        if e.tip in (ElemanTipi.KOLON, ElemanTipi.PERDE) and len(e.cevre) >= 3
    ]
    if not mesnetler:
        return
    for e in elemanlar:
        if e.tip != ElemanTipi.KIRIS or not e.segmentler:
            continue
        brut = e.toplam_uzunluk
        e.ekstra["brut_segmentler"] = [
            Segment(s.baslangic, s.bitis, s.aciklama) for s in e.segmentler
        ]
        yeni: list[Segment] = []
        for seg in e.segmentler:
            yeni.extend(segmenti_poligonlarla_kirp(seg, mesnetler))
        if not yeni:
            e.not_ekle(
                "Kiris ekseninin tamami mesnet icinde kaldi; net aciklik sifir. "
                "Kolon/perde kesitleriyle cakisma kontrol edilmeli."
            )
            e.guven = min(e.guven, 0.4)
            continue
        e.olculer["brut_uzunluk"] = round(brut, 4)
        e.olculer["net_uzunluk"] = round(sum(s.uzunluk for s in yeni), 4)
        e.olculer["mesnet_dusumu"] = round(brut - e.olculer["net_uzunluk"], 4)
        for i, s in enumerate(yeni, 1):
            s.aciklama = f"{i}. aciklik"
        e.segmentler = yeni


def _etiketleri_bagla(
    elemanlar: list[Eleman], etiketler: list[Etiket], ayarlar: Ayarlar
) -> None:
    """Once ic bolgeye dusen etiketleri, sonra yakindakileri baglar."""
    # Kucuk elemanlar once eslessin ki buyuk doseme etiketleri kapmasin
    sirali = sorted(
        elemanlar,
        key=lambda e: alan(e.cevre) if len(e.cevre) >= 3 else 0.0,
    )
    for e in sirali:
        et = en_uygun_etiket(etiketler, e.cevre, e.tip, ayarlar, e.merkez)
        etiketi_uygula(et, e)


def _adlari_tamamla(elemanlar: list[Eleman]) -> None:
    """Etiketi olmayan elemanlara sirali otomatik ad verir."""
    sayaclar: dict[ElemanTipi, int] = defaultdict(int)
    kullanilan = {e.ad for e in elemanlar if e.ad}
    for e in elemanlar:
        if e.ad:
            continue
        while True:
            sayaclar[e.tip] += 1
            aday = f"{e.tip.kisa_kod}{sayaclar[e.tip]:02d}*"
            if aday not in kullanilan:
                break
        e.ad = aday
        kullanilan.add(aday)
        e.not_ekle(
            "Cizimde etiket bulunamadigi icin ad otomatik verildi (* isareti "
            "otomatik adlandirmayi gosterir)."
        )


def _kesitleri_etiketten_guncelle(elemanlar: list[Eleman], ayarlar: Ayarlar) -> None:
    """Etiketten okunan kesit olculerini geometriyle karsilastirip uygular."""
    tol = 0.03
    for e in elemanlar:
        et_b = e.olculer.get("etiket_b")
        et_h = e.olculer.get("etiket_h")
        et_t = e.olculer.get("etiket_t")

        if e.tip == ElemanTipi.KIRIS:
            if et_b is not None and et_h is not None:
                geo_b = e.olculer.get("b")
                if geo_b is not None and abs(geo_b - et_b) > tol:
                    # Etiket "25/50" ise b=25 kirisin genisligidir; geometriyle
                    # uyusmuyorsa etikete guven ama uyari dus.
                    e.not_ekle(
                        f"Etiketteki genislik ({et_b:.2f} m) cizimden olculen "
                        f"({geo_b:.2f} m) ile uyusmuyor; etiket esas alindi."
                    )
                    e.guven = min(e.guven, 0.7)
                e.olculer["b"] = et_b
                e.olculer["h"] = et_h
        elif e.tip == ElemanTipi.KOLON:
            if et_b is not None and et_h is not None:
                geo_b = e.olculer.get("b", 0.0)
                geo_h = e.olculer.get("h", 0.0)
                et_kucuk, et_buyuk = min(et_b, et_h), max(et_b, et_h)
                if (
                    abs(geo_b - et_kucuk) > tol or abs(geo_h - et_buyuk) > tol
                ) and geo_b > 0:
                    e.not_ekle(
                        f"Etiket kesiti {et_b:.2f}/{et_h:.2f} m, cizimden olculen "
                        f"{geo_b:.2f}/{geo_h:.2f} m. Cizim olcusu esas alindi."
                    )
                    e.guven = min(e.guven, 0.8)
        elif e.tip == ElemanTipi.PERDE:
            if et_t is not None:
                e.olculer["t"] = et_t
            elif et_b is not None and e.olculer.get("t") is None:
                e.olculer["t"] = et_b
        elif e.tip in (ElemanTipi.DOSEME, ElemanTipi.MERDIVEN):
            if et_t is not None:
                e.olculer["t"] = et_t
