"""SVG kontrol paftasi.

Otomatik metrajda en buyuk risk, yanlis tespit edilen bir elemanin fark
edilmeden cetvele girmesidir. Bu pafta, sistemin ciziminizi NASIL anladigini
gosterir: her eleman tespit edildigi tiple boyanir, adi ve olcusu yazilir,
perde/kiris orta eksenleri (kirik olcu zinciri) ustune cizilir.

Metraji teslim etmeden once bu paftayi acip 3 seyi kontrol edin:
  1. Her kolon/perde/kiris boyanmis mi (atlanan var mi)?
  2. Renkler dogru mu (kolon perde sayilmis mi)?
  3. Kesikli eksen cizgileri elemanin ortasindan geciyor mu?
"""

from __future__ import annotations

import html
from pathlib import Path

from hakedis.geometry import sinir_kutusu
from hakedis.model import Eleman, ElemanTipi, MetrajSonucu, Nokta

RENKLER: dict[ElemanTipi, tuple[str, str]] = {
    # (dolgu, kenar)
    ElemanTipi.KOLON: ("#e74c3c", "#922b21"),
    ElemanTipi.PERDE: ("#8e44ad", "#4a235a"),
    ElemanTipi.KIRIS: ("#2980b9", "#1a5276"),
    ElemanTipi.DOSEME: ("#95a5a6", "#5d6d7e"),
    ElemanTipi.MERDIVEN: ("#f39c12", "#9c640c"),
    ElemanTipi.BOSLUK: ("#ffffff", "#7f8c8d"),
    ElemanTipi.BILINMEYEN: ("#bdc3c7", "#7f8c8d"),
}

KENAR_BOSLUGU = 70.0  # px - kenardaki etiketlerin kirpilmamasi icin
HEDEF_GENISLIK = 1400.0  # px


class _Donusum:
    """Model koordinatlarini (metre, y yukari) SVG'ye (px, y asagi) tasir."""

    def __init__(self, kutu: tuple[float, float, float, float], olcek: float, yuk: float):
        self.x0, self.y0, self.x1, self.y1 = kutu
        self.olcek = olcek
        self.yuk = yuk

    def x(self, deger: float) -> float:
        return (deger - self.x0) * self.olcek + KENAR_BOSLUGU

    def y(self, deger: float) -> float:
        return self.yuk - ((deger - self.y0) * self.olcek + KENAR_BOSLUGU)

    def p(self, n: Nokta) -> str:
        return f"{self.x(n.x):.2f},{self.y(n.y):.2f}"


def _poligon(
    d: _Donusum, noktalar: list[Nokta], dolgu: str, kenar: str, opak: float, kalin: float
) -> str:
    if len(noktalar) < 3:
        return ""
    pts = " ".join(d.p(p) for p in noktalar)
    return (
        f'<polygon points="{pts}" fill="{dolgu}" fill-opacity="{opak}" '
        f'stroke="{kenar}" stroke-width="{kalin}" />'
    )


def _eleman_cizimi(d: _Donusum, e: Eleman) -> list[str]:
    dolgu, kenar = RENKLER.get(e.tip, RENKLER[ElemanTipi.BILINMEYEN])
    parcalar: list[str] = []

    if e.tip == ElemanTipi.DOSEME:
        parcalar.append(_poligon(d, e.cevre, dolgu, kenar, 0.18, 1.5))
        for b in e.bosluklar:
            parcalar.append(_poligon(d, b, "#ffffff", "#c0392b", 1.0, 1.5))
    elif e.tip == ElemanTipi.KIRIS:
        b = e.olculer.get("b", 0.25)
        for s in e.segmentler:
            parcalar.append(
                f'<line x1="{d.x(s.baslangic.x):.2f}" y1="{d.y(s.baslangic.y):.2f}" '
                f'x2="{d.x(s.bitis.x):.2f}" y2="{d.y(s.bitis.y):.2f}" '
                f'stroke="{dolgu}" stroke-width="{max(b * d.olcek, 2.0):.2f}" '
                f'stroke-opacity="0.45" stroke-linecap="butt" />'
            )
    else:
        parcalar.append(_poligon(d, e.cevre, dolgu, kenar, 0.55, 1.2))

    # Kirik olcu ekseni (perde ve kiris icin)
    if e.tip in (ElemanTipi.PERDE, ElemanTipi.KIRIS):
        for s in e.segmentler:
            parcalar.append(
                f'<line x1="{d.x(s.baslangic.x):.2f}" y1="{d.y(s.baslangic.y):.2f}" '
                f'x2="{d.x(s.bitis.x):.2f}" y2="{d.y(s.bitis.y):.2f}" '
                f'stroke="{kenar}" stroke-width="1.4" stroke-dasharray="7,4" />'
            )
            # Kirilim noktalari
            for uc in (s.baslangic, s.bitis):
                parcalar.append(
                    f'<circle cx="{d.x(uc.x):.2f}" cy="{d.y(uc.y):.2f}" r="3" '
                    f'fill="{kenar}" />'
                )
    return parcalar


def _cakismayan_konum(
    x: float, y: float, yerlesim: list[tuple[float, float]]
) -> tuple[float, float]:
    """Ust uste binen etiketleri dusey kaydirarak okunur hale getirir."""
    for _ in range(12):
        if all(
            abs(x - ax) > 46.0 or abs(y - ay) > 30.0 for ax, ay in yerlesim
        ):
            break
        y += 32.0
    yerlesim.append((x, y))
    return x, y


def _etiket(d: _Donusum, e: Eleman, yerlesim: list[tuple[float, float]]) -> str:
    m = e.merkez
    if e.tip == ElemanTipi.KIRIS and e.segmentler:
        m = max(e.segmentler, key=lambda s: s.uzunluk).orta
    ad = html.escape(e.ad)
    if e.tip == ElemanTipi.KIRIS:
        olcu = f"{e.olculer.get('b', 0):.2f}/{e.olculer.get('h', 0):.2f}"
        ek = f"L={e.toplam_uzunluk:.2f}"
    elif e.tip == ElemanTipi.PERDE:
        olcu = f"t={e.olculer.get('t', 0):.2f}"
        ek = f"L={e.toplam_uzunluk:.2f}"
    elif e.tip == ElemanTipi.KOLON:
        olcu = f"{e.olculer.get('b', 0):.2f}/{e.olculer.get('h', 0):.2f}"
        ek = ""
    else:
        olcu = f"t={e.olculer.get('t', 0):.2f}"
        ek = f"A={e.olculer.get('net_alan', e.olculer.get('brut_alan', 0)):.2f}"

    uyari = "" if e.guven >= 0.7 else " !"
    x, y = _cakismayan_konum(d.x(m.x), d.y(m.y), yerlesim)
    return (
        f'<g class="etiket">'
        f'<rect x="{x - 34:.1f}" y="{y - 15:.1f}" width="68" height="{28 if ek else 18}" '
        f'fill="#ffffff" fill-opacity="0.72" stroke="none" rx="3" />'
        f'<text x="{x:.1f}" y="{y - 4:.1f}" text-anchor="middle" '
        f'class="ad">{ad}{uyari}</text>'
        f'<text x="{x:.1f}" y="{y + 8:.1f}" text-anchor="middle" '
        f'class="olcu">{html.escape(olcu)}</text>'
        + (
            f'<text x="{x:.1f}" y="{y + 19:.1f}" text-anchor="middle" '
            f'class="olcu">{html.escape(ek)}</text>'
            if ek
            else ""
        )
        + "</g>"
    )


def svg_yaz(sonuc: MetrajSonucu, hedef: str | Path) -> Path:
    """Tespit sonuclarini gosteren SVG kontrol paftasi yazar."""
    hedef = Path(hedef)
    tum_noktalar: list[Nokta] = []
    for e in sonuc.elemanlar:
        tum_noktalar.extend(e.cevre)
        for s in e.segmentler:
            tum_noktalar.extend([s.baslangic, s.bitis])
    if not tum_noktalar:
        tum_noktalar = [Nokta(0, 0), Nokta(1, 1)]

    kutu = sinir_kutusu(tum_noktalar)
    genislik_m = max(kutu[2] - kutu[0], 1e-6)
    yukseklik_m = max(kutu[3] - kutu[1], 1e-6)
    olcek = (HEDEF_GENISLIK - 2 * KENAR_BOSLUGU) / genislik_m
    svg_g = HEDEF_GENISLIK
    svg_y = yukseklik_m * olcek + 2 * KENAR_BOSLUGU
    aciklama_y = 150.0
    d = _Donusum(kutu, olcek, svg_y)

    govde: list[str] = []
    # Cizim sirasi: doseme altta, kiris, sonra kolon/perde ustte
    sira = {
        ElemanTipi.DOSEME: 0,
        ElemanTipi.MERDIVEN: 1,
        ElemanTipi.KIRIS: 2,
        ElemanTipi.PERDE: 3,
        ElemanTipi.KOLON: 4,
    }
    for e in sorted(sonuc.elemanlar, key=lambda x: sira.get(x.tip, 9)):
        govde.extend(_eleman_cizimi(d, e))
    yerlesim: list[tuple[float, float]] = []
    for e in sorted(sonuc.elemanlar, key=lambda x: -sira.get(x.tip, 9)):
        govde.append(_etiket(d, e, yerlesim))

    ozet = sonuc.ozet()
    aciklama: list[str] = []
    ay = svg_y + 26
    aciklama.append(
        f'<text x="{KENAR_BOSLUGU}" y="{ay}" class="baslik">'
        f"KONTROL PAFTASI &#8211; {html.escape(sonuc.kat or 'Kat')} "
        f"&#8211; {html.escape(Path(sonuc.kaynak_dosya).name)}</text>"
    )
    ay += 24
    for tip, renk in (
        (ElemanTipi.KOLON, RENKLER[ElemanTipi.KOLON][0]),
        (ElemanTipi.PERDE, RENKLER[ElemanTipi.PERDE][0]),
        (ElemanTipi.KIRIS, RENKLER[ElemanTipi.KIRIS][0]),
        (ElemanTipi.DOSEME, RENKLER[ElemanTipi.DOSEME][0]),
    ):
        k = ozet.get(tip.value)
        if not k:
            continue
        metin = (
            f"{tip.value}: {int(k['adet'])} adet &#8226; "
            f"beton {k['beton_m3']:.2f} m&#179; &#8226; "
            f"kalip {k['kalip_m2']:.2f} m&#178;"
        )
        if k.get("demir_kg"):
            metin += f" &#8226; demir ~{k['demir_kg']:.0f} kg"
        aciklama.append(
            f'<rect x="{KENAR_BOSLUGU}" y="{ay - 10}" width="14" height="14" '
            f'fill="{renk}" fill-opacity="0.6" stroke="#333" />'
            f'<text x="{KENAR_BOSLUGU + 22}" y="{ay + 2}" class="aciklama">'
            f"{metin}</text>"
        )
        ay += 20

    if sonuc.uyarilar:
        ay += 6
        aciklama.append(
            f'<text x="{KENAR_BOSLUGU}" y="{ay}" class="uyari-baslik">'
            f"UYARILAR ({len(sonuc.uyarilar)}):</text>"
        )
        ay += 16
        for u in sonuc.uyarilar[:8]:
            aciklama.append(
                f'<text x="{KENAR_BOSLUGU + 10}" y="{ay}" class="uyari">'
                f"&#8226; {html.escape(u[:150])}</text>"
            )
            ay += 15
    aciklama_y = max(aciklama_y, ay - svg_y + 20)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{svg_g:.0f}" \
height="{svg_y + aciklama_y:.0f}" viewBox="0 0 {svg_g:.0f} {svg_y + aciklama_y:.0f}">
<style>
  text {{ font-family: "DejaVu Sans", Arial, sans-serif; }}
  .ad {{ font-size: 12px; font-weight: 700; fill: #111; }}
  .olcu {{ font-size: 10px; fill: #333; }}
  .baslik {{ font-size: 16px; font-weight: 700; fill: #111; }}
  .aciklama {{ font-size: 12px; fill: #222; }}
  .uyari-baslik {{ font-size: 12px; font-weight: 700; fill: #c0392b; }}
  .uyari {{ font-size: 11px; fill: #c0392b; }}
</style>
<rect width="100%" height="100%" fill="#ffffff" />
{chr(10).join(govde)}
{chr(10).join(aciklama)}
</svg>
"""
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(svg, encoding="utf-8")
    return hedef
