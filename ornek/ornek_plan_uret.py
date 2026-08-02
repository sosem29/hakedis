#!/usr/bin/env python3
"""Test ve deneme icin sentetik bir kalip plani (DXF) uretir.

Gercek bir betonarme kalip planinin tipik ozelliklerini tasir:
  - 6 adet 30/60 kolon (kapali polyline, KOLON katmani)
  - 1 adet L seklinde 25'lik perde (PERDE katmani)
  - Iki paralel cizgi olarak cizilmis 25/50 kirisler (KIRIS katmani)
  - Bosluklu doseme (DOSEME + BOSLUK katmanlari)
  - "S01 30/60", "K101 25/50", "TD=15" tarzi etiketler (YAZI katmani)

Kullanim:
    python ornek/ornek_plan_uret.py ornek/kalip_plani.dxf
"""

from __future__ import annotations

import sys
from pathlib import Path

import ezdxf

# Tum olculer SANTIMETRE cinsindendir ($INSUNITS = 5)
AKS_X = [0, 600, 1200]
AKS_Y = [0, 500]
KOLON_B = 30  # x yonu
KOLON_H = 60  # y yonu
KIRIS_B = 25
PERDE_T = 25


def dikdortgen(merkez_x, merkez_y, en, boy):
    yx, yy = en / 2.0, boy / 2.0
    return [
        (merkez_x - yx, merkez_y - yy),
        (merkez_x + yx, merkez_y - yy),
        (merkez_x + yx, merkez_y + yy),
        (merkez_x - yx, merkez_y + yy),
    ]


def uret(hedef: Path) -> Path:
    doc = ezdxf.new("R2013", setup=True)
    doc.header["$INSUNITS"] = 5  # santimetre
    msp = doc.modelspace()

    for ad, renk in (
        ("KOLON", 1),
        ("PERDE", 6),
        ("KIRIS", 5),
        ("DOSEME", 3),
        ("BOSLUK", 2),
        ("YAZI", 7),
        ("AKS", 8),
    ):
        if ad not in doc.layers:
            doc.layers.add(ad, color=renk)

    # --- Doseme siniri ---------------------------------------------------
    d_x0, d_y0 = -KOLON_B / 2, -KOLON_H / 2
    d_x1, d_y1 = AKS_X[-1] + KOLON_B / 2, AKS_Y[-1] + KOLON_H / 2
    msp.add_lwpolyline(
        [(d_x0, d_y0), (d_x1, d_y0), (d_x1, d_y1), (d_x0, d_y1)],
        close=True,
        dxfattribs={"layer": "DOSEME"},
    )
    # Saft boslugu
    msp.add_lwpolyline(
        [(700, 200), (800, 200), (800, 280), (700, 280)],
        close=True,
        dxfattribs={"layer": "BOSLUK"},
    )

    # --- Kolonlar --------------------------------------------------------
    sayac = 0
    for iy, y in enumerate(AKS_Y):
        for ix, x in enumerate(AKS_X):
            sayac += 1
            msp.add_lwpolyline(
                dikdortgen(x, y, KOLON_B, KOLON_H),
                close=True,
                dxfattribs={"layer": "KOLON"},
            )
            msp.add_text(
                f"S{sayac:02d} {KOLON_B}/{KOLON_H}",
                height=18,
                dxfattribs={"layer": "YAZI"},
            ).set_placement((x - 25, y + KOLON_H / 2 + 12))

    # --- L seklinde perde ------------------------------------------------
    msp.add_lwpolyline(
        [
            (250, 150),
            (450, 150),
            (450, 150 + PERDE_T),
            (250 + PERDE_T, 150 + PERDE_T),
            (250 + PERDE_T, 325),
            (250, 325),
        ],
        close=True,
        dxfattribs={"layer": "PERDE"},
    )
    msp.add_text(
        f"P1 {PERDE_T}", height=18, dxfattribs={"layer": "YAZI"}
    ).set_placement((300, 250))

    # --- Kirisler (iki paralel cizgi) ------------------------------------
    yari = KIRIS_B / 2.0
    kiris_no = 100
    for y in AKS_Y:  # x dogrultusunda kirisler
        kiris_no += 1
        for ofset in (-yari, yari):
            msp.add_line(
                (AKS_X[0] - KOLON_B / 2, y + ofset),
                (AKS_X[-1] + KOLON_B / 2, y + ofset),
                dxfattribs={"layer": "KIRIS"},
            )
        msp.add_text(
            f"K{kiris_no} {KIRIS_B}/50", height=18, dxfattribs={"layer": "YAZI"}
        ).set_placement((AKS_X[1] - 60, y + yari + 8))

    for x in AKS_X:  # y dogrultusunda kirisler
        kiris_no += 1
        for ofset in (-yari, yari):
            msp.add_line(
                (x + ofset, AKS_Y[0] - KOLON_H / 2),
                (x + ofset, AKS_Y[-1] + KOLON_H / 2),
                dxfattribs={"layer": "KIRIS"},
            )
        msp.add_text(
            f"K{kiris_no} {KIRIS_B}/50", height=18, dxfattribs={"layer": "YAZI"}
        ).set_placement((x + yari + 8, AKS_Y[0] + 180))

    # --- Doseme kalinlik etiketi ve aks cizgileri ------------------------
    msp.add_text("TD=15", height=22, dxfattribs={"layer": "YAZI"}).set_placement(
        (950, 380)
    )
    for x in AKS_X:
        msp.add_line((x, -150), (x, AKS_Y[-1] + 150), dxfattribs={"layer": "AKS"})
    for y in AKS_Y:
        msp.add_line((-150, y), (AKS_X[-1] + 150, y), dxfattribs={"layer": "AKS"})

    hedef.parent.mkdir(parents=True, exist_ok=True)
    doc.saveas(str(hedef))
    return hedef


if __name__ == "__main__":
    cikti = Path(sys.argv[1] if len(sys.argv) > 1 else "ornek/kalip_plani.dxf")
    print(f"Ornek kalip plani yazildi: {uret(cikti)}")
