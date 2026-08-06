"""Yaklasik maliyet hesabi: metraj satirlari x poz birim fiyatlari.

Poz numaralari (ornegin "16.058/1-K") ile metraj cetvelindeki miktarlar
eslenir ve tutar = miktar x birim fiyat uygulanir. Dusum satirlari eksili
yazilir. Fiyatlar yapilandirmadaki `maliyet.poz_fiyatlari` bolumunden gelir;
guncel bakanlik birim fiyatlari buraya girilir (bu moduldeki degerler
ORNEKTIR).
"""

from __future__ import annotations

from hakedis.config import Ayarlar
from hakedis.model import MetrajSonucu


def maliyet_hesapla(sonuc: MetrajSonucu, ayarlar: Ayarlar) -> dict:
    """Metraj sonucuna poz fiyatlarini uygulayarak maliyet tablosu uretir."""
    fiyatlar = ayarlar.al("maliyet.poz_fiyatlari", {}) or {}
    kalemler: list[dict] = []
    fiyatli_pozlar: set[str] = set()

    for s in sonuc.satirlar:
        fiyat = fiyatlar.get(s.poz)
        if fiyat is None:
            continue
        fiyatli_pozlar.add(s.poz)
        miktar = s.miktar
        if s.dusum_mu:
            miktar = -miktar
        tutar = miktar * float(fiyat)
        if abs(tutar) < 1e-9:
            continue
        kalemler.append(
            {
                "poz": s.poz,
                "tanim": s.tanim,
                "eleman": s.eleman_adi,
                "birim": s.birim,
                "miktar": miktar,
                "fiyat": float(fiyat),
                "tutar": tutar,
                "dusum": s.dusum_mu,
            }
        )

    ara_toplam = sum(k["tutar"] for k in kalemler)
    kdv_oran = float(ayarlar.al("maliyet.kdv_oran", 20))
    kdv = ara_toplam * kdv_oran / 100.0
    genel_toplam = ara_toplam + kdv
    eksik = sorted({s.poz for s in sonuc.satirlar} - fiyatli_pozlar)

    return {
        "aktif": bool(ayarlar.al("maliyet.aktif", False)),
        "para_birimi": str(ayarlar.al("maliyet.para_birimi", "TL")),
        "kdv_oran": kdv_oran,
        "kalemler": kalemler,
        "ara_toplam": ara_toplam,
        "kdv": kdv,
        "genel_toplam": genel_toplam,
        "fiyatsiz_pozlar": eksik,
        "not": (
            "Birim fiyatlar ORNEKTIR. Kesin bedel icin guncel bakanlik/il "
            "birim fiyatlarini 'Maliyet' bolumune girin."
        ),
    }


def maliyet_konsol(m: dict) -> str:
    """Maliyet sozlugunu konsola yazdirilabilir metne cevirir."""
    if not m["kalemler"]:
        return "Maliyet: hicbir poz icin birim fiyat tanimli degil."
    satirlar = ["", "YAKLASIK MALIYET", "=" * 62]
    satirlar.append(f"{'POZ':<16}{'TANIM':<34}{'MIKTAR':>10}  TUTAR")
    satirlar.append("-" * 62)
    for k in m["kalemler"]:
        isaret = "-" if k["dusum"] else ""
        satirlar.append(
            f"{k['poz']:<16}{k['tanim'][:33]:<34}"
            f"{isaret}{k['miktar']:>9.2f}  {k['tutar']:>12,.0f}"
        )
    satirlar.append("-" * 62)
    satirlar.append(f"ARA TOPLAM{'':<50}{m['ara_toplam']:>12,.0f}")
    satirlar.append(
        f"KDV (%{m['kdv_oran']:g}){'':<49}{m['kdv']:>12,.0f}"
    )
    satirlar.append(
        f"GENEL TOPLAM ({m['para_birimi']}){'':<38}{m['genel_toplam']:>12,.0f}"
    )
    if m["fiyatsiz_pozlar"]:
        satirlar.append(
            f"\nFiyat tanimsiz pozlar: {', '.join(m['fiyatsiz_pozlar'])}"
        )
    satirlar.append(f"\n{m['not']}")
    return "\n".join(satirlar)
