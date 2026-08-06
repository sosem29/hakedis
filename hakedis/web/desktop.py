"""Masaustu uygulamasi: yerel web sunucusu + yerli pencere.

Ayri bir islem/port gerekmez; uygulama kendi arka plan sunucusunu
127.0.0.1 uzerinde baslatir ve icerigi yerli bir webview penceresinde
(macOS: WKWebView, Windows: WebView2, Linux: WebKitGTK) gosterir.

pywebview kurulu degilse arayuz varsayilan tarayicida acilir.
"""

from __future__ import annotations

import socket
import threading
import time
import webbrowser

BASLIK = "hakedis - Kirik Olcu Metrajı"


def _bos_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _sunucu_baslat(host: str, port: int) -> tuple:
    """uvicorn sunucusunu arka plan is parcaliginda baslatir.

    (server, url) dondurur; server.should_exit=True ile durdurulabilir.
    """
    import uvicorn

    from hakedis.web.server import app

    if port == 0:
        port = _bos_port()
    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    is_parcacigi = threading.Thread(target=server.run, daemon=True)
    is_parcacigi.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return server, f"http://{host}:{port}"


def tarayicida_ac(port: int = 0, host: str = "127.0.0.1") -> str:
    """Sunucuyu baslatir, varsayilan tarayiciyi acar, URL dondurur."""
    server, url = _sunucu_baslat(host, port)
    webbrowser.open(url)
    return url


def masaustu_ac(port: int = 0, host: str = "127.0.0.1", debug: bool = False) -> int:
    """Yerli webview penceresinde arayuzu acar; pencere kapaninca dondurur."""
    try:
        import webview
    except ImportError:
        print(
            "Uyari: pywebview kurulu degil; arayuz varsayilan tarayicida aciliyor.\n"
            "Masaustu penceresi icin: pip install 'hakedis[web]'"
        )
        tarayicida_ac(port, host)
        return 0

    server, url = _sunucu_baslat(host, port)
    webview.create_window(BASLIK, url, width=1400, height=920, min_size=(1100, 720))
    webview.start(debug=debug)
    server.should_exit = True
    return 0
