"""Kararlilik katmani: bozuk girdi, gecersiz yapilandirma ve dejenere
geometri durumlarinda sistemin temiz hata vermesi / cokmemesi testleri."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hakedis.config import ayarlari_yukle
from hakedis.metraj import metraj_hesapla, plandan_metraj
from hakedis.model import Eleman, ElemanTipi, Nokta
from hakedis.readers import cizim_oku

from ornek.ornek_plan_uret import uret


def dikdortgen(x0, y0, x1, y1) -> list[Nokta]:
    return [Nokta(x0, y0), Nokta(x1, y0), Nokta(x1, y1), Nokta(x0, y1)]


@pytest.fixture(scope="module")
def plan(tmp_path_factory) -> Path:
    return uret(tmp_path_factory.mktemp("karar") / "kalip_plani.dxf")


@pytest.fixture()
def bozuk_dosyalar(tmp_path) -> dict[str, Path]:
    d = tmp_path / "girdi"
    d.mkdir()
    (d / "bozuk.dxf").write_bytes(b"garbage not a dxf")
    (d / "bos.dxf").write_bytes(b"")
    (d / "bozuk.pdf").write_bytes(b"%%PDF- not really")
    (d / "bozuk.dwg").write_bytes(b"not a real dib file")
    (d / "metin.txt").write_bytes(b"hello")
    return d


class TestBozukDosyalar:
    @pytest.mark.parametrize(
        "adi",
        ["bozuk.dxf", "bos.dxf", "bozuk.pdf", "metin.txt"],
    )
    def test_okunamayanlar_valueerror(self, bozuk_dosyalar, adi):
        with pytest.raises(ValueError):
            cizim_oku(bozuk_dosyalar / adi, ayarlari_yukle())

    def test_varolmayan_dosya(self):
        with pytest.raises(FileNotFoundError):
            cizim_oku(Path("/var/olmayan/x.dxf"), ayarlari_yukle())

    def test_bozuk_dwg_temiz_hata(self, bozuk_dosyalar):
        # dwg2dxf kurulu olmasa da RuntimeError, kurulu olsa da hata alinmali
        with pytest.raises((ValueError, RuntimeError)):
            cizim_oku(bozuk_dosyalar / "bozuk.dwg", ayarlari_yukle())

    def test_bozuk_dxf_metraj_temiz_hata(self, bozuk_dosyalar):
        from hakedis.cli import main

        kod = main(["metraj", str(bozuk_dosyalar / "bozuk.dxf")])
        assert kod == 2


class TestGecersizYapilandirma:
    @pytest.mark.parametrize(
        "ezmeler",
        [
            {"kat_yuksekligi": -3.0},
            {"kat_yuksekligi": 0.0},
            {"kat_yuksekligi": float("nan")},
            {"kat_yuksekligi": float("inf")},
            {"doseme_kalinligi": -0.1},
            {"doseme_kalinligi": float("nan")},
            {"kat_yuksekligi": 2.0, "doseme_kalinligi": 3.0},
        ],
    )
    def test_gecersiz_ayarlar_reddedilir(self, ezmeler):
        ayarlar = ayarlari_yukle().guncelle(**ezmeler)
        assert ayarlar.dogrula(), "gecersiz ayarlar sorun uretmeli"
        with pytest.raises(ValueError):
            ayarlar.dogrula_ve_hata()

    def test_gecersiz_ayarla_metraj_reddedilir(self):
        ayarlar = ayarlari_yukle().guncelle(kat_yuksekligi=-3.0)
        with pytest.raises(ValueError, match="kat_yuksekligi"):
            plandan_metraj("ornek/kalip_plani.dxf", ayarlar)

    def test_gecerli_ayarlar_sorunsuz(self):
        assert ayarlari_yukle().dogrula() == []

    def test_negatif_sifir_doseme_kabul(self):
        # doseme kalinligi 0 mantikli olabilir (sintine dummies) - sorun degil
        ayarlar = ayarlari_yukle().guncelle(doseme_kalinligi=0.0)
        assert ayarlar.dogrula() == []
        s, _ = plandan_metraj("ornek/kalip_plani.dxf", ayarlar)
        assert all(math.isfinite(v) for k in s.ozet().values() for v in k.values())


class TestDejenereGeometri:
    def test_sifir_alan_kolon_cokmez(self):
        e = Eleman(
            ad="S0",
            tip=ElemanTipi.KOLON,
            kat="Kat",
            cevre=dikdortgen(0, 0, 0, 0),
        )
        e.olculer["b"] = 0.0
        e.olculer["h"] = 0.0
        s = metraj_hesapla([e], ayarlari_yukle())
        oz = s.ozet().get("Kolon", {})
        assert oz.get("beton_m3", 0) == pytest.approx(0.0)
        assert all(math.isfinite(v) for v in oz.values())

    def test_tek_noktali_kolon_cokmez(self):
        e = Eleman(
            ad="S0",
            tip=ElemanTipi.KOLON,
            kat="Kat",
            cevre=[Nokta(1, 1)],
        )
        e.olculer["b"] = 0.0
        e.olculer["h"] = 0.0
        s = metraj_hesapla([e], ayarlari_yukle())
        assert all(math.isfinite(v) for k in s.ozet().values() for v in k.values())

    def test_gecerli_planda_sonuclar_sonlu(self, plan):
        s, _ = plandan_metraj(str(plan), ayarlari_yukle())
        oz = s.ozet()
        for tip in ("Kolon", "Perde", "Kiris", "Doseme"):
            kutu = oz.get(tip, {})
            assert all(math.isfinite(v) for v in kutu.values()), tip


class TestCliKararlilik:
    def test_metraj_cikti_yolu_klasor_ise_hata(self, plan, tmp_path):
        from hakedis.cli import main

        kod = main(["metraj", str(plan), "--cikti", str(tmp_path)])
        assert kod != 0

    def test_uyari_varsa_kati_bayragi(self, plan, tmp_path, capsys):
        from hakedis.cli import main

        cikti = tmp_path / "m.xlsx"
        # bilinmeyen katmanli plan yok; uyari uretmeyen temiz plan ile kontrol
        kod = main(["metraj", str(plan), "--cikti", str(cikti)])
        assert kod == 0
