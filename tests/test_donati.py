"""Donati (demir) planindan cap/adet/aralik okuyup kg metraji testleri."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hakedis.config import ayarlari_yukle
from hakedis.donati import (
    DonatiKalem,
    donati_kg,
    donati_kalemleri,
    donati_okumalari,
    donati_satirlari,
)
from hakedis.metraj import plandan_metraj
from hakedis.model import Eleman, ElemanTipi, HamVarlik, Nokta

from ornek.ornek_plan_uret import uret


def dikdortgen(x0, y0, x1, y1) -> list[Nokta]:
    return [Nokta(x0, y0), Nokta(x1, y0), Nokta(x1, y1), Nokta(x0, y1)]


def _kolon_elemani() -> Eleman:
    e = Eleman(
        ad="S01",
        tip=ElemanTipi.KOLON,
        kat="Kat",
        cevre=dikdortgen(0, 0, 0.3, 0.6),
    )
    e.olculer["b"] = 0.30
    e.olculer["h"] = 0.60
    e.olculer["kesit_alani"] = 0.18
    return e


@pytest.fixture(scope="module")
def plan(tmp_path_factory) -> Path:
    return uret(tmp_path_factory.mktemp("plan") / "kalip_plani.dxf")


@pytest.fixture(scope="module")
def donati_plani(tmp_path_factory) -> Path:
    """Kolon yakini ve perde uzerinde donati etiketleri olan plan (cm)."""
    return _donati_plani(tmp_path_factory.mktemp("donati") / "donati.dxf")


def _donati_plani(hedef: Path) -> Path:
    import ezdxf

    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 5
    msp = doc.modelspace()
    for kat in ("DONATI", "YAZI"):
        if kat not in doc.layers:
            doc.layers.add(kat, color=2)
    # S05 kolonu (600,500) merkez
    msp.add_text("4Ø18", height=18, dxfattribs={"layer": "DONATI"}).set_placement(
        (600, 500)
    )
    msp.add_text("Ø8/20", height=18, dxfattribs={"layer": "DONATI"}).set_placement(
        (600, 470)
    )
    # Perde uzerinde
    msp.add_text("3Φ16", height=18, dxfattribs={"layer": "DONATI"}).set_placement(
        (300, 250)
    )
    # Donati olmayan bir etiket
    msp.add_text("TD=15", height=22, dxfattribs={"layer": "YAZI"}).set_placement(
        (950, 380)
    )
    doc.saveas(str(hedef))
    return hedef


class TestEtiketAyristirma:
    @pytest.mark.parametrize(
        "metin,beklenen",
        [
            ("8Ø14", [DonatiKalem(14, adet=8)]),
            ("4Φ20", [DonatiKalem(20, adet=4)]),
            ("2Ø12+3Ø14", [DonatiKalem(12, adet=2), DonatiKalem(14, adet=3)]),
            ("Ø8/20", [DonatiKalem(8, aralik_cm=20.0)]),
            ("d10/15", [DonatiKalem(10, aralik_cm=15.0)]),
            ("N301 8Ø14", [DonatiKalem(14, adet=8)]),
            ("Ø16", [DonatiKalem(16, adet=1)]),
        ],
    )
    def test_bilinen_desenler(self, metin, beklenen):
        assert donati_kalemleri(metin, ayarlari_yukle()) == beklenen

    @pytest.mark.parametrize(
        "metin",
        ["LAMEL", "PENCERE", "TD=15", "K101 25/50", "", "3.50 m", "S01 30/60"],
    )
    def test_donati_olmayanlar_elenir(self, metin):
        assert donati_kalemleri(metin, ayarlari_yukle()) == []

    def test_birim_agirlik_formulu(self):
        assert DonatiKalem(8).birim_agirlik == pytest.approx(0.395, abs=0.002)
        assert DonatiKalem(18).birim_agirlik == pytest.approx(2.0, abs=0.01)
        assert DonatiKalem(32).birim_agirlik == pytest.approx(6.317, abs=0.02)


class TestDonatiKg:
    def test_kolon_boyuna_ve_etriye(self):
        from hakedis.donati import DonatiOkuma

        ayarlar = ayarlari_yukle()
        e = _kolon_elemani()
        oku = DonatiOkuma(
            metin="4Ø18",
            konum=Nokta(0.15, 0.3),
            kalemler=donati_kalemleri("4Ø18", ayarlar),
            eleman=e,
        )
        H = 2.85
        boyuna = 4 * H * DonatiKalem(18).birim_agirlik
        assert donati_kg(oku, ayarlar, H) == pytest.approx(boyuna, rel=1e-6)

    def test_etriye_eklenir(self):
        from hakedis.donati import DonatiOkuma

        ayarlar = ayarlari_yukle()
        e = _kolon_elemani()
        oku = DonatiOkuma(
            metin="Ø8/20",
            konum=Nokta(0.15, 0.3),
            kalemler=donati_kalemleri("Ø8/20", ayarlar),
            eleman=e,
        )
        H = 2.85
        cevre = 2 * (0.30 + 0.60) - 8 * 0.03 + 0.15
        n = int(H / 0.20) + 1
        etriye = n * cevre * DonatiKalem(8).birim_agirlik
        assert donati_kg(oku, ayarlar, H) == pytest.approx(etriye, rel=1e-6)


class TestPlanaEsasliMetraj:
    def test_plan_okumasi_satir_uretir(self, plan, donati_plani):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["donati"] = {
            "aktif": True,
            "plan_okuma": True,
            "katsayilar": {"kolon": 110},
        }
        s, _ = plandan_metraj(
            str(plan), ayarlar, donati_dosya=str(donati_plani)
        )
        plan_satirlar = [
            r for r in s.satirlar if "DONATI PLANINDAN" in (r.tanim or "")
        ]
        assert plan_satirlar, "donati plani okununca plan satirlari uretilmeli"
        # katsayi esasli satirlar kapatilir (cift sayim onlenir)
        assert not any("KATSAYI" in (r.tanim or "") for r in s.satirlar)
        # kolon icin en az bir donati satiri var
        assert any("(kolon)" in (r.tanim or "").lower() for r in plan_satirlar)
        assert any("DONATI PLANINDAN" in u for u in s.uyarilar)
        assert s.parametreler.get("donati", {}).get("etiket", 0) >= 3

    def test_plan_okuma_kapaliyken_ignored(self, plan, donati_plani):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["donati"] = {"aktif": False, "plan_okuma": False}
        s, _ = plandan_metraj(
            str(plan), ayarlar, donati_dosya=str(donati_plani)
        )
        assert not any(
            "DONATI PLANINDAN" in (r.tanim or "") for r in s.satirlar
        )
        assert all(r.kg is None for r in s.satirlar)

    def test_okumalari_metinden_toplar(self, donati_plani):
        from hakedis.readers import cizim_oku

        ayarlar = ayarlari_yukle()
        cizim = cizim_oku(str(donati_plani), ayarlar)
        okumalar = donati_okumalari(cizim.varliklar, ayarlar)
        assert len(okumalar) == 3
        assert any(o.kalemler[0].cap_mm == 18 and o.kalemler[0].adet == 4 for o in okumalar)

    def test_elemanina_atama(self, plan, donati_plani):
        from hakedis.detect import elemanlari_tespit_et
        from hakedis.donati import donati_elemana_ata
        from hakedis.readers import cizim_oku

        ayarlar = ayarlari_yukle()
        cizim = cizim_oku(str(plan), ayarlar)
        elemanlar, _ = elemanlari_tespit_et(cizim, ayarlar)
        d_cizim = cizim_oku(str(donati_plani), ayarlar)
        okumalar = donati_okumalari(d_cizim.varliklar, ayarlar)
        donati_elemana_ata(okumalar, elemanlar)
        # 4Ø18 etiketi kolona, 3Φ16 perdeye atanmis olmali
        kolonlu = [o for o in okumalar if o.eleman and o.eleman.tip == ElemanTipi.KOLON]
        perdeli = [o for o in okumalar if o.eleman and o.eleman.tip == ElemanTipi.PERDE]
        assert kolonlu, "kolon yakini etiketi kolona atanmali"
        assert perdeli, "perde uzeri etiketi perdeye atanmali"

    def test_doseme_mesh_alan_bazli(self):
        ayarlar = ayarlari_yukle()
        ayarlar.ham["donati"] = {"plan_okuma": True, "mesh_iki_yon": True}
        e = Eleman(
            ad="D01",
            tip=ElemanTipi.DOSEME,
            kat="Kat",
            cevre=dikdortgen(0, 0, 4, 5),
        )
        e.olculer["t"] = 0.15
        e.olculer["eksen_uzunlugu"] = 4.0
        e.olculer["net_uzunluk"] = 4.0
        satirlar = donati_satirlari(
            donati_okumalari(
                [HamVarlik("metin", katman="MESH", noktalar=[Nokta(2, 2)], metin="d8/20")],
                ayarlar,
            ),
            [e],
            ayarlar,
            2.85,
        )
        assert satirlar
        # d8 iki yon mesh: 20 m2 alan, 1/0.2 = 5 m/m2 x 2 yon
        beklenen = 20 * (1 / 0.2) * 2 * DonatiKalem(8).birim_agirlik
        assert satirlar[0].kg == pytest.approx(beklenen, rel=1e-6)


class TestCli:
    def test_metraj_donati_bayragi(self, plan, donati_plani, tmp_path, capsys):
        from hakedis.cli import main

        cikti = tmp_path / "donati.xlsx"
        kod = main(
            [
                "metraj",
                str(plan),
                "--donati",
                str(donati_plani),
                "--cikti",
                str(cikti),
            ]
        )
        assert kod == 0
        assert cikti.exists()
        out = capsys.readouterr().out
        assert "DONATI PLANINDAN" in out
        assert "KATSAYI" not in out
