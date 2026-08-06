"""Asmolen (guseli) plan tanima ve kirpilmis DWG/DXF korumasi testleri."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hakedis.config import ayarlari_yukle
from hakedis.metraj import plandan_metraj
from hakedis.model import ElemanTipi
from hakedis.readers.pdf import _donati_etiketi_mi, _sta4cad_tespit_esleme
from tests.yardimci import basit_pdf_yaz


def asmolen_plani_pdf(hedef: Path) -> Path:
    """1 pt = 1 cm; guseli plani andiran vektor PDF uretir.

    Gri buyuk dikdortgen = doseme, kirmizi 30x60 dikdortgenler = gurultulu
    kolon adaylari, cok sayida kisa kirmizi cizgi = asmolen blok deseni.
    """
    parcalar: list[str] = []

    # Doseme: gri kapali dikdortgen 350x250 pt = 3.5 x 2.5 m
    parcalar.append("0.6 0.6 0.6 RG 0.5 w")
    parcalar.append("50 50 350 250 re S")

    # Kolon adaylari: kirmizi 30x60 pt (0.30 x 0.60 m)
    parcalar.append("1 0 0 RG 1.5 w")
    for x in (120, 260):
        for y in (80, 180):
            parcalar.append(f"{x} {y} 30 60 re S")

    # Asmolen blok deseni: kisa kirmizi cizgiler (5 pt, esigin altinda)
    for i in range(60):
        x = 60 + (i % 12) * 20
        y = 70 + (i // 12) * 15
        parcalar.append(f"1 0 0 RG 0.5 w")
        parcalar.append(f"{x} {y} m {x + 5} {y} l S")

    return basit_pdf_yaz(hedef, "\n".join(parcalar))


@pytest.fixture
def asmolen_ayarlari():
    ayarlar = ayarlari_yukle()
    ayarlar.ham["pdf"]["kalibrasyon"] = {"pdf_mesafe": 1.0, "gercek_mesafe": 0.01}
    ayarlar.ham["pdf"].pop("renk_esleme", None)
    return ayarlar


class TestAsmolenTespitBirimi:
    def test_yogun_desen_yoksayma_eslemesi_uretir(self):
        ayarlar = ayarlari_yukle()
        esleme = _sta4cad_tespit_esleme({}, kisa_cizgi=80, toplam_cizgi=100, ayarlar=ayarlar)
        assert esleme.get("#ff0000") == "yoksay"

    def test_esik_altinda_esleme_degismez(self):
        ayarlar = ayarlari_yukle()
        esleme = _sta4cad_tespit_esleme({}, kisa_cizgi=10, toplam_cizgi=100, ayarlar=ayarlar)
        assert esleme == {}

    def test_kullanici_eslemesi_varken_dokunulmaz(self):
        ayarlar = ayarlari_yukle()
        kullanici = {"#ff0000": "kolon"}
        esleme = _sta4cad_tespit_esleme(kullanici, 80, 100, ayarlar)
        assert esleme["#ff0000"] == "kolon"
        assert esleme.get("#269900") == "yoksay"

    def test_otomatik_kapaliyken_dokunulmaz(self):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["pdf"]["sta4cad_otomatik"] = False
        esleme = _sta4cad_tespit_esleme({}, 80, 100, ayarlar)
        assert esleme == {}


class TestDonatiEtiketi:
    def test_donati_isaretleri_taninir(self):
        for metin in ("ƒ8/20", "∅8/20", "#8/20", "l=4.50", "4ƒ14"):
            assert _donati_etiketi_mi(metin), metin

    def test_donati_olmayanlar_elenir(self):
        for metin in ("S01", "K101 25/50", "TD=15", "Kolon"):
            assert not _donati_etiketi_mi(metin), metin


class TestAsmolenUctanUca:
    def test_yalnizca_doseme_metraji_uretilir(self, tmp_path, asmolen_ayarlari):
        pdf = asmolen_plani_pdf(tmp_path / "asmolen.pdf")
        sonuc, cizim = plandan_metraj(str(pdf), asmolen_ayarlari)

        assert sonuc.tipe_gore(ElemanTipi.KOLON) == []
        assert sonuc.tipe_gore(ElemanTipi.PERDE) == []
        dosemeler = sonuc.tipe_gore(ElemanTipi.DOSEME)
        assert len(dosemeler) == 1
        assert dosemeler[0].olculer["net_alan"] == pytest.approx(8.75, abs=0.02)

    def test_asmolen_niteligi_isaretlenir(self, tmp_path, asmolen_ayarlari):
        pdf = asmolen_plani_pdf(tmp_path / "asmolen2.pdf")
        _, cizim = plandan_metraj(str(pdf), asmolen_ayarlari)
        assert cizim.nitelikler.get("asmolen") is True
        assert cizim.nitelikler.get("asmolen_sadece_doseme") is True

    def test_yalnizca_doseme_uyarisi_eklenir(self, tmp_path, asmolen_ayarlari):
        pdf = asmolen_plani_pdf(tmp_path / "asmolen3.pdf")
        sonuc, cizim = plandan_metraj(str(pdf), asmolen_ayarlari)
        assert any("yalnizca doseme" in u for u in sonuc.uyarilar)
        assert any("algilandi" in n for n in cizim.notlar)


class TestKirpilmisDxfKorumasi:
    def test_kucuk_plan_hata_verir(self, tmp_path):
        import ezdxf

        doc = ezdxf.new("R2013")
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (0.4, 0), (0.4, 0.4), (0, 0.4)], close=True)
        yol = tmp_path / "kucuk.dxf"
        doc.saveas(str(yol))
        with pytest.raises(ValueError, match="kirpilmis"):
            plandan_metraj(str(yol), ayarlari_yukle())

    def test_kucuk_plan_kontrol_kapaliyken_okunur(self, tmp_path):
        import ezdxf

        doc = ezdxf.new("R2013")
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (0.4, 0), (0.4, 0.4), (0, 0.4)], close=True)
        yol = tmp_path / "kucuk2.dxf"
        doc.saveas(str(yol))
        ayarlar = ayarlari_yukle()
        ayarlar.ham["dxf"]["min_plan_boyutu"] = 0
        sonuc, _ = plandan_metraj(str(yol), ayarlar)
        assert len(sonuc.tipe_gore(ElemanTipi.KOLON)) == 1
