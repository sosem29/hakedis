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


async def _kaydet(dosya: UploadFile) -> str:
    """Yuklenen dosyayi gecici bir yola yazar, yolunu dondurur."""
    uzanti = Path(dosya.filename or "").suffix.lower()
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


def _excel_b64(sonuc, toplu: bool = False) -> str:
    from hakedis.report import excel_yaz, excel_yaz_toplu

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        yol = tmp.name
    try:
        if toplu:
            excel_yaz_toplu(sonuc, yol)
        else:
            excel_yaz(sonuc, yol)
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

    from hakedis.report.veri import sonuc_verisi

    paket = sonuc_verisi(sonuc)
    paket["svg"] = _svg_metni(sonuc)
    paket["excel_b64"] = _excel_b64(sonuc)
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

    from hakedis.report.veri import toplu_verisi

    paket = toplu_verisi(sonuclar)
    paket["excel_b64"] = _excel_b64(sonuclar, toplu=True)
    return paket


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
