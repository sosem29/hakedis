"""Cizim okuyuculari: DXF, DWG ve PDF."""

from __future__ import annotations

from pathlib import Path

from hakedis.config import Ayarlar
from hakedis.model import Cizim


def cizim_oku(yol: str | Path, ayarlar: Ayarlar) -> Cizim:
    """Uzantiya gore dogru okuyucuyu secer.

    Tum okuyucu hatalari `ValueError`'da birlestirilir: arayuz ve CLI bu
    istisnayi tek yoldan (temiz Turkce mesajla) yakalayabilsin. Kaynak
    istisna `__cause__` zincirinde korunur.
    """
    p = Path(yol)
    if not p.exists():
        raise FileNotFoundError(f"Dosya bulunamadi: {p}")
    uzanti = p.suffix.lower()
    if uzanti not in (".dxf", ".dwg", ".pdf"):
        raise ValueError(
            f"Desteklenmeyen dosya turu: {uzanti}. Desteklenenler: .dwg, .dxf, .pdf"
        )
    try:
        if uzanti == ".dxf":
            from hakedis.readers.dxf import dxf_oku

            return dxf_oku(p, ayarlar)
        if uzanti == ".dwg":
            from hakedis.readers.dwg import dwg_oku

            return dwg_oku(p, ayarlar)
        from hakedis.readers.pdf import pdf_oku

        return pdf_oku(p, ayarlar)
    except (FileNotFoundError, ValueError):
        raise
    except Exception as e:  # noqa: BLE001
        raise ValueError(
            f"{uzanti} dosyasi okunamadi: {p.name} ({type(e).__name__}: {e})"
        ) from e


__all__ = ["cizim_oku"]
