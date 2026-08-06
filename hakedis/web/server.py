"""hakedis web arayuzu: FastAPI arka ucu.

DWG/DXF/PDF dosyasi yuklenir, yapilandirma formdan verilir, metraj
(veya cok katli `toplu`) calistirilir; sonuc JSON, SVG kontrol paftasi ve
base64-encoded Excel olarak dondurulur. Statik arayuz `web/static`
altinda tek sayfa olarak sunulur.
"""

from __future__ import annotations

import base64
import json
import re
import sys
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from hakedis import __version__
from hakedis.config import (
    VARSAYILAN_YOL,
    ayarlari_json_ile,
    ayarlari_yaml_metinden,
    varsayilan_ayarlar,
)

STATIK_YOL = Path(__file__).parent / "static"

app = FastAPI(title="hakedis", version=__version__)

if STATIK_YOL.exists():
    app.mount("/static", StaticFiles(directory=STATIK_YOL), name="static")


# ---------------------------------------------------------------------------
# Yardimcilar
# ---------------------------------------------------------------------------


def _ondalik(deger: str | None, alan: str) -> float | None:
    if deger in (None, ""):
        return None
    try:
        return float(deger.replace(",", "."))
    except ValueError:
        raise HTTPException(
            422, f"'{alan}' sayisal olmali, '{deger}' verildi."
        )


def _ayarlari_kur(ayarlar: str | None, yaml_metni: str | None) -> object:
    """Form alanlarindan Ayarlar nesnesi uretir (JSON veya YAML metni)."""
    if yaml_metni and yaml_metni.strip():
        return ayarlari_yaml_metinden(yaml_metni)
    try:
        veri = json.loads(ayarlar) if ayarlar else None
    except json.JSONDecodeError as e:
        raise HTTPException(422, f"ayarlar JSON cozulemedi: {e}")
    return ayarlari_json_ile(veri)


def _ezmeleri_uygula(ayarlar, form: dict) -> object:
    """CLI'daki --kat-yuksekligi vb. ezmelerin web karsiligi."""
    ayarlar = ayarlar.guncelle(
        birim=form.get("birim") or None,
        kat_adi=form.get("kat_adi") or None,
        kat_yuksekligi=_ondalik(form.get("kat_yuksekligi"), "kat_yuksekligi"),
        doseme_kalinligi=_ondalik(form.get("doseme_kalinligi"), "doseme_kalinligi"),
        olcek=form.get("olcek") or None,
        sayfa=_sayfa_int(form.get("sayfa")),
    )
    kalibre = (form.get("kalibre") or "").strip()
    if kalibre:
        m = re.match(r"^\s*([\d.]+)\s*:\s*([\d.]+)\s*$", kalibre)
        if not m:
            raise HTTPException(
                422, f"kalibre bicimi hatali: {kalibre!r}. Beklenen: 340.5:6.00"
            )
        ayarlar.ham.setdefault("pdf", {})["kalibrasyon"] = {
            "pdf_mesafe": float(m.group(1)),
            "gercek_mesafe": float(m.group(2)),
        }
    return ayarlar


def _sayfa_int(deger: str | None) -> int | None:
    if deger in (None, ""):
        return None
    try:
        return int(deger)
    except ValueError:
        raise HTTPException(422, f"'sayfa' tam sayi olmali, '{deger}' verildi.")


# Metraja girme ihtimali dusuk olan yaygin katman parcalari (olcu, tarama,
# pencere/dograma, donati vb.) icin onerilen "yoksay" eslesmesi.
YOKSAY_KATMAN_ISARETLERI = (
    "OLCU", "OLCULENDIR", "DIM", "TARAMA", "HATCH", "ANTET", "CERCEVE",
    "PENC", "PENH", "PEND", "KAPI", "DOGRAMA", "DONATI", "AKS", "KOTA",
    "KILAVUZ", "TEXT",
)


def _katman_onerisi(katman_adi: str) -> str | None:
    """Katman adina gore metraja girmemesi onerilecek tipi dondurur."""
    buyuk = (katman_adi or "").upper()
    if not buyuk:
        return None
    if any(isaret in buyuk for isaret in YOKSAY_KATMAN_ISARETLERI):
        return "yoksay"
    return None


def _dosya_uzantisi(ad: str) -> str:
    """Dosya adindan uzantiyi ayiklar (bosluk sonrasi ekleri yok sayar).

    'istinat.dwg 2' gibi isimlerde Path.suffix '.dwg 2' doner; gercek
    uzanti ilk bosluga kadardir.
    """
    ad = (ad or "").strip()
    son_dot = ad.rfind(".")
    if son_dot == -1:
        return ""
    return ad[son_dot:].split()[0].lower()


async def _kaydet(dosya: UploadFile) -> str:
    """Yuklenen dosyayi gecici bir yola yazar, yolunu dondurur."""
    uzanti = _dosya_uzantisi(dosya.filename or "")
    if uzanti not in (".dwg", ".dxf", ".pdf"):
        raise HTTPException(
            422,
            f"Desteklenmeyen dosya turu: {uzanti or '?'}. "
            "Desteklenenler: .dwg, .dxf, .pdf",
        )
    with tempfile.NamedTemporaryFile(
        suffix=uzanti, delete=False
    ) as tmp:
        tmp.write(await dosya.read())
        yol = tmp.name
    return yol


def _excel_b64(sonuc, toplu: bool = False, ayarlar=None) -> str:
    from hakedis.report import excel_yaz, excel_yaz_toplu

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        yol = tmp.name
    try:
        if toplu:
            excel_yaz_toplu(sonuc, yol, ayarlar=ayarlar)
        else:
            excel_yaz(sonuc, yol, ayarlar=ayarlar)
        return base64.b64encode(Path(yol).read_bytes()).decode("ascii")
    finally:
        Path(yol).unlink(missing_ok=True)


def _svg_metni(sonuc) -> str:
    from hakedis.report.svg import svg_metni

    return svg_metni(sonuc)


def _bagimlilik_ozeti() -> list[dict]:
    sonuc: list[dict] = []
    for ad, paket in (
        ("ezdxf (DXF)", "ezdxf"),
        ("shapely (geometri)", "shapely"),
        ("numpy", "numpy"),
        ("openpyxl (Excel)", "openpyxl"),
        ("pdfplumber (PDF)", "pdfplumber"),
        ("PyYAML", "yaml"),
    ):
        try:
            modul = __import__(paket)
            sonuc.append({"ad": ad, "tamam": True, "surum": getattr(modul, "__version__", "?")})
        except ImportError:
            sonuc.append({"ad": ad, "tamam": False, "surum": ""})
    try:
        from hakedis.readers.dwg import donusturucu_bul

        bulunan = donusturucu_bul()
        if bulunan:
            sonuc.append({"ad": f"DWG donusturucu ({bulunan[0]})", "tamam": True, "surum": str(bulunan[1])})
        else:
            sonuc.append({"ad": "DWG donusturucu", "tamam": False, "surum": "kurulu degil"})
    except Exception as e:  # noqa: BLE001
        sonuc.append({"ad": "DWG donusturucu", "tamam": False, "surum": str(e)})
    return sonuc


# ---------------------------------------------------------------------------
# Sayfalar
# ---------------------------------------------------------------------------


@app.get("/", response_class=HTMLResponse)
def anasayfa() -> str:
    if not STATIK_YOL.exists():
        raise HTTPException(500, "Statik arayuz dosyalari bulunamadi.")
    return (STATIK_YOL / "index.html").read_text(encoding="utf-8")


@app.get("/api/durum")
def durum() -> dict:
    return {
        "versiyon": __version__,
        "python": sys.version.split()[0],
        "bagimliliklar": _bagimlilik_ozeti(),
        "varsayilan": varsayilan_ayarlar().ham,
    }


@app.get("/api/varsayilan")
def varsayilan() -> dict:
    return {
        "versiyon": __version__,
        "varsayilan_yaml": VARSAYILAN_YOL.read_text(encoding="utf-8"),
        "varsayilan": varsayilan_ayarlar().ham,
    }


# ---------------------------------------------------------------------------
# YAML <-> JSON (ayarlar sekmesinin ileri yoneticisi)
# ---------------------------------------------------------------------------


@app.post("/api/yaml-coz")
async def yaml_coz(body: dict) -> dict:
    metin = body.get("yaml") or ""
    try:
        ayarlar = ayarlari_yaml_metinden(metin)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"YAML cozulemedi: {e}")
    return {"ok": True, "ayarlar": ayarlar.ham}


@app.post("/api/yaml-uret")
async def yaml_uret(body: dict) -> dict:
    import yaml

    veri = body.get("ayarlar")
    if not isinstance(veri, dict):
        raise HTTPException(422, "ayarlar sozluk olmali")
    try:
        metin = yaml.safe_dump(veri, allow_unicode=True, sort_keys=False)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"YAML uretilemedi: {e}")
    return {"ok": True, "yaml": metin}


# ---------------------------------------------------------------------------
# Metraj
# ---------------------------------------------------------------------------


@app.post("/api/metraj")
async def metraj(
    dosya: UploadFile = File(...),
    ayarlar: str | None = Form(None),
    yaml: str | None = Form(None),
    kat_adi: str | None = Form(None),
    kat_yuksekligi: str | None = Form(None),
    doseme_kalinligi: str | None = Form(None),
    birim: str | None = Form(None),
    olcek: str | None = Form(None),
    sayfa: str | None = Form(None),
    kalibre: str | None = Form(None),
) -> dict:
    from hakedis.metraj import plandan_metraj

    ezmeler = {
        "kat_adi": kat_adi,
        "kat_yuksekligi": kat_yuksekligi,
        "doseme_kalinligi": doseme_kalinligi,
        "birim": birim,
        "olcek": olcek,
        "sayfa": sayfa,
        "kalibre": kalibre,
    }
    ayarlar_nesnesi = _ezmeleri_uygula(_ayarlari_kur(ayarlar, yaml), ezmeler)
    yol = await _kaydet(dosya)
    try:
        sonuc, _ = plandan_metraj(yol, ayarlar_nesnesi)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Metraj uretilemedi: {e}")
    finally:
        Path(yol).unlink(missing_ok=True)

    from hakedis.maliyet import maliyet_hesapla
    from hakedis.report.veri import sonuc_verisi

    paket = sonuc_verisi(sonuc)
    if ayarlar_nesnesi.al("maliyet.aktif", False):
        paket["maliyet"] = maliyet_hesapla(sonuc, ayarlar_nesnesi)
    paket["svg"] = _svg_metni(sonuc)
    paket["excel_b64"] = _excel_b64(sonuc, ayarlar=ayarlar_nesnesi)
    return paket


# ---------------------------------------------------------------------------
# Toplu (cok katli / cok paftali)
# ---------------------------------------------------------------------------


@app.post("/api/toplu")
async def toplu(
    dosyalar: list[UploadFile] = File(...),
    kat_adlari: str | None = Form(None),
    ayarlar: str | None = Form(None),
    yaml: str | None = Form(None),
    kat_yuksekligi: str | None = Form(None),
    doseme_kalinligi: str | None = Form(None),
    birim: str | None = Form(None),
    olcek: str | None = Form(None),
    kalibre: str | None = Form(None),
) -> dict:
    from hakedis.metraj import plandan_metraj

    if not dosyalar:
        raise HTTPException(422, "En az bir dosya yukleyin.")
    ezmeler = {
        "kat_yuksekligi": kat_yuksekligi,
        "doseme_kalinligi": doseme_kalinligi,
        "birim": birim,
        "olcek": olcek,
        "kalibre": kalibre,
    }
    ayarlar_nesnesi = _ezmeleri_uygula(_ayarlari_kur(ayarlar, yaml), ezmeler)

    adlar: list[str] = []
    if kat_adlari:
        try:
            adlar = json.loads(kat_adlari)
        except json.JSONDecodeError:
            adlar = [p.strip() for p in kat_adlari.split(",") if p.strip()]

    sonuclar = []
    gecici: list[str] = []
    try:
        for i, d in enumerate(dosyalar):
            yol = await _kaydet(d)
            gecici.append(yol)
            kat = adlar[i] if i < len(adlar) else Path(d.filename or "").stem
            sonuc, _ = plandan_metraj(yol, ayarlar_nesnesi.guncelle(kat_adi=kat))
            sonuclar.append(sonuc)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Toplu metraj uretilemedi: {e}")
    finally:
        for yol in gecici:
            Path(yol).unlink(missing_ok=True)

    from hakedis.maliyet import maliyet_hesapla
    from hakedis.metraj import sonuclari_birlestir
    from hakedis.report.veri import toplu_verisi

    paket = toplu_verisi(sonuclar)
    if ayarlar_nesnesi.al("maliyet.aktif", False):
        paket["maliyet"] = maliyet_hesapla(
            sonuclari_birlestir(sonuclar), ayarlar_nesnesi
        )
        paket["kat_maliyetleri"] = [
            {
                "kat": s.kat or "?",
                "ara_toplam": m["ara_toplam"],
                "kdv": m["kdv"],
                "genel_toplam": m["genel_toplam"],
                "fiyatsiz_pozlar": m["fiyatsiz_pozlar"],
            }
            for s in sonuclar
            for m in [maliyet_hesapla(s, ayarlar_nesnesi)]
        ]
    paket["excel_b64"] = _excel_b64(sonuclar, toplu=True, ayarlar=ayarlar_nesnesi)
    return paket


# ---------------------------------------------------------------------------
# Eslestirme (renk/katman -> tip arayuzu)
# ---------------------------------------------------------------------------


@app.post("/api/esle-tara")
async def esle_tara(
    dosya: UploadFile = File(...),
    ayarlar: str | None = Form(None),
    sayfa: str | None = Form(None),
) -> dict:
    """Dosyadaki renk (PDF) veya katman (DXF/DWG) adaylarini listeler.

    Kullanici her adayi bir eleman tipine baglar; arayuz `pdf.renk_esleme`
    veya `katmanlar.kesin` uretir. Bu uclu, 'pdf.renk_esleme bos' gibi
    uyarilarin yerine gorsel eslestirme sunar.
    """
    from hakedis.readers import cizim_oku
    from hakedis.readers.pdf import (
        TERS_TIP_KATMANI,
        _katman_ata,
        renk_esleme_adaylari,
    )

    ayarlar_nesnesi = _ayarlari_kur(ayarlar, None)
    sayfa_no = _sayfa_int(sayfa)
    if sayfa_no is not None:
        ayarlar_nesnesi.ham.setdefault("pdf", {})["sayfa"] = sayfa_no

    yol = await _kaydet(dosya)
    uzanti = _dosya_uzantisi(dosya.filename or yol)
    try:
        if uzanti == ".pdf":
            adaylar = renk_esleme_adaylari(yol, sayfa_no or 1)
            sta4cad_renkler = [
                str(r).lower()
                for r in (ayarlar_nesnesi.al("pdf.sta4cad_renkler", []) or [])
            ]
            for aday in adaylar:
                katman = _katman_ata(aday["anahtar"], 0.0, ayarlar_nesnesi)
                aday["suanki_tip"] = TERS_TIP_KATMANI.get(katman)
                aday["oneri_tip"] = (
                    "yoksay"
                    if aday["anahtar"].lower() in sta4cad_renkler
                    and aday["suanki_tip"] is None
                    else None
                )
                aday["ornek_renk"] = aday["anahtar"]
                aday["aciklama"] = (
                    f"kalınlık {aday['kalinliklar']} pt • {aday['turler']}"
                )
            esleme_turu = "renk"
            toplam_adet = sum(a["adet"] for a in adaylar)
        else:
            # Inceleme modu: kirpilmis/bozuk DWG'lerde bile katman listesi
            # gosterilir; boyut dogrulamasi yalnizca METRAJ icindir.
            ayarlar_nesnesi.ham.setdefault("dxf", {})["min_plan_boyutu"] = 0
            cizim = cizim_oku(yol, ayarlar_nesnesi)
            adaylar = []
            for katman_adi, adet in cizim.katmanlar().items():
                adaylar.append(
                    {
                        "anahtar": katman_adi,
                        "adet": adet,
                        "suanki_tip": ayarlar_nesnesi.katman_tipi(katman_adi),
                        "oneri_tip": _katman_onerisi(katman_adi),
                        "ornek_renk": None,
                        "aciklama": "",
                    }
                )
            adaylar.sort(key=lambda a: -a["adet"])
            esleme_turu = "katman"
            toplam_adet = sum(a["adet"] for a in adaylar)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Plan incelenemedi: {e}")
    finally:
        Path(yol).unlink(missing_ok=True)

    eslenmeyen_adet = sum(
        a["adet"] for a in adaylar if a["suanki_tip"] is None
    )
    return {
        "tur": esleme_turu,
        "dosya": dosya.filename or "",
        "toplam_adet": toplam_adet,
        "eslenmeyen_adet": eslenmeyen_adet,
        "adaylar": adaylar,
    }


# ---------------------------------------------------------------------------
# PDF inceleme
# ---------------------------------------------------------------------------


@app.post("/api/pdf-incele")
async def pdf_incele(
    dosya: UploadFile = File(...),
    sayfa: str | None = Form(None),
) -> dict:
    from hakedis.readers.pdf import pdf_incele as pdf_incele_f

    sayfa_no = _sayfa_int(sayfa) or 1
    yol = await _kaydet(dosya)
    try:
        return pdf_incele_f(yol, sayfa_no)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"PDF incelenemedi: {e}")
    finally:
        Path(yol).unlink(missing_ok=True)
