"""Geometri cekirdegi testleri."""

from __future__ import annotations

import math

import pytest

from hakedis.geometry import (
    alan,
    dogrusallari_sadelestir,
    eksenleri_birlestir,
    isaretli_alan,
    kenarlar,
    konveks_kabuk,
    min_donmus_dikdortgen,
    nokta_icinde_mi,
    ortogonale_yasla,
    paralel_cift_eksenleri,
    poligondan_eksen,
    segmenti_poligonlarla_kirp,
    zincirle,
)
from hakedis.model import Nokta, Segment


def dikdortgen(x0, y0, x1, y1) -> list[Nokta]:
    return [Nokta(x0, y0), Nokta(x1, y0), Nokta(x1, y1), Nokta(x0, y1)]


class TestAlan:
    def test_dikdortgen_alani(self):
        assert alan(dikdortgen(0, 0, 4, 3)) == pytest.approx(12.0)

    def test_isaret_yon_bagimli(self):
        d = dikdortgen(0, 0, 4, 3)
        assert isaretli_alan(d) > 0
        assert isaretli_alan(list(reversed(d))) < 0

    def test_l_seklinde_alan(self):
        # 4x4 kareden 2x2 kose cikarilmis
        l = [
            Nokta(0, 0),
            Nokta(4, 0),
            Nokta(4, 2),
            Nokta(2, 2),
            Nokta(2, 4),
            Nokta(0, 4),
        ]
        assert alan(l) == pytest.approx(12.0)

    def test_ucgen_alani(self):
        assert alan([Nokta(0, 0), Nokta(3, 0), Nokta(0, 4)]) == pytest.approx(6.0)


class TestMinDonmusDikdortgen:
    def test_eksene_paralel(self):
        d = min_donmus_dikdortgen(dikdortgen(0, 0, 0.3, 0.6))
        assert d is not None
        assert d.en == pytest.approx(0.3, abs=1e-6)
        assert d.boy == pytest.approx(0.6, abs=1e-6)
        assert d.narinlik == pytest.approx(2.0, abs=1e-6)

    def test_45_derece_donmus_kolon(self):
        """Donmus kolonda sinir kutusu yaniltir; min dikdortgen dogru olmali."""
        a = math.radians(45)
        merkez = Nokta(10.0, 5.0)
        yari = [(0.15, 0.30), (-0.15, 0.30), (-0.15, -0.30), (0.15, -0.30)]
        pts = [
            Nokta(
                merkez.x + u * math.cos(a) - v * math.sin(a),
                merkez.y + u * math.sin(a) + v * math.cos(a),
            )
            for u, v in yari
        ]
        d = min_donmus_dikdortgen(pts)
        assert d is not None
        assert d.en == pytest.approx(0.30, abs=1e-6)
        assert d.boy == pytest.approx(0.60, abs=1e-6)
        assert d.aci == pytest.approx(135.0, abs=0.5)

    def test_konveks_kabuk_ic_noktalari_atar(self):
        pts = dikdortgen(0, 0, 2, 2) + [Nokta(1, 1)]
        assert len(konveks_kabuk(pts)) == 4


class TestPerdeEkseni:
    def test_duz_perde(self):
        """4.00 x 0.25 duz perde -> tek eksen parcasi, tam boy."""
        eksenler, t = poligondan_eksen(dikdortgen(0, 0, 4.0, 0.25))
        assert t == pytest.approx(0.25, abs=1e-6)
        assert sum(s.uzunluk for s in eksenler) == pytest.approx(4.0, abs=1e-6)
        assert all(s.orta.y == pytest.approx(0.125, abs=1e-6) for s in eksenler)

    def test_l_perde_kirilim_noktasinda_birlesir(self):
        """L perde: iki parca, kose kirilim noktasinda tam birlesmeli."""
        t = 0.25
        cevre = [
            Nokta(2.50, 1.50),
            Nokta(4.50, 1.50),
            Nokta(4.50, 1.50 + t),
            Nokta(2.50 + t, 1.50 + t),
            Nokta(2.50 + t, 3.25),
            Nokta(2.50, 3.25),
        ]
        eksenler, kalinlik = poligondan_eksen(cevre)
        assert kalinlik == pytest.approx(t, abs=1e-6)
        assert len(eksenler) == 2
        toplam = sum(s.uzunluk for s in eksenler)
        # Yatay kol: 4.50 - 2.625 = 1.875 ; Dusey kol: 3.25 - 1.625 = 1.625
        assert toplam == pytest.approx(3.50, abs=1e-6)
        # Iki parca ortak kirilim noktasinda bulusmali
        uclar = [s.baslangic for s in eksenler] + [s.bitis for s in eksenler]
        kose = Nokta(2.625, 1.625)
        assert sum(1 for p in uclar if p.mesafe(kose) < 1e-6) == 2

    def test_egik_perde(self):
        """30 derece egik perde de dogru eksen ve kalinlik vermeli."""
        a = math.radians(30)
        L, t = 5.0, 0.30
        yerel = [(0, 0), (L, 0), (L, t), (0, t)]
        cevre = [
            Nokta(u * math.cos(a) - v * math.sin(a), u * math.sin(a) + v * math.cos(a))
            for u, v in yerel
        ]
        eksenler, kalinlik = poligondan_eksen(cevre)
        assert kalinlik == pytest.approx(t, abs=1e-6)
        assert sum(s.uzunluk for s in eksenler) == pytest.approx(L, abs=1e-6)


class TestKirisEslesme:
    def test_paralel_cizgi_cifti_eksene_donusur(self):
        cizgiler = [
            Segment(Nokta(0, -0.125), Nokta(6, -0.125)),
            Segment(Nokta(0, 0.125), Nokta(6, 0.125)),
        ]
        ciftler = paralel_cift_eksenleri(cizgiler, 0.15, 1.0)
        assert len(ciftler) == 1
        eksen, genislik = ciftler[0]
        assert genislik == pytest.approx(0.25, abs=1e-6)
        assert eksen.uzunluk == pytest.approx(6.0, abs=1e-6)
        assert eksen.orta.y == pytest.approx(0.0, abs=1e-6)

    def test_uzak_cizgiler_eslesmez(self):
        cizgiler = [
            Segment(Nokta(0, 0), Nokta(6, 0)),
            Segment(Nokta(0, 5), Nokta(6, 5)),
        ]
        assert paralel_cift_eksenleri(cizgiler, 0.15, 1.0) == []

    def test_dik_cizgiler_eslesmez(self):
        cizgiler = [
            Segment(Nokta(0, 0), Nokta(6, 0)),
            Segment(Nokta(0, 0.25), Nokta(0, 6)),
        ]
        assert paralel_cift_eksenleri(cizgiler, 0.15, 1.0) == []


class TestMesnetKirpma:
    def test_kiris_mesnetlerde_bolunur(self):
        """12.30 m eksen, 3 adet 0.30 kolon -> 11.40 m net, 2 aciklik."""
        seg = Segment(Nokta(-0.15, 0), Nokta(12.15, 0))
        mesnetler = [
            dikdortgen(x - 0.15, -0.30, x + 0.15, 0.30) for x in (0.0, 6.0, 12.0)
        ]
        parcalar = segmenti_poligonlarla_kirp(seg, mesnetler)
        assert len(parcalar) == 2
        assert sum(p.uzunluk for p in parcalar) == pytest.approx(11.40, abs=0.02)

    def test_mesnetsiz_eksen_bolunmez(self):
        seg = Segment(Nokta(0, 0), Nokta(5, 0))
        assert segmenti_poligonlarla_kirp(seg, []) == [seg]


class TestYardimcilar:
    def test_ortogonale_yaslama(self):
        pts = [Nokta(0, 0), Nokta(5.0, 0.004)]
        assert ortogonale_yasla(pts)[1].y == pytest.approx(0.0)

    def test_dogrusal_ara_nokta_atilir(self):
        pts = [Nokta(0, 0), Nokta(2, 0), Nokta(4, 0), Nokta(4, 3), Nokta(0, 3)]
        assert len(dogrusallari_sadelestir(pts)) == 4

    def test_zincirleme_sirayi_duzeltir(self):
        segler = [
            Segment(Nokta(2, 0), Nokta(2, 2)),
            Segment(Nokta(0, 0), Nokta(2, 0)),
        ]
        zincir = zincirle(segler)
        assert zincir[0].baslangic.mesafe(Nokta(0, 0)) < 1e-9
        assert zincir[-1].bitis.mesafe(Nokta(2, 2)) < 1e-9

    def test_nokta_icinde(self):
        d = dikdortgen(0, 0, 4, 3)
        assert nokta_icinde_mi(Nokta(2, 1.5), d)
        assert not nokta_icinde_mi(Nokta(5, 1.5), d)

    def test_kenar_sayisi(self):
        assert len(kenarlar(dikdortgen(0, 0, 1, 1), kapali=True)) == 4
        assert len(kenarlar(dikdortgen(0, 0, 1, 1), kapali=False)) == 3
