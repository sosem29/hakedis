"""Bolme duvari metraji ve tekrarlanan kat carpani testleri."""

from hakedis.config import ayarlari_yukle
from hakedis.metraj import _duvar_satirlari, sonuclari_cogalt
from hakedis.model import (
    Eleman,
    ElemanTipi,
    KirikOlcuSatiri,
    MetrajSonucu,
    Nokta,
    Segment,
)


def _duvar_elemani(uzunluk=4.0, genislik=0.15):
    e = Eleman(ad="", tip=ElemanTipi.DUVAR, kaynak_katman="MIMARI_DUVAR")
    e.segmentler = [
        Segment(Nokta(0.0, 0.0), Nokta(uzunluk, 0.0), aciklama="duvar")
    ]
    e.olculer["b"] = genislik
    e.olculer["eksen_uzunlugu"] = uzunluk
    e.kat = "Zemin"
    return e


def _aciklik(tip, en=0.9, boy=2.1, x=1.0):
    e = Eleman(ad="K1", tip=tip, kaynak_katman="MIMARI_ETIKET")
    e.olculer["en"] = en
    e.olculer["boy"] = boy
    e.cevre = [
        Nokta(x - 0.06, -0.06), Nokta(x + 0.06, -0.06),
        Nokta(x + 0.06, 0.06), Nokta(x - 0.06, 0.06),
    ]
    e.kat = "Zemin"
    return e


def _satir_ornek(a):
    return KirikOlcuSatiri(
        poz=a.poz("duvar"),
        eleman_adi="D1",
        tip=ElemanTipi.DUVAR,
        tanim="Bolme duvari",
        alan=4.0 * 2.8,
        yukseklik=2.8,
        birim="m2",
        kat="Zemin",
    )


def test_duvar_satirlari_brut_alan():
    a = ayarlari_yukle()
    a.ham["duvar"] = {"aktif": True, "yukseklik": 2.8, "siva_iki_yuz": False}
    satirlar = _duvar_satirlari(_duvar_elemani(4.0, 0.15), a, [])
    assert len(satirlar) == 1
    s = satirlar[0]
    assert s.tip == ElemanTipi.DUVAR
    assert s.miktar == 4.0 * 2.8
    assert s.poz == a.poz("duvar")
    assert s.birim == "m2"


def test_duvar_bosluk_dusumu():
    a = ayarlari_yukle()
    a.ham["duvar"] = {"aktif": True, "yukseklik": 2.8, "siva_iki_yuz": False}
    kapi = _aciklik(ElemanTipi.KAPI, en=0.9, boy=2.1, x=1.0)
    pencere = _aciklik(ElemanTipi.PENCERE, en=1.5, boy=1.2, x=3.0)
    satirlar = _duvar_satirlari(_duvar_elemani(4.0, 0.15), a, [kapi, pencere])
    dusum = 0.9 * 2.1 + 1.5 * 1.2
    assert satirlar[0].miktar == 4.0 * 2.8 - dusum


def test_duvar_uzak_aciklik_dusulmez():
    a = ayarlari_yukle()
    a.ham["duvar"] = {"aktif": True, "yukseklik": 2.8, "siva_iki_yuz": False}
    uzak = _aciklik(ElemanTipi.KAPI, en=0.9, boy=2.1, x=10.0)
    satirlar = _duvar_satirlari(_duvar_elemani(4.0, 0.15), a, [uzak])
    assert satirlar[0].miktar == 4.0 * 2.8


def test_duvar_siva_iki_yuz():
    a = ayarlari_yukle()
    a.ham["duvar"] = {"aktif": True, "yukseklik": 2.8, "siva_iki_yuz": True}
    satirlar = _duvar_satirlari(_duvar_elemani(4.0, 0.15), a, [])
    assert len(satirlar) == 2
    siva = satirlar[1]
    assert siva.poz == a.poz("duvar_siva")
    assert siva.miktar == 2 * 4.0 * 2.8


def test_sonuclari_cogalt_katlari_aciyor():
    a = ayarlari_yukle()
    e = _duvar_elemani()
    s = _satir_ornek(a)
    sonuc = MetrajSonucu(
        kat="Zemin", elemanlar=[e], satirlar=[s], uyarilar=[], parametreler={}
    )
    genisletilmis = sonuclari_cogalt([sonuc], [3])
    assert len(genisletilmis) == 3
    assert [x.kat for x in genisletilmis] == [
        "Zemin (1/3)", "Zemin (2/3)", "Zemin (3/3)"
    ]
    assert all(x.satirlar[0].kat == x.kat for x in genisletilmis)
    assert all(x.elemanlar[0].kat == x.kat for x in genisletilmis)


def test_sonuclari_cogalt_tekil_degisiklik():
    a = ayarlari_yukle()
    sonuc = MetrajSonucu(
        kat="Zemin", elemanlar=[_duvar_elemani()],
        satirlar=[_satir_ornek(a)], uyarilar=[], parametreler={}
    )
    tek = sonuclari_cogalt([sonuc], [1])
    assert len(tek) == 1
    assert tek[0].kat == "Zemin"
