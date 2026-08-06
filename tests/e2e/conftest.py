"""Playwright (tarayici) E2E testleri icin sunucu kurulumu.

Sunucu ayri bir surecte uvicorn ile ayaklandirilir; `base_url` fixture'i
tum testler icin ayni sunucuyu paylasir. Sayfa/tarayici fixture'lari
pytest-playwright eklentisinden gelir.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

KOK = Path(__file__).resolve().parent.parent.parent


def _bos_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def base_url() -> str:
    port = _bos_port()
    env = dict(os.environ)
    env["PYTHONPATH"] = str(KOK)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "hakedis.web.server:app",
         "--host", "127.0.0.1", "--port", str(port), "--log-level", "warning"],
        cwd=str(KOK),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            with urllib.request.urlopen(url + "/api/durum", timeout=1) as r:
                if r.status == 200:
                    break
        except Exception:
            time.sleep(0.2)
    else:
        proc.kill()
        raise RuntimeError("hakedis web sunucusu baslatilamadi")
    try:
        yield url
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


@pytest.fixture(scope="session")
def plan(tmp_path_factory) -> Path:
    from ornek.ornek_plan_uret import uret
    return uret(tmp_path_factory.mktemp("e2e") / "kalip_plani.dxf")


@pytest.fixture(scope="session")
def pdf(tmp_path_factory) -> Path:
    from tests.yardimci import kalip_plani_pdf
    return kalip_plani_pdf(tmp_path_factory.mktemp("e2e") / "plan.pdf")
