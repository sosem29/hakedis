"""JSON-uyumlu veri paketleri.

CLI `--json` ciktisi ile web arayuzunun kullandigi veri yapisini tek yerde
toplar; iki arayuz arasindaki tutarsizlik onlenir.
"""

from __future__ import annotations

from hakedis.metraj import sonuclari_birlestir
from hakedis.model import Eleman, KirikOlcuSatiri, MetrajSonucu


def eleman_verisi(e: Eleman) -> dict:
    return {
        "ad": e.ad,
        "tip": e.tip.value,
        "kat": e.kat,
        "katman": e.kaynak_katman,
        "etiket": e.etiket_metni,
        "olculer": e.olculer,
        "guven": e.guven,
        "notlar": e.notlar,
        "kirik_olcu": [
            {
                "baslangic": [s.baslangic.x, s.baslangic.y],
                "bitis": [s.bitis.x, s.bitis.y],
                "uzunluk": round(s.uzunluk, 4),
                "aciklama": s.aciklama,
            }
            for s in e.segmentler
        ],
        "cevre": [[p.x, p.y] for p in e.cevre],
        "bosluklar": [[[p.x, p.y] for p in b] for b in e.bosluklar],
    }


def satir_verisi(s: KirikOlcuSatiri) -> dict:
    return {
        "poz": s.poz,
        "eleman": s.eleman_adi,
        "tip": s.tip.value,
        "tanim": s.tanim,
        "benzer": s.benzer,
        "en": s.en,
        "boy": s.boy,
        "yukseklik": s.yukseklik,
        "alan": s.alan,
        "hacim": s.hacim,
        "demir": s.kg,
        "miktar": s.miktar,
        "birim": s.birim,
        "formul": s.formul,
        "dusum": s.dusum_mu,
        "detay": s.detay,
        "kat": s.kat,
    }


def sonuc_verisi(sonuc: MetrajSonucu) -> dict:
    """Tek bir metraj sonucunun tam JSON paketi (CLI --json ile ayni)."""
    return {
        "kat": sonuc.kat,
        "kaynak_dosya": sonuc.kaynak_dosya,
        "parametreler": sonuc.parametreler,
        "ozet": sonuc.ozet(),
        "uyarilar": sonuc.uyarilar,
        "elemanlar": [eleman_verisi(e) for e in sonuc.elemanlar],
        "satirlar": [satir_verisi(s) for s in sonuc.satirlar],
    }


def toplu_verisi(sonuclar: list[MetrajSonucu]) -> dict:
    """Cok katli/paftali calismanin web arayuzu icin ozet paketi."""
    birlesik = sonuclari_birlestir(sonuclar)
    return {
        "tur": "toplu",
        "katlar": [
            {
                "kat": s.kat,
                "kaynak_dosya": s.kaynak_dosya,
                "ozet": s.ozet(),
                "uyari_sayisi": len(s.uyarilar),
            }
            for s in sonuclar
        ],
        "toplam": birlesik.ozet(),
        "uyarilar": birlesik.uyarilar,
        "satirlar": [satir_verisi(s) for s in birlesik.satirlar],
    }
