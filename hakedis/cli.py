"""hakedis komut satiri arayuzu."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
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
    sonuc, _ = plandan_metraj(args.dosya, ayarlar)

    print(konsol_ozeti(sonuc, ayrintili=args.ayrintili))

    kaynak = Path(args.dosya)
    cikti = Path(args.cikti) if args.cikti else kaynak.with_suffix(".metraj.xlsx")
    excel_yaz(sonuc, cikti)
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
    veri = {
        "kat": sonuc.kat,
        "kaynak_dosya": sonuc.kaynak_dosya,
        "parametreler": sonuc.parametreler,
        "ozet": sonuc.ozet(),
        "uyarilar": sonuc.uyarilar,
        "elemanlar": [
            {
                "ad": e.ad,
                "tip": e.tip.value,
                "kat": e.kat,
                "katman": e.kaynak_katman,
                "etiket": e.etiket_metni,
                "olculer": e.olculer,
                "guven": e.guven,
                "notlar": e.notlar,
                "kirik_olcu": [
                    {
                        "baslangic": [s.baslangic.x, s.baslangic.y],
                        "bitis": [s.bitis.x, s.bitis.y],
                        "uzunluk": round(s.uzunluk, 4),
                        "aciklama": s.aciklama,
                    }
                    for s in e.segmentler
                ],
                "cevre": [[p.x, p.y] for p in e.cevre],
                "bosluklar": [[[p.x, p.y] for p in b] for b in e.bosluklar],
            }
            for e in sonuc.elemanlar
        ],
        "satirlar": [
            {
                "poz": s.poz,
                "eleman": s.eleman_adi,
                "tip": s.tip.value,
                "tanim": s.tanim,
                "en": s.en,
                "boy": s.boy,
                "yukseklik": s.yukseklik,
                "alan": s.alan,
                "hacim": s.hacim,
                "birim": s.birim,
                "formul": s.formul,
                "dusum": s.dusum_mu,
                "detay": s.detay,
            }
            for s in sonuc.satirlar
        ],
    }
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(
        json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8"
    )


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


def komut_kesfet(args) -> int:
    """Katman adlarina bakmadan, geometriden eleman tiplerini cikarir."""
    from hakedis.otomatik import imzalari_cikar, yapilandirma_metni
    from hakedis.readers import cizim_oku

    ayarlar = _ayarlari_hazirla(args)
    cizim = cizim_oku(args.dosya, ayarlar)
    imzalar = imzalari_cikar(cizim, ayarlar)

    print(f"Dosya : {args.dosya}")
    print(f"Birim : {cizim.birim}")
    x0, y0, x1, y1 = cizim.sinirlar()
    print(f"Sinir : {x1 - x0:.2f} m x {y1 - y0:.2f} m")
    print()
    print(
        f"{'KATMAN':<26}{'ADET':>6}  {'BULUNAN TIP':<12}{'GUVEN':>7}  GEREKCE"
    )
    print("-" * 100)
    for i in imzalar:
        tip = i.onerilen_tip or "-"
        if i.onerilen_tip and i.guven >= 0.5:
            isaret = "  " if i.guven >= 0.75 else "? "
        else:
            isaret = "! "
            tip = "belirsiz"
        print(
            f"{isaret}{i.katman[:24]:<24}{i.varlik_sayisi:>6}  {tip:<12}"
            f"{i.guven:>7.2f}  {i.gerekce}"
        )
    print("-" * 100)
    print("  = guvenilir    ? = kontrol edin    ! = siniflandirilamadi")

    if args.cikti:
        hedef = Path(args.cikti)
        if hedef.exists() and not args.ustune_yaz:
            print(
                f"\n{hedef} zaten var. Ustune yazmak icin --ustune-yaz kullanin.",
                file=sys.stderr,
            )
            return 1
        temel = VARSAYILAN_YOL.read_text(encoding="utf-8")
        # Varsayilan 'katmanlar' bolumunu kesif sonucuyla degistir
        satirlar = temel.splitlines(keepends=True)
        cikti_satirlari: list[str] = []
        atla = False
        for satir in satirlar:
            if satir.startswith("katmanlar:"):
                atla = True
                cikti_satirlari.append(yapilandirma_metni(imzalar))
                continue
            if atla:
                # Girintisiz yeni bir ust bolum baslayinca atlamayi birak
                if satir.strip() and not satir.startswith((" ", "#")):
                    atla = False
                else:
                    continue
            cikti_satirlari.append(satir)
        hedef.parent.mkdir(parents=True, exist_ok=True)
        hedef.write_text("".join(cikti_satirlari), encoding="utf-8")
        print(f"\nYapilandirma yazildi: {hedef}")
        print(f"Kullanmak icin      : hakedis metraj {args.dosya} --config {hedef}")
    else:
        print(
            "\nBu eslemeyi kalici hale getirmek icin:\n"
            f"  hakedis kesfet {args.dosya} --cikti ofis.yml"
        )
    return 0


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


# ---------------------------------------------------------------------------
# Ana giris
# ---------------------------------------------------------------------------


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

    k = alt.add_parser("katmanlar", help="Cizimdeki katmanlari ve eslemeleri listele")
    _ortak_argumanlar(k)
    k.set_defaults(func=komut_katmanlar)

    ke = alt.add_parser(
        "kesfet",
        help="Katman adlarina bakmadan, geometriden eleman tiplerini cikar",
    )
    _ortak_argumanlar(ke)
    ke.add_argument(
        "--cikti", "-o", help="Bulunan eslemeyi yapilandirma dosyasi olarak yaz"
    )
    ke.add_argument("--ustune-yaz", action="store_true", help="Varsa ustune yaz")
    ke.set_defaults(func=komut_kesfet)

    pi = alt.add_parser("pdf-incele", help="PDF paftasindaki renkleri/olcegi incele")
    pi.add_argument("dosya", help="PDF dosyasi")
    pi.add_argument("--sayfa", type=int, default=1, help="Sayfa numarasi")
    pi.set_defaults(func=komut_pdf_incele)

    c = alt.add_parser("config-yaz", help="Duzenlenebilir yapilandirma dosyasi olustur")
    c.add_argument("--cikti", "-o", default="hakedis.yml", help="Hedef YAML yolu")
    c.add_argument("--ustune-yaz", action="store_true", help="Varsa ustune yaz")
    c.set_defaults(func=komut_config_yaz)

    o = alt.add_parser("ornek", help="Deneme icin sentetik kalip plani uret")
    o.add_argument("cikti", nargs="?", default="ornek_kalip_plani.dxf")
    o.set_defaults(func=komut_ornek)

    d = alt.add_parser("dogrula", help="Kurulumu ve bagimliliklari kontrol et")
    d.set_defaults(func=komut_dogrula)

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
