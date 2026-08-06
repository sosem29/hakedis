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
    demir_var = any(k["demir_kg"] for k in ozet.values())
    baslik = f"{'Eleman':<12}{'Adet':>6}{'Beton (m3)':>14}{'Kalip (m2)':>14}"
    if demir_var:
        baslik += f"{'Demir (kg)':>14}"
    sat.append(baslik)
    sat.append(_cizgi())
    beton_t = kalip_t = demir_t = 0.0
    for tip in ElemanTipi:
        k = ozet.get(tip.value)
        if not k or (k["adet"] == 0 and k["beton_m3"] == 0 and k["kalip_m2"] == 0):
            continue
        satir_metni = (
            f"{tip.value:<12}{int(k['adet']):>6}"
            f"{k['beton_m3']:>14.3f}{k['kalip_m2']:>14.3f}"
        )
        if demir_var:
            satir_metni += f"{k['demir_kg']:>14.2f}"
        sat.append(satir_metni)
        beton_t += k["beton_m3"]
        kalip_t += k["kalip_m2"]
        demir_t += k["demir_kg"]
    sat.append(_cizgi())
    toplam = f"{'TOPLAM':<12}{'':>6}{beton_t:>14.3f}{kalip_t:>14.3f}"
    if demir_var:
        toplam += f"{demir_t:>14.2f}"
    sat.append(toplam)
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


def konsol_ozeti_toplu(sonuclar: list) -> str:
    """Cok katli calismanin kat bazinda ozetini dondurur."""
    from hakedis.metraj import sonuclari_birlestir

    birlesik = sonuclari_birlestir(sonuclar)
    sat: list[str] = []
    sat.append(_cizgi("="))
    sat.append(f"TOPLU KIRIK OLCU METRAJI  |  {len(sonuclar)} kat")
    sat.append(f"Kaynak: {birlesik.kaynak_dosya}")
    sat.append(_cizgi("="))

    demir_var = any(s.kat and s.kg for s in birlesik.satirlar)
    baslik = f"{'Kat':<16}{'Beton (m3)':>14}{'Kalip (m2)':>14}"
    if demir_var:
        baslik += f"{'Demir (kg)':>14}"
    sat.append(baslik)
    sat.append(_cizgi())

    kats = list(dict.fromkeys(s.kat for s in birlesik.satirlar if s.kat))
    bt_t = kt_t = dt_t = 0.0
    for kat in kats:
        grubu = [s for s in birlesik.satirlar if s.kat == kat]
        bt = kt = dt = 0.0
        for s in grubu:
            isaret = -1.0 if s.dusum_mu else 1.0
            if s.birim == "m3":
                bt += isaret * (s.hacim or 0.0)
            elif s.birim == "m2":
                kt += isaret * (s.alan or 0.0)
            elif s.birim == "kg":
                dt += isaret * (s.kg or 0.0)
        satir = f"{kat:<16}{bt:>14.3f}{kt:>14.3f}"
        if demir_var:
            satir += f"{dt:>14.2f}"
        sat.append(satir)
        bt_t += bt
        kt_t += kt
        dt_t += dt

    sat.append(_cizgi())
    toplam = f"{'TOPLAM':<16}{bt_t:>14.3f}{kt_t:>14.3f}"
    if demir_var:
        toplam += f"{dt_t:>14.2f}"
    sat.append(toplam)

    if birlesik.uyarilar:
        sat.append("")
        sat.append(_cizgi("!"))
        sat.append(
            f"UYARILAR ({len(birlesik.uyarilar)}) - Excel 'Uyarilar' "
            "sayfasinda kat bazli listelenir."
        )
        sat.append(_cizgi("!"))
    return "\n".join(sat)
