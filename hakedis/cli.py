"""hakedis komut satiri arayuzu."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

from hakedis import __version__
from hakedis.config import VARSAYILAN_YOL, ayarlari_yukle


def _ortak_argumanlar(alt: argparse.ArgumentParser) -> None:
    alt.add_argument("dosya", help="Kalip plani dosyasi (.dwg / .dxf / .pdf)")
    alt.add_argument(
        "--config", "-c", help="Ofis yapilandirma dosyasi (YAML)", default=None
    )
    alt.add_argument(
        "--birim",
        choices=["mm", "cm", "m"],
        help="Cizim birimi (DXF basligindaki degeri ezer)",
    )
    alt.add_argument("--kat", dest="kat_adi", help="Kat adi (ornek: '3. Normal Kat')")
    alt.add_argument(
        "--kat-yuksekligi",
        dest="kat_yuksekligi",
        type=float,
        help="Kat yuksekligi (m), varsayilan 3.00",
    )
    alt.add_argument(
        "--doseme-kalinligi",
        dest="doseme_kalinligi",
        type=float,
        help="Doseme kalinligi (m), varsayilan 0.15",
    )
    alt.add_argument("--olcek", help="PDF pafta olcegi (ornek: 1/50)")
    alt.add_argument("--sayfa", type=int, help="PDF sayfa numarasi (varsayilan 1)")
    alt.add_argument(
        "--kalibre",
        help=(
            "PDF iki nokta kalibrasyonu: PDF_MESAFE:GERCEK_MESAFE "
            "(ornek: --kalibre 340.5:6.00). Olcekten daha guvenilirdir."
        ),
    )


def _ayarlari_hazirla(args) -> object:
    ayarlar = ayarlari_yukle(getattr(args, "config", None))
    ayarlar = ayarlar.guncelle(
        birim=getattr(args, "birim", None),
        kat_adi=getattr(args, "kat_adi", None),
        kat_yuksekligi=getattr(args, "kat_yuksekligi", None),
        doseme_kalinligi=getattr(args, "doseme_kalinligi", None),
        olcek=getattr(args, "olcek", None),
        sayfa=getattr(args, "sayfa", None),
    )
    if getattr(args, "sta4cad", False):
        ayarlar.ham.setdefault("sta4cad", {})["aktif"] = True
    kalibre = getattr(args, "kalibre", None)
    if kalibre:
        try:
            pdf_m, gercek = kalibre.split(":")
            ayarlar.ham.setdefault("pdf", {})["kalibrasyon"] = {
                "pdf_mesafe": float(pdf_m),
                "gercek_mesafe": float(gercek),
            }
        except ValueError:
            raise SystemExit(
                f"--kalibre bicimi hatali: {kalibre!r}. Beklenen: 340.5:6.00"
            )
    return ayarlar


# ---------------------------------------------------------------------------
# Komutlar
# ---------------------------------------------------------------------------


def komut_metraj(args) -> int:
    from hakedis.metraj import plandan_metraj
    from hakedis.report import excel_yaz, konsol_ozeti, svg_yaz

    ayarlar = _ayarlari_hazirla(args)
    mahal_dosya = getattr(args, "mahal", None)
    donati_dosya = getattr(args, "donati", None)
    if donati_dosya:
        ayarlar.ham.setdefault("donati", {})["plan_okuma"] = True
    sonuc, _ = plandan_metraj(
        args.dosya, ayarlar, mahal_dosya=mahal_dosya, donati_dosya=donati_dosya
    )

    print(konsol_ozeti(sonuc, ayrintili=args.ayrintili))

    if ayarlar.al("maliyet.aktif", False):
        from hakedis.maliyet import maliyet_hesapla, maliyet_konsol

        print(maliyet_konsol(maliyet_hesapla(sonuc, ayarlar)))

    kaynak = Path(args.dosya)
    cikti = Path(args.cikti) if args.cikti else kaynak.with_suffix(".metraj.xlsx")
    excel_yaz(sonuc, cikti, ayarlar=ayarlar)
    print(f"\nMetraj cetveli yazildi : {cikti}")

    if args.svg is not False:
        svg_yolu = Path(args.svg) if args.svg else cikti.with_suffix(".kontrol.svg")
        svg_yaz(sonuc, svg_yolu)
        print(f"Kontrol paftasi yazildi: {svg_yolu}")
        print(
            "\n>> Teslim etmeden once kontrol paftasini acip her elemanin "
            "dogru tipte\n   boyandigini ve atlanan eleman olmadigini "
            "dogrulayin."
        )

    if args.json:
        _json_yaz(sonuc, Path(args.json))
        print(f"JSON ciktisi yazildi   : {args.json}")

    return 1 if sonuc.uyarilar and args.katı else 0


def _json_yaz(sonuc, hedef: Path) -> None:
    from hakedis.report.veri import sonuc_verisi

    veri = sonuc_verisi(sonuc)
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(
        json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def komut_maliyet(args) -> int:
    """Daha once uretilmis bir metraj JSON'una birim fiyatlari uygular."""
    from hakedis.maliyet import maliyet_hesapla, maliyet_konsol
    from hakedis.model import ElemanTipi, KirikOlcuSatiri, MetrajSonucu

    veri = json.loads(Path(args.metraj_json).read_text(encoding="utf-8"))
    ayarlar = ayarlari_yukle(args.config)
    satirlar = veri["satirlar"] if isinstance(veri, dict) and "satirlar" in veri else veri

    def _tip(t: str) -> ElemanTipi:
        try:
            return ElemanTipi(t)
        except ValueError:  # pragma: no cover
            return ElemanTipi.BILINMEYEN

    sonuc = MetrajSonucu(
        kat=str(veri.get("kat", "")) if isinstance(veri, dict) else "",
        kaynak_dosya=str(veri.get("kaynak_dosya", "")) if isinstance(veri, dict) else "",
        satirlar=[
            KirikOlcuSatiri(
                poz=s["poz"],
                eleman_adi=s.get("eleman", ""),
                tip=_tip(s.get("tip", "Bilinmeyen")),
                tanim=s.get("tanim", ""),
                benzer=float(s.get("benzer", 1) or 1),
                en=float(s["en"]) if s.get("en") is not None else None,
                boy=float(s["boy"]) if s.get("boy") is not None else None,
                yukseklik=float(s["yukseklik"]) if s.get("yukseklik") is not None else None,
                alan=float(s["alan"]) if s.get("alan") is not None else None,
                hacim=float(s["hacim"]) if s.get("hacim") is not None else None,
                kg=float(s["demir"]) if s.get("demir") is not None else None,
                birim=s.get("birim", ""),
                formul=s.get("formul", ""),
                kat=s.get("kat", ""),
                detay=s.get("detay", []),
                dusum_mu=bool(s.get("dusum")),
            )
            for s in satirlar
        ],
    )
    print(maliyet_konsol(maliyet_hesapla(sonuc, ayarlar)))
    return 0


def komut_katmanlar(args) -> int:
    """Cizimdeki katmanlari ve hangi tipe eslestiklerini gosterir."""
    from hakedis.readers import cizim_oku

    ayarlar = _ayarlari_hazirla(args)
    cizim = cizim_oku(args.dosya, ayarlar)
    katmanlar = cizim.katmanlar()

    print(f"Dosya : {args.dosya}")
    print(f"Birim : {cizim.birim}")
    print(f"Varlik: {len(cizim.varliklar)}")
    x0, y0, x1, y1 = cizim.sinirlar()
    print(f"Sinir : {x1 - x0:.2f} m x {y1 - y0:.2f} m")
    print()
    print(f"{'KATMAN':<34}{'ADET':>7}  {'ESLESTIGI TIP':<14}")
    print("-" * 62)
    eslenmeyen = 0
    for ad, adet in katmanlar.items():
        tip = ayarlar.katman_tipi(ad)
        if tip is None:
            eslenmeyen += adet
            gosterim = "-- ESLESMEDI --"
        elif tip == "yoksay":
            gosterim = "(yoksayildi)"
        else:
            gosterim = tip
        print(f"{ad[:33]:<34}{adet:>7}  {gosterim:<14}")
    print("-" * 62)
    if eslenmeyen:
        print(
            f"\n{eslenmeyen} varlik hicbir desene uymuyor. Bunlarin metraja "
            f"girmesi icin:\n"
            f"  1. hakedis config-yaz --cikti ofis.yml\n"
            f"  2. ofis.yml icindeki 'katmanlar' bolumune kendi katman "
            f"adlarinizi ekleyin\n"
            f"  3. hakedis metraj {args.dosya} --config ofis.yml"
        )
    return 0


def komut_mahal(args) -> int:
    """Mahal planindan odalari oku ve ozet tablosunu yaz."""
    from hakedis.mahal import mahal_satirlari, mahalleri_oku

    ayarlar = _ayarlari_hazirla(args)
    mahaller, uyarilar = mahalleri_oku(args.dosya, ayarlar)

    print(f"{len(mahaller)} oda/mahal bulundu.\n")
    print(f"{'Mahal':<24} {'Tur':<10} {'Alan (m2)':>10} {'Cevre (m)':>10}")
    print("-" * 58)
    for m in mahaller:
        print(
            f"{(m.ad or '?'):<24} {m.tip:<10} {m.alan:>10.3f} {m.cevre:>10.3f}"
        )
    if uyarilar:
        print("\nUyarilar:")
        for u in uyarilar:
            print(f"  - {u}")

    if getattr(args, "ayrintili", False):
        print("\nUretilecek satirlar:")
        for s in mahal_satirlari(mahaller, ayarlar):
            print(
                f"  {s.poz:<10} {s.eleman_adi:<28} {s.tanim:<50} {s.alan:.3f} m2"
            )
    return 1 if uyarilar and getattr(args, "kati", False) else 0


def komut_pdf_incele(args) -> int:
    """PDF paftasindaki renk/kalinlik dagilimini dokumler."""
    from hakedis.readers.pdf import MM_PER_PT, pdf_incele

    bilgi = pdf_incele(args.dosya, args.sayfa or 1)
    print(f"Dosya  : {args.dosya}")
    print(f"Sayfa  : {args.sayfa or 1} / {bilgi['sayfa_sayisi']}")
    print(
        f"Boyut  : {bilgi['genislik_pt']} x {bilgi['yukseklik_pt']} pt "
        f"({bilgi['genislik_mm']} x {bilgi['yukseklik_mm']} mm kagit)"
    )
    print(f"Yazi   : {bilgi['yazi_sayisi']} karakter")
    if not bilgi["renkler"]:
        print(
            "\nVektor cizgi bulunamadi. Bu PDF taranmis (goruntu) olabilir; "
            "metraj cikarilamaz."
        )
        return 2
    print()
    print(f"{'RENK':<10}{'KALINLIK':>10}{'ADET':>8}{'TOPLAM PT':>12}  TURLER")
    print("-" * 62)
    for s in bilgi["renkler"]:
        print(
            f"{s['renk']:<10}{s['kalinlik']:>10.2f}{s['adet']:>8}"
            f"{s['toplam_uzunluk_pt']:>12.1f}  {s['turler']}"
        )
    print("-" * 62)
    print(
        "\nYapilandirmanizdaki pdf.renk_esleme bolumunu bu renklere gore "
        "doldurun, ornek:\n"
        "  pdf:\n"
        "    renk_esleme:\n"
        f"      \"{bilgi['renkler'][0]['renk']}\": kolon\n"
        "      \"#0000ff\": kiris\n"
    )
    olcek_ipucu = 1000.0 / MM_PER_PT
    print(
        f"Olcek dogrulamasi: paftada boyu bildiginiz bir mesafeyi (aks araligi "
        f"gibi)\nseciip `--kalibre <PDF_PT>:<GERCEK_M>` verin. 1 m gercek boy, "
        f"1/50'de\n{olcek_ipucu / 50:.1f} pt eder."
    )
    return 0


def komut_config_yaz(args) -> int:
    """Varsayilan yapilandirmayi kullanicinin duzenlemesi icin kopyalar."""
    hedef = Path(args.cikti)
    if hedef.exists() and not args.ustune_yaz:
        print(
            f"{hedef} zaten var. Ustune yazmak icin --ustune-yaz kullanin.",
            file=sys.stderr,
        )
        return 1
    hedef.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(VARSAYILAN_YOL, hedef)
    print(f"Yapilandirma yazildi: {hedef}")
    print(
        "Katman adlarinizi 'katmanlar' bolumune, kat yuksekligi/doseme "
        "kalinligini\n'kat' bolumune, poz numaralarinizi 'pozlar' bolumune "
        "girin."
    )
    return 0


def komut_ornek(args) -> int:
    """Deneme icin sentetik bir kalip plani uretir."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from ornek.ornek_plan_uret import uret

    hedef = uret(Path(args.cikti))
    print(f"Ornek kalip plani yazildi: {hedef}")
    print(f"Denemek icin: hakedis metraj {hedef}")
    return 0


def komut_dogrula(args) -> int:
    """Sistemin calismasi icin gereken bilesenleri kontrol eder."""
    from hakedis.readers.dwg import donusturucu_bul

    print(f"hakedis {__version__}")
    print(f"Python  {sys.version.split()[0]}")
    print()
    tamam = True
    for ad, ithal in (
        ("ezdxf (DXF okuma)", "ezdxf"),
        ("shapely (geometri)", "shapely"),
        ("numpy", "numpy"),
        ("openpyxl (Excel)", "openpyxl"),
        ("pdfplumber (PDF)", "pdfplumber"),
        ("PyYAML", "yaml"),
    ):
        try:
            modul = __import__(ithal)
            surum = getattr(modul, "__version__", "?")
            print(f"  [ok] {ad:<26} {surum}")
        except ImportError:
            print(f"  [--] {ad:<26} KURULU DEGIL")
            tamam = False

    print()
    bulunan = donusturucu_bul()
    if bulunan:
        tur, yol = bulunan
        print(f"  [ok] DWG donusturucu ({tur}): {yol}")
    else:
        print("  [--] DWG donusturucu bulunamadi -> .dwg dosyalari okunamaz")
        print("       Debian/Ubuntu: sudo apt install libredwg-tools")
        print("       macOS        : brew install libredwg")
        print("       (.dxf ve .pdf dosyalari bundan etkilenmez)")
    return 0 if tamam else 1


def komut_web(args) -> int:
    """Gorsel arayuzu varsayilan tarayicida acar (yerel sunucu)."""
    from hakedis.web.desktop import tarayicida_ac

    url = tarayicida_ac(port=args.port, host=args.host)
    print(f"hakedis web arayuzu: {url}")
    print("Kapatmak icin Ctrl+C.")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:  # pragma: no cover
        pass
    return 0


def komut_masaustu(args) -> int:
    """Gorsel arayuzu yerli masaustu penceresinde acar (webview)."""
    from hakedis.web.desktop import masaustu_ac

    return masaustu_ac(port=args.port, host=args.host, debug=args.debug)


# ---------------------------------------------------------------------------
# Ana giris
# ---------------------------------------------------------------------------


def _toplu_isleri_hazirla(
    args, temel
) -> list[tuple[str, str, object]]:
    """Toplu calismada her kat icin (kat_adi, dosya, ayarlar) uretir.

    Iki yol vardir:
      - `--paftalar "1:Giris,2:1.Kat"` : tek cok sayfali PDF'in sayfalari
      - coklu dosya + `--kat-adlari`    : her dosya ayri kat
    """
    paftalar = getattr(args, "paftalar", None)
    if paftalar:
        isler: list[tuple[str, str, object]] = []
        for parca in paftalar.split(","):
            parca = parca.strip()
            if not parca:
                continue
            if ":" not in parca:
                raise SystemExit(
                    f"--paftalar bicimi hatali: {parca!r}. Beklenen: "
                    "1:Giris,2:1.Kat"
                )
            sayfa, kat = parca.split(":", 1)
            kat = kat.strip() or f"Sayfa {sayfa}"
            ayarlar = temel.guncelle(kat_adi=kat)
            ayarlar.ham.setdefault("pdf", {})["sayfa"] = int(sayfa)
            isler.append((kat, args.dosyalar[0], ayarlar))
        return isler

    katlar = list(getattr(args, "kat_adlari", None) or [])
    isler = []
    for i, dosya in enumerate(args.dosyalar):
        kat = katlar[i] if i < len(katlar) else Path(dosya).stem
        ayarlar = temel.guncelle(kat_adi=kat)
        isler.append((kat, dosya, ayarlar))
    return isler


def komut_toplu(args) -> int:
    """Cok katli / cok paftali metraj: birden fazla dosya veya PDF sayfasi."""
    from hakedis.metraj import plandan_metraj, sonuclari_birlestir, sonuclari_cogalt
    from hakedis.report import excel_yaz_toplu, konsol_ozeti_toplu

    temel = _ayarlari_hazirla(args)
    isler = _toplu_isleri_hazirla(args, temel)
    mahal_dosya = getattr(args, "mahal", None)
    donati_dosya = getattr(args, "donati", None)
    if donati_dosya:
        temel.ham.setdefault("donati", {})["plan_okuma"] = True

    sonuclar: list = []
    for kat, dosya, ayarlar in isler:
        print(f"[toplu] {kat}: {dosya} ...", file=sys.stderr)
        sonuc, _ = plandan_metraj(
            dosya, ayarlar, mahal_dosya=mahal_dosya, donati_dosya=donati_dosya
        )
        sonuclar.append(sonuc)

    adetler = _adet_listesi(args)
    if any(a > 1 for a in adetler):
        for i, s in enumerate(sonuclar):
            a = adetler[i] if i < len(adetler) else 1
            if a > 1:
                print(
                    f"[toplu] {s.kat} plani {a} katta tekrar ediyor.",
                    file=sys.stderr,
                )
        sonuclar = sonuclari_cogalt(sonuclar, adetler)

    print(konsol_ozeti_toplu(sonuclar))

    if temel.al("maliyet.aktif", False):
        from hakedis.maliyet import maliyet_hesapla, maliyet_konsol

        print(maliyet_konsol(maliyet_hesapla(sonuclari_birlestir(sonuclar), temel)))
        print("KAT BAZINDA YAKLASIK MALIYET")
        for s in sonuclar:
            m = maliyet_hesapla(s, temel)
            print(
                f"  {s.kat or '?':<20} ara {m['ara_toplam']:>14,.0f}  "
                f"genel {m['genel_toplam']:>14,.0f} TL"
            )

    kaynak = Path(args.dosyalar[0])
    cikti = Path(args.cikti) if args.cikti else kaynak.with_suffix(".toplu.xlsx")
    excel_yaz_toplu(sonuclar, cikti, ayarlar=temel)
    print(f"\nToplu metraj cetveli yazildi : {cikti}")

    if args.json:
        _toplu_json_yaz(sonuclar, Path(args.json))
        print(f"JSON ciktisi yazildi   : {args.json}")
    return 0


def _adet_listesi(args) -> list[int]:
    """--adet degerini dosya bazli adet listesine cevirir.

    Tek sayi ("4") tum dosyalara uygulanir; virgullu degerler ("1,4,2")
    sirayla dosyalara biner. Bos deger icin [1, 1, ...] dondurur.
    """
    ham = (getattr(args, "adet", "") or "").strip()
    adet = int(ham) if ham.isdigit() else 1
    parcalar = [int(p.strip()) for p in ham.split(",") if p.strip().isdigit()]
    dosya_sayisi = len(getattr(args, "dosyalar", []) or [])
    if parcalar:
        return [(parcalar[i] if i < len(parcalar) else 1) for i in range(dosya_sayisi)]
    return [adet] * dosya_sayisi


def _toplu_json_yaz(sonuclar, hedef: Path) -> None:
    from hakedis.metraj import sonuclari_birlestir

    birlesik = sonuclari_birlestir(sonuclar)
    veri = {
        "tur": "toplu",
        "katlar": [
            {
                "kat": s.kat,
                "kaynak_dosya": s.kaynak_dosya,
                "ozet": s.ozet(),
            }
            for s in sonuclar
        ],
        "toplam": birlesik.ozet(),
        "uyarilar": birlesik.uyarilar,
    }
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(
        json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def olustur_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="hakedis",
        description=(
            "Kalip planindan (DWG/DXF/PDF) eleman bazli kirik olcu metraji "
            "uretir."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tipik kullanim:
  hakedis dogrula                          # kurulumu kontrol et
  hakedis ornek deneme.dxf                 # ornek plan uret
  hakedis katmanlar plan.dxf               # katmanlari gor
  hakedis config-yaz --cikti ofis.yml      # ofis ayarlarini olustur
  hakedis metraj plan.dwg --config ofis.yml --kat "3. Normal Kat"
  hakedis pdf-incele plan.pdf              # PDF renklerini gor
  hakedis metraj plan.pdf --olcek 1/50 --kalibre 340.5:6.00

Gorsel arayuz:
  hakedis web                              # tarayicida acar
  hakedis masaustu                         # yerli masaustu penceresi

Cok katli / cok paftali:
  hakedis toplu gir.dxf kat1.dxf --kat-adlari "Giris" "1. Kat"
  hakedis toplu plan.pdf --paftalar "1:Giris,2:1.Kat,3:2.Kat"
""",
    )
    p.add_argument("--version", action="version", version=f"hakedis {__version__}")
    alt = p.add_subparsers(dest="komut", required=True)

    m = alt.add_parser("metraj", help="Kalip planindan metraj cikar")
    _ortak_argumanlar(m)
    m.add_argument("--cikti", "-o", help="Excel cikti yolu (.xlsx)")
    m.add_argument(
        "--svg",
        nargs="?",
        const=None,
        default=None,
        help="SVG kontrol paftasi yolu (varsayilan: cikti yaninda)",
    )
    m.add_argument(
        "--svg-yok",
        dest="svg",
        action="store_const",
        const=False,
        help="Kontrol paftasi uretme",
    )
    m.add_argument("--json", help="Sonucu JSON olarak da yaz")
    m.add_argument(
        "--ayrintili",
        "-v",
        action="store_true",
        help="Konsola kirik olcu kirilimlarini da yaz",
    )
    m.add_argument(
        "--kati",
        dest="katı",
        action="store_true",
        help="Uyari varsa cikis kodu 1 dondur (otomasyon icin)",
    )
    m.set_defaults(func=komut_metraj)
    m.add_argument(
        "--mahal",
        help="Mahal plani dosyasi (.dwg/.dxf/.pdf); verilirse kaplama/tesviye/"
        "siva metraji oda bazinda uretilir",
    )
    m.add_argument(
        "--sta4cad",
        action="store_true",
        help="Sta4CAD kalip/temel plani profili: ek katman eslemeleri ve "
        "'Temel' katmanini doseme say",
    )
    m.add_argument(
        "--donati",
        help="Donati plani dosyasi (.dwg/.dxf/.pdf); verilirse katsayi "
        "yerine cap/adet/aralik etiketlerinden kg satirlari uretilir",
    )

    t = alt.add_parser(
        "toplu",
        help="Cok katli/paftali metraj: coklu dosya veya cok sayfali PDF",
    )
    t.add_argument(
        "dosyalar", nargs="+", help="Kat/pafta dosyalari (.dwg / .dxf / .pdf)"
    )
    t.add_argument(
        "--kat-adlari",
        nargs="*",
        default=[],
        help="Dosyalarla sirayla eslesen kat adlari (verilmezse dosya adi kullanilir)",
    )
    t.add_argument(
        "--paftalar",
        help=(
            "Cok sayfali PDF icin sayfa-kat eslemesi, ornek: "
            "'1:Giris Kat,2:1.Normal Kat'"
        ),
    )
    t.add_argument(
        "--adet",
        default="",
        help=(
            "Tekrar eden kat sayilari: her dosyanin kac katta gecerli oldugunu "
            "verir (tek sayi tum dosyalara, virgulle ayri degerler dosya "
            "bazinda). Ornek: --adet 4  veya  --adet '1,4,2'"
        ),
    )
    t.add_argument("--config", "-c", help="Ofis yapilandirma dosyasi (YAML)", default=None)
    t.add_argument(
        "--birim",
        choices=["mm", "cm", "m"],
        help="Cizim birimi (DXF basligindaki degeri ezer)",
    )
    t.add_argument(
        "--kat-yuksekligi",
        dest="kat_yuksekligi",
        type=float,
        help="Kat yuksekligi (m), varsayilan 3.00",
    )
    t.add_argument(
        "--doseme-kalinligi",
        dest="doseme_kalinligi",
        type=float,
        help="Doseme kalinligi (m), varsayilan 0.15",
    )
    t.add_argument("--olcek", help="PDF pafta olcegi (ornek: 1/50)")
    t.add_argument(
        "--kalibre",
        help="PDF iki nokta kalibrasyonu: PDF_MESAFE:GERCEK_MESAFE",
    )
    t.add_argument("--cikti", "-o", help="Excel cikti yolu (.xlsx)")
    t.add_argument("--json", help="Sonucu JSON olarak da yaz")
    t.add_argument(
        "--mahal",
        help="Tek bir mahal plani dosyasi (.dwg/.dxf/.pdf); verilirse tum "
        "kayitlara uygulanir",
    )
    t.add_argument(
        "--sta4cad",
        action="store_true",
        help="Sta4CAD kalip/temel plani profili (ek katman eslemeleri)",
    )
    t.add_argument(
        "--donati",
        help="Tek bir donati plani dosyasi (.dwg/.dxf/.pdf); verilirse tum "
        "kayitlara uygulanir ve katsayi yerine plan esasli kg uretilir",
    )
    t.set_defaults(func=komut_toplu)

    k = alt.add_parser("katmanlar", help="Cizimdeki katmanlari ve eslemeleri listele")
    _ortak_argumanlar(k)
    k.set_defaults(func=komut_katmanlar)

    mk = alt.add_parser(
        "maliyet",
        help="Metraj JSON'una poz birim fiyatlarini uygula (yaklasik maliyet)",
    )
    mk.add_argument("metraj_json", help="`--json` ile uretilmis metraj dosyasi")
    mk.add_argument("--config", "-c", help="Ofis yapilandirma dosyasi (YAML)")
    mk.set_defaults(func=komut_maliyet)

    pi = alt.add_parser("pdf-incele", help="PDF paftasindaki renkleri/olcegi incele")
    pi.add_argument("dosya", help="PDF dosyasi")
    pi.add_argument("--sayfa", type=int, default=1, help="Sayfa numarasi")
    pi.set_defaults(func=komut_pdf_incele)

    mh = alt.add_parser("mahal", help="Mahal planindan odalari oku")
    _ortak_argumanlar(mh)
    mh.add_argument("--ayrintili", "-v", action="store_true",
                    help="Odalardan uretilecek metraj satirlarini da yaz")
    mh.add_argument("--kati", dest="katı", action="store_true",
                    help="Uyari varsa cikis kodu 1 dondur (otomasyon icin)")
    mh.set_defaults(func=komut_mahal)

    c = alt.add_parser("config-yaz", help="Duzenlenebilir yapilandirma dosyasi olustur")
    c.add_argument("--cikti", "-o", default="hakedis.yml", help="Hedef YAML yolu")
    c.add_argument("--ustune-yaz", action="store_true", help="Varsa ustune yaz")
    c.set_defaults(func=komut_config_yaz)

    o = alt.add_parser("ornek", help="Deneme icin sentetik kalip plani uret")
    o.add_argument("cikti", nargs="?", default="ornek_kalip_plani.dxf")
    o.set_defaults(func=komut_ornek)

    d = alt.add_parser("dogrula", help="Kurulumu ve bagimliliklari kontrol et")
    d.set_defaults(func=komut_dogrula)

    w = alt.add_parser(
        "web", help="Gorsel arayuzu varsayilan tarayicida acar"
    )
    w.add_argument("--host", default="127.0.0.1", help="Baglanma adresi")
    w.add_argument("--port", type=int, default=0, help="Sunucu portu (0 = otomatik)")
    w.set_defaults(func=komut_web)

    m = alt.add_parser(
        "masaustu",
        help="Gorsel arayuzu yerli masaustu penceresinde acar (webview)",
    )
    m.add_argument("--host", default="127.0.0.1", help="Baglanma adresi")
    m.add_argument("--port", type=int, default=0, help="Sunucu portu (0 = otomatik)")
    m.add_argument("--debug", action="store_true", help="Gelistirici araclarini ac")
    m.set_defaults(func=komut_masaustu)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = olustur_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args) or 0)
    except (FileNotFoundError, ValueError, RuntimeError) as e:
        print(f"\nHATA: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:  # pragma: no cover
        print("\nIptal edildi.", file=sys.stderr)
        return 130


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
