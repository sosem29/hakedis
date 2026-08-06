"""Eslestirme arayuzu testleri: kesin esleme, /api/esle-tara ve uctan-uca."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hakedis.config import ayarlari_yukle
from hakedis.metraj import plandan_metraj
from hakedis.model import ElemanTipi
from tests.yardimci import kalip_plani_pdf


class TestKesinEsleme:
    def test_kesin_desenlerden_once_uygulanir(self):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["katmanlar"]["kesin"] = {"KOLON-X": "kiris"}
        assert ayarlar.katman_tipi("KOLON-X") == "kiris"

    def test_kesin_yoksay_regex_oncesi_gecerli(self):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["katmanlar"]["kesin"] = {"AKS-101": "kolon"}
        assert ayarlar.katman_tipi("AKS-101") == "kolon"

    def test_kesin_buyuk_kucuk_harf_duyarsiz(self):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["katmanlar"]["kesin"] = {"Duvar_P1": "perde"}
        assert ayarlar.katman_tipi("duvar_p1") == "perde"

    def test_sezgisel_degeri_eslenmemis_sayar(self):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["katmanlar"]["kesin"] = {"BELIRSIZ": "sezgisel"}
        assert ayarlar.katman_tipi("BELIRSIZ") is None

    def test_eslenmeyen_katman_hicbirine_eslesmez(self):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["katmanlar"]["kesin"] = {"KOLON-X": "kiris"}
        assert ayarlar.katman_tipi("ASDASDASD") is None


class TestEsleTaraPdf:
    def test_renk_adaylari_donulur(self, tmp_path):
        from fastapi.testclient import TestClient
        from hakedis.web.server import app

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            c = TestClient(app)
        pdf = kalip_plani_pdf(tmp_path / "plan.pdf")
        r = c.post(
            "/api/esle-tara",
            files={"dosya": ("plan.pdf", pdf.read_bytes(), "application/pdf")},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["tur"] == "renk"
        renkler = {a["anahtar"] for a in d["adaylar"]}
        assert {"#ff0000", "#0000ff", "#999999"} <= renkler
        kirmizi = next(a for a in d["adaylar"] if a["anahtar"] == "#ff0000")
        assert kirmizi["adet"] == 6
        assert kirmizi["suanki_tip"] is None

    def test_eslenmis_renk_suanki_tip_verir(self, tmp_path):
        from fastapi.testclient import TestClient
        from hakedis.web.server import app

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            c = TestClient(app)
        pdf = kalip_plani_pdf(tmp_path / "plan2.pdf")
        ayarlar = '{"pdf": {"renk_esleme": {"#ff0000": "kolon"}}}'
        r = c.post(
            "/api/esle-tara",
            files={"dosya": ("plan2.pdf", pdf.read_bytes(), "application/pdf")},
            data={"ayarlar": ayarlar},
        )
        d = r.json()
        kirmizi = next(a for a in d["adaylar"] if a["anahtar"] == "#ff0000")
        assert kirmizi["suanki_tip"] == "kolon"


class TestEsleTaraDxf:
    def test_katman_adaylari_donulur(self, tmp_path):
        import ezdxf
        from fastapi.testclient import TestClient
        from hakedis.web.server import app

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            c = TestClient(app)
        doc = ezdxf.new("R2013")
        msp = doc.modelspace()
        msp.add_lwpolyline(
            [(0, 0), (3, 0), (3, 2), (0, 2)], close=True, dxfattribs={"layer": "KOLON-1"}
        )
        msp.add_lwpolyline(
            [(0, 0), (1, 0), (1, 1), (0, 1)], close=True, dxfattribs={"layer": "AKS-10"}
        )
        dxf = tmp_path / "p.dxf"
        doc.saveas(str(dxf))

        ayarlar = '{"dxf": {"min_plan_boyutu": 0}}'
        r = c.post(
            "/api/esle-tara",
            files={"dosya": ("p.dxf", dxf.read_bytes(), "application/dxf")},
            data={"ayarlar": ayarlar},
        )
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["tur"] == "katman"
        katmanlar = {a["anahtar"]: a for a in d["adaylar"]}
        assert "KOLON-1" in katmanlar
        aks = katmanlar["AKS-10"]
        assert aks["oneri_tip"] == "yoksay"

    def test_bosluklu_dosya_adi_kabul_edilir(self):
        """'istinat.dwg 2' gibi isimlerde uzanti ilk bosluga kadardir."""
        from hakedis.web.server import _dosya_uzantisi

        assert _dosya_uzantisi("istinat.dwg 2") == ".dwg"
        assert _dosya_uzantisi("plan.dwg 2") == ".dwg"
        assert _dosya_uzantisi("plan.PDF") == ".pdf"
        assert _dosya_uzantisi("  plan.dxf  ") == ".dxf"
        assert _dosya_uzantisi("istinat") == ""


class TestUctanUcaEsleme:
    def test_pdf_renk_eslemesi_metraja_yansir(self, tmp_path):
        pdf = kalip_plani_pdf(tmp_path / "plan.pdf")
        ayarlar = ayarlari_yukle()
        ayarlar.ham["pdf"]["kalibrasyon"] = {"pdf_mesafe": 1.0, "gercek_mesafe": 0.01}
        ayarlar.ham["pdf"]["renk_esleme"] = {
            "#ff0000": "kolon",
            "#0000ff": "kiris",
            "#999999": "doseme",
        }
        sonuc, _ = plandan_metraj(str(pdf), ayarlar)
        assert len(sonuc.tipe_gore(ElemanTipi.KOLON)) == 6
        assert len(sonuc.tipe_gore(ElemanTipi.KIRIS)) == 5
        assert len(sonuc.tipe_gore(ElemanTipi.DOSEME)) == 1

    def test_dxf_kesin_esleme_metraja_yansir(self, tmp_path):
        import ezdxf

        doc = ezdxf.new("R2013")
        msp = doc.modelspace()
        msp.add_lwpolyline(
            [(0, 0), (3, 0), (3, 2), (0, 2)], close=True, dxfattribs={"layer": "DUVAR-X"}
        )
        dxf = tmp_path / "p.dxf"
        doc.saveas(str(dxf))
        ayarlar = ayarlari_yukle()
        ayarlar.ham["katmanlar"]["kesin"] = {"DUVAR-X": "kolon"}
        sonuc, _ = plandan_metraj(str(dxf), ayarlar)
        assert len(sonuc.tipe_gore(ElemanTipi.KOLON)) == 1

    def test_kismi_esleme_asmolen_bastirmasini_surdurur(self):
        """Kullanici yalnizca bir renk eslerse kirmizi desen yine yoksayilmali."""
        ayarlar = ayarlari_yukle()
        ayarlar.ham.setdefault("pdf", {})["renk_esleme"] = {"#0000ff": "doseme"}
        sonuc, cizim = plandan_metraj("veri/asmolen_klp.pdf", ayarlar)
        assert cizim.nitelikler.get("asmolen_sadece_doseme") is True
        assert sonuc.tipe_gore(ElemanTipi.KOLON) == []
        assert any("dolgu deseni algilandi" in n for n in cizim.notlar)
