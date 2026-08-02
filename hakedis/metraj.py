"""Kirik olcu metraj motoru.

Her eleman icin beton (m3) ve kalip (m2) miktarlari, olcunun nasil
alindigini gosteren kirilim satirlariyla birlikte uretilir. Amac sadece
sonucu degil, denetlenebilir olcuyu vermektir: kontrol muhendisi her
sayinin nereden geldigini satirda gorebilmelidir.
"""

from __future__ import annotations

from hakedis.config import Ayarlar
from hakedis.geometry import (
    alan,
    cevre_uzunlugu,
    kiris_ayak_izi,
    net_kalip_alani,
    nokta_icinde_mi,
    poligonu_shapelye,
    segment_poligon_kesisim_uzunlugu,
)
from hakedis.model import (
    Cizim,
    Eleman,
    ElemanTipi,
    KirikOlcuSatiri,
    MetrajSonucu,
    Nokta,
    Segment,
)


def _y(deger: float, basamak: int = 3) -> float:
    return round(deger + 0.0, basamak)


def _net_yukseklik(ayarlar: Ayarlar) -> tuple[float, str]:
    """Kolon/perde net kalip yuksekligi ve aciklamasi."""
    H = ayarlar.kat_yuksekligi
    kural = str(ayarlar.al("metraj.kolon_net_yukseklik_dusumu", "doseme"))
    if kural == "doseme":
        t = ayarlar.doseme_kalinligi
        return H - t, f"kat yuksekligi {H:.2f} - doseme {t:.2f}"
    if kural == "kiris":
        h = float(ayarlar.al("kat.kiris_yuksekligi", 0.50))
        return H - h, f"kat yuksekligi {H:.2f} - kiris {h:.2f}"
    return H, f"kat yuksekligi {H:.2f}"


# ---------------------------------------------------------------------------
# Kolon
# ---------------------------------------------------------------------------


def _kolon_satirlari(
    e: Eleman, ayarlar: Ayarlar, kirisler: list[Eleman]
) -> list[KirikOlcuSatiri]:
    H, H_aciklama = _net_yukseklik(ayarlar)
    b = e.olculer.get("b", 0.0)
    h = e.olculer.get("h", 0.0)
    A = e.olculer.get("kesit_alani", b * h)
    U = e.olculer.get("cevre_uzunlugu", 2 * (b + h))
    kat = e.kat

    detay = [f"Kesit: {b:.2f} x {h:.2f} m  (kesit alani {A:.4f} m2)"]
    detay += [
        f"  kenar {i}: {s.olcu_metni()}" for i, s in enumerate(e.segmentler, 1)
    ]
    detay.append(f"Kesit cevresi = {U:.3f} m")
    detay.append(f"Net yukseklik H = {H:.2f} m  ({H_aciklama})")

    beton = KirikOlcuSatiri(
        poz=ayarlar.poz("kolon_beton"),
        eleman_adi=e.ad,
        tip=ElemanTipi.KOLON,
        tanim=f"Kolon betonu {b:.2f}/{h:.2f}",
        benzer=1,
        en=_y(b),
        boy=_y(h),
        yukseklik=_y(H),
        hacim=_y(A * H),
        birim="m3",
        formul=f"A={A:.4f} m2 x H={H:.2f} m",
        kat=kat,
        detay=list(detay),
    )

    kalip_alan = U * H
    kalip = KirikOlcuSatiri(
        poz=ayarlar.poz("kolon_kalip"),
        eleman_adi=e.ad,
        tip=ElemanTipi.KOLON,
        tanim=f"Kolon kalibi {b:.2f}/{h:.2f}",
        benzer=1,
        en=_y(U),
        yukseklik=_y(H),
        alan=_y(kalip_alan),
        birim="m2",
        formul=f"cevre={U:.3f} m x H={H:.2f} m",
        kat=kat,
        detay=list(detay),
    )
    satirlar = [beton, kalip]

    if bool(ayarlar.al("metraj.kolon_kalibindan_kiris_dus", True)):
        dus = _mesnet_kiris_dusumu(e, kirisler, ayarlar)
        if dus["alan"] > 1e-6:
            satirlar.append(
                KirikOlcuSatiri(
                    poz=ayarlar.poz("kolon_kalip"),
                    eleman_adi=e.ad,
                    tip=ElemanTipi.KOLON,
                    tanim="  (-) Saplanan kiris yuzeyi dusumu",
                    benzer=1,
                    alan=_y(dus["alan"]),
                    birim="m2",
                    formul=dus["formul"],
                    kat=kat,
                    detay=dus["detay"],
                    dusum_mu=True,
                )
            )
    return satirlar


def _saplanan_yuz_sayisi(mesnet: Eleman, kiris: Eleman, tol: float = 0.01) -> int:
    """Kirisin mesnede kac yuzden saplandigini sayar.

    Net aciklik parcalarinin uclari mesnet yuzunde biter. Bir ucun mesnede
    dayanip dayanmadigi, ucun aciklik disina dogru bir miktar otelenmis
    halinin mesnet kesiti icine dusup dusmedigine bakilarak belirlenir.
    Boylece ara kolonlarda 2 (iki taraftan), uc kolonlarda 1 yuz cikar.
    """
    if len(mesnet.cevre) < 3:
        return 0
    sayi = 0
    for s in kiris.segmentler:
        if s.uzunluk <= tol:
            continue
        ux = (s.bitis.x - s.baslangic.x) / s.uzunluk
        uy = (s.bitis.y - s.baslangic.y) / s.uzunluk
        # Baslangic ucu: aciklik disina (geriye) otele
        if nokta_icinde_mi(
            Nokta(s.baslangic.x - ux * tol, s.baslangic.y - uy * tol), mesnet.cevre
        ):
            sayi += 1
        # Bitis ucu: aciklik disina (ileriye) otele
        if nokta_icinde_mi(
            Nokta(s.bitis.x + ux * tol, s.bitis.y + uy * tol), mesnet.cevre
        ):
            sayi += 1
    return sayi


def _mesnet_kiris_dusumu(
    mesnet: Eleman, kirisler: list[Eleman], ayarlar: Ayarlar
) -> dict:
    """Kolona/perdeye saplanan kirislerin kalip yuzeyinden dusulecek alani."""
    t_doseme = ayarlar.doseme_kalinligi
    dusum_doseme = bool(ayarlar.al("metraj.kiris_yan_kalip_doseme_dusumu", True))
    toplam = 0.0
    detay: list[str] = []
    parcalar: list[str] = []
    if len(mesnet.cevre) < 3:
        return {"alan": 0.0, "formul": "", "detay": []}

    for k in kirisler:
        temas = _saplanan_yuz_sayisi(mesnet, k)
        if temas == 0:
            # Net aciklik hic uretilmemisse brut eksene bak
            brut = k.ekstra.get("brut_segmentler") or []
            if any(
                segment_poligon_kesisim_uzunlugu(seg, mesnet.cevre) > 0.01
                for seg in brut
            ):
                temas = 1
            else:
                continue
        b = k.olculer.get("b", 0.0)
        h = k.olculer.get("h", 0.0)
        yuz = max(h - t_doseme, 0.0) if dusum_doseme else h
        alan_ = b * yuz * temas
        if alan_ <= 1e-6:
            continue
        toplam += alan_
        detay.append(
            f"  {k.ad}: {b:.2f} m x {yuz:.2f} m x {temas} yuz = {alan_:.3f} m2"
        )
        parcalar.append(f"{b:.2f}x{yuz:.2f}x{temas}")
    return {
        "alan": toplam,
        "formul": " + ".join(parcalar),
        "detay": (["Saplanan kirisler:"] + detay) if detay else [],
    }


# ---------------------------------------------------------------------------
# Perde
# ---------------------------------------------------------------------------


def _perde_satirlari(
    e: Eleman, ayarlar: Ayarlar, kirisler: list[Eleman]
) -> list[KirikOlcuSatiri]:
    H, H_aciklama = _net_yukseklik(ayarlar)
    t = e.olculer.get("t") or float(ayarlar.al("kat.perde_kalinligi", 0.25))
    kat = e.kat

    detay = [
        f"Kalinlik t = {t:.2f} m,  net yukseklik H = {H:.2f} m ({H_aciklama})",
        "Kirik olcu (orta eksen):",
    ]
    toplam_L = 0.0
    for i, s in enumerate(e.segmentler, 1):
        toplam_L += s.uzunluk
        detay.append(f"  {i}. parca: {s.olcu_metni()}")
    detay.append(f"Toplam eksen boyu L = {toplam_L:.3f} m")

    beton = KirikOlcuSatiri(
        poz=ayarlar.poz("perde_beton"),
        eleman_adi=e.ad,
        tip=ElemanTipi.PERDE,
        tanim=f"Perde betonu t={t:.2f}",
        benzer=1,
        en=_y(t),
        boy=_y(toplam_L),
        yukseklik=_y(H),
        hacim=_y(toplam_L * t * H),
        birim="m3",
        formul=f"L={toplam_L:.3f} x t={t:.2f} x H={H:.2f}",
        kat=kat,
        detay=list(detay),
    )

    # Iki yuz + serbest uclardaki bas kaliplari
    yuz_alani = 2.0 * toplam_L * H
    serbest = int(e.olculer.get("serbest_uc", 0) or 0)
    bas_alani = serbest * t * H
    kalip_detay = list(detay) + [
        f"Iki yuz: 2 x {toplam_L:.3f} x {H:.2f} = {yuz_alani:.3f} m2",
    ]
    if serbest:
        kalip_detay.append(
            f"Bas kalibi: {serbest} uc x {t:.2f} x {H:.2f} = {bas_alani:.3f} m2"
        )
    kalip = KirikOlcuSatiri(
        poz=ayarlar.poz("perde_kalip"),
        eleman_adi=e.ad,
        tip=ElemanTipi.PERDE,
        tanim=f"Perde kalibi t={t:.2f}",
        benzer=1,
        boy=_y(toplam_L),
        yukseklik=_y(H),
        alan=_y(yuz_alani + bas_alani),
        birim="m2",
        formul=f"2 x L={toplam_L:.3f} x H={H:.2f}"
        + (f" + {serbest} x t={t:.2f} x H={H:.2f}" if serbest else ""),
        kat=kat,
        detay=kalip_detay,
    )
    satirlar = [beton, kalip]

    if bool(ayarlar.al("metraj.kolon_kalibindan_kiris_dus", True)):
        dus = _mesnet_kiris_dusumu(e, kirisler, ayarlar)
        if dus["alan"] > 1e-6:
            satirlar.append(
                KirikOlcuSatiri(
                    poz=ayarlar.poz("perde_kalip"),
                    eleman_adi=e.ad,
                    tip=ElemanTipi.PERDE,
                    tanim="  (-) Saplanan kiris yuzeyi dusumu",
                    benzer=1,
                    alan=_y(dus["alan"]),
                    birim="m2",
                    formul=dus["formul"],
                    kat=kat,
                    detay=dus["detay"],
                    dusum_mu=True,
                )
            )
    return satirlar


# ---------------------------------------------------------------------------
# Kiris
# ---------------------------------------------------------------------------


def _kiris_satirlari(e: Eleman, ayarlar: Ayarlar) -> list[KirikOlcuSatiri]:
    b = e.olculer.get("b", float(ayarlar.al("kat.kiris_genisligi", 0.25)))
    h = e.olculer.get("h", float(ayarlar.al("kat.kiris_yuksekligi", 0.50)))
    t = ayarlar.doseme_kalinligi
    kat = e.kat

    beton_h = max(h - t, 0.0) if bool(
        ayarlar.al("metraj.kiris_betonu_doseme_dusumu", True)
    ) else h
    yan_h = max(h - t, 0.0) if bool(
        ayarlar.al("metraj.kiris_yan_kalip_doseme_dusumu", True)
    ) else h

    toplam_L = sum(s.uzunluk for s in e.segmentler)
    detay = [f"Kesit: {b:.2f} / {h:.2f} m"]
    if "brut_uzunluk" in e.olculer:
        detay.append(
            f"Brut eksen boyu {e.olculer['brut_uzunluk']:.3f} m, "
            f"mesnet dusumu {e.olculer.get('mesnet_dusumu', 0.0):.3f} m"
        )
    detay.append("Kirik olcu (net aciklıklar):")
    for i, s in enumerate(e.segmentler, 1):
        etiket = s.aciklama or f"{i}. parca"
        detay.append(f"  {etiket}: {s.olcu_metni()}")
    detay.append(f"Toplam net boy L = {toplam_L:.3f} m")

    beton = KirikOlcuSatiri(
        poz=ayarlar.poz("kiris_beton"),
        eleman_adi=e.ad,
        tip=ElemanTipi.KIRIS,
        tanim=f"Kiris betonu {b:.2f}/{h:.2f}",
        benzer=1,
        en=_y(b),
        boy=_y(toplam_L),
        yukseklik=_y(beton_h),
        hacim=_y(b * beton_h * toplam_L),
        birim="m3",
        formul=(
            f"b={b:.2f} x (h-t)={beton_h:.2f} x L={toplam_L:.3f}"
            if beton_h != h
            else f"b={b:.2f} x h={h:.2f} x L={toplam_L:.3f}"
        ),
        kat=kat,
        detay=list(detay),
    )

    alt = b * toplam_L
    yan = 2.0 * yan_h * toplam_L
    kalip = KirikOlcuSatiri(
        poz=ayarlar.poz("kiris_kalip"),
        eleman_adi=e.ad,
        tip=ElemanTipi.KIRIS,
        tanim=f"Kiris kalibi {b:.2f}/{h:.2f}",
        benzer=1,
        en=_y(b),
        boy=_y(toplam_L),
        yukseklik=_y(yan_h),
        alan=_y(alt + yan),
        birim="m2",
        formul=(
            f"alt: {b:.2f}x{toplam_L:.3f}={alt:.3f} + "
            f"yan: 2x{yan_h:.2f}x{toplam_L:.3f}={yan:.3f}"
        ),
        kat=kat,
        detay=list(detay)
        + [
            f"Alt kalip = {b:.2f} x {toplam_L:.3f} = {alt:.3f} m2",
            f"Yan kalip = 2 x {yan_h:.2f} x {toplam_L:.3f} = {yan:.3f} m2",
        ],
    )
    return [beton, kalip]


# ---------------------------------------------------------------------------
# Doseme
# ---------------------------------------------------------------------------


def _doseme_satirlari(
    e: Eleman,
    ayarlar: Ayarlar,
    kirisler: list[Eleman],
    mesnetler: list[Eleman] | None = None,
) -> list[KirikOlcuSatiri]:
    t = e.olculer.get("t", ayarlar.doseme_kalinligi)
    kat = e.kat
    brut = alan(e.cevre)

    detay = ["Kirik olcu (kose koordinatlari):"]
    for i, p in enumerate(e.cevre, 1):
        detay.append(f"  {i:>2}. kose: ({p.x:.3f}, {p.y:.3f})")
    detay.append(f"Gauss (kirik olcu) alani = {brut:.4f} m2")
    detay.append(f"Cevre = {cevre_uzunlugu(e.cevre):.3f} m,  kalinlik t = {t:.2f} m")

    bosluk_alani = 0.0
    for i, b in enumerate(e.bosluklar, 1):
        a = alan(b)
        bosluk_alani += a
        detay.append(f"  (-) {i}. bosluk: {a:.4f} m2")
    net = max(brut - bosluk_alani, 0.0)
    if bosluk_alani > 0:
        detay.append(f"Net alan = {brut:.4f} - {bosluk_alani:.4f} = {net:.4f} m2")

    e.olculer["net_alan"] = _y(net, 4)
    e.olculer["bosluk_alani"] = _y(bosluk_alani, 4)

    satirlar = [
        KirikOlcuSatiri(
            poz=ayarlar.poz("doseme_beton"),
            eleman_adi=e.ad,
            tip=ElemanTipi.DOSEME,
            tanim=f"Doseme betonu t={t:.2f}",
            benzer=1,
            alan=_y(net, 4),
            yukseklik=_y(t),
            hacim=_y(net * t),
            birim="m3",
            formul=f"A={net:.4f} m2 x t={t:.2f} m",
            kat=kat,
            detay=list(detay),
        )
    ]

    kalip_alani = net
    kalip_detay = list(detay)
    ayak_izi = 0.0
    if bool(ayarlar.al("metraj.doseme_kalibindan_kiris_dus", True)):
        # Kiris + kolon + perde ayak izlerinin BIRLESIMI dusulur; birlesim
        # kullanildigi icin kiris-kolon cakisma alani iki kez dusulmez.
        dusulecekler = []
        parcalar: list[str] = []
        for k in kirisler:
            b = k.olculer.get("b", 0.0)
            icerde = sum(
                s.uzunluk for s in k.segmentler if nokta_icinde_mi(s.orta, e.cevre)
            )
            if icerde <= 1e-6 or b <= 0:
                continue
            iz = kiris_ayak_izi(k.segmentler, b)
            if iz is not None:
                dusulecekler.append(iz)
                parcalar.append(f"{k.ad} ({b:.2f} m genislik, {icerde:.3f} m boy)")
        if bool(ayarlar.al("metraj.doseme_kalibindan_mesnet_dus", True)):
            for m in mesnetler or []:
                iz = poligonu_shapelye(m.cevre)
                if iz is not None:
                    dusulecekler.append(iz)
                    parcalar.append(f"{m.ad} kesiti")
        if dusulecekler:
            kalip_alani, ayak_izi = net_kalip_alani(e.cevre, e.bosluklar, dusulecekler)
            if ayak_izi > 1e-6:
                kalip_detay.append(
                    "Tabla kalibindan dusulen ayak izleri (birlesim alani):"
                )
                kalip_detay += [f"  - {p}" for p in parcalar]
                kalip_detay.append(f"  Birlesim = {ayak_izi:.4f} m2")

    satirlar.append(
        KirikOlcuSatiri(
            poz=ayarlar.poz("doseme_kalip"),
            eleman_adi=e.ad,
            tip=ElemanTipi.DOSEME,
            tanim=f"Doseme (tabla) kalibi t={t:.2f}",
            benzer=1,
            alan=_y(kalip_alani, 4),
            birim="m2",
            formul=(
                f"net alan {net:.4f} - kiris/kolon ayak izi {ayak_izi:.4f}"
                if ayak_izi > 1e-6
                else f"net alan {net:.4f} m2"
            ),
            kat=kat,
            detay=kalip_detay,
        )
    )
    return satirlar


def _merdiven_satirlari(e: Eleman, ayarlar: Ayarlar) -> list[KirikOlcuSatiri]:
    t = e.olculer.get("t", ayarlar.doseme_kalinligi)
    a = alan(e.cevre)
    detay = ["Kirik olcu (plan izdusumu kose koordinatlari):"]
    detay += [f"  {i:>2}. kose: ({p.x:.3f}, {p.y:.3f})" for i, p in enumerate(e.cevre, 1)]
    detay.append(f"Plan alani = {a:.4f} m2 (egim katsayisi UYGULANMADI)")
    return [
        KirikOlcuSatiri(
            poz=ayarlar.poz("merdiven_beton"),
            eleman_adi=e.ad,
            tip=ElemanTipi.MERDIVEN,
            tanim=f"Merdiven betonu t={t:.2f} (plan izdusumu)",
            benzer=1,
            alan=_y(a, 4),
            yukseklik=_y(t),
            hacim=_y(a * t),
            birim="m3",
            formul=f"A={a:.4f} x t={t:.2f}",
            kat=e.kat,
            detay=detay,
        ),
        KirikOlcuSatiri(
            poz=ayarlar.poz("merdiven_kalip"),
            eleman_adi=e.ad,
            tip=ElemanTipi.MERDIVEN,
            tanim="Merdiven kalibi (plan izdusumu)",
            benzer=1,
            alan=_y(a, 4),
            birim="m2",
            formul=f"A={a:.4f} m2",
            kat=e.kat,
            detay=detay,
        ),
    ]


# ---------------------------------------------------------------------------
# Ana akis
# ---------------------------------------------------------------------------


def metraj_hesapla(
    elemanlar: list[Eleman], ayarlar: Ayarlar, uyarilar: list[str] | None = None
) -> MetrajSonucu:
    """Tespit edilmis elemanlardan kirik olcu metraj cetvelini uretir."""
    kat = ayarlar.kat_adi
    for e in elemanlar:
        if not e.kat:
            e.kat = kat

    kirisler = [e for e in elemanlar if e.tip == ElemanTipi.KIRIS]
    mesnetler = [
        e for e in elemanlar if e.tip in (ElemanTipi.KOLON, ElemanTipi.PERDE)
    ]
    satirlar: list[KirikOlcuSatiri] = []

    sira = {
        ElemanTipi.KOLON: 0,
        ElemanTipi.PERDE: 1,
        ElemanTipi.KIRIS: 2,
        ElemanTipi.DOSEME: 3,
        ElemanTipi.MERDIVEN: 4,
    }
    for e in sorted(elemanlar, key=lambda x: (sira.get(x.tip, 9), x.ad)):
        if e.tip == ElemanTipi.KOLON:
            satirlar.extend(_kolon_satirlari(e, ayarlar, kirisler))
        elif e.tip == ElemanTipi.PERDE:
            satirlar.extend(_perde_satirlari(e, ayarlar, kirisler))
        elif e.tip == ElemanTipi.KIRIS:
            satirlar.extend(_kiris_satirlari(e, ayarlar))
        elif e.tip == ElemanTipi.DOSEME:
            satirlar.extend(_doseme_satirlari(e, ayarlar, kirisler, mesnetler))
        elif e.tip == ElemanTipi.MERDIVEN:
            satirlar.extend(_merdiven_satirlari(e, ayarlar))

    sonuc = MetrajSonucu(
        kat=kat,
        elemanlar=elemanlar,
        satirlar=satirlar,
        uyarilar=list(uyarilar or []),
        parametreler={
            "kat_yuksekligi": ayarlar.kat_yuksekligi,
            "doseme_kalinligi": ayarlar.doseme_kalinligi,
            "birim": ayarlar.birim,
            "net_yukseklik": _net_yukseklik(ayarlar)[0],
        },
    )

    for e in elemanlar:
        if e.guven < 0.7:
            sonuc.uyari_ekle(
                f"{e.ad} ({e.tip.value}) dusuk guvenle tespit edildi - "
                + (e.notlar[0] if e.notlar else "kontrol edin")
            )
    return sonuc


def plandan_metraj(
    dosya: str, ayarlar: Ayarlar
) -> tuple[MetrajSonucu, Cizim]:
    """Uctan uca: dosyayi oku, elemanlari tespit et, metraji hesapla."""
    from hakedis.detect import elemanlari_tespit_et
    from hakedis.readers import cizim_oku

    cizim = cizim_oku(dosya, ayarlar)
    elemanlar, uyarilar = elemanlari_tespit_et(cizim, ayarlar)
    sonuc = metraj_hesapla(elemanlar, ayarlar, uyarilar)
    sonuc.kaynak_dosya = str(dosya)
    return sonuc, cizim
