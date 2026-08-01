"""Test yardimcilari - disariya bagimlilik olmadan vektor PDF uretir."""

from __future__ import annotations

from pathlib import Path


def basit_pdf_yaz(hedef: Path, icerik: str, genislik: int = 842, yukseklik: int = 595) -> Path:
    """Verilen icerik akisiyla gecerli, minimal bir vektor PDF yazar.

    reportlab gibi ek bir bagimlilik gerektirmemek icin PDF sozdizimi elle
    kurulur; xref kaymalari dogru hesaplanir.
    """
    nesneler: list[bytes] = [
        b"<</Type/Catalog/Pages 2 0 R>>",
        b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
        (
            f"<</Type/Page/Parent 2 0 R/MediaBox[0 0 {genislik} {yukseklik}]"
            f"/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>"
        ).encode("ascii"),
        None,  # icerik akisi asagida
        b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>",
    ]
    akis = icerik.encode("ascii")
    nesneler[3] = b"<</Length " + str(len(akis)).encode() + b">>\nstream\n" + akis + b"\nendstream"

    cikti = bytearray(b"%PDF-1.4\n")
    kaymalar: list[int] = []
    for i, govde in enumerate(nesneler, start=1):
        kaymalar.append(len(cikti))
        cikti += f"{i} 0 obj\n".encode("ascii") + govde + b"\nendobj\n"

    xref_kayma = len(cikti)
    cikti += f"xref\n0 {len(nesneler) + 1}\n".encode("ascii")
    cikti += b"0000000000 65535 f \n"
    for k in kaymalar:
        cikti += f"{k:010d} 00000 n \n".encode("ascii")
    cikti += (
        f"trailer\n<</Size {len(nesneler) + 1}/Root 1 0 R>>\n"
        f"startxref\n{xref_kayma}\n%%EOF\n"
    ).encode("ascii")

    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_bytes(bytes(cikti))
    return hedef


def kalip_plani_pdf(hedef: Path) -> Path:
    """1 pt = 1 cm olacak sekilde basit bir kalip plani PDF'i uretir.

    Kirmizi dikdortgenler = kolon (30x60), mavi cizgi ciftleri = kiris (25),
    gri dikdortgen = doseme.
    """
    parcalar: list[str] = []

    # Doseme: gri kapali dikdortgen (dolgu ile)
    parcalar.append("0.6 0.6 0.6 RG 0.5 w")
    parcalar.append("85 85 630 330 re S")

    # Kolonlar: kirmizi, 30x60 pt, akslarda
    parcalar.append("1 0 0 RG 1.5 w")
    for x in (100, 400, 700):
        for y in (100, 400):
            parcalar.append(f"{x - 15} {y - 30} 30 60 re S")

    # Kirisler: mavi, iki paralel cizgi (aciklik 25 pt)
    parcalar.append("0 0 1 RG 1 w")
    for y in (100, 400):
        for ofset in (-12.5, 12.5):
            parcalar.append(f"85 {y + ofset} m 715 {y + ofset} l S")
    for x in (100, 400, 700):
        for ofset in (-12.5, 12.5):
            parcalar.append(f"{x + ofset} 70 m {x + ofset} 430 l S")

    # Etiketler
    parcalar.append("BT /F1 9 Tf 0 0 0 rg")
    sayac = 0
    for x in (100, 400, 700):
        for y in (100, 400):
            sayac += 1
            parcalar.append(f"1 0 0 1 {x - 20} {y + 36} Tm (S{sayac:02d} 30/60) Tj")
    parcalar.append(f"1 0 0 1 300 250 Tm (K101 25/50) Tj")
    parcalar.append("ET")

    return basit_pdf_yaz(hedef, "\n".join(parcalar))
