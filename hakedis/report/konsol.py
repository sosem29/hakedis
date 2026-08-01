"""Konsol ozeti - metraji Excel acmadan hizlica gormek icin."""

from __future__ import annotations

from hakedis.model import ElemanTipi, MetrajSonucu

GENISLIK = 78


def _cizgi(karakter: str = "-") -> str:
    return karakter * GENISLIK


def konsol_ozeti(sonuc: MetrajSonucu, ayrintili: bool = False) -> str:
    """Metraj sonucunu okunabilir metin olarak dondurur."""
    sat: list[str] = []
    sat.append(_cizgi("="))
    sat.append(f"KIRIK OLCU METRAJI  |  {sonuc.kat or 'Kat belirtilmedi'}")
    sat.append(f"Kaynak: {sonuc.kaynak_dosya}")
    p = sonuc.parametreler
    if p:
        sat.append(
            f"Kat yuks. {p.get('kat_yuksekligi', 0):.2f} m  |  "
            f"Doseme {p.get('doseme_kalinligi', 0):.2f} m  |  "
            f"Net yuks. {p.get('net_yukseklik', 0):.2f} m  |  "
            f"Birim: {p.get('birim', '?')}"
        )
    sat.append(_cizgi("="))

    ozet = sonuc.ozet()
    sat.append(
        f"{'Eleman':<12}{'Adet':>6}{'Beton (m3)':>14}{'Kalip (m2)':>14}"
    )
    sat.append(_cizgi())
    beton_t = kalip_t = 0.0
    for tip in ElemanTipi:
        k = ozet.get(tip.value)
        if not k or (k["adet"] == 0 and k["beton_m3"] == 0 and k["kalip_m2"] == 0):
            continue
        sat.append(
            f"{tip.value:<12}{int(k['adet']):>6}"
            f"{k['beton_m3']:>14.3f}{k['kalip_m2']:>14.3f}"
        )
        beton_t += k["beton_m3"]
        kalip_t += k["kalip_m2"]
    sat.append(_cizgi())
    sat.append(f"{'TOPLAM':<12}{'':>6}{beton_t:>14.3f}{kalip_t:>14.3f}")
    sat.append("")

    if ayrintili:
        sat.append("ELEMAN BAZLI KIRIK OLCU")
        sat.append(_cizgi())
        for s in sonuc.satirlar:
            isaret = "-" if s.dusum_mu else " "
            sat.append(
                f"{isaret}{s.eleman_adi:<8}{s.tanim:<38}"
                f"{s.miktar:>10.3f} {s.birim:<4}{s.formul}"
            )
            for d in s.detay:
                sat.append(f"          {d}")
            sat.append("")

    if sonuc.uyarilar:
        sat.append(_cizgi("!"))
        sat.append(f"UYARILAR ({len(sonuc.uyarilar)}) - teslim oncesi kontrol edin:")
        for i, u in enumerate(sonuc.uyarilar, 1):
            sat.append(f"  {i}. {u}")
        sat.append(_cizgi("!"))
    return "\n".join(sat)
