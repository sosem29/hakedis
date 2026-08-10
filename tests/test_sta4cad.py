"""Sta4CAD kalip/temel plani (DXF/DWG) profili testleri."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hakedis.config import ayarlari_yukle
from hakedis.metraj import plandan_metraj


def _sta4cad_plani(hedef: Path) -> Path:
    """Sta4CAD tarzi katmanlarla sentetik kalip/temel plani.

    Katmanlar: Kolonlar, Kirişler, Döşeme, Temel. "Temel" yalnizca Sta4CAD
    profili aktifken doseme (plak) sayilir.
    """
    import ezdxf

    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 5
    msp = doc.modelspace()
    for ad in ("Kolonlar", "Kirişler", "Döşeme", "Temel"):
        if ad not in doc.layers:
            doc.layers.add(ad, color=3)

    for i in range(3):
        msp.add_lwpolyline(
            [(i * 500, 0), (i * 500 + 40, 0), (i * 500 + 40, 60), (i * 500, 60)],
            close=True,
            dxfattribs={"layer": "Kolonlar"},
        )
    msp.add_lwpolyline(
        [(100, 100), (1400, 100), (1400, 140), (100, 140)],
        close=True,
        dxfattribs={"layer": "Kirişler"},
    )
    msp.add_lwpolyline(
        [(0, 0), (1500, 0), (1500, 800), (0, 800)],
        close=True,
        dxfattribs={"layer": "Döşeme"},
    )
    msp.add_lwpolyline(
        [(0, -300), (1500, -300), (1500, -150), (0, -150)],
        close=True,
        dxfattribs={"layer": "Temel"},
    )
    doc.saveas(hedef)
    return hedef


@pytest.fixture(scope="module")
def sta4cad_plani(tmp_path_factory) -> Path:
    return _sta4cad_plani(tmp_path_factory.mktemp("sta4cad") / "kalip.dxf")


class TestKatmanEsleme:
    def test_profil_kapaliyken_temel_eslenmez(self):
        ayarlar = ayarlari_yukle()
        assert ayarlar.katman_tipi("Temel") is None
        assert ayarlar.katman_tipi("Tabliye") is None

    def test_profil_aktifken_temel_doseme_sayilir(self):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["sta4cad"]["aktif"] = True
        assert ayarlar.katman_tipi("Temel") == "doseme"

    def test_profil_aktifken_sta4cad_desenleri(self):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["sta4cad"]["aktif"] = True
        assert ayarlar.katman_tipi("Tabliye") == "doseme"
        assert ayarlar.katman_tipi("Sahanlık") == "merdiven"
        assert ayarlar.katman_tipi("Kirişler") == "kiris"

    def test_temel_doseme_kapaliysa_temel_yok_sayilir(self):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["sta4cad"]["aktif"] = True
        ayarlar.ham["sta4cad"]["temel_doseme"] = False
        assert ayarlar.katman_tipi("Temel") is None


class TestUctanUca:
    def test_profil_kapaliyken_temel_plani_metraja_girmez(self, sta4cad_plani):
        ayarlar = ayarlari_yukle()
        sonuc, _ = plandan_metraj(str(sta4cad_plani), ayarlar)
        doseme_adet = sonuc.ozet().get("Doseme", {}).get("adet", 0)
        assert doseme_adet == 1  # yalnizca "Doseme" katmani

    def test_profil_aktifken_temel_doseme_olarak_olculur(self, sta4cad_plani):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["sta4cad"]["aktif"] = True
        sonuc, _ = plandan_metraj(str(sta4cad_plani), ayarlar)
        doseme = sonuc.ozet()["Doseme"]
        assert doseme["adet"] == 2  # Doseme + Temel

        # Temel plagi: 15.0 x 1.5 m x 0.15 m = 3.375 m3
        # Doseme: 15.0 x 8.0 m x 0.15 m = 18.0 m3
        # (kolon/kiris dusumleri ihmal)
        assert doseme["beton_m3"] == pytest.approx(18.0 + 3.375, abs=0.2)

    def test_profil_aktifken_kolonlar_algilanir(self, sta4cad_plani):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["sta4cad"]["aktif"] = True
        sonuc, _ = plandan_metraj(str(sta4cad_plani), ayarlar)
        assert sonuc.ozet()["Kolon"]["adet"] == 3
        assert sonuc.ozet()["Kiris"]["adet"] == 1
