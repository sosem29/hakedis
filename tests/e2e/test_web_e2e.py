"""Playwright ile web arayuzu uctan uca testleri.

Chromium'da gercek bir tarayici kullanilarak form akislari denenir:
metraj yukleme, maliyet ozeti, tekrarlanan kat (adet), Maliyet sekmesi
(fiyat onerisi) ve beton sinifi secimi.
"""

from __future__ import annotations

import pytest

pytest.importorskip("playwright.sync_api")
pytest.importorskip("pytest_playwright")
pytestmark = pytest.mark.e2e


def _metraj_sonuc_gorunene_kadar(page):
    page.wait_for_selector("#metraj-sonuc:not([hidden])", timeout=30000)
    assert page.is_hidden("#metraj-hata")


def test_anasayfa_menu(base_url, page):
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector("#surum-alani", timeout=15000)
    page.wait_for_function(
        "document.querySelector('#surum-alani').textContent.includes('v')"
    )
    assert page.title().startswith("hakedis")
    secmeler = page.locator(".menu-ogesi").all_inner_texts()
    birlesik = " ".join(secmeler)
    for beklenen in ("Metraj", "Eşleştir", "Toplu Metraj", "Maliyet", "PDF İncele", "Ayarlar"):
        assert beklenen in birlesik


def test_metraj_dxf(base_url, page, plan):
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector("#surum-alani", timeout=15000)
    page.set_input_files("#metraj-dosya", str(plan))
    page.fill("#metraj-kat-adi", "E2E Kat")
    page.click("#metraj-hesapla")
    _metraj_sonuc_gorunene_kadar(page)
    icerik = page.locator("#metraj-sonuc").inner_text()
    assert "E2E Kat" in icerik
    assert "Kolon" in icerik and "Döşeme" in icerik
    assert page.locator("#metraj-sonuc .pafta-kapsayici img").count() > 0


def test_metraj_maliyet_ozeti(base_url, page, plan):
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector("#surum-alani", timeout=15000)
    page.set_input_files("#metraj-dosya", str(plan))
    page.locator('#metraj-hizli-form input[data-yol="maliyet.aktif"] + .kaydirici').click()
    assert page.locator('#metraj-hizli-form input[data-yol="maliyet.aktif"]').is_checked()
    page.click("#metraj-hesapla")
    _metraj_sonuc_gorunene_kadar(page)
    icerik = page.locator("#metraj-sonuc").inner_text()
    assert "Yaklaşık Maliyet" in icerik
    assert "GENEL TOPLAM" in icerik


def test_metraj_pdf(base_url, page, pdf):
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector("#surum-alani", timeout=15000)
    page.set_input_files("#metraj-dosya", str(pdf))
    page.click("#metraj-hesapla")
    _metraj_sonuc_gorunene_kadar(page)
    assert "Kolon" in page.locator("#metraj-sonuc").inner_text()


def test_toplu_tekrarlanan_kat(base_url, page, plan):
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector("#surum-alani", timeout=15000)
    page.click('.menu-ogesi[data-sekme="toplu"]')
    satir = page.locator(".toplu-satir").first
    satir.locator("input[type=file]").set_input_files(str(plan))
    satir.locator("input[type=text]").fill("Zemin")
    satir.locator(".toplu-adet input").fill("2")
    page.click("#toplu-hesapla")
    page.wait_for_selector("#toplu-sonuc:not([hidden])", timeout=30000)
    assert page.is_hidden("#toplu-hata")
    icerik = page.locator("#toplu-sonuc").inner_text()
    assert "Zemin (1/2)" in icerik and "Zemin (2/2)" in icerik
    assert "TOPLAM" in icerik


def test_maliyet_sekmesi_fiyat_onerisi(base_url, page, plan):
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector("#surum-alani", timeout=15000)

    # Once metraj uret ki poz listesi dolsun
    page.set_input_files("#metraj-dosya", str(plan))
    page.click("#metraj-hesapla")
    _metraj_sonuc_gorunene_kadar(page)

    # Maliyet sekmesi: pozlar tablosu gelmeli
    page.click('.menu-ogesi[data-sekme="maliyet"]')
    page.wait_for_selector("#maliyet-form [data-maliyet-fiyat]", timeout=15000)
    poz_sayisi = page.locator("#maliyet-form [data-maliyet-fiyat]").count()
    assert poz_sayisi > 0

    # Varsayilan fiyatlardan birini sil -> o poz "fiyatsiz" kalir
    ilk = page.locator("#maliyet-form [data-maliyet-fiyat]").first
    silinen_poz = ilk.get_attribute("data-maliyet-fiyat")
    ilk.fill("")

    # Hesapla -> sonucta fiyatsiz pozlar icin oneri butonu cikmali
    page.click("#maliyet-hesapla")
    page.wait_for_selector("#maliyet-sonuc:not([hidden])", timeout=15000)
    sonuc = page.locator("#maliyet-sonuc").inner_text()
    assert "GENEL TOPLAM" in sonuc
    assert "Fiyat tanımsız" in sonuc
    oneri = page.locator("#maliyet-sonuc [data-oner-sonuc]").first
    assert oneri.count() > 0

    # Oneriye tikla -> fiyat geri dolar ve form da dolar
    oneri.click()
    page.wait_for_selector("#maliyet-sonuc:not([hidden])", timeout=15000)
    dolu = page.locator(f'#maliyet-form [data-maliyet-fiyat="{silinen_poz}"]').input_value()
    assert dolu != ""


def test_ayarlar_beton_sinifi(base_url, page):
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_selector("#surum-alani", timeout=15000)
    page.click('.menu-ogesi[data-sekme="ayarlar"]')
    secim = page.locator('select[data-yol="kat.beton_sinifi"]')
    secim.wait_for(state="attached", timeout=15000)
    assert secim.input_value() == "C25/30"
    secim.select_option("C30/37")
    assert secim.input_value() == "C30/37"
