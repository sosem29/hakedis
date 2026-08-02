"""Cizim okuyuculari: DXF, DWG ve PDF."""

from __future__ import annotations

from pathlib import Path

from hakedis.config import Ayarlar
from hakedis.model import Cizim


def cizim_oku(yol: str | Path, ayarlar: Ayarlar) -> Cizim:
    """Uzantiya gore dogru okuyucuyu secer."""
    p = Path(yol)
    if not p.exists():
        raise FileNotFoundError(f"Dosya bulunamadi: {p}")
    uzanti = p.suffix.lower()
    if uzanti == ".dxf":
        from hakedis.readers.dxf import dxf_oku

        return dxf_oku(p, ayarlar)
    if uzanti == ".dwg":
        from hakedis.readers.dwg import dwg_oku

        return dwg_oku(p, ayarlar)
    if uzanti == ".pdf":
        from hakedis.readers.pdf import pdf_oku

        return pdf_oku(p, ayarlar)
    raise ValueError(
        f"Desteklenmeyen dosya turu: {uzanti}. Desteklenenler: .dwg, .dxf, .pdf"
    )


__all__ = ["cizim_oku"]
