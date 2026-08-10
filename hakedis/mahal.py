"""Mahal (oda) plani okuma ve kaplama/siva metrajina cevirme.

Kalip plani yaninda bir mahal plani (.dwg/.dxf/.pdf) yuklendiginde:

  * Her oda poligonunun alani  -> zemin kaplama + tesviye alani
  * Oda adi (icindeki etiket)  -> kaplama cinsi (seramik/parke/...)
  * Oda cevresi x duvar yukseklik -> ic duvar sivasi alani
  * Oda alani                  -> tavan siva/badana alani

Bu sekilde `_siva_kaplama_satirlari`nin formkorku YAKLASIK degerleri yerine
oda bazinda (yine de kot farklarisiz) degerler kullanilir.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from hakedis.config import Ayarlar
from hakedis.geometry import (
    alan,
    cevre_uzunlugu,
    dogrusallari_sadelestir,
    nokta_icinde_mi,
    ortogonale_yasla,
    tekrarlari_temizle,
)
from hakedis.model import Cizim, ElemanTipi, HamVarlik, KirikOlcuSatiri, Nokta
from hakedis.readers import cizim_oku


@dataclass
class Mahal:
    """Bir oda/mahal plani okumasinin sonucu."""

    ad: str
    tip: str  # kaplama turu: seramik | parke | karo | beton | ...
    alan: float  # zemin alani (m2)
    cevre: float  # duvar cevresi (m)
    noktalar: list[Nokta] = field(default_factory=list)
    uyari: str = ""

    def duvar_alani(self, yukseklik: float) -> float:
        return self.cevre * yukseklik


def _kapali_poligonlar(cizim: Cizim, ayarlar: Ayarlar) -> list[list[Nokta]]:
    """Mahal planindan oda sinir poligonlarini secer.

    Katman deseni verilmisse o katmanlardaki kapali poligonlar kullanilir;
    PDF gibi katman bilgisi olmayan kaynaklarda tum kapali poligonlar adaydir.
    """
    desenler = [
        re.compile(d, re.IGNORECASE)
        for d in (ayarlar.al("mahal.katmanlar", []) or [])
    ]
    adaylar: list[HamVarlik] = [
        v
        for v in cizim.varliklar
        if v.tur in ("poligon", "tarama") and v.kapali and len(v.noktalar) >= 3
    ]
    if desenler:
        eslenen = [v for v in adaylar if any(d.search(v.katman) for d in desenler)]
        if eslenen:
            adaylar = eslenen

    min_alan = float(ayarlar.al("mahal.min_alan", 1.0) or 1.0)
    poligonlar: list[list[Nokta]] = []
    for v in adaylar:
        pts = dogrusallari_sadelestir(
            ortogonale_yasla(tekrarlari_temizle(v.noktalar))
        )
        if len(pts) >= 3 and alan(pts) >= min_alan:
            poligonlar.append(pts)

    # Buyuk poligonun icindeki kucuk detay poligonlarini at (oda icindeki
    # govde/yerlesim cizgileri). Ayni buyuklukteki komşu odalar birbirini
    # kapsamaz, bu yuzden guvenli bir yaklasimdir.
    poligonlar.sort(key=alan, reverse=True)
    secilen: list[list[Nokta]] = []
    for pts in poligonlar:
        if any(nokta_icinde_mi(pts[0], buyuk) for buyuk in secilen):
            continue
        secilen.append(pts)
    return secilen


def _odadaki_etiket(poligon: list[Nokta], metinler: list[HamVarlik]) -> str:
    """Poligonun icinde kalan, sayi-olmayan ilk etiketi ad olarak dondurur."""
    for m in metinler:
        if not m.metin or not m.noktalar:
            continue
        if nokta_icinde_mi(m.noktalar[0], poligon):
            metin = m.metin.strip()
            if not metin or re.fullmatch(r"[\d.,\s/*xX×%²m²]{1,12}", metin):
                continue
            return metin.upper()
    return ""


def _kaplama_turu(ad: str, ayarlar: Ayarlar) -> str:
    esleme = ayarlar.al("mahal.kaplama_esleme", {}) or {}
    varsayilan = str(esleme.get("varsayilan", "parke"))
    ad_kucuk = (ad or "").lower()
    for anahtar, tur in esleme.items():
        if anahtar == "varsayilan":
            continue
        if str(anahtar).lower() in ad_kucuk:
            return str(tur)
    return varsayilan


def mahalleri_oku(dosya: str | Path, ayarlar: Ayarlar) -> tuple[list[Mahal], list[str]]:
    """Mahal plani dosyasini okur ve oda listesi cikarir."""
    cizim = cizim_oku(dosya, ayarlar)
    uyarilar: list[str] = list(cizim.notlar)
    metinler = [v for v in cizim.varliklar if v.tur == "metin" and v.metin]

    # Mahal etiketi katmanlarindaki yazilara oncelik ver (DXF icin)
    etiket_desenleri = [
        re.compile(d, re.IGNORECASE)
        for d in (ayarlar.al("katmanlar.mahal_etiket", []) or [])
    ]
    if etiket_desenleri:
        oncelikli = [
            v for v in metinler if any(d.search(v.katman) for d in etiket_desenleri)
        ]
        if oncelikli:
            metinler = oncelikli + [v for v in metinler if v not in oncelikli]

    mahaller: list[Mahal] = []
    for pts in _kapali_poligonlar(cizim, ayarlar):
        ad = _odadaki_etiket(pts, metinler)
        a = alan(pts)
        c = cevre_uzunlugu(pts)
        tip = _kaplama_turu(ad, ayarlar)
        mahaller.append(
            Mahal(ad=ad or "Mahal", tip=tip, alan=a, cevre=c, noktalar=pts)
        )

    if not mahaller:
        uyarilar.append(
            "Mahal planindan oda tespit edilemedi; kapali oda poligonlari "
            "ve oda adi etiketlerini kontrol edin."
        )
    else:
        adsiz = [m for m in mahaller if not m.ad or m.ad == "Mahal"]
        if adsiz:
            uyarilar.append(
                f"{len(adsiz)} oda adi okunamadi; kaplama cinsi 'varsayilan' "
                "turuyle atandi."
            )
    return mahaller, uyarilar


def mahal_duvar_yuksekligi(ayarlar: Ayarlar) -> float:
    h = float(ayarlar.al("mahal.duvar_yuksekligi", 0.0) or 0.0)
    if h <= 0.0:
        h = float(ayarlar.al("kat.kat_yuksekligi", 3.0) or 3.0)
    return h


def _satir(
    poz: str,
    eleman_adi: str,
    tanim: str,
    alan_m2: float,
    formul: str,
    detay: list[str],
    ayarlar: Ayarlar,
) -> KirikOlcuSatiri:
    return KirikOlcuSatiri(
        poz=poz,
        eleman_adi=eleman_adi,
        tip=ElemanTipi.BILINMEYEN,
        tanim=tanim,
        benzer=1,
        alan=round(alan_m2, 4),
        birim="m2",
        formul=formul,
        kat=ayarlar.kat_adi,
        detay=detay,
    )


def mahal_satirlari(
    mahaller: list[Mahal], ayarlar: Ayarlar
) -> list[KirikOlcuSatiri]:
    """Mahal listesinden kaplama/tesviye/siva satirlari uretir."""
    kat = ayarlar.kat_adi
    h = mahal_duvar_yuksekligi(ayarlar)
    toplam = sum(m.alan for m in mahaller)
    satirlar: list[KirikOlcuSatiri] = []
    if toplam <= 1e-9:
        return satirlar

    # Zemin kaplamasi: cins bazinda
    by_tip: dict[str, float] = {}
    for m in mahaller:
        by_tip[m.tip] = by_tip.get(m.tip, 0.0) + m.alan
    seramik_poz = str(ayarlar.al("kaplama.seramik_poz", "23.062/S"))
    parke_poz = str(ayarlar.al("kaplama.parke_poz", "23.063"))
    poz_tanimi = {
        "seramik": ("Seramik zemin kaplamasi", seramik_poz),
        "karo": ("Karo zemin kaplamasi", seramik_poz),
        "parke": ("Parke zemin kaplamasi", parke_poz),
        "laminat": ("Laminat zemin kaplamasi", parke_poz),
    }
    for tur, m2 in sorted(by_tip.items(), key=lambda x: -x[1]):
        if m2 <= 1e-9:
            continue
        tanim, poz = poz_tanimi.get(
            tur, (f"{tur.title()} zemin kaplamasi", seramik_poz)
        )
        odalar = ", ".join(
            f"{m.ad} ({m.alan:.2f})" for m in mahaller if m.tip == tur
        )
        satirlar.append(
            _satir(
                poz,
                "KAPLAMA",
                f"{tanim} - MAHAL PLANINDAN",
                m2,
                f"{len([m for m in mahaller if m.tip == tur])} oda",
                [f"Odalar: {odalar}", f"Duvar yuksekligi H = {h:.2f} m"],
                ayarlar,
            )
        )

    # Tesviye: tum oda zeminleri
    satirlar.append(
        _satir(
            str(ayarlar.al("kaplama.tesviye_poz", "23.062/T")),
            "TESVIYE",
            "Doseme tesviye (suphe tabakasi) - MAHAL PLANINDAN",
            toplam,
            f"toplam zemin {toplam:.3f} m2",
            ["Oda zemin alanlari toplami."],
            ayarlar,
        )
    )

    # Ic duvar sivasi: oda cevresi x duvar yuksekligi
    if bool(ayarlar.al("siva.aktif", False)):
        siva = sum(m.duvar_alani(h) for m in mahaller)
        satirlar.append(
            _satir(
                ayarlar.poz("siva"),
                "SIVA",
                "Ic duvar sivasi - MAHAL PLANINDAN",
                siva,
                f"toplam oda cevresi {sum(m.cevre for m in mahaller):.3f} m x H={h:.2f} m",
                [
                    "Oda cevreleri toplami x duvar yuksekligi; kot farklari ve "
                    "kapi/pencere bosluk dusumu icin fiziksel kontrol gerekir.",
                ],
                ayarlar,
            )
        )
        satirlar.append(
            _satir(
                ayarlar.poz("siva_tavan"),
                "TAVAN",
                "Tavan siva + badana - MAHAL PLANINDAN",
                toplam,
                f"toplam zemin {toplam:.3f} m2",
                ["Oda zemin alanlari toplami; asma tavan/baca dusumu kontrol edilmeli."],
                ayarlar,
            )
        )
    return satirlar
