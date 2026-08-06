"""Etiket (yazi) ayristirma ve elemanla eslestirme.

Kalip planlarindaki "K101 25/50", "S01 30x60", "TD=15" gibi yazilardan
eleman adi ve kesit olculeri okunur.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from hakedis.config import Ayarlar, birim_carpani
from hakedis.geometry import nokta_icinde_mi, sinir_kutusu
from hakedis.model import ElemanTipi, HamVarlik, Nokta

# Ad on eklerinden eleman tipi tahmini
ON_EK_TIPLERI: dict[str, ElemanTipi] = {
    "S": ElemanTipi.KOLON,
    "K": ElemanTipi.KIRIS,
    "P": ElemanTipi.PERDE,
    "D": ElemanTipi.DOSEME,
    "M": ElemanTipi.MERDIVEN,
    "KOLON": ElemanTipi.KOLON,
    "KIRIS": ElemanTipi.KIRIS,
    "PERDE": ElemanTipi.PERDE,
    "DOSEME": ElemanTipi.DOSEME,
}


@dataclass
class Etiket:
    """Cizimden okunmus tek bir yazi ve ondan cikarilan bilgiler."""

    metin: str
    konum: Nokta
    katman: str = ""
    ad: str | None = None
    b: float | None = None  # kesit genisligi (m)
    h: float | None = None  # kesit yuksekligi (m)
    t: float | None = None  # kalinlik (m)
    tip_ipucu: ElemanTipi | None = None
    kullanildi: bool = False
    dogrulama: bool = False  # kapi/pencere bosluk (dograma) etiketi

    @property
    def bilgi_var(self) -> bool:
        return any(v is not None for v in (self.ad, self.b, self.h, self.t))


def _sayi(metin: str, birim: str) -> float:
    """Etiketteki sayiyi metreye cevirir.

    '25' -> 0.25 m (cm varsayimi), '0.25' -> 0.25 m (zaten metre).
    Ondalikli ve 5'ten kucuk degerler metre kabul edilir; kesitler
    pratikte 5 m'yi gecmez, cm cinsinden de 5 cm'lik kesit olmaz.
    """
    ham = metin.replace(",", ".").strip()
    deger = float(ham)
    ondalikli = "." in ham
    if ondalikli and deger <= 5.0:
        return deger
    return deger * birim_carpani(birim)


def _tip_ipucu(ad: str | None) -> ElemanTipi | None:
    if not ad:
        return None
    m = re.match(r"^([A-ZÇĞİÖŞÜa-zçğıöşü]+)", ad.strip())
    if not m:
        return None
    on = m.group(1).upper().replace("İ", "I").replace("Ş", "S").replace("Ö", "O")
    if on in ON_EK_TIPLERI:
        return ON_EK_TIPLERI[on]
    if len(on) == 1 and on in ON_EK_TIPLERI:
        return ON_EK_TIPLERI[on]
    return None


def etiket_ayristir(metin: str, ayarlar: Ayarlar) -> Etiket:
    """Serbest metinden ad/kesit bilgisi cikarir."""
    birim = str(ayarlar.al("etiket.kesit_birimi", "cm"))
    temiz = " ".join(metin.replace("\n", " ").split())
    et = Etiket(metin=temiz, konum=Nokta(0.0, 0.0))

    for desen in ayarlar.al("etiket.desenler.kesit", []) or []:
        m = re.search(desen, temiz)
        if m:
            gd = m.groupdict()
            if gd.get("ad"):
                et.ad = gd["ad"].replace(" ", "").replace("_", "").upper()
            try:
                if gd.get("b"):
                    et.b = _sayi(gd["b"], birim)
                if gd.get("h"):
                    et.h = _sayi(gd["h"], birim)
            except ValueError:  # pragma: no cover
                pass
            break

    if et.b is None:
        for desen in ayarlar.al("etiket.desenler.kalinlik", []) or []:
            m = re.search(desen, temiz)
            if m:
                gd = m.groupdict()
                if gd.get("ad") and not et.ad:
                    et.ad = gd["ad"].replace(" ", "").upper()
                try:
                    if gd.get("t"):
                        et.t = _sayi(gd["t"], birim)
                except ValueError:  # pragma: no cover
                    pass
                break

    if et.ad is None:
        for desen in ayarlar.al("etiket.desenler.ad", []) or []:
            m = re.search(desen, temiz)
            if m and m.groupdict().get("ad"):
                et.ad = m.group("ad").replace(" ", "").replace("_", "").upper()
                break

    # Kapi/pencere (dograma boslugu) etiketi: "KD101", "P12", "90x220"
    for desen in ayarlar.al("etiket.desenler.dogrular", []) or []:
        m = re.search(desen, temiz)
        if m:
            et.dogrulama = True
            gd = m.groupdict()
            if gd.get("ad") and not et.ad:
                et.ad = gd["ad"].replace(" ", "").upper()
            break

    # Kesitte b > h ise ters yazilmis olabilir; kirislerde h >= b beklenir
    et.tip_ipucu = _tip_ipucu(et.ad)
    return et


def etiketleri_topla(varliklar: list[HamVarlik], ayarlar: Ayarlar) -> list[Etiket]:
    """Cizimdeki tum yazilari ayristirilmis etiketlere cevirir."""
    etiketler: list[Etiket] = []
    for v in varliklar:
        if v.tur != "metin" or not v.metin.strip():
            continue
        et = etiket_ayristir(v.metin, ayarlar)
        et.konum = v.noktalar[0] if v.noktalar else Nokta(0.0, 0.0)
        et.katman = v.katman
        etiketler.append(et)
    return etiketler


def _tip_uyumlu(et: Etiket, tip: ElemanTipi) -> bool:
    """Etiketin on eki elemanin tipiyle celisiyor mu?"""
    if et.dogrulama:
        return tip in (ElemanTipi.KAPI, ElemanTipi.PENCERE)
    if tip in (ElemanTipi.KAPI, ElemanTipi.PENCERE):
        return False
    if et.tip_ipucu is None:
        return True
    if et.tip_ipucu == tip:
        return True
    # Kolon/perde on ekleri birbirinin yerine kullanilabiliyor
    if {et.tip_ipucu, tip} <= {ElemanTipi.KOLON, ElemanTipi.PERDE}:
        return True
    return False


def en_uygun_etiket(
    etiketler: list[Etiket],
    cevre: list[Nokta],
    tip: ElemanTipi,
    ayarlar: Ayarlar,
    merkez: Nokta | None = None,
) -> Etiket | None:
    """Bir elemana en uygun etiketi secer.

    Oncelik sirasi:
      1. Elemanin ic bolgesine dusen, bilgi tasiyan etiketler
      2. Arama yaricapi icindeki en yakin, bilgi tasiyan etiket
    """
    yaricap = float(ayarlar.al("etiket.arama_yaricapi", 1.5))
    if merkez is None:
        if cevre:
            x0, y0, x1, y1 = sinir_kutusu(cevre)
            merkez = Nokta((x0 + x1) / 2, (y0 + y1) / 2)
        else:
            return None

    icerdekiler: list[tuple[float, Etiket]] = []
    yakindakiler: list[tuple[float, Etiket]] = []
    for et in etiketler:
        if et.kullanildi or not et.bilgi_var or not _tip_uyumlu(et, tip):
            continue
        d = et.konum.mesafe(merkez)
        if cevre and len(cevre) >= 3 and nokta_icinde_mi(et.konum, cevre):
            icerdekiler.append((d, et))
        elif d <= yaricap:
            yakindakiler.append((d, et))

    havuz = icerdekiler or yakindakiler
    if not havuz:
        return None
    havuz.sort(key=lambda t: (0 if t[1].ad else 1, t[0]))
    return havuz[0][1]


def etiketi_uygula(et: Etiket | None, eleman) -> None:
    """Etiketten okunan olculeri elemana isler."""
    if et is None:
        return
    et.kullanildi = True
    eleman.etiket_metni = et.metin
    if et.ad:
        eleman.ad = et.ad
    if et.b is not None:
        eleman.olculer.setdefault("etiket_b", et.b)
    if et.h is not None:
        eleman.olculer.setdefault("etiket_h", et.h)
    if et.t is not None:
        eleman.olculer.setdefault("etiket_t", et.t)
