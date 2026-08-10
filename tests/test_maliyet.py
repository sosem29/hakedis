"""Yaklasik maliyet ve fiyat verisi (birim fiyat, oneri, beton sinifi) testleri."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hakedis.config import ayarlari_yukle
from hakedis.maliyet import fiyat_sozlugu, maliyet_hesapla
from hakedis.metraj import metraj_hesapla
from hakedis.model import Eleman, ElemanTipi


def _ayarlar(fiyat_yolu: str | None = None) -> object:
    a = ayarlari_yukle()
    a.ham["maliyet"]["aktif"] = True
    if fiyat_yolu:
        a.ham["maliyet"]["fiyatlar_yolu"] = fiyat_yolu
    return a


class TestFiyatSozlugu:
    def test_yeni_pozlar_fiyatlidir(self):
        a = _ayarlar()
        f = fiyat_sozlugu(a)
        assert f["21.121"] == 850  # bolme duvar
        assert f["23.063"] == 260  # parke

    def test_beton_sinifi_ezmesi(self):
        a = _ayarlar()
        a.ham["kat"]["beton_sinifi"] = "C35/45"
        f = fiyat_sozlugu(a)
        assert f["16.058/1-K"] == 4800
        assert f["16.058/1-Kr"] == 4900

    def test_beton_sinifi_varsayilan_c2530(self):
        a = _ayarlar()
        f = fiyat_sozlugu(a)
        assert f["16.058/1-K"] == 4200

    def test_dosyadan_beton_siniflari_okunur(self, tmp_path):
        yol = tmp_path / "fiyatlar.yml"
        yol.write_text(
            "\n".join(
                [
                    '"24.001": 555',  # varsayilanlarda olmayan poz
                    "beton_siniflari:",
                    "  C35/45:",
                    '    "24.002": 666',
                ]
            ),
            encoding="utf-8",
        )
        a = _ayarlar(str(yol))
        a.ham["kat"]["beton_sinifi"] = "C35/45"
        f = fiyat_sozlugu(a)
        # dosyadaki duz poz fiyati okunur
        assert f["24.001"] == 555
        # dosyadaki sinif ezmesi de okunur
        assert f["24.002"] == 666

        a2 = _ayarlar(str(yol))
        a2.ham["kat"]["beton_sinifi"] = "C25/30"
        f2 = fiyat_sozlugu(a2)
        assert "24.002" not in f2  # sinif ezmesi yalnizca secili sinifta

    def test_dosyadaki_sinif_duz_fiyatin_ustune_biner(self, tmp_path):
        yol = tmp_path / "fiyatlar.yml"
        yol.write_text(
            "\n".join(
                [
                    '"16.058/1-K": 4200',
                    '"21.011/K": 480',
                    "beton_siniflari:",
                    "  C30/37:",
                    '    "16.058/1-K": 4500',
                ]
            ),
            encoding="utf-8",
        )
        a = _ayarlar(str(yol))
        a.ham["kat"]["beton_sinifi"] = "C30/37"
        f = fiyat_sozlugu(a)
        assert f["16.058/1-K"] == 4500
        assert f["21.011/K"] == 480


class TestFiyatOnerisi:
    def test_oneri_ayni_on_ek_medyanindan(self):
        from hakedis.maliyet import _fiyat_onerisi

        fiyatlar = {"21.061": 250, "21.071": 210, "16.058/1-K": 4200}
        # "21.121" icin "21" on ekindeki {210, 250} medyani = 250
        assert _fiyat_onerisi(fiyatlar, "21.121") == 250

    def test_oneri_yoksa_none(self):
        from hakedis.maliyet import _fiyat_onerisi

        assert _fiyat_onerisi({}, "21.121") is None


class TestMaliyetHesabi:
    def _doseme_sonucu(self):
        e = Eleman(
            ad="D01",
            tip=ElemanTipi.DOSEME,
            kat="Kat",
            cevre=[(0, 0), (1000, 0), (1000, 500), (0, 500)],
        )
        e.olculer["t"] = 0.15
        return metraj_hesapla([e], _ayarlar())

    def test_parke_poz_fiyatli(self):
        a = _ayarlar()
        sonuc = metraj_hesapla([], a, mahaller=[])
        from hakedis.mahal import Mahal, mahal_satirlari

        m = [Mahal(ad="SALON", tip="parke", alan=25.0, cevre=20.0)]
        sonuc.satirlar.extend(mahal_satirlari(m, a))
        maliyet = maliyet_hesapla(sonuc, a)
        parke = next(k for k in maliyet["kalemler"] if k["poz"] == "23.063")
        assert parke["tutar"] == pytest.approx(25.0 * 260)
        assert "23.063" not in maliyet["fiyatsiz_pozlar"]

    def test_duvar_poz_fiyatli(self):
        from hakedis.metraj import _duvar_satirlari

        a = _ayarlar()
        e = Eleman(
            ad="D1",
            tip=ElemanTipi.DUVAR,
            kat="Kat",
            cevre=[(0, 0), (1000, 0), (1000, 20), (0, 20)],
        )
        e.olculer["b"] = 0.20
        e.olculer["eksen_uzunlugu"] = 10.0
        satirlar = _duvar_satirlari(e, a, [])
        sonuc = metraj_hesapla([], a)
        sonuc.satirlar.extend(satirlar)
        maliyet = maliyet_hesapla(sonuc, a)
        duvar = [k for k in maliyet["kalemler"] if k["poz"] == "21.121"]
        assert duvar, "duvar satirlari fiyatlandirilmali"
