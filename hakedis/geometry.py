"""Geometri yardimcilari.

Kirik olcu metrajinin matematigi burada. Her fonksiyon metre cinsinden
calisir ve saf (yan etkisiz) tutulmustur; boylece testlenebilir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

from hakedis.model import Nokta, Segment

EPS = 1e-9


# ---------------------------------------------------------------------------
# Temel olcumler
# ---------------------------------------------------------------------------


def isaretli_alan(noktalar: Sequence[Nokta]) -> float:
    """Gauss (shoelace) alani. Saat yonunun tersi pozitiftir."""
    n = len(noktalar)
    if n < 3:
        return 0.0
    toplam = 0.0
    for i in range(n):
        a = noktalar[i]
        b = noktalar[(i + 1) % n]
        toplam += a.x * b.y - b.x * a.y
    return toplam / 2.0


def alan(noktalar: Sequence[Nokta]) -> float:
    """Mutlak alan (m2)."""
    return abs(isaretli_alan(noktalar))


def cevre_uzunlugu(noktalar: Sequence[Nokta], kapali: bool = True) -> float:
    if len(noktalar) < 2:
        return 0.0
    toplam = 0.0
    for i in range(len(noktalar) - 1):
        toplam += noktalar[i].mesafe(noktalar[i + 1])
    if kapali:
        toplam += noktalar[-1].mesafe(noktalar[0])
    return toplam


def kenarlar(noktalar: Sequence[Nokta], kapali: bool = True) -> list[Segment]:
    """Bir nokta zincirini kenar (segment) listesine cevirir."""
    out: list[Segment] = []
    n = len(noktalar)
    if n < 2:
        return out
    ust = n if kapali else n - 1
    for i in range(ust):
        a = noktalar[i]
        b = noktalar[(i + 1) % n]
        if a.mesafe(b) > EPS:
            out.append(Segment(a, b))
    return out


def tekrarlari_temizle(noktalar: Sequence[Nokta], tol: float = 1e-6) -> list[Nokta]:
    """Ust uste binen ardisik noktalari atar, kapali halkanin son tekrarini siler."""
    out: list[Nokta] = []
    for p in noktalar:
        if not out or out[-1].mesafe(p) > tol:
            out.append(p)
    if len(out) > 1 and out[0].mesafe(out[-1]) <= tol:
        out.pop()
    return out


def dogrusallari_sadelestir(
    noktalar: Sequence[Nokta], aci_tol_derece: float = 1.0, kapali: bool = True
) -> list[Nokta]:
    """Ayni dogrultuda devam eden ara noktalari atar.

    Kirik olcuda gereksiz kirilim noktasi metraj cetvelini sisirir; ayni
    dogrultudaki parcalar tek olcu olarak birlestirilir.
    """
    pts = tekrarlari_temizle(noktalar)
    n = len(pts)
    if n < 3:
        return pts
    tut: list[Nokta] = []
    aralik = range(n) if kapali else range(1, n - 1)
    if not kapali:
        tut.append(pts[0])
    for i in aralik:
        onceki = pts[(i - 1) % n]
        simdi = pts[i]
        sonraki = pts[(i + 1) % n]
        v1 = (simdi.x - onceki.x, simdi.y - onceki.y)
        v2 = (sonraki.x - simdi.x, sonraki.y - simdi.y)
        a1 = math.degrees(math.atan2(v1[1], v1[0]))
        a2 = math.degrees(math.atan2(v2[1], v2[0]))
        fark = abs((a1 - a2 + 180.0) % 360.0 - 180.0)
        if fark > aci_tol_derece:
            tut.append(simdi)
    if not kapali:
        tut.append(pts[-1])
    return tut if len(tut) >= 3 or not kapali else pts


def ortogonale_yasla(noktalar: Sequence[Nokta], tol_derece: float = 2.0) -> list[Nokta]:
    """Neredeyse yatay/dusey kenarlari tam yatay/dusey yapar.

    CAD cizimlerinde 0.3 mm'lik kaymalar metrajda 0.001 m2'lik artiklara yol
    acar; bu fonksiyon onlari temizler.
    """
    pts = list(noktalar)
    if len(pts) < 2:
        return pts
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        dx, dy = b.x - a.x, b.y - a.y
        if abs(dx) < EPS and abs(dy) < EPS:
            continue
        aci = abs(math.degrees(math.atan2(dy, dx))) % 180.0
        if aci < tol_derece or aci > 180.0 - tol_derece:
            pts[i + 1] = Nokta(b.x, a.y)
        elif abs(aci - 90.0) < tol_derece:
            pts[i + 1] = Nokta(a.x, b.y)
    return pts


# ---------------------------------------------------------------------------
# Dogru / vektor islemleri
# ---------------------------------------------------------------------------


def _birim(seg: Segment) -> tuple[float, float]:
    dx = seg.bitis.x - seg.baslangic.x
    dy = seg.bitis.y - seg.baslangic.y
    u = math.hypot(dx, dy)
    if u < EPS:
        return (0.0, 0.0)
    return (dx / u, dy / u)


def aci_farki(a: float, b: float) -> float:
    """Iki dogrultu arasindaki aci farki (0-90 derece)."""
    d = abs(a - b) % 180.0
    return min(d, 180.0 - d)


def noktanin_dogruya_uzakligi(p: Nokta, seg: Segment) -> float:
    """Sonsuz dogruya dik uzaklik."""
    ux, uy = _birim(seg)
    if ux == 0.0 and uy == 0.0:
        return p.mesafe(seg.baslangic)
    vx = p.x - seg.baslangic.x
    vy = p.y - seg.baslangic.y
    return abs(vx * uy - vy * ux)


def izdusum_parametresi(p: Nokta, seg: Segment) -> float:
    """p noktasinin seg dogrultusundaki skaler izdusumu (metre)."""
    ux, uy = _birim(seg)
    return (p.x - seg.baslangic.x) * ux + (p.y - seg.baslangic.y) * uy


def nokta_segment_uzakligi(p: Nokta, seg: Segment) -> float:
    """p noktasinin seg segmentine (sinirli) en kisa uzaklik."""
    t = izdusum_parametresi(p, seg)
    t = min(max(t, 0.0), seg.uzunluk)
    q = parametreden_nokta(seg, t)
    return p.mesafe(q)


def parametreden_nokta(seg: Segment, t: float) -> Nokta:
    ux, uy = _birim(seg)
    return Nokta(seg.baslangic.x + ux * t, seg.baslangic.y + uy * t)


def dogru_kesisimi(a: Segment, b: Segment) -> Nokta | None:
    """Iki sonsuz dogrunun kesisimi (paralelse None)."""
    x1, y1 = a.baslangic.x, a.baslangic.y
    x2, y2 = a.bitis.x, a.bitis.y
    x3, y3 = b.baslangic.x, b.baslangic.y
    x4, y4 = b.bitis.x, b.bitis.y
    payda = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(payda) < EPS:
        return None
    t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / payda
    return Nokta(x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def segment_kesisiyor_mu(a: Segment, b: Segment, tol: float = 1e-6) -> bool:
    k = dogru_kesisimi(a, b)
    if k is None:
        return False
    for seg in (a, b):
        t = izdusum_parametresi(k, seg)
        if t < -tol or t > seg.uzunluk + tol:
            return False
    return True


# ---------------------------------------------------------------------------
# Minimum donmus dikdortgen (kolon kesiti icin)
# ---------------------------------------------------------------------------


@dataclass
class Dikdortgen:
    merkez: Nokta
    en: float  # kisa kenar
    boy: float  # uzun kenar
    aci: float  # uzun kenarin yatayla acisi (derece)
    koseler: list[Nokta]

    @property
    def alan(self) -> float:
        return self.en * self.boy

    @property
    def narinlik(self) -> float:
        return self.boy / self.en if self.en > EPS else math.inf


def min_donmus_dikdortgen(noktalar: Sequence[Nokta]) -> Dikdortgen | None:
    """Donen kaliper yontemiyle en kucuk alanli cevreleyen dikdortgen.

    Kolon/perde kesitinin gercek en-boy olcusunu verir; eksene paralel
    olmayan (donmus) kolonlarda bbox yanlis sonuc verecegi icin gereklidir.
    """
    pts = tekrarlari_temizle(noktalar)
    if len(pts) < 3:
        return None
    hull = konveks_kabuk(pts)
    if len(hull) < 3:
        return None

    en_iyi: Dikdortgen | None = None
    for i in range(len(hull)):
        a = hull[i]
        b = hull[(i + 1) % len(hull)]
        kenar = Segment(a, b)
        ux, uy = _birim(kenar)
        if ux == 0.0 and uy == 0.0:
            continue
        us: list[float] = []
        vs: list[float] = []
        for p in hull:
            dx, dy = p.x - a.x, p.y - a.y
            us.append(dx * ux + dy * uy)
            vs.append(-dx * uy + dy * ux)
        genislik = max(us) - min(us)
        yukseklik = max(vs) - min(vs)
        alan_ = genislik * yukseklik
        if en_iyi is not None and alan_ >= en_iyi.alan - 1e-12:
            continue
        u0, u1 = min(us), max(us)
        v0, v1 = min(vs), max(vs)

        def yerel(u: float, v: float) -> Nokta:
            return Nokta(a.x + ux * u - uy * v, a.y + uy * u + ux * v)

        koseler = [yerel(u0, v0), yerel(u1, v0), yerel(u1, v1), yerel(u0, v1)]
        merkez = Nokta(
            sum(k.x for k in koseler) / 4.0, sum(k.y for k in koseler) / 4.0
        )
        if genislik >= yukseklik:
            en, boy = yukseklik, genislik
            aci = math.degrees(math.atan2(uy, ux)) % 180.0
        else:
            en, boy = genislik, yukseklik
            aci = (math.degrees(math.atan2(uy, ux)) + 90.0) % 180.0
        en_iyi = Dikdortgen(merkez, en, boy, aci, koseler)
    return en_iyi


def konveks_kabuk(noktalar: Sequence[Nokta]) -> list[Nokta]:
    """Andrew monotone chain."""
    pts = sorted({(p.x, p.y) for p in noktalar})
    if len(pts) < 3:
        return [Nokta(*p) for p in pts]

    def capraz(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    alt: list[tuple[float, float]] = []
    for p in pts:
        while len(alt) >= 2 and capraz(alt[-2], alt[-1], p) <= 0:
            alt.pop()
        alt.append(p)
    ust: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(ust) >= 2 and capraz(ust[-2], ust[-1], p) <= 0:
            ust.pop()
        ust.append(p)
    return [Nokta(*p) for p in alt[:-1] + ust[:-1]]


# ---------------------------------------------------------------------------
# Perde / kiris ekseni cikarma
# ---------------------------------------------------------------------------


def _ortak_izdusum(a: Segment, b: Segment) -> tuple[float, float] | None:
    """b kenarinin a dogrultusundaki izdusumu ile a'nin ortak araligi."""
    ta0, ta1 = 0.0, a.uzunluk
    tb0 = izdusum_parametresi(b.baslangic, a)
    tb1 = izdusum_parametresi(b.bitis, a)
    tb0, tb1 = min(tb0, tb1), max(tb0, tb1)
    lo = max(ta0, tb0)
    hi = min(ta1, tb1)
    if hi - lo <= EPS:
        return None
    return (lo, hi)


def poligondan_eksen(
    noktalar: Sequence[Nokta],
    min_kalinlik: float = 0.10,
    max_kalinlik: float = 1.20,
    aci_tol: float = 3.0,
    kalinlik_tol: float = 0.03,
) -> tuple[list[Segment], float]:
    """Bir perde/kiris plan kesitinden orta eksen parcalarini cikarir.

    Yontem: kapali cevrenin karsilikli, birbirine paralel ve aralarindaki
    dik mesafe eleman kalinligina esit olan kenar ciftleri eslestirilir.
    Her cift, ortak izdusum araligi boyunca bir orta eksen parcasi uretir.
    L, T ve U seklindeki perdelerde de dogru calisir.

    Dondurur: (eksen parcalari, tespit edilen kalinlik).
    """
    pts = dogrusallari_sadelestir(tekrarlari_temizle(noktalar))
    kn = kenarlar(pts, kapali=True)
    if len(kn) < 4:
        return ([], 0.0)

    adaylar: list[tuple[Segment, float, float]] = []  # (eksen, kalinlik, ortusme)
    for i in range(len(kn)):
        for j in range(i + 1, len(kn)):
            a, b = kn[i], kn[j]
            if aci_farki(a.aci, b.aci) > aci_tol:
                continue
            # Ters yonlu olmali (cevrede karsilikli yuzler)
            ua = _birim(a)
            ub = _birim(b)
            if ua[0] * ub[0] + ua[1] * ub[1] > -0.5:
                continue
            d = (
                noktanin_dogruya_uzakligi(b.baslangic, a)
                + noktanin_dogruya_uzakligi(b.bitis, a)
            ) / 2.0
            if not (min_kalinlik - kalinlik_tol <= d <= max_kalinlik + kalinlik_tol):
                continue
            aralik = _ortak_izdusum(a, b)
            if aralik is None:
                continue
            lo, hi = aralik
            ortusme = hi - lo
            if ortusme < d * 0.5:
                continue
            # Orta eksen: a uzerindeki ortak aralik, b'ye dogru d/2 otelenir
            ux, uy = ua
            p0 = parametreden_nokta(a, lo)
            p1 = parametreden_nokta(a, hi)
            nx, ny = -uy, ux
            # Normalin b'ye bakan yonunu sec
            ort_b = b.orta
            isaret = 1.0 if ((ort_b.x - p0.x) * nx + (ort_b.y - p0.y) * ny) > 0 else -1.0
            kaydir_x = nx * isaret * d / 2.0
            kaydir_y = ny * isaret * d / 2.0
            eksen = Segment(
                Nokta(p0.x + kaydir_x, p0.y + kaydir_y),
                Nokta(p1.x + kaydir_x, p1.y + kaydir_y),
            )
            adaylar.append((eksen, d, ortusme))

    if not adaylar:
        return ([], 0.0)

    # Baskin kalinlik: en uzun ortusmeye sahip ciftlerin kalinligi
    adaylar.sort(key=lambda t: -t[2])
    baskin_kalinlik = adaylar[0][1]
    secilen = [
        (eksen, d)
        for eksen, d, _ in adaylar
        if abs(d - baskin_kalinlik) <= max(kalinlik_tol, baskin_kalinlik * 0.15)
    ]

    # Ayni dogrultudaki ust uste binen eksenleri tekillestir
    benzersiz: list[Segment] = []
    for eksen, _ in secilen:
        yinelenen = False
        for mevcut in benzersiz:
            if (
                aci_farki(eksen.aci, mevcut.aci) < aci_tol
                and noktanin_dogruya_uzakligi(eksen.orta, mevcut) < baskin_kalinlik * 0.3
                and _ortak_izdusum(mevcut, eksen) is not None
            ):
                yinelenen = True
                break
        if not yinelenen:
            benzersiz.append(eksen)

    return (eksenleri_birlestir(benzersiz, baskin_kalinlik), baskin_kalinlik)


def eksenleri_birlestir(
    segmentler: Sequence[Segment], kalinlik: float, aci_tol: float = 3.0
) -> list[Segment]:
    """Kose noktalarinda kopuk kalan eksen parcalarini kesisime uzatir.

    L/T perdelerde iki eksen parcasi kalinligin yarisi kadar kopuk kalir;
    bunlari gercek kirilim noktasinda birlestirir. Kirik olcunun "kirilim"
    noktalari bunlardir.
    """
    segs = [Segment(s.baslangic, s.bitis, s.aciklama) for s in segmentler]
    if len(segs) < 2:
        return segs
    esik = kalinlik * 1.6 + 1e-6
    for i in range(len(segs)):
        for j in range(i + 1, len(segs)):
            a, b = segs[i], segs[j]
            if aci_farki(a.aci, b.aci) < aci_tol:
                continue
            k = dogru_kesisimi(a, b)
            if k is None:
                continue
            # Kesisim her iki parcanin da bir ucuna yakinsa oraya tasi
            for idx, seg in ((i, a), (j, b)):
                d_bas = k.mesafe(seg.baslangic)
                d_bit = k.mesafe(seg.bitis)
                if d_bas <= esik and d_bas <= d_bit:
                    segs[idx] = Segment(k, seg.bitis, seg.aciklama)
                elif d_bit <= esik:
                    segs[idx] = Segment(seg.baslangic, k, seg.aciklama)
    return [s for s in segs if s.uzunluk > 1e-6]


def zincirle(segmentler: Sequence[Segment], tol: float = 1e-4) -> list[Segment]:
    """Eksen parcalarini uc uca ekleyerek surekli bir zincire dizer.

    Kirik olcu cetvelinde parcalar cizim sirasina gore degil, elemanin
    fiziksel devamlilik sirasina gore yazilir.
    """
    kalan = list(segmentler)
    if not kalan:
        return []
    zincir = [kalan.pop(0)]
    ilerleme = True
    while kalan and ilerleme:
        ilerleme = False
        bas = zincir[0].baslangic
        son = zincir[-1].bitis
        for idx, seg in enumerate(kalan):
            if seg.bitis.mesafe(bas) <= tol:
                zincir.insert(0, kalan.pop(idx))
            elif seg.baslangic.mesafe(bas) <= tol:
                s = kalan.pop(idx)
                zincir.insert(0, Segment(s.bitis, s.baslangic, s.aciklama))
            elif seg.baslangic.mesafe(son) <= tol:
                zincir.append(kalan.pop(idx))
            elif seg.bitis.mesafe(son) <= tol:
                s = kalan.pop(idx)
                zincir.append(Segment(s.bitis, s.baslangic, s.aciklama))
            else:
                continue
            ilerleme = True
            break
    return zincir + zincirle(kalan, tol) if kalan else zincir


def paralel_cift_eksenleri(
    cizgiler: Sequence[Segment],
    min_genislik: float,
    max_genislik: float,
    aci_tol: float = 2.0,
    min_uzunluk: float = 0.30,
) -> list[tuple[Segment, float]]:
    """Iki paralel cizgi olarak cizilmis kirisleri eksen + genislige cevirir.

    Kalip planlarinda kirisler cogunlukla kapali poligon degil, iki paralel
    cizgi olarak cizilir. Bu fonksiyon o cizgileri eslestirir.
    """
    uygun = [c for c in cizgiler if c.uzunluk >= min_uzunluk]
    kullanildi: set[int] = set()
    sonuc: list[tuple[Segment, float]] = []
    # Uzun cizgiler once eslessin
    sirali = sorted(range(len(uygun)), key=lambda i: -uygun[i].uzunluk)
    for i in sirali:
        if i in kullanildi:
            continue
        a = uygun[i]
        en_iyi: tuple[int, float, float] | None = None  # (j, mesafe, ortusme)
        for j in sirali:
            if j == i or j in kullanildi:
                continue
            b = uygun[j]
            if aci_farki(a.aci, b.aci) > aci_tol:
                continue
            d = (
                noktanin_dogruya_uzakligi(b.baslangic, a)
                + noktanin_dogruya_uzakligi(b.bitis, a)
            ) / 2.0
            if not (min_genislik <= d <= max_genislik):
                continue
            aralik = _ortak_izdusum(a, b)
            if aralik is None:
                continue
            ortusme = aralik[1] - aralik[0]
            if ortusme < min_uzunluk:
                continue
            if en_iyi is None or ortusme > en_iyi[2]:
                en_iyi = (j, d, ortusme)
        if en_iyi is None:
            continue
        j, d, _ = en_iyi
        b = uygun[j]
        aralik = _ortak_izdusum(a, b)
        assert aralik is not None
        lo, hi = aralik
        ux, uy = _birim(a)
        nx, ny = -uy, ux
        isaret = (
            1.0
            if ((b.orta.x - a.baslangic.x) * nx + (b.orta.y - a.baslangic.y) * ny) > 0
            else -1.0
        )
        dx, dy = nx * isaret * d / 2.0, ny * isaret * d / 2.0
        p0 = parametreden_nokta(a, lo)
        p1 = parametreden_nokta(a, hi)
        eksen = Segment(Nokta(p0.x + dx, p0.y + dy), Nokta(p1.x + dx, p1.y + dy))
        sonuc.append((eksen, d))
        kullanildi.add(i)
        kullanildi.add(j)
    return sonuc


# ---------------------------------------------------------------------------
# Nokta / poligon iliskileri
# ---------------------------------------------------------------------------


def nokta_icinde_mi(p: Nokta, poligon: Sequence[Nokta]) -> bool:
    """Ray casting."""
    n = len(poligon)
    if n < 3:
        return False
    icinde = False
    j = n - 1
    for i in range(n):
        pi, pj = poligon[i], poligon[j]
        if (pi.y > p.y) != (pj.y > p.y):
            x_kesisim = (pj.x - pi.x) * (p.y - pi.y) / (pj.y - pi.y + EPS) + pi.x
            if p.x < x_kesisim:
                icinde = not icinde
        j = i
    return icinde


def poligon_icinde_mi(ic: Sequence[Nokta], dis: Sequence[Nokta]) -> bool:
    return bool(ic) and all(nokta_icinde_mi(p, dis) for p in ic)


def sinir_kutusu(noktalar: Iterable[Nokta]) -> tuple[float, float, float, float]:
    xs = [p.x for p in noktalar]
    ys = [p.y for p in noktalar]
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


def kutu_kesisim_alani(
    a: tuple[float, float, float, float], b: tuple[float, float, float, float]
) -> float:
    x0 = max(a[0], b[0])
    y0 = max(a[1], b[1])
    x1 = min(a[2], b[2])
    y1 = min(a[3], b[3])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    return (x1 - x0) * (y1 - y0)


def segment_poligon_kesisim_uzunlugu(
    seg: Segment, poligon: Sequence[Nokta], adim: int = 64
) -> float:
    """Bir eksen parcasinin poligon icinde kalan uzunlugu (yaklasik).

    Kirisin kolona saplanan kismini (mesnet icinde kalan boy) hesaplamak
    icin kullanilir; net acikligi bulmak icin bu deger dusulur.
    """
    if seg.uzunluk < EPS or len(poligon) < 3:
        return 0.0
    icerde = 0
    for i in range(adim):
        t = (i + 0.5) / adim
        p = Nokta(
            seg.baslangic.x + (seg.bitis.x - seg.baslangic.x) * t,
            seg.baslangic.y + (seg.bitis.y - seg.baslangic.y) * t,
        )
        if nokta_icinde_mi(p, poligon):
            icerde += 1
    return seg.uzunluk * icerde / adim


def kiris_ayak_izi(
    segmentler: Sequence[Segment], genislik: float
) -> "object | None":
    """Kiris eksenlerinden plandaki ayak izi alanini (shapely) uretir."""
    if genislik <= 0:
        return None
    try:
        from shapely.geometry import LineString
        from shapely.ops import unary_union
    except ImportError:  # pragma: no cover
        return None
    parcalar = []
    for s in segmentler:
        if s.uzunluk <= EPS:
            continue
        ls = LineString([(s.baslangic.x, s.baslangic.y), (s.bitis.x, s.bitis.y)])
        parcalar.append(ls.buffer(genislik / 2.0, cap_style=2, join_style=2))
    if not parcalar:
        return None
    return unary_union(parcalar)


def poligonu_shapelye(noktalar: Sequence[Nokta]) -> "object | None":
    """Nokta zincirini gecerli bir shapely poligonuna cevirir."""
    if len(noktalar) < 3:
        return None
    try:
        from shapely.geometry import Polygon
    except ImportError:  # pragma: no cover
        return None
    try:
        poly = Polygon([(p.x, p.y) for p in noktalar])
        if not poly.is_valid:
            poly = poly.buffer(0)
        return poly if not poly.is_empty else None
    except Exception:  # pragma: no cover
        return None


def net_kalip_alani(
    cevre: Sequence[Nokta],
    bosluklar: Sequence[Sequence[Nokta]],
    dusulecekler: Sequence["object"],
) -> tuple[float, float]:
    """Doseme tabla kalibi alani.

    Bruttan bosluklar ve (kiris + kolon + perde) ayak izlerinin BIRLESIMI
    dusulur; birlesim kullanildigi icin kiris-kolon cakismasi iki kez
    dusulmez. Dondurur: (net kalip alani, dusulen ayak izi alani).
    """
    taban = poligonu_shapelye(cevre)
    if taban is None:
        return (0.0, 0.0)
    try:
        from shapely.ops import unary_union
    except ImportError:  # pragma: no cover
        return (abs(isaretli_alan(cevre)), 0.0)

    for b in bosluklar:
        bp = poligonu_shapelye(b)
        if bp is not None:
            taban = taban.difference(bp)
    net_brut = taban.area

    gecerli = [d for d in dusulecekler if d is not None and not d.is_empty]
    if not gecerli:
        return (net_brut, 0.0)
    birlesim = unary_union(gecerli).intersection(taban)
    return (max(net_brut - birlesim.area, 0.0), birlesim.area)


def segmenti_poligonlarla_kirp(
    seg: Segment, poligonlar: Sequence[Sequence[Nokta]], adim: int = 400
) -> list[Segment]:
    """Eksen parcasindan poligonlarin (mesnetlerin) icinde kalan kisimlari atar.

    Geriye kalan parcalar kirisin net acikliklaridir; kirik olcuda her aciklik
    ayri bir olcu satiri olur.
    """
    if seg.uzunluk < EPS:
        return []
    if not poligonlar:
        return [seg]
    n = max(adim, int(seg.uzunluk * 200))
    dx = (seg.bitis.x - seg.baslangic.x) / n
    dy = (seg.bitis.y - seg.baslangic.y) / n
    parcalar: list[Segment] = []
    basla: int | None = None
    for i in range(n):
        t = i + 0.5
        p = Nokta(seg.baslangic.x + dx * t, seg.baslangic.y + dy * t)
        disarda = not any(nokta_icinde_mi(p, poly) for poly in poligonlar)
        if disarda and basla is None:
            basla = i
        elif not disarda and basla is not None:
            parcalar.append(
                Segment(
                    Nokta(seg.baslangic.x + dx * basla, seg.baslangic.y + dy * basla),
                    Nokta(seg.baslangic.x + dx * i, seg.baslangic.y + dy * i),
                )
            )
            basla = None
    if basla is not None:
        parcalar.append(Segment(parametreden_nokta(seg, basla * seg.uzunluk / n), seg.bitis))
    return [p for p in parcalar if p.uzunluk > 0.02]
