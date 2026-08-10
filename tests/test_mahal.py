"""Mahal (oda) planindan kaplama/tesviye/siva metraji testleri."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hakedis.config import ayarlari_yukle
from hakedis.mahal import (
    _kapali_poligonlar,
    _kaplama_turu,
    mahal_duvar_yuksekligi,
    mahal_satirlari,
    mahalleri_oku,
)
from hakedis.metraj import plandan_metraj


def _mahal_plani(hedef: Path) -> Path:
    """Iki odali sentetik mahal plani: MUTFAK (seramik) + SALON (parke)."""
    import ezdxf

    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 5
    msp = doc.modelspace()
    for ad in ("MAHAL", "ODA_ADI"):
        if ad not in doc.layers:
            doc.layers.add(ad, color=3)

    msp.add_lwpolyline(
        [(0, 0), (400, 0), (400, 300), (0, 300)],
        close=True,
        dxfattribs={"layer": "MAHAL"},
    )
    msp.add_lwpolyline(
        [(400, 0), (900, 0), (900, 500), (400, 500)],
        close=True,
        dxfattribs={"layer": "MAHAL"},
    )
    msp.add_text("MUTFAK", height=30, dxfattribs={"layer": "ODA_ADI"}).set_placement(
        (150, 140)
    )
    msp.add_text("SALON", height=30, dxfattribs={"layer": "ODA_ADI"}).set_placement(
        (600, 250)
    )
    doc.saveas(hedef)
    return hedef


@pytest.fixture(scope="module")
def mahal_plani(tmp_path_factory) -> Path:
    return _mahal_plani(tmp_path_factory.mktemp("mahal") / "mahal.dxf")


class TestMahalOkuma:
    def test_odalar_tespit_edilir(self, mahal_plani):
        m, uyarilar = mahalleri_oku(str(mahal_plani), ayarlari_yukle())
        assert not uyarilar
        assert len(m) == 2

        by_ad = {x.ad: x for x in m}
        assert by_ad["MUTFAK"].alan == pytest.approx(12.0)
        assert by_ad["MUTFAK"].cevre == pytest.approx(14.0)
        assert by_ad["SALON"].alan == pytest.approx(25.0)
        assert by_ad["SALON"].cevre == pytest.approx(20.0)

    def test_kaplama_turu_eslemesi(self, mahal_plani):
        m, _ = mahalleri_oku(str(mahal_plani), ayarlari_yukle())
        by_ad = {x.ad: x for x in m}
        assert by_ad["MUTFAK"].tip == "seramik"
        assert by_ad["SALON"].tip == "parke"

    def test_kucuk_poligonlar_elenir(self, mahal_plani):
        a = ayarlari_yukle()
        a.ham["mahal"] = {"aktif": True, "min_alan": 20.0}
        m, _ = mahalleri_oku(str(mahal_plani), a)
        assert [x.ad for x in m] == ["SALON"]


class TestMahalSatirlari:
    def test_kaplama_poz_bazinda_toplanir(self, mahal_plani):
        a = ayarlari_yukle()
        m, _ = mahalleri_oku(str(mahal_plani), a)
        satirlar = mahal_satirlari(m, a)
        pozlar = {s.eleman_adi: s for s in satirlar}

        assert sum(s.alan for s in satirlar if s.eleman_adi == "KAPLAMA") == pytest.approx(37.0)
        assert pozlar["TESVIYE"].alan == pytest.approx(37.0)

    def test_kaplama_cinsler_ayri_satir(self, mahal_plani):
        a = ayarlari_yukle()
        m, _ = mahalleri_oku(str(mahal_plani), a)
        # seramik (mutfak 12) ve parke (salon 25) ayri satirlar olmali
        a.ham["kaplama"] = {
            "aktif": True,
            "seramik_poz": "23.062/S",
            "parke_poz": "23.063",
            "tesviye_poz": "23.062/T",
        }
        satirlar = mahal_satirlari(m, a)
        kap = [s for s in satirlar if s.eleman_adi == "KAPLAMA"]
        assert len(kap) == 2
        seramik = next(s for s in kap if "Seramik" in s.tanim)
        parke = next(s for s in kap if "Parke" in s.tanim)
        assert seramik.alan == pytest.approx(12.0)
        assert parke.alan == pytest.approx(25.0)

    def test_siva_ve_tavan_aktifken_uretilir(self, mahal_plani):
        a = ayarlari_yukle()
        a.ham["siva"] = {"aktif": True}
        m, _ = mahalleri_oku(str(mahal_plani), a)
        satirlar = mahal_satirlari(m, a)
        eleman = {s.eleman_adi: s for s in satirlar}
        assert eleman["SIVA"].alan == pytest.approx((14.0 + 20.0) * 3.0)
        assert eleman["TAVAN"].alan == pytest.approx(37.0)

    def test_siva_kapaliysa_uretilmez(self, mahal_plani):
        a = ayarlari_yukle()
        a.ham["siva"] = {"aktif": False}
        m, _ = mahalleri_oku(str(mahal_plani), a)
        satirlar = mahal_satirlari(m, a)
        assert all(s.eleman_adi != "SIVA" for s in satirlar)

    def test_duvar_yuksekligi_kattan_alinir(self):
        a = ayarlari_yukle()
        a.ham["kat"] = {"kat_yuksekligi": 3.2}
        assert mahal_duvar_yuksekligi(a) == pytest.approx(3.2)

    def test_duvar_yuksekligi_ozel_deger(self):
        a = ayarlari_yukle()
        a.ham["mahal"] = {"aktif": True, "duvar_yuksekligi": 2.8}
        assert mahal_duvar_yuksekligi(a) == pytest.approx(2.8)

    def test_ozel_duvar_yuksekligi_sivaya_yansir(self, mahal_plani):
        a = ayarlari_yukle()
        a.ham["siva"] = {"aktif": True}
        a.ham["mahal"] = {"aktif": True, "duvar_yuksekligi": 2.5}
        m, _ = mahalleri_oku(str(mahal_plani), a)
        siva = next(s for s in mahal_satirlari(m, a) if s.eleman_adi == "SIVA")
        assert siva.alan == pytest.approx((14.0 + 20.0) * 2.5)


class TestEntegrasyon:
    def test_plandan_metraj_mahal_dosyasi_ile(self, mahal_plani):
        import ezdxf

        plan = mahal_plani.parent / "kalip.dxf"
        doc = ezdxf.new("R2013", setup=True)
        doc.header["$INSUNITS"] = 5
        msp = doc.modelspace()
        if "DOSEME" not in doc.layers:
            doc.layers.add("DOSEME", color=3)
        msp.add_lwpolyline(
            [(0, 0), (900, 0), (900, 500), (0, 500)],
            close=True,
            dxfattribs={"layer": "DOSEME"},
        )
        doc.saveas(plan)

        a = ayarlari_yukle()
        a.ham["siva"] = {"aktif": True}
        a.ham["kaplama"] = {"aktif": True}
        sonuc, _ = plandan_metraj(str(plan), a, mahal_dosya=str(mahal_plani))

        eleman = {s.eleman_adi: s for s in sonuc.satirlar}
        assert sum(s.alan for s in sonuc.satirlar if s.eleman_adi == "KAPLAMA") == pytest.approx(37.0)
        assert eleman["TESVIYE"].alan == pytest.approx(37.0)
        assert eleman["SIVA"].alan == pytest.approx(102.0)
        assert sonuc.parametreler["mahal"]["adet"] == 2
        assert any("MAHAL PLANINDAN" in u for u in sonuc.uyarilar)

    def test_plandan_metraj_mahalsiz_uyari_yok(self):
        import ezdxf

        plan = Path(__file__).parent / "tmp_kalip.dxf"
        try:
            doc = ezdxf.new("R2013", setup=True)
            doc.header["$INSUNITS"] = 5
            msp = doc.modelspace()
            if "DOSEME" not in doc.layers:
                doc.layers.add("DOSEME", color=3)
            msp.add_lwpolyline(
                [(0, 0), (900, 0), (900, 500), (0, 500)],
                close=True,
                dxfattribs={"layer": "DOSEME"},
            )
            doc.saveas(plan)
            a = ayarlari_yukle()
            a.ham["kaplama"] = {"aktif": True}
            sonuc, _ = plandan_metraj(str(plan), a)
            assert "mahal" not in sonuc.parametreler
            assert any("YAKLASIK" in u for u in sonuc.uyarilar)
        finally:
            if plan.exists():
                plan.unlink()
