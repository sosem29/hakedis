"""CLI alt komutlari (katmanlar, config-yaz, ornek, dogrula, pdf-incele,
mahal, maliyet, toplu) uctan uca testleri."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hakedis.cli import main

from ornek.ornek_plan_uret import uret  # noqa: E402
from tests.yardimci import kalip_plani_pdf  # noqa: E402


@pytest.fixture(scope="module")
def plan(tmp_path_factory) -> Path:
    return uret(tmp_path_factory.mktemp("cli") / "kalip_plani.dxf")


@pytest.fixture(scope="module")
def pdf(tmp_path_factory) -> Path:
    return kalip_plani_pdf(tmp_path_factory.mktemp("cli") / "plan.pdf")


@pytest.fixture(scope="module")
def mahal_plani(tmp_path_factory) -> Path:
    from tests.test_mahal import _mahal_plani

    return _mahal_plani(tmp_path_factory.mktemp("cli") / "mahal.dxf")


def run(args):
    try:
        return main(args)
    except SystemExit as e:  # optparse/argparse hatalari
        return e.code or 1


class TestKatmanlar:
    def test_katmanlari_listeler(self, plan, capsys):
        assert run(["katmanlar", str(plan)]) == 0
        out = capsys.readouterr().out
        assert "KATMAN" in out and "KOLON" in out and "ESLESTIGI TIP" in out
        assert "kolon" in out.lower()

    def test_eslenmeyen_uyari(self, tmp_path, capsys):
        import ezdxf

        hedef = tmp_path / "yabanci.dxf"
        doc = ezdxf.new("R2013")
        doc.header["$INSUNITS"] = 5
        msp = doc.modelspace()
        msp.add_lwpolyline([(0, 0), (100, 0), (100, 50), (0, 50)], close=True,
                           dxfattribs={"layer": "GIZEGELMEYEN"})
        doc.saveas(str(hedef))
        run(["katmanlar", str(hedef)])
        out = capsys.readouterr().out
        assert "ESLESMEDI" in out


class TestConfigYaz:
    def test_yazar_ve_ustune_yazma_kontrolu(self, tmp_path, capsys):
        hedef = tmp_path / "ofis.yml"
        assert run(["config-yaz", "--cikti", str(hedef)]) == 0
        assert hedef.exists()
        # ustune yazmadan tekrar deneme -> hata (kod 1)
        assert run(["config-yaz", "--cikti", str(hedef)]) == 1
        # --ustune-yaz ile basarili
        assert run(["config-yaz", "--cikti", str(hedef), "--ustune-yaz"]) == 0

    def test_varsayilan_cikti(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        assert run(["config-yaz"]) == 0
        assert (tmp_path / "hakedis.yml").exists()


class TestOrnek:
    def test_ornek_plan_uretir(self, tmp_path):
        hedef = tmp_path / "ornek.dxf"
        assert run(["ornek", str(hedef)]) == 0
        assert hedef.exists()


class TestDogrula:
    def test_kurulum_testi(self, capsys):
        assert run(["dogrula"]) == 0
        out = capsys.readouterr().out
        assert "ezdxf" in out


class TestPdfIncele:
    def test_bilgi_dokumleri(self, pdf, capsys):
        assert run(["pdf-incele", str(pdf)]) == 0
        out = capsys.readouterr().out
        assert "Sayfa" in out and "RENK" in out and "kolon" in out.lower()


class TestMahalKomutu:
    def test_odalari_listeler(self, mahal_plani, capsys):
        assert run(["mahal", str(mahal_plani)]) == 0
        out = capsys.readouterr().out
        assert "oda" in out.lower() and "MUTFAK" in out and "SALON" in out

    def test_ayrintili_satirlar(self, mahal_plani, capsys):
        run(["mahal", str(mahal_plani), "--ayrintili"])
        out = capsys.readouterr().out
        assert "Uretilecek satirlar" in out


class TestMaliyet:
    def test_metraj_json_sonrasi_maliyet(self, plan, tmp_path, capsys):
        mj = tmp_path / "m.json"
        assert run(["metraj", str(plan), "--json", str(mj), "--svg-yok"]) == 0
        # maliyet aktif olmadan JSON'da maliyet anahtari yoktur
        veri = __import__("json").loads(mj.read_text(encoding="utf-8"))
        assert "satirlar" in veri
        # maliyet komutu calisir (fiyatlar ornek)
        assert run(["maliyet", str(mj)]) == 0
        out = capsys.readouterr().out
        assert "ARA TOPLAM" in out or "GENEL TOPLAM" in out


class TestTopluCli:
    def test_coklu_dosya(self, plan, tmp_path, capsys):
        cikti = tmp_path / "toplu.xlsx"
        assert (
            run(
                [
                    "toplu",
                    str(plan),
                    str(plan),
                    "--kat-adlari",
                    "Giris",
                    "1. Kat",
                    "--cikti",
                    str(cikti),
                ]
            )
            == 0
        )
        assert cikti.exists()
        out = capsys.readouterr().out
        assert "TOPLU" in out

    def test_paftalar_pdf(self, pdf, tmp_path, capsys):
        cikti = tmp_path / "toplu2.xlsx"
        kod = run(
            [
                "toplu",
                str(pdf),
                "--paftalar",
                "1:Giris",
                "--cikti",
                str(cikti),
            ]
        )
        assert kod in (0, 2)  # pafta deseni PDF icinde bulunamayabilir ama cokmemeli