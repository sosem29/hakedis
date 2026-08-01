"""Etiket ayristirma ve yapilandirma testleri."""

from __future__ import annotations

import pytest

from hakedis.config import ayarlari_yukle, birim_carpani, olcegi_coz
from hakedis.labels import etiket_ayristir
from hakedis.model import ElemanTipi


@pytest.fixture(scope="module")
def ayarlar():
    return ayarlari_yukle()


class TestEtiketAyristirma:
    @pytest.mark.parametrize(
        "metin,ad,b,h",
        [
            ("K101 25/50", "K101", 0.25, 0.50),
            ("S01 30/60", "S01", 0.30, 0.60),
            ("K-12 30x70", "K-12", 0.30, 0.70),
            ("S5 (25/50)", "S5", 0.25, 0.50),
            ("K201 20*40", "K201", 0.20, 0.40),
        ],
    )
    def test_kesit_okumasi(self, ayarlar, metin, ad, b, h):
        et = etiket_ayristir(metin, ayarlar)
        assert et.ad == ad.replace("-", "").replace(" ", "") or et.ad == ad
        assert et.b == pytest.approx(b)
        assert et.h == pytest.approx(h)

    def test_metre_cinsinden_yazilan_kesit(self, ayarlar):
        """'0.25/0.50' zaten metredir, tekrar cm'den cevrilmemeli."""
        et = etiket_ayristir("K101 0.25/0.50", ayarlar)
        assert et.b == pytest.approx(0.25)
        assert et.h == pytest.approx(0.50)

    def test_doseme_kalinligi(self, ayarlar):
        assert etiket_ayristir("TD=15", ayarlar).t == pytest.approx(0.15)
        assert etiket_ayristir("T = 20", ayarlar).t == pytest.approx(0.20)

    def test_perde_adi_ve_kalinligi(self, ayarlar):
        et = etiket_ayristir("P1 25", ayarlar)
        assert et.ad == "P1"
        assert et.t == pytest.approx(0.25)

    def test_sadece_ad(self, ayarlar):
        et = etiket_ayristir("S12", ayarlar)
        assert et.ad == "S12"
        assert et.tip_ipucu == ElemanTipi.KOLON

    def test_tip_ipuclari(self, ayarlar):
        assert etiket_ayristir("K101 25/50", ayarlar).tip_ipucu == ElemanTipi.KIRIS
        assert etiket_ayristir("P1 25", ayarlar).tip_ipucu == ElemanTipi.PERDE

    def test_alakasiz_metin_bilgi_vermez(self, ayarlar):
        assert not etiket_ayristir("KALIP PLANI 1/50", ayarlar).bilgi_var


class TestBirimVeOlcek:
    def test_birim_carpanlari(self):
        assert birim_carpani("cm") == pytest.approx(0.01)
        assert birim_carpani("mm") == pytest.approx(0.001)
        assert birim_carpani("m") == pytest.approx(1.0)

    def test_bilinmeyen_birim_hata_verir(self):
        with pytest.raises(ValueError):
            birim_carpani("fersah")

    @pytest.mark.parametrize("deger,beklenen", [("1/50", 50), ("1:100", 100), (25, 25)])
    def test_olcek_cozumu(self, deger, beklenen):
        assert olcegi_coz(deger) == pytest.approx(beklenen)

    def test_bozuk_olcek_hata_verir(self):
        with pytest.raises(ValueError):
            olcegi_coz("yarim")


class TestKatmanEsleme:
    @pytest.mark.parametrize(
        "katman,tip",
        [
            ("KOLON", "kolon"),
            ("PERDE-25", "perde"),
            ("KIRIS", "kiris"),
            ("KİRİŞ", "kiris"),
            ("DOSEME", "doseme"),
            ("DÖŞEME-SINIR", "doseme"),
            ("ASANSOR-BOSLUK", "bosluk"),
            ("AKS", "yoksay"),
            ("DEFPOINTS", "yoksay"),
        ],
    )
    def test_katman_tipleri(self, ayarlar, katman, tip):
        assert ayarlar.katman_tipi(katman) == tip

    def test_eslesmeyen_katman(self, ayarlar):
        assert ayarlar.katman_tipi("RASTGELE-KATMAN-XYZ") is None

    def test_cli_ezmesi(self, ayarlar):
        yeni = ayarlar.guncelle(kat_yuksekligi=3.6, birim="mm")
        assert yeni.kat_yuksekligi == pytest.approx(3.6)
        assert yeni.birim == "mm"
        # Ozgun ayarlar degismemeli
        assert ayarlar.kat_yuksekligi == pytest.approx(3.0)

    def test_none_degerler_ezmez(self, ayarlar):
        assert ayarlar.guncelle(kat_yuksekligi=None).kat_yuksekligi == pytest.approx(3.0)
