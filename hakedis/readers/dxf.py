"""DXF okuyucu (ezdxf tabanli).

Model uzayindaki varliklari normalize edilmis HamVarlik listesine cevirir.
Bloklar (INSERT) sanal varliklara patlatilir; boylece kolon/kiris bloklari
da metraja girer.
"""

from __future__ import annotations

import math
from pathlib import Path

import ezdxf
from ezdxf import bbox
from ezdxf.entities import DXFEntity

from hakedis.config import Ayarlar, DXF_INSUNITS, birim_carpani
from hakedis.model import Cizim, HamVarlik, Nokta

# Blok patlatmada sonsuz dongu emniyeti
MAX_BLOK_DERINLIGI = 6


def _renk_kodu(varlik: DXFEntity) -> str:
    try:
        renk = varlik.dxf.get("color", 256)
    except Exception:  # pragma: no cover - ezdxf surum farklari
        renk = 256
    try:
        if hasattr(varlik.dxf, "true_color") and varlik.dxf.hasattr("true_color"):
            tc = int(varlik.dxf.true_color)
            return f"#{tc & 0xFFFFFF:06x}"
    except Exception:  # pragma: no cover
        pass
    return f"aci:{renk}"


def _yay_noktalari(
    merkez, yaricap: float, bas_aci: float, bit_aci: float, bolum: int = 24
) -> list[tuple[float, float]]:
    if bit_aci < bas_aci:
        bit_aci += 360.0
    adim = (bit_aci - bas_aci) / max(bolum, 2)
    return [
        (
            merkez[0] + yaricap * math.cos(math.radians(bas_aci + adim * i)),
            merkez[1] + yaricap * math.sin(math.radians(bas_aci + adim * i)),
        )
        for i in range(int(max(bolum, 2)) + 1)
    ]


def _metni_temizle(ham: str) -> str:
    """MTEXT bicimlendirme kodlarini atar."""
    try:
        from ezdxf.tools.text import plain_text

        return plain_text(ham)
    except Exception:  # pragma: no cover
        return ham


def _varligi_cevir(
    varlik: DXFEntity, carpan: float, derinlik: int = 0
) -> list[HamVarlik]:
    """Tek bir DXF varligini HamVarlik listesine cevirir."""
    tur = varlik.dxftype()
    try:
        katman = str(varlik.dxf.layer)
    except Exception:  # pragma: no cover
        katman = ""
    renk = _renk_kodu(varlik)

    def P(seq) -> list[Nokta]:
        return [Nokta(float(p[0]) * carpan, float(p[1]) * carpan) for p in seq]

    if tur == "LINE":
        a = varlik.dxf.start
        b = varlik.dxf.end
        return [
            HamVarlik(
                tur="cizgi",
                katman=katman,
                noktalar=P([(a.x, a.y), (b.x, b.y)]),
                renk=renk,
            )
        ]

    if tur == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in varlik.get_points("xy")]
        if len(pts) < 2:
            return []
        kapali = bool(varlik.closed)
        return [
            HamVarlik(
                tur="poligon" if kapali else "cizgi",
                katman=katman,
                noktalar=P(pts),
                kapali=kapali,
                renk=renk,
            )
        ]

    if tur == "POLYLINE":
        try:
            pts = [(v.dxf.location.x, v.dxf.location.y) for v in varlik.vertices]
        except Exception:  # pragma: no cover
            return []
        if len(pts) < 2:
            return []
        kapali = bool(varlik.is_closed)
        return [
            HamVarlik(
                tur="poligon" if kapali else "cizgi",
                katman=katman,
                noktalar=P(pts),
                kapali=kapali,
                renk=renk,
            )
        ]

    if tur == "CIRCLE":
        m = varlik.dxf.center
        r = float(varlik.dxf.radius)
        pts = _yay_noktalari((m.x, m.y), r, 0.0, 360.0, 32)[:-1]
        return [
            HamVarlik(
                tur="poligon",
                katman=katman,
                noktalar=P(pts),
                kapali=True,
                renk=renk,
                ekstra={"daire": True, "yaricap": r * carpan},
            )
        ]

    if tur == "ARC":
        m = varlik.dxf.center
        pts = _yay_noktalari(
            (m.x, m.y),
            float(varlik.dxf.radius),
            float(varlik.dxf.start_angle),
            float(varlik.dxf.end_angle),
        )
        return [HamVarlik(tur="yay", katman=katman, noktalar=P(pts), renk=renk)]

    if tur in ("TEXT", "ATTRIB"):
        try:
            ekle = varlik.dxf.insert
            konum = (ekle.x, ekle.y)
        except Exception:  # pragma: no cover
            konum = (0.0, 0.0)
        metin = _metni_temizle(str(varlik.dxf.text))
        if not metin.strip():
            return []
        return [
            HamVarlik(
                tur="metin",
                katman=katman,
                noktalar=P([konum]),
                metin=metin,
                yazi_yuksekligi=float(getattr(varlik.dxf, "height", 0.0)) * carpan,
                renk=renk,
            )
        ]

    if tur == "MTEXT":
        try:
            konum = (varlik.dxf.insert.x, varlik.dxf.insert.y)
        except Exception:  # pragma: no cover
            konum = (0.0, 0.0)
        metin = _metni_temizle(varlik.text)
        if not metin.strip():
            return []
        return [
            HamVarlik(
                tur="metin",
                katman=katman,
                noktalar=P([konum]),
                metin=metin,
                yazi_yuksekligi=float(getattr(varlik.dxf, "char_height", 0.0)) * carpan,
                renk=renk,
            )
        ]

    if tur == "HATCH":
        cikti: list[HamVarlik] = []
        try:
            for yol in varlik.paths:
                pts: list[tuple[float, float]] = []
                if hasattr(yol, "vertices"):
                    pts = [(v[0], v[1]) for v in yol.vertices]
                elif hasattr(yol, "edges"):
                    for kenar in yol.edges:
                        if hasattr(kenar, "start"):
                            pts.append((kenar.start[0], kenar.start[1]))
                if len(pts) >= 3:
                    cikti.append(
                        HamVarlik(
                            tur="tarama",
                            katman=katman,
                            noktalar=P(pts),
                            kapali=True,
                            renk=renk,
                        )
                    )
        except Exception:  # pragma: no cover
            return []
        return cikti

    if tur in ("SOLID", "TRACE"):
        try:
            pts = [
                (varlik.dxf.vtx0.x, varlik.dxf.vtx0.y),
                (varlik.dxf.vtx1.x, varlik.dxf.vtx1.y),
                (varlik.dxf.vtx3.x, varlik.dxf.vtx3.y),
                (varlik.dxf.vtx2.x, varlik.dxf.vtx2.y),
            ]
        except Exception:  # pragma: no cover
            return []
        return [
            HamVarlik(
                tur="poligon", katman=katman, noktalar=P(pts), kapali=True, renk=renk
            )
        ]

    if tur == "INSERT" and derinlik < MAX_BLOK_DERINLIGI:
        cikti = []
        try:
            for alt in varlik.virtual_entities():
                cikti.extend(_varligi_cevir(alt, carpan, derinlik + 1))
        except Exception:  # pragma: no cover - bozuk blok tanimlari
            return []
        # Blok icindeki varliklarin katmani "0" ise INSERT'in katmanini devral
        for v in cikti:
            if v.katman in ("", "0"):
                v.katman = katman
        return cikti

    return []


def dxf_birimi(doc, ayarlar: Ayarlar) -> tuple[str, list[str]]:
    """Cizim birimini belirler. Dondurur: (birim, notlar)."""
    notlar: list[str] = []
    kod = 0
    try:
        kod = int(doc.header.get("$INSUNITS", 0))
    except Exception:  # pragma: no cover
        kod = 0
    dxf_birim = DXF_INSUNITS.get(kod, "")
    ayar_birim = ayarlar.birim
    if dxf_birim:
        if dxf_birim != ayar_birim:
            notlar.append(
                f"DXF basligindaki birim ($INSUNITS={kod}) '{dxf_birim}'; "
                f"yapilandirmadaki '{ayar_birim}' yerine bu kullanildi. "
                f"Yanlissa --birim ile ezin."
            )
        return dxf_birim, notlar
    notlar.append(
        f"DXF dosyasinda birim tanimi yok ($INSUNITS=0); yapilandirmadaki "
        f"'{ayar_birim}' varsayildi. Olculer tutmuyorsa --birim ile degistirin."
    )
    return ayar_birim, notlar


def dxf_oku(yol: str | Path, ayarlar: Ayarlar) -> Cizim:
    """Bir DXF dosyasini okuyup normalize edilmis Cizim dondurur."""
    p = Path(yol)
    try:
        doc = ezdxf.readfile(str(p))
    except ezdxf.DXFStructureError as e:
        try:
            from ezdxf import recover

            doc, denetim = recover.readfile(str(p))
        except Exception:
            raise ValueError(
                f"DXF okunamadi: {p.name}. Dosya bozuk olabilir. Ozgun hata: {e}"
            ) from e
    except UnicodeDecodeError:
        from ezdxf import recover

        doc, _ = recover.readfile(str(p))

    birim, notlar = dxf_birimi(doc, ayarlar)
    carpan = birim_carpani(birim)

    varliklar: list[HamVarlik] = []
    msp = doc.modelspace()
    for varlik in msp:
        try:
            varliklar.extend(_varligi_cevir(varlik, carpan))
        except Exception as e:  # pragma: no cover
            notlar.append(f"{varlik.dxftype()} varligi atlandi: {e}")

    if not varliklar:
        notlar.append(
            "Model uzayinda cizim varligi bulunamadi. Cizim paper space'te "
            "olabilir; AutoCAD'de model uzayina tasiyip tekrar deneyin."
        )
    else:
        _plan_boyutunu_dogrula(varliklar, p.name, ayarlar)

    return Cizim(varliklar=varliklar, kaynak=str(p), birim=birim, notlar=notlar)


def _plan_boyutunu_dogrula(
    varliklar: list, dosya_adi: str, ayarlar: Ayarlar
) -> None:
    """Geometrinin gercekci bir plan boyutunda oldugunu dogrular.

    LibreDWG ile cevrilen bazı DWG'ler (Sta4CAD gibi) model uzayina yalnizca
    kucuk bir kirpilmis parca dusurur; boyle bir dosyadan metraj cikarmak
    anlamsizdir. Bu durumda net bir hata verilir.
    """
    esik = float(ayarlar.al("dxf.min_plan_boyutu", 1.0))
    if esik <= 0:
        return
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    for v in varliklar:
        if v.tur == "metin":
            continue
        for n in v.noktalar:
            min_x = min(min_x, n.x)
            min_y = min(min_y, n.y)
            max_x = max(max_x, n.x)
            max_y = max(max_y, n.y)
    if min_x == float("inf"):
        return
    en = max_x - min_x
    boy = max_y - min_y
    if en < esik and boy < esik:
        raise ValueError(
            f"{dosya_adi} icinden okunabilir plan geometrisi cikmadi: "
            f"boyut yalnizca {en:.2f} x {boy:.2f} m. Bu dosya kirpilmis bir "
            f"gorsel/parca olabilir veya LibreDWG cevirimi kayipli olabilir. "
            f"Kalip planinin PDF surumunu yukleyin veya DXF'e AutoCAD "
            f"(ODA) uzerinden kaydedip tekrar deneyin."
        )


def dxf_katman_dokumu(yol: str | Path) -> list[tuple[str, int]]:
    """Bir DXF'teki katmanlari ve varlik sayilarini dondurur (tani amacli)."""
    doc = ezdxf.readfile(str(yol))
    sayac: dict[str, int] = {}
    for varlik in doc.modelspace():
        ad = str(getattr(varlik.dxf, "layer", ""))
        sayac[ad] = sayac.get(ad, 0) + 1
    return sorted(sayac.items(), key=lambda kv: -kv[1])
