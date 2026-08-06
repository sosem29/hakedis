"""Cekirdek veri modeli.

Tum ic hesaplar METRE cinsindendir. Okuyucular (DXF/PDF) kendi birimlerini
metreye cevirerek bu modele aktarir.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Sequence


class ElemanTipi(str, Enum):
    """Kalip planinda metraji cikarilan tasiyici eleman tipleri."""

    KOLON = "Kolon"
    PERDE = "Perde"
    KIRIS = "Kiris"
    DOSEME = "Doseme"
    MERDIVEN = "Merdiven"
    BOSLUK = "Bosluk"
    KAPI = "Kapi"
    PENCERE = "Pencere"
    BILINMEYEN = "Bilinmeyen"

    @property
    def kisa_kod(self) -> str:
        return {
            ElemanTipi.KOLON: "S",
            ElemanTipi.PERDE: "P",
            ElemanTipi.KIRIS: "K",
            ElemanTipi.DOSEME: "D",
            ElemanTipi.MERDIVEN: "M",
            ElemanTipi.BOSLUK: "B",
            ElemanTipi.KAPI: "KA",
            ElemanTipi.PENCERE: "PN",
            ElemanTipi.BILINMEYEN: "X",
        }[self]


@dataclass(frozen=True)
class Nokta:
    """Duzlemsel nokta (metre)."""

    x: float
    y: float

    def __iter__(self):
        yield self.x
        yield self.y

    def mesafe(self, other: "Nokta") -> float:
        return math.hypot(self.x - other.x, self.y - other.y)

    def yuvarla(self, basamak: int = 4) -> "Nokta":
        return Nokta(round(self.x, basamak), round(self.y, basamak))

    def __add__(self, other: "Nokta") -> "Nokta":
        return Nokta(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Nokta") -> "Nokta":
        return Nokta(self.x - other.x, self.y - other.y)

    def __mul__(self, k: float) -> "Nokta":
        return Nokta(self.x * k, self.y * k)


@dataclass
class Segment:
    """Kirik olcunun tek bir parcasi.

    Kirik olcu metrajinin ozu budur: bir elemanin uzunlugu tek bir sayi
    olarak degil, olculebilir/denetlenebilir parcalar zinciri olarak tutulur.
    """

    baslangic: Nokta
    bitis: Nokta
    aciklama: str = ""

    @property
    def uzunluk(self) -> float:
        return self.baslangic.mesafe(self.bitis)

    @property
    def aci(self) -> float:
        """Yatayla yaptigi aci (derece, 0-180)."""
        a = math.degrees(
            math.atan2(self.bitis.y - self.baslangic.y, self.bitis.x - self.baslangic.x)
        )
        return a % 180.0

    @property
    def orta(self) -> Nokta:
        return Nokta(
            (self.baslangic.x + self.bitis.x) / 2.0,
            (self.baslangic.y + self.bitis.y) / 2.0,
        )

    def olcu_metni(self) -> str:
        return (
            f"({self.baslangic.x:.2f}, {self.baslangic.y:.2f}) -> "
            f"({self.bitis.x:.2f}, {self.bitis.y:.2f}) = {self.uzunluk:.3f} m"
        )


@dataclass
class Eleman:
    """Kalip planindan tespit edilmis tek bir tasiyici eleman."""

    ad: str
    tip: ElemanTipi
    kat: str = ""
    # Kirik olcu zinciri: perde/kiris icin eksen parcalari,
    # doseme icin cevre kenarlari, kolon icin kesit kenarlari.
    segmentler: list[Segment] = field(default_factory=list)
    # Kapali cevre koordinatlari (doseme/kolon/perde plan kesiti)
    cevre: list[Nokta] = field(default_factory=list)
    # Doseme bosluklari (ic halkalar)
    bosluklar: list[list[Nokta]] = field(default_factory=list)
    # Olculer (metre): b=genislik/kalinlik, h=kesit yuksekligi, t=kalinlik,
    # H=kat/serbest yukseklik
    olculer: dict[str, float] = field(default_factory=dict)
    kaynak_katman: str = ""
    etiket_metni: str = ""
    # Tespitin ne kadar guvenilir oldugu (0-1). Dusuk olanlar rapora uyari duser.
    guven: float = 1.0
    notlar: list[str] = field(default_factory=list)
    ekstra: dict[str, Any] = field(default_factory=dict)

    @property
    def toplam_uzunluk(self) -> float:
        return sum(s.uzunluk for s in self.segmentler)

    @property
    def merkez(self) -> Nokta:
        pts = self.cevre or [s.orta for s in self.segmentler]
        if not pts:
            return Nokta(0.0, 0.0)
        return Nokta(
            sum(p.x for p in pts) / len(pts), sum(p.y for p in pts) / len(pts)
        )

    def not_ekle(self, metin: str) -> None:
        if metin not in self.notlar:
            self.notlar.append(metin)


@dataclass
class KirikOlcuSatiri:
    """Metraj cetvelinin tek satiri.

    Klasik Turk metraj cetveli duzeni:
    Poz No | Tanim | Benzer (adet) | En | Boy | Yukseklik | Alan | Hacim
    """

    poz: str
    eleman_adi: str
    tip: ElemanTipi
    tanim: str
    benzer: float = 1.0
    en: float | None = None
    boy: float | None = None
    yukseklik: float | None = None
    alan: float | None = None
    hacim: float | None = None
    kg: float | None = None  # yaklasik demir (donati) metraji, birim "kg"
    birim: str = ""
    formul: str = ""
    kat: str = ""
    # Bu satirin altinda gosterilecek kirik olcu parcalari
    detay: list[str] = field(default_factory=list)
    dusum_mu: bool = False

    @property
    def miktar(self) -> float:
        if self.birim == "adet":
            return self.benzer
        if self.kg is not None:
            return self.kg
        if self.hacim is not None:
            return self.hacim
        if self.alan is not None:
            return self.alan
        if self.boy is not None:
            return self.boy
        return 0.0


@dataclass
class MetrajSonucu:
    """Bir kalip planinin tam metraj ciktisi."""

    kat: str = ""
    kaynak_dosya: str = ""
    elemanlar: list[Eleman] = field(default_factory=list)
    satirlar: list[KirikOlcuSatiri] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)
    parametreler: dict[str, Any] = field(default_factory=dict)

    def tipe_gore(self, tip: ElemanTipi) -> list[Eleman]:
        return [e for e in self.elemanlar if e.tip == tip]

    def satirlar_tipe_gore(self, tip: ElemanTipi) -> list[KirikOlcuSatiri]:
        return [s for s in self.satirlar if s.tip == tip]

    def ozet(self) -> dict[str, dict[str, float]]:
        """Tip bazinda beton (m3) / kalip (m2) / demir (kg) / adet ozeti."""
        out: dict[str, dict[str, float]] = {}
        for satir in self.satirlar:
            kutu = out.setdefault(
                satir.tip.value,
                {"adet": 0.0, "beton_m3": 0.0, "kalip_m2": 0.0, "demir_kg": 0.0},
            )
            isaret = -1.0 if satir.dusum_mu else 1.0
            if satir.birim == "m3":
                kutu["beton_m3"] += isaret * (satir.hacim or 0.0)
            elif satir.birim == "m2":
                kutu["kalip_m2"] += isaret * (satir.alan or 0.0)
            elif satir.birim == "kg":
                kutu["demir_kg"] += isaret * (satir.kg or 0.0)
        for tip in ElemanTipi:
            elemanlar = self.tipe_gore(tip)
            if elemanlar:
                out.setdefault(
                    tip.value,
                    {"adet": 0.0, "beton_m3": 0.0, "kalip_m2": 0.0, "demir_kg": 0.0},
                )["adet"] = float(len(elemanlar))
        return out

    def uyari_ekle(self, metin: str) -> None:
        if metin not in self.uyarilar:
            self.uyarilar.append(metin)


@dataclass
class HamVarlik:
    """Okuyuculardan gelen normalize edilmis cizim varligi.

    DXF ve PDF okuyucular ciktilarini bu ortak tipe indirger; tespit
    algoritmalari kaynak formatindan bagimsiz calisir.
    """

    tur: str  # "cizgi" | "poligon" | "yay" | "daire" | "metin" | "tarama"
    katman: str = ""
    noktalar: list[Nokta] = field(default_factory=list)
    kapali: bool = False
    metin: str = ""
    yazi_yuksekligi: float = 0.0
    renk: str = ""
    kalinlik: float = 0.0
    ekstra: dict[str, Any] = field(default_factory=dict)

    @property
    def uzunluk(self) -> float:
        return sum(
            self.noktalar[i].mesafe(self.noktalar[i + 1])
            for i in range(len(self.noktalar) - 1)
        )


@dataclass
class Cizim:
    """Okunmus bir kalip plani paftasi."""

    varliklar: list[HamVarlik] = field(default_factory=list)
    kaynak: str = ""
    birim: str = "m"
    olcek: float = 1.0
    notlar: list[str] = field(default_factory=list)
    # Okuyucunun tespit asamasina aktardigi ozel bilgiler
    nitelikler: dict[str, Any] = field(default_factory=dict)

    def katmanlar(self) -> dict[str, int]:
        sayac: dict[str, int] = {}
        for v in self.varliklar:
            sayac[v.katman] = sayac.get(v.katman, 0) + 1
        return dict(sorted(sayac.items(), key=lambda kv: -kv[1]))

    def katmanda(self, katmanlar: Iterable[str]) -> list[HamVarlik]:
        kume = {k.upper() for k in katmanlar}
        return [v for v in self.varliklar if v.katman.upper() in kume]

    def metinler(self) -> list[HamVarlik]:
        return [v for v in self.varliklar if v.tur == "metin" and v.metin.strip()]

    def sinirlar(self) -> tuple[float, float, float, float]:
        xs: list[float] = []
        ys: list[float] = []
        for v in self.varliklar:
            for p in v.noktalar:
                xs.append(p.x)
                ys.append(p.y)
        if not xs:
            return (0.0, 0.0, 0.0, 0.0)
        return (min(xs), min(ys), max(xs), max(ys))


def noktalari_donustur(
    ham: Sequence[Sequence[float]], carpan: float = 1.0
) -> list[Nokta]:
    """(x, y[, z]) dizisini metre cinsinden Nokta listesine cevirir."""
    return [Nokta(float(p[0]) * carpan, float(p[1]) * carpan) for p in ham]
