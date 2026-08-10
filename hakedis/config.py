"""Yapilandirma yukleme ve birim donusumu."""

from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

VARSAYILAN_YOL = Path(__file__).parent / "data" / "varsayilan.yml"

# Metreye cevirme carpanlari
BIRIM_CARPANI: dict[str, float] = {
    "mm": 0.001,
    "cm": 0.01,
    "dm": 0.1,
    "m": 1.0,
    "in": 0.0254,
    "ft": 0.3048,
    "inch": 0.0254,
    "feet": 0.3048,
}

# DXF $INSUNITS kodlari -> birim adi
DXF_INSUNITS: dict[int, str] = {
    0: "",  # tanimsiz
    1: "in",
    2: "ft",
    4: "mm",
    5: "cm",
    6: "m",
    8: "in",  # microinch benzeri nadir kodlar icin guvenli varsayilan degil
}


def birim_carpani(birim: str) -> float:
    b = (birim or "").strip().lower()
    if b not in BIRIM_CARPANI:
        raise ValueError(
            f"Bilinmeyen birim: {birim!r}. Gecerli degerler: {', '.join(BIRIM_CARPANI)}"
        )
    return BIRIM_CARPANI[b]


def _derin_birlestir(temel: dict, ustune: dict) -> dict:
    out = copy.deepcopy(temel)
    for k, v in (ustune or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _derin_birlestir(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


@dataclass
class Ayarlar:
    """Yapilandirmanin tipli sarmalayicisi."""

    ham: dict[str, Any] = field(default_factory=dict)

    # -- erisimciler ---------------------------------------------------------
    def al(self, yol: str, varsayilan: Any = None) -> Any:
        """Noktali yol ile deger okur: al('kat.kat_yuksekligi')."""
        dugum: Any = self.ham
        for parca in yol.split("."):
            if not isinstance(dugum, dict) or parca not in dugum:
                return varsayilan
            dugum = dugum[parca]
        return dugum

    @property
    def birim(self) -> str:
        return str(self.al("birim", "cm"))

    @property
    def kat_yuksekligi(self) -> float:
        return float(self.al("kat.kat_yuksekligi", 3.0))

    @property
    def doseme_kalinligi(self) -> float:
        return float(self.al("kat.doseme_kalinligi", 0.15))

    @property
    def kat_adi(self) -> str:
        return str(self.al("kat.ad", ""))

    @property
    def yuvarlama(self) -> int:
        return int(self.al("metraj.yuvarlama", 3))

    def poz(self, anahtar: str) -> str:
        return str(self.al(f"pozlar.{anahtar}", ""))

    # -- katman esleme -------------------------------------------------------
    def katman_desenleri(self, tip: str) -> list[re.Pattern[str]]:
        desenler = list(self.al(f"katmanlar.{tip}", []) or [])
        if self.al("sta4cad.aktif", False):
            desenler += list(self.al(f"sta4cad.katmanlar.{tip}", []) or [])
        return [re.compile(d, re.IGNORECASE) for d in desenler]

    def katman_tipi(self, katman: str) -> str | None:
        """Katman adindan eleman tipi cikarir. Eslesme yoksa None."""
        ad = (katman or "").strip()
        if not ad:
            return None
        # Kesin (exact) esleme once uygulanir: kullanici arayuzden bir katmani
        # acikca hangi tipe bagladiysa desen eslemelerinden once gecerlidir.
        kesin = self.al("katmanlar.kesin", {}) or {}
        for katman_adi, tip in kesin.items():
            if str(katman_adi).upper() == ad.upper():
                tip = str(tip)
                if tip == "sezgisel":
                    return None
                return tip
        for desen in self.katman_desenleri("yoksay"):
            if desen.search(ad):
                return "yoksay"
        # Uzun/ozgul tipler once denenmeli: bosluk, dosemeden once gelmeli
        for tip in (
            "bosluk",
            "merdiven",
            "kolon",
            "perde",
            "kiris",
            "doseme",
            "duvar",
            "kapi",
            "pencere",
            "metin",
            "temel",
        ):
            for desen in self.katman_desenleri(tip):
                if desen.search(ad):
                    if tip == "temel" and not self.al("sta4cad.temel_doseme", True):
                        return None
                    return "doseme" if tip == "temel" else tip
        return None

    def guncelle(self, **kwargs: Any) -> "Ayarlar":
        """CLI'dan gelen ezmeleri uygular (None olanlar yok sayilir)."""
        ust: dict[str, Any] = {}
        eslesme = {
            "birim": ("birim",),
            "kat_adi": ("kat", "ad"),
            "kat_yuksekligi": ("kat", "kat_yuksekligi"),
            "doseme_kalinligi": ("kat", "doseme_kalinligi"),
            "olcek": ("pdf", "olcek"),
            "sayfa": ("pdf", "sayfa"),
        }
        for anahtar, deger in kwargs.items():
            if deger is None or anahtar not in eslesme:
                continue
            yol = eslesme[anahtar]
            dugum = ust
            for parca in yol[:-1]:
                dugum = dugum.setdefault(parca, {})
            dugum[yol[-1]] = deger
        return Ayarlar(_derin_birlestir(self.ham, ust))


def varsayilan_ayarlar() -> Ayarlar:
    with open(VARSAYILAN_YOL, "r", encoding="utf-8") as f:
        return Ayarlar(yaml.safe_load(f) or {})


def ayarlari_yukle(yol: str | Path | None = None) -> Ayarlar:
    """Varsayilan ayarlari yukler, verilmisse kullanici dosyasini ustune biner."""
    temel = varsayilan_ayarlar()
    if yol is None:
        return temel
    p = Path(yol)
    if not p.exists():
        raise FileNotFoundError(f"Yapilandirma dosyasi bulunamadi: {p}")
    with open(p, "r", encoding="utf-8") as f:
        kullanici = yaml.safe_load(f) or {}
    return Ayarlar(_derin_birlestir(temel.ham, kullanici))


def ayarlari_yaml_metinden(metin: str) -> Ayarlar:
    """YAML metnini varsayilanlarin ustune bindirir (web arayuzu icin)."""
    temel = varsayilan_ayarlar()
    kullanici = yaml.safe_load(metin or "") or {}
    return Ayarlar(_derin_birlestir(temel.ham, kullanici))


def ayarlari_json_ile(veri: dict | None) -> Ayarlar:
    """JSON sozlugunu varsayilanlarin ustune bindirir (web arayuzu icin)."""
    temel = varsayilan_ayarlar()
    return Ayarlar(_derin_birlestir(temel.ham, veri or {}))


def olcegi_coz(deger: Any) -> float:
    """'1/50', '1:50', 50 -> 50.0 seklinde olcek paydasi dondurur."""
    if deger is None:
        raise ValueError("Olcek belirtilmedi")
    if isinstance(deger, (int, float)):
        return float(deger)
    metin = str(deger).strip()
    m = re.match(r"^\s*1\s*[/:]\s*(\d+(?:[.,]\d+)?)\s*$", metin)
    if m:
        return float(m.group(1).replace(",", "."))
    m = re.match(r"^\s*(\d+(?:[.,]\d+)?)\s*$", metin)
    if m:
        return float(m.group(1).replace(",", "."))
    raise ValueError(f"Olcek cozulemedi: {deger!r}. Ornek: '1/50' veya 50")
