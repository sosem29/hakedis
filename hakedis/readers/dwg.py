"""DWG okuyucu.

DWG kapali bir formattir; acik kaynak ve ucretsiz tek tam cozum GNU LibreDWG'dir
(GPLv3). Bu modul dosyayi once DXF'e cevirir, sonra DXF okuyucusuna devreder.

Desteklenen donusturuculer (bulunan ilki kullanilir):
  1. dwg2dxf      - GNU LibreDWG, tamamen acik kaynak (onerilen)
  2. ODAFileConverter - Open Design Alliance, ucretsiz fakat kapali kaynak
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from hakedis.config import Ayarlar
from hakedis.model import Cizim

KURULUM_YARDIMI = """
DWG dosyalarini okumak icin bir donusturucu gerekiyor. Ikisinden biri yeterli:

  1) GNU LibreDWG (acik kaynak, GPLv3) - onerilen
     Debian/Ubuntu : sudo apt install libredwg-tools
     macOS (brew)  : brew install libredwg
     Kaynaktan     : https://github.com/LibreDWG/libredwg
     Kurulunca `dwg2dxf` komutu PATH'te olmalidir.

  2) ODA File Converter (ucretsiz, kapali kaynak)
     https://www.opendesign.com/guestfiles/oda_file_converter
     Kurulunca `ODAFileConverter` komutu PATH'te olmalidir.

Alternatif: dosyayi AutoCAD/BricsCAD/LibreCAD ile "DXF R2013" olarak kaydedip
hakedis'e .dxf uzantisiyla verin - bu yol her zaman calisir.
""".strip()


def donusturucu_bul() -> tuple[str, str] | None:
    """Sistemde kurulu DWG->DXF donusturucusunu bulur.

    Dondurur: (tur, yol) ya da None. tur: 'libredwg' | 'oda'
    """
    for ad in ("dwg2dxf",):
        yol = shutil.which(ad)
        if yol:
            return ("libredwg", yol)
    for ad in ("ODAFileConverter", "ODAFileConverter.exe"):
        yol = shutil.which(ad)
        if yol:
            return ("oda", yol)
    # Yaygin kurulum dizinleri
    adaylar = [
        "/usr/bin/dwg2dxf",
        "/usr/local/bin/dwg2dxf",
        "/opt/homebrew/bin/dwg2dxf",
        "/usr/bin/ODAFileConverter",
        "/opt/ODAFileConverter/ODAFileConverter",
    ]
    for aday in adaylar:
        if os.path.isfile(aday) and os.access(aday, os.X_OK):
            return (
                ("libredwg" if "dwg2dxf" in aday else "oda"),
                aday,
            )
    return None


def dwg_dxfe_cevir(kaynak: str | Path, hedef_dizin: str | Path | None = None) -> Path:
    """DWG dosyasini DXF'e cevirir ve olusan DXF'in yolunu dondurur."""
    kaynak = Path(kaynak).resolve()
    if not kaynak.exists():
        raise FileNotFoundError(f"DWG dosyasi bulunamadi: {kaynak}")

    bulunan = donusturucu_bul()
    if bulunan is None:
        raise RuntimeError(
            f"DWG donusturucu bulunamadi.\n\n{KURULUM_YARDIMI}"
        )
    tur, arac = bulunan
    hedef_dizin = Path(hedef_dizin or tempfile.mkdtemp(prefix="hakedis_dwg_"))
    hedef_dizin.mkdir(parents=True, exist_ok=True)
    hedef = hedef_dizin / (kaynak.stem + ".dxf")

    if tur == "libredwg":
        komut = [arac, "-y", "-o", str(hedef), str(kaynak)]
    else:
        # ODAFileConverter <girdi_dizini> <cikti_dizini> <surum> <tur> <ozyinele> <denetle>
        komut = [
            arac,
            str(kaynak.parent),
            str(hedef_dizin),
            "ACAD2013",
            "DXF",
            "0",
            "1",
            kaynak.name,
        ]

    try:
        sonuc = subprocess.run(
            komut, capture_output=True, text=True, timeout=600, check=False
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            f"DWG donusumu zaman asimina ugradi (10 dk): {kaynak.name}"
        ) from e
    except OSError as e:
        raise RuntimeError(f"Donusturucu calistirilamadi ({arac}): {e}") from e

    if not hedef.exists():
        # ODA farkli buyuk/kucuk harfle yazabilir
        adaylar = list(hedef_dizin.glob("*.dxf")) + list(hedef_dizin.glob("*.DXF"))
        if adaylar:
            hedef = adaylar[0]

    if not hedef.exists() or hedef.stat().st_size == 0:
        ayrinti = (sonuc.stderr or sonuc.stdout or "").strip()[:1500]
        raise RuntimeError(
            f"DWG -> DXF donusumu basarisiz oldu ({tur}).\n"
            f"Komut: {' '.join(komut)}\n"
            f"Cikti: {ayrinti or '(bos)'}\n\n"
            f"Dosya cok yeni bir DWG surumunde olabilir. Cizimi CAD "
            f"programindan 'DXF R2013' olarak kaydedip tekrar deneyin."
        )
    return hedef


def dwg_oku(yol: str | Path, ayarlar: Ayarlar) -> Cizim:
    """DWG dosyasini DXF'e cevirip okur."""
    from hakedis.readers.dxf import dxf_oku

    with tempfile.TemporaryDirectory(prefix="hakedis_dwg_") as gecici:
        dxf_yolu = dwg_dxfe_cevir(yol, gecici)
        cizim = dxf_oku(dxf_yolu, ayarlar)
    cizim.kaynak = str(Path(yol))
    tur = (donusturucu_bul() or ("?", ""))[0]
    cizim.notlar.insert(
        0,
        f"DWG dosyasi {tur} ile DXF'e cevrilerek okundu. Donusumde kaybolan "
        f"varliklar olabilir; kontrol paftasini (--svg) mutlaka inceleyin.",
    )
    return cizim
