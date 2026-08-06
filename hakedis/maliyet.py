"""Yaklasik maliyet hesabi: metraj satirlari x poz birim fiyatlari.

Poz numaralari (ornegin "16.058/1-K") ile metraj cetvelindeki miktarlar
eslenir ve tutar = miktar x birim fiyat uygulanir. Dusum satirlari eksili
yazilir.

Fiyat kaynaklari (ustteki ustune biner):
  1. `birim_fiyatlar.yml`  - yil bazli resmi birim fiyat veritabani
     (`maliyet.fiyatlar_yolu` ile yol verilir; yoksa sessizce atlanir).
  2. `maliyet.poz_fiyatlari` - yapilandirmadaki poz -> fiyat tablosu.

Cikti YIGS (yaklasik maliyet) duzenine yakin hazirlanir: her kalemde sirasi,
poz no, tanim, birim, miktar, birim fiyat ve tutar bulunur ve kalemler
bolumlere (betonarme, siva, dograma, kaplama) ayrilir.
"""

from __future__ import annotations

from pathlib import Path

from hakedis.config import Ayarlar
from hakedis.model import MetrajSonucu

# Poz on eklerine gore yaklasik maliyet bolumleri
BOLUMLER: list[tuple[str, tuple[str, ...]]] = [
    ("BETONARME", ("16.", "18.", "21.011")),
    ("SIVA-BADANA", ("21.",)),
    ("DOGRAMA", ("22.",)),
    ("DOSEME KAPLAMA", ("23.",)),
]


def _bolum(poz: str) -> str:
    for ad, on_ekler in BOLUMLER:
        if poz.startswith(on_ekler):
            return ad
    return "DIGER"


def fiyat_sozlugu(ayarlar: Ayarlar) -> dict[str, float]:
    """Birim fiyat veritabanini tek sozlukte birlestirir (config oncelikli)."""
    birlestik: dict[str, float] = {}
    yol = str(ayarlar.al("maliyet.fiyatlar_yolu", "") or "").strip()
    if yol:
        import yaml

        p = Path(yol)
        if p.exists():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    tablo = yaml.safe_load(f) or {}
                for k, v in tablo.items():
                    try:
                        birlestik[str(k)] = float(v)
                    except (TypeError, ValueError):  # pragma: no cover
                        continue
            except Exception:  # pragma: no cover
                pass
    for k, v in (ayarlar.al("maliyet.poz_fiyatlari", {}) or {}).items():
        try:
            birlestik[str(k)] = float(v)
        except (TypeError, ValueError):  # pragma: no cover
            continue
    return birlestik


def maliyet_hesapla(sonuc: MetrajSonucu, ayarlar: Ayarlar) -> dict:
    """Metraj sonucuna poz fiyatlarini uygulayarak maliyet tablosu uretir."""
    fiyatlar = fiyat_sozlugu(ayarlar)
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
        tutar = miktar * fiyat
        if abs(tutar) < 1e-9:
            continue
        kalemler.append(
            {
                "poz": s.poz,
                "tanim": s.tanim,
                "eleman": s.eleman_adi,
                "birim": s.birim,
                "miktar": miktar,
                "fiyat": fiyat,
                "tutar": tutar,
                "dusum": s.dusum_mu,
                "bolum": _bolum(s.poz),
            }
        )

    bolum_sirasi = {ad: i for i, (ad, _) in enumerate(BOLUMLER)}
    kalemler.sort(key=lambda k: (bolum_sirasi.get(k["bolum"], 99), 0))
    for i, k in enumerate(kalemler, 1):
        k["sira"] = i

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
            "birim fiyatlarini 'Maliyet' bolumune veya birim_fiyatlar.yml "
            "dosyasina girin."
        ),
    }


def maliyet_konsol(m: dict) -> str:
    """Maliyet sozlugunu konsola yazdirilabilir metne cevirir."""
    if not m["kalemler"]:
        return "Maliyet: hicbir poz icin birim fiyat tanimli degil."
    satirlar = ["", "YAKLASIK MALIYET", "=" * 66]
    satirlar.append(f"{'NO':>4} {'POZ':<16}{'TANIM':<32}{'MIKTAR':>9}  TUTAR")
    satirlar.append("-" * 66)
    son_bolum = None
    for k in m["kalemler"]:
        if k["bolum"] != son_bolum:
            satirlar.append(f"  {k['bolum']}")
            son_bolum = k["bolum"]
        isaret = "-" if k["dusum"] else ""
        satirlar.append(
            f"{k['sira']:>4} {k['poz']:<16}{k['tanim'][:31]:<32}"
            f"{isaret}{k['miktar']:>8.2f}  {k['tutar']:>12,.0f}"
        )
    satirlar.append("-" * 66)
    satirlar.append(f"ARA TOPLAM{'':<52}{m['ara_toplam']:>12,.0f}")
    satirlar.append(
        f"KDV (%{m['kdv_oran']:g}){'':<51}{m['kdv']:>12,.0f}"
    )
    satirlar.append(
        f"GENEL TOPLAM ({m['para_birimi']}){'':<40}{m['genel_toplam']:>12,.0f}"
    )
    if m["fiyatsiz_pozlar"]:
        satirlar.append(
            f"\nFiyat tanimsiz pozlar: {', '.join(m['fiyatsiz_pozlar'])}"
        )
    satirlar.append(f"\n{m['not']}")
    return "\n".join(satirlar)
