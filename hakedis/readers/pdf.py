"""PDF okuyucu (pdfplumber tabanli).

PDF'te katman kavrami yoktur; bu yuzden DXF'e gore daha az bilgi vardir.
Iki seyi disaridan almak gerekir:

  1. OLCEK  - PDF birimi punto'dur (1 pt = 1/72 inc). Gercek boyu bulmak icin
              paftanin olcegi (1/50 gibi) ya da bilinen iki nokta arasi
              gercek mesafe (kalibrasyon) gerekir.
  2. SINIFLANDIRMA - Eleman tipi cizgi rengi/kalinligi ile eslenir. Once
              `hakedis pdf-incele plan.pdf` calistirip paftadaki gercek
              renkleri gorun, sonra yapilandirmadaki `pdf.renk_esleme`yi
              doldurun.

Yalnizca VEKTOR PDF'ler okunabilir. Taranmis (raster/goruntu) PDF'lerde
cizgi verisi yoktur; bu durumda acik bir hata verilir.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from hakedis.config import Ayarlar, olcegi_coz
from hakedis.model import Cizim, HamVarlik, Nokta

# 1 PDF puntosu kac milimetre kagit eder
MM_PER_PT = 25.4 / 72.0

# renk_esleme degerlerinin karsilik geldigi standart katman adlari
TIP_KATMANI: dict[str, str] = {
    "kolon": "KOLON",
    "perde": "PERDE",
    "kiris": "KIRIS",
    "doseme": "DOSEME",
    "bosluk": "BOSLUK",
    "merdiven": "MERDIVEN",
    "yoksay": "AKS-YOKSAY",
}

# TIP_KATMANI'nin tersi: katman adindan esleme tipini bulmak icin
TERS_TIP_KATMANI: dict[str, str] = {v: k for k, v in TIP_KATMANI.items()}

ISIM_RENKLERI: dict[str, str] = {
    "siyah": "#000000",
    "beyaz": "#ffffff",
    "kirmizi": "#ff0000",
    "yesil": "#00ff00",
    "mavi": "#0000ff",
    "sari": "#ffff00",
    "camgobegi": "#00ffff",
    "macenta": "#ff00ff",
    "gri": "#808080",
}


def renk_normalize(renk: Any) -> str:
    """pdfplumber renk degerini '#rrggbb' bicimine cevirir."""
    if renk is None:
        return "#000000"
    if isinstance(renk, str):
        d = renk.strip().lower()
        if d in ISIM_RENKLERI:
            return ISIM_RENKLERI[d]
        if d.startswith("#") and len(d) == 7:
            return d
        return "#000000"
    if isinstance(renk, (int, float)):
        g = max(0, min(255, int(round(float(renk) * 255))))
        return f"#{g:02x}{g:02x}{g:02x}"
    try:
        bilesenler = [float(x) for x in renk]
    except (TypeError, ValueError):
        return "#000000"
    if len(bilesenler) == 1:
        g = max(0, min(255, int(round(bilesenler[0] * 255))))
        return f"#{g:02x}{g:02x}{g:02x}"
    if len(bilesenler) == 3:
        r, g, b = (max(0, min(255, int(round(v * 255)))) for v in bilesenler)
        return f"#{r:02x}{g:02x}{b:02x}"
    if len(bilesenler) == 4:  # CMYK
        c, m, y, k = bilesenler
        r = max(0, min(255, int(round(255 * (1 - c) * (1 - k)))))
        g = max(0, min(255, int(round(255 * (1 - m) * (1 - k)))))
        b = max(0, min(255, int(round(255 * (1 - y) * (1 - k)))))
        return f"#{r:02x}{g:02x}{b:02x}"
    return "#000000"


def olcek_carpani(ayarlar: Ayarlar) -> tuple[float, str]:
    """PDF puntosunu metreye ceviren carpani hesaplar.

    Kalibrasyon verilmisse (pdf.kalibrasyon.pdf_mesafe / gercek_mesafe) o
    kullanilir; yoksa pafta olceginden hesaplanir.
    """
    kal = ayarlar.al("pdf.kalibrasyon")
    if isinstance(kal, dict) and kal.get("pdf_mesafe") and kal.get("gercek_mesafe"):
        pdf_m = float(kal["pdf_mesafe"])
        gercek = float(kal["gercek_mesafe"])
        if pdf_m <= 0:
            raise ValueError("Kalibrasyondaki pdf_mesafe sifirdan buyuk olmali")
        carpan = gercek / pdf_m
        return carpan, (
            f"iki nokta kalibrasyonu: {pdf_m:.2f} pt = {gercek:.3f} m "
            f"(1 pt = {carpan:.6f} m)"
        )
    olcek = olcegi_coz(ayarlar.al("pdf.olcek", "1/50"))
    carpan = MM_PER_PT * olcek / 1000.0
    return carpan, f"pafta olcegi 1/{olcek:g} (1 pt = {carpan:.6f} m)"


def _katman_ata(
    renk: str, kalinlik: float, ayarlar: Ayarlar, esleme: dict | None = None
) -> str:
    """Renk/kalinliktan katman adi turetir."""
    if esleme is None:
        esleme = ayarlar.al("pdf.renk_esleme", {}) or {}
    for anahtar, tip in esleme.items():
        if renk_normalize(anahtar) == renk:
            return TIP_KATMANI.get(str(tip).lower(), str(tip).upper())
    return f"PDF-{renk}-w{kalinlik:.2f}"


def _sta4cad_deseni_yogun_mu(
    kisa_cizgi: int, toplam_cizgi: int, ayarlar: Ayarlar
) -> bool:
    """Sta4CAD dolgu deseni (cok sayida kisa blok/kirisçik cizgisi) var mi."""
    esik = float(ayarlar.al("pdf.sta4cad_kisa_cizgi_orani", 0.40))
    if toplam_cizgi <= 0 or (kisa_cizgi / toplam_cizgi) < esik:
        return False
    return bool(ayarlar.al("pdf.sta4cad_otomatik", True))


def _sta4cad_tespit_esleme(
    esleme: dict, kisa_cizgi: int, toplam_cizgi: int, ayarlar: Ayarlar
) -> dict:
    """Sta4CAD ciktilarinda dolgu (hatch) renkleri icin varsayilan esleme.

    Sta4CAD kalip/temel planlarinda betonarme elemanlarin dolgusu kirmizi,
    kiriscik/tarama yesil cizgilerle cizilir; geometriyi kapali poligon
    olarak degil yuzlerce kucuk parca olarak verir. Bu desen sezgisel tespite
    gurultu olarak yansir; dolgu renkleri varsayilan olarak yok sayilir.
    Kullanici bir rengi zaten bir tipe bagladiysa secimine dokunulmaz.
    """
    if not _sta4cad_deseni_yogun_mu(kisa_cizgi, toplam_cizgi, ayarlar):
        return esleme
    otomatik = dict(esleme)
    for renk in ayarlar.al("pdf.sta4cad_renkler", ["#ff0000", "#269900"]) or []:
        otomatik.setdefault(str(renk).lower(), "yoksay")
    return otomatik


def _nokta_listesi(nesne: dict, carpan: float) -> list[Nokta]:
    """pdfplumber nesnesinden kose noktalarini metre cinsinden cikarir."""
    tur = nesne.get("object_type")
    if tur == "line":
        return [
            Nokta(float(nesne["x0"]) * carpan, float(nesne["y0"]) * carpan),
            Nokta(float(nesne["x1"]) * carpan, float(nesne["y1"]) * carpan),
        ]
    if tur == "rect":
        x0 = float(nesne["x0"]) * carpan
        x1 = float(nesne["x1"]) * carpan
        y0 = float(nesne["y0"]) * carpan
        y1 = float(nesne["y1"]) * carpan
        return [Nokta(x0, y0), Nokta(x1, y0), Nokta(x1, y1), Nokta(x0, y1)]
    if tur == "curve":
        pts = nesne.get("pts") or []
        return [Nokta(float(p[0]) * carpan, float(p[1]) * carpan) for p in pts]
    return []


def pdf_oku(yol: str | Path, ayarlar: Ayarlar) -> Cizim:
    """Vektor PDF'ten normalize edilmis Cizim uretir."""
    try:
        import pdfplumber
    except ImportError as e:  # pragma: no cover
        raise RuntimeError(
            "PDF okumak icin pdfplumber gerekli: pip install pdfplumber"
        ) from e

    p = Path(yol)
    carpan, olcek_aciklama = olcek_carpani(ayarlar)
    sayfa_no = int(ayarlar.al("pdf.sayfa", 1))
    min_kalinlik = float(ayarlar.al("pdf.min_cizgi_kalinligi", 0.0) or 0.0)
    metin_oku = bool(ayarlar.al("pdf.metin_oku", True))
    kisa_esik_pt = float(ayarlar.al("pdf.asmolen_kisa_cizgi_pt", 10.0))

    notlar = [
        f"PDF olcegi: {olcek_aciklama}. Yanlissa --olcek veya "
        f"--kalibre ile duzeltin.",
        "PDF'te katman bilgisi yoktur; eleman tipleri renk eslemesi ve "
        "geometrik sezgisellerle belirlenir. Kontrol paftasini (--svg) "
        "mutlaka inceleyin.",
    ]
    varliklar: list[HamVarlik] = []

    with pdfplumber.open(str(p)) as pdf:
        if sayfa_no < 1 or sayfa_no > len(pdf.pages):
            raise ValueError(
                f"Sayfa {sayfa_no} yok; PDF {len(pdf.pages)} sayfa iceriyor. "
                f"--sayfa ile secin."
            )
        sayfa = pdf.pages[sayfa_no - 1]

        # Asmolen deseni icin once kisa cizgi yogunlugu olculur (punto ile)
        kisa_cizgi = 0
        toplam_cizgi = 0
        for tur_adi in ("lines", "rects", "curves"):
            for nesne in getattr(sayfa, tur_adi, []) or []:
                toplam_cizgi += 1
                uzunluk = abs(
                    float(nesne.get("x1", 0.0)) - float(nesne.get("x0", 0.0))
                ) + abs(float(nesne.get("bottom", 0.0)) - float(nesne.get("top", 0.0)))
                if uzunluk < kisa_esik_pt:
                    kisa_cizgi += 1

        renk_esleme = ayarlar.al("pdf.renk_esleme", {}) or {}
        sta4cad_tespit = _sta4cad_tespit_esleme(
            renk_esleme, kisa_cizgi, toplam_cizgi, ayarlar
        )
        sta4cad_pasif = False
        dolgu_renkleri = [
            str(r).lower()
            for r in (ayarlar.al("pdf.sta4cad_renkler", ["#ff0000", "#269900"]) or [])
        ]
        if sta4cad_tespit.get("#ff0000") == "yoksay" and _sta4cad_deseni_yogun_mu(
            kisa_cizgi, toplam_cizgi, ayarlar
        ):
            if sta4cad_tespit != renk_esleme:
                notlar.append(
                    "Sta4CAD dolgu deseni algilandi: kirmizi/yesil hatch "
                    "cizgileri blok/tarama deseni sayilarak yok sayildi. "
                    "Buyuk kapali alanlar doseme olarak sezgisel tespit edilir; "
                    "kolon/kiris/perde geometrisi bu PDF'te dolgu oldugundan "
                    "guvenilir metraj cikmaz. Kesin sonuc icin DWG dosyasini "
                    "veya Eslestirme sekmesini kullanin."
                )
            renk_esleme = sta4cad_tespit
            sta4cad_pasif = True

        for tur_adi in ("lines", "rects", "curves"):
            for nesne in getattr(sayfa, tur_adi, []) or []:
                kalinlik = float(nesne.get("linewidth") or 0.0)
                if min_kalinlik and kalinlik < min_kalinlik:
                    continue
                noktalar = _nokta_listesi(nesne, carpan)
                if len(noktalar) < 2:
                    continue
                renk = renk_normalize(
                    nesne.get("stroking_color") or nesne.get("non_stroking_color")
                )
                katman = _katman_ata(renk, kalinlik, ayarlar, renk_esleme)
                kapali = tur_adi == "rects" or bool(nesne.get("fill")) and len(
                    noktalar
                ) >= 3
                varliklar.append(
                    HamVarlik(
                        tur="poligon" if kapali else "cizgi",
                        katman=katman,
                        noktalar=noktalar,
                        kapali=kapali,
                        renk=renk,
                        kalinlik=kalinlik,
                    )
                )

        donati_isaretli = 0
        donati_toplam = 0
        if metin_oku:
            try:
                kelimeler = sayfa.extract_words(
                    keep_blank_chars=False, use_text_flow=False
                )
            except Exception:  # pragma: no cover
                kelimeler = []
            # Kelime nesnelerinde koordinat tepeden olculur; cizgilerle ayni
            # eksen takimina getirmek icin sayfa yuksekliginden cikarilir.
            sayfa_yuksekligi = float(sayfa.height)
            for k in _kelimeleri_birlestir(kelimeler):
                donati_toplam += 1
                if _donati_etiketi_mi(str(k["text"])):
                    donati_isaretli += 1
                y_alt = sayfa_yuksekligi - float(k["bottom"])
                varliklar.append(
                    HamVarlik(
                        tur="metin",
                        katman="PDF-YAZI",
                        noktalar=[
                            Nokta(float(k["x0"]) * carpan, y_alt * carpan)
                        ],
                        metin=str(k["text"]),
                        yazi_yuksekligi=float(k.get("height", 0.0)) * carpan,
                    )
                )
        if donati_toplam:
            oran = donati_isaretli / donati_toplam
            donati_esik = float(ayarlar.al("pdf.donati_etiket_orani", 0.10))
            if oran >= donati_esik:
                notlar.append(
                    f"Paftadaki etiketlerin %{oran * 100:.0f} donati isareti "
                    f"(ƒ/#/@/l=) iceriyor; bu bir donati/kiris detay paftasi "
                    f"olabilir. Kalip metraji icin kalip planini (asmolen_klp "
                    f"gibi) yukleyin."
                )

    cizgi_sayisi = sum(1 for v in varliklar if v.tur != "metin")
    if cizgi_sayisi == 0:
        raise ValueError(
            f"{p.name} icinde vektor cizgi bulunamadi. Bu PDF taranmis "
            f"(goruntu) olabilir. Taranmis paftadan metraj cikarilamaz; "
            f"CAD dosyasini (DWG/DXF) veya vektorel PDF ciktisini kullanin."
        )
    if not renk_esleme:
        notlar.append(
            "pdf.renk_esleme bos; tum cizgiler sezgisel havuza dustu. "
            "Dogruluk icin `hakedis pdf-incele` ile renkleri gorup esleme "
            "tanimlayin."
        )

    nitelikler: dict = {}
    if sta4cad_pasif:
        nitelikler["sta4cad"] = True
        nitelikler["sta4cad_sadece_doseme"] = True
        # Geriye donuk uyumluluk (eski asmolen anahtari)
        nitelikler["asmolen"] = True
        nitelikler["asmolen_sadece_doseme"] = True

    return Cizim(
        varliklar=varliklar,
        kaynak=str(p),
        birim="m",
        olcek=carpan,
        notlar=notlar,
        nitelikler=nitelikler,
    )


def _donati_etiketi_mi(metin: str) -> bool:
    """Donati (demir) etiketi olup olmadigini sezdirir."""
    return any(ch in metin for ch in ("ƒ", "ø", "∅", "#", "@")) or bool(
        re.search(r"\bl\s*=", metin)
    )


def _kelimeleri_birlestir(kelimeler: list[dict], bosluk_esigi: float = 12.0) -> list[dict]:
    """Ayni satirda yan yana duran kelimeleri tek etikete birlestirir.

    "K101" ve "25/50" ayri kelime nesneleri olarak gelir; kesit okumasi icin
    bunlarin tek metin olmasi gerekir.
    """
    if not kelimeler:
        return []
    sirali = sorted(kelimeler, key=lambda k: (round(float(k["top"]), 1), float(k["x0"])))
    cikti: list[dict] = []
    mevcut: dict | None = None
    for k in sirali:
        if (
            mevcut is not None
            and abs(float(k["top"]) - float(mevcut["top"])) < 2.0
            and float(k["x0"]) - float(mevcut["x1"]) < bosluk_esigi
        ):
            mevcut = {
                **mevcut,
                "text": f"{mevcut['text']} {k['text']}",
                "x1": k["x1"],
            }
            cikti[-1] = mevcut
        else:
            mevcut = dict(k)
            cikti.append(mevcut)
    return cikti


def pdf_incele(yol: str | Path, sayfa_no: int = 1) -> dict:
    """Paftadaki renk/kalinlik dagilimini cikarir (renk_esleme yazmak icin)."""
    import pdfplumber

    p = Path(yol)
    ozet: dict[str, dict[str, Any]] = {}
    bilgi: dict[str, Any] = {}
    with pdfplumber.open(str(p)) as pdf:
        bilgi["sayfa_sayisi"] = len(pdf.pages)
        if sayfa_no < 1 or sayfa_no > len(pdf.pages):
            raise ValueError(f"Sayfa {sayfa_no} yok; PDF {len(pdf.pages)} sayfa.")
        sayfa = pdf.pages[sayfa_no - 1]
        bilgi["genislik_pt"] = round(float(sayfa.width), 2)
        bilgi["yukseklik_pt"] = round(float(sayfa.height), 2)
        bilgi["genislik_mm"] = round(float(sayfa.width) * MM_PER_PT, 1)
        bilgi["yukseklik_mm"] = round(float(sayfa.height) * MM_PER_PT, 1)
        bilgi["yazi_sayisi"] = len(sayfa.chars)

        for tur_adi in ("lines", "rects", "curves"):
            for nesne in getattr(sayfa, tur_adi, []) or []:
                renk = renk_normalize(
                    nesne.get("stroking_color") or nesne.get("non_stroking_color")
                )
                kalinlik = round(float(nesne.get("linewidth") or 0.0), 2)
                anahtar = f"{renk} | kalinlik {kalinlik}"
                kutu = ozet.setdefault(
                    anahtar,
                    {
                        "renk": renk,
                        "kalinlik": kalinlik,
                        "adet": 0,
                        "toplam_uzunluk_pt": 0.0,
                        "turler": set(),
                    },
                )
                kutu["adet"] += 1
                kutu["turler"].add(tur_adi)
                try:
                    kutu["toplam_uzunluk_pt"] += abs(
                        float(nesne["x1"]) - float(nesne["x0"])
                    ) + abs(float(nesne["y1"]) - float(nesne["y0"]))
                except Exception:  # pragma: no cover
                    pass

    satirlar = []
    for kutu in ozet.values():
        satirlar.append(
            {
                "renk": kutu["renk"],
                "kalinlik": kutu["kalinlik"],
                "adet": kutu["adet"],
                "toplam_uzunluk_pt": round(kutu["toplam_uzunluk_pt"], 1),
                "turler": ",".join(sorted(kutu["turler"])),
            }
        )
    satirlar.sort(key=lambda s: -s["adet"])
    bilgi["renkler"] = satirlar
    return bilgi


def renk_esleme_adaylari(yol: str | Path, sayfa_no: int = 1) -> list[dict]:
    """renk_esleme arayuzu icin renk bazinda aday listesi uretir.

    pdf_incele'den farkli olarak kalinlik yerine RENK bazinda gruplar; cunku
    pdf.renk_esleme anahtari renktir. Her aday: anahtar (hex renk), adet,
    toplam uzunluk (pt), karsilasilan kalinliklar ve turler.
    """
    import pdfplumber

    p = Path(yol)
    gruplar: dict[str, dict[str, Any]] = {}
    with pdfplumber.open(str(p)) as pdf:
        if sayfa_no < 1 or sayfa_no > len(pdf.pages):
            raise ValueError(f"Sayfa {sayfa_no} yok; PDF {len(pdf.pages)} sayfa.")
        sayfa = pdf.pages[sayfa_no - 1]
        for tur_adi in ("lines", "rects", "curves"):
            for nesne in getattr(sayfa, tur_adi, []) or []:
                renk = renk_normalize(
                    nesne.get("stroking_color") or nesne.get("non_stroking_color")
                )
                kalinlik = round(float(nesne.get("linewidth") or 0.0), 2)
                kutu = gruplar.setdefault(
                    renk,
                    {"renk": renk, "adet": 0, "toplam_pt": 0.0, "kalinliklar": set(), "turler": set()},
                )
                kutu["adet"] += 1
                kutu["kalinliklar"].add(kalinlik)
                kutu["turler"].add(tur_adi)
                try:
                    kutu["toplam_pt"] += abs(
                        float(nesne["x1"]) - float(nesne["x0"])
                    ) + abs(float(nesne["y1"]) - float(nesne["y0"]))
                except Exception:  # pragma: no cover
                    pass

    adaylar = []
    for kutu in gruplar.values():
        adaylar.append(
            {
                "anahtar": kutu["renk"],
                "adet": kutu["adet"],
                "toplam_pt": round(kutu["toplam_pt"], 1),
                "kalinliklar": ",".join(
                    f"{k:g}" for k in sorted(kutu["kalinliklar"])
                ),
                "turler": ",".join(sorted(kutu["turler"])),
            }
        )
    adaylar.sort(key=lambda a: -a["adet"])
    return adaylar
