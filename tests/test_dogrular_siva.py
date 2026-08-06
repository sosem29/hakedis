"""Kapi/pencere dogrulama listesi ve siva/kaplama metraji testleri."""

from hakedis.config import ayarlari_yukle
from hakedis.detect import _dogrular_tespit
from hakedis.labels import etiket_ayristir
from hakedis.metraj import _dogrular_satirlari, _siva_kaplama_satirlari
from hakedis.model import ElemanTipi, KirikOlcuSatiri, Nokta


def _elemanlar(metinler: list[str]):
    a = ayarlari_yukle()
    etiketler = [etiket_ayristir(m, a) for m in metinler]
    for i, et in enumerate(etiketler):
        et.konum = Nokta(float(i), 0.0)
    elemanlar = []
    _dogrular_tespit(etiketler, a, elemanlar)
    return a, elemanlar


def test_dogrulama_etiketleri_taniniyor():
    a = ayarlari_yukle()
    kd = etiket_ayristir("KD101", a)
    p = etiket_ayristir("P101", a)
    olcu = etiket_ayristir("90x220", a)
    assert kd.dogrulama and kd.ad == "KD101"
    assert p.dogrulama and p.ad == "P101"
    assert olcu.dogrulama


def test_perde_etiketi_dogrulama_sayilmaz():
    a = ayarlari_yukle()
    et = etiket_ayristir("P12 25", a)
    assert not et.dogrulama
    assert et.t == 0.25
    et2 = etiket_ayristir("P12 (30)", a)
    assert not et2.dogrulama


def test_yapisal_etiket_dogrulama_sayilmaz():
    a = ayarlari_yukle()
    assert not etiket_ayristir("K101 25/50", a).dogrulama
    assert not etiket_ayristir("S01 30x60", a).dogrulama
    assert not etiket_ayristir("186.2 D107", a).dogrulama
    assert not etiket_ayristir("5 D101", a).dogrulama


def test_dogrular_adet_olarak_birlesir():
    a, elemanlar = _elemanlar(["KD101", "KD101", "P101", "P101", "P101", "90x220"])
    tipler = {e.tip for e in elemanlar}
    assert ElemanTipi.KAPI in tipler
    assert ElemanTipi.PENCERE in tipler
    assert len(elemanlar) == 6  # etiket basina bir eleman

    satirlar = _dogrular_satirlari(elemanlar, a)
    assert len(satirlar) == 3  # KD101, P101, 90x220 ayri satirlar
    by_ad = {s.eleman_adi: s for s in satirlar}
    assert by_ad["KD101"].birim == "adet"
    assert by_ad["KD101"].miktar == 2.0
    assert by_ad["KD101"].poz == a.poz("kapi")
    assert by_ad["P101"].miktar == 3.0
    assert by_ad["P101"].poz == a.poz("pencere")


def test_siva_kaplama_aktif_degilken_bos():
    a = ayarlari_yukle()
    yapay = [
        KirikOlcuSatiri(poz="21.011/K", eleman_adi="S1", tip=ElemanTipi.KOLON,
                        tanim="", alan=12.0, birim="m2"),
        KirikOlcuSatiri(poz="21.011/D", eleman_adi="D1", tip=ElemanTipi.DOSEME,
                        tanim="", alan=40.0, birim="m2"),
    ]
    assert _siva_kaplama_satirlari(yapay, a) == []


def test_siva_kaplama_miktarlari():
    a = ayarlari_yukle()
    a.ham["siva"] = {"aktif": True, "yuzey_dusumu": 0.9}
    a.ham["kaplama"] = {"aktif": True}
    yapay = [
        KirikOlcuSatiri(poz="21.011/K", eleman_adi="S1", tip=ElemanTipi.KOLON,
                        tanim="", alan=12.0, birim="m2"),
        KirikOlcuSatiri(poz="21.011/D", eleman_adi="D1", tip=ElemanTipi.DOSEME,
                        tanim="", alan=40.0, birim="m2"),
    ]
    satirlar = _siva_kaplama_satirlari(yapay, a)
    by_poz = {s.poz: s for s in satirlar}
    assert by_poz[a.poz("siva")].miktar == 10.8
    assert by_poz[a.poz("siva_tavan")].miktar == 40.0
    assert by_poz["23.062/T"].miktar == 40.0
    assert by_poz["23.062/S"].miktar == 40.0
