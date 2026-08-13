"""Web arayuzu (FastAPI) uctan uca testleri."""

from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hakedis.web.server import app  # noqa: E402

from ornek.ornek_plan_uret import uret  # noqa: E402
from tests.yardimci import kalip_plani_pdf  # noqa: E402


@pytest.fixture(scope="module")
def plan(tmp_path_factory) -> Path:
    return uret(tmp_path_factory.mktemp("web") / "kalip_plani.dxf")


@pytest.fixture(scope="module")
def pdf(tmp_path_factory) -> Path:
    return kalip_plani_pdf(tmp_path_factory.mktemp("web") / "plan.pdf")


@pytest.fixture(scope="module")
def mahal_plani(tmp_path_factory) -> Path:
    from tests.test_mahal import _mahal_plani

    return _mahal_plani(tmp_path_factory.mktemp("web") / "mahal.dxf")


@pytest.fixture(scope="module")
def donati_plani(tmp_path_factory) -> Path:
    from tests.test_donati import _donati_plani

    return _donati_plani(tmp_path_factory.mktemp("web") / "donati.dxf")


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestSayfalar:
    def test_anasayfa(self, client):
        r = client.get("/")
        assert r.status_code == 200
        assert "hakedis" in r.text
        assert "Metraj" in r.text

    def test_statik_dosyalar(self, client):
        r = client.get("/static/app.js")
        assert r.status_code == 200
        assert "baslangicYukle" in r.text

    def test_durum(self, client):
        r = client.get("/api/durum")
        assert r.status_code == 200
        veri = r.json()
        assert veri["versiyon"]
        assert "varsayilan" in veri
        assert any(b["ad"].startswith("ezdxf") and b["tamam"] for b in veri["bagimliliklar"])

    def test_varsayilan_yaml(self, client):
        r = client.get("/api/varsayilan")
        assert r.status_code == 200
        veri = r.json()
        assert "katmanlar" in veri["varsayilan_yaml"]
        assert veri["varsayilan"]["kat"]["kat_yuksekligi"] == 3.0


class TestYaml:
    def test_coz_uret_cevirimi(self, client):
        uret = client.post(
            "/api/yaml-uret",
            json={"ayarlar": {"kat": {"kat_yuksekligi": 3.2}, "donati": {"aktif": True}}},
        )
        assert uret.status_code == 200
        metin = uret.json()["yaml"]

        coz = client.post("/api/yaml-coz", json={"yaml": metin})
        assert coz.status_code == 200
        ayarlar = coz.json()["ayarlar"]
        # varsayilanlar korunuyor, yeni degerler bindiriliyor
        assert ayarlar["kat"]["kat_yuksekligi"] == 3.2
        assert ayarlar["donati"]["aktif"] is True
        assert "katmanlar" in ayarlar

    def test_gecersiz_yaml(self, client):
        r = client.post("/api/yaml-coz", json={"yaml": "]:bozuk["})
        assert r.status_code == 422


class TestMetraj:
    def test_metraj_api(self, client, plan):
        r = client.post(
            "/api/metraj",
            files={"dosya": ("kalip_plani.dxf", plan.read_bytes(), "application/dxf")},
            data={
                "kat_adi": "1. Normal Kat",
                "ayarlar": json.dumps({"donati": {"aktif": True}}),
            },
        )
        assert r.status_code == 200, r.text
        veri = r.json()
        assert veri["kat"] == "1. Normal Kat"
        assert veri["ozet"]["Kolon"]["adet"] == 6
        assert veri["ozet"]["Doseme"]["beton_m3"] == pytest.approx(10.212, abs=1e-3)
        assert veri["ozet"]["Kolon"]["demir_kg"] > 0
        assert veri["satirlar"]
        assert "<svg" in veri["svg"]
        # Excel base64: zip sihirli sayisiyla baslar
        ex = base64.b64decode(veri["excel_b64"])
        assert ex[:2] == b"PK"

    def test_metraj_gecersiz_tur(self, client):
        r = client.post(
            "/api/metraj",
            files={"dosya": ("plan.txt", b"merhaba", "text/plain")},
        )
        assert r.status_code == 422

    def test_metraj_yaml_yapilandirma(self, client, plan):
        r = client.post(
            "/api/metraj",
            files={"dosya": ("kalip_plani.dxf", plan.read_bytes(), "application/dxf")},
            data={"yaml": "donati:\n  aktif: true\n", "kat_adi": "YAML Kat"},
        )
        assert r.status_code == 200, r.text
        veri = r.json()
        assert veri["kat"] == "YAML Kat"
        # donati.aktif varsayilanlarla birlestirildi, demir satiri uretildi
        assert veri["ozet"]["Kolon"]["demir_kg"] > 0

    def test_metraj_mahal_dosyasi(self, client, plan, mahal_plani):
        r = client.post(
            "/api/metraj",
            files={
                "dosya": ("kalip_plani.dxf", plan.read_bytes(), "application/dxf"),
                "mahal_dosya": ("mahal.dxf", mahal_plani.read_bytes(), "application/dxf"),
            },
            data={"ayarlar": json.dumps({"siva": {"aktif": True}})},
        )
        assert r.status_code == 200, r.text
        veri = r.json()
        assert veri["parametreler"]["mahal"]["adet"] == 2
        satirlar = veri["satirlar"]
        kap = sum(s["alan"] for s in satirlar if s["eleman"] == "KAPLAMA")
        assert kap == pytest.approx(37.0, abs=1e-3)
        siva = next(s for s in satirlar if s["eleman"] == "SIVA")
        assert siva["alan"] == pytest.approx(102.0, abs=1e-3)

    def test_metraj_donati_dosyasi(self, client, plan, donati_plani):
        r = client.post(
            "/api/metraj",
            files={
                "dosya": ("kalip_plani.dxf", plan.read_bytes(), "application/dxf"),
                "donati_dosya": ("donati.dxf", donati_plani.read_bytes(), "application/dxf"),
            },
        )
        assert r.status_code == 200, r.text
        veri = r.json()
        # donati plani otomatik plan_okuma acar ve plan esasli kg satiri uretir
        assert veri["parametreler"]["donati"]["etiket"] == 3
        plan_satirlar = [
            s for s in veri["satirlar"] if "DONATI PLANINDAN" in (s["tanim"] or "")
        ]
        assert plan_satirlar
        assert any("KATSAYI" in (s["tanim"] or "") for s in veri["satirlar"]) is False


class TestToplu:
    def test_toplu_api(self, client, plan):
        r = client.post(
            "/api/toplu",
            files=[
                ("dosyalar", ("giris.dxf", plan.read_bytes(), "application/dxf")),
                ("dosyalar", ("kat1.dxf", plan.read_bytes(), "application/dxf")),
            ],
            data={"kat_adlari": json.dumps(["Giris", "1. Kat"])},
        )
        assert r.status_code == 200, r.text
        veri = r.json()
        assert veri["tur"] == "toplu"
        assert len(veri["katlar"]) == 2
        assert veri["katlar"][0]["kat"] == "Giris"
        # iki ozdes kat: toplam tek katın iki kati
        tek = veri["katlar"][0]["ozet"]["Doseme"]["beton_m3"]
        assert veri["toplam"]["Doseme"]["beton_m3"] == pytest.approx(2 * tek, abs=1e-3)
        assert veri["excel_b64"]
        assert base64.b64decode(veri["excel_b64"])[:2] == b"PK"


class TestProjeler:
    def test_proje_kaydet_listele_yukle_sil(self, client, monkeypatch, tmp_path):
        import hakedis.web.server as server

        # Projeleri test dizinine yaz
        monkeypatch.setattr(server, "PROJE_DIZINI", tmp_path / "projeler")

        # kaydet
        r = client.post(
            "/api/projeler",
            json={
                "ad": "Test Projesi",
                "kaynak": "plan.dxf",
                "tip": "metraj",
                "ayarlar": {"donati": {"aktif": True}},
                "veri": {"kat": "1. Kat", "satirlar": [{"poz": "16.058/1-K"}]},
            },
        )
        assert r.status_code == 200, r.text

        # listele
        r = client.get("/api/projeler")
        assert r.status_code == 200
        projeler = r.json()["projeler"]
        assert len(projeler) == 1
        assert projeler[0]["ad"] == "Test Projesi"
        assert projeler[0]["kaynak"] == "plan.dxf"

        # yukle
        r = client.get("/api/projeler/Test_Projesi")
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["ad"] == "Test Projesi"
        assert p["ayarlar"]["donati"]["aktif"] is True
        assert p["veri"]["satirlar"][0]["poz"] == "16.058/1-K"

        # varolmayan proje yuklenemez
        r = client.get("/api/projeler/bulunmaz")
        assert r.status_code == 404

        # sil
        r = client.delete("/api/projeler/Test_Projesi")
        assert r.status_code == 200
        assert client.get("/api/projeler").json()["projeler"] == []

    def test_proje_gecersiz_ad(self, client, monkeypatch, tmp_path):
        import hakedis.web.server as server

        monkeypatch.setattr(server, "PROJE_DIZINI", tmp_path / "projeler")
        r = client.post("/api/projeler", json={"ad": "   ", "veri": {}})
        assert r.status_code == 422

    def test_proje_ayni_adi_ustune_yazar(self, client, monkeypatch, tmp_path):
        import hakedis.web.server as server

        monkeypatch.setattr(server, "PROJE_DIZINI", tmp_path / "projeler")
        client.post("/api/projeler", json={"ad": "A", "kaynak": "x.dxf", "veri": {"a": 1}})
        client.post("/api/projeler", json={"ad": "A", "kaynak": "y.dxf", "veri": {"a": 2}})
        projeler = client.get("/api/projeler").json()["projeler"]
        assert len(projeler) == 1
        assert projeler[0]["kaynak"] == "y.dxf"


class TestPdf:
    def test_pdf_incele(self, client, pdf):
        r = client.post(
            "/api/pdf-incele",
            files={"dosya": ("plan.pdf", pdf.read_bytes(), "application/pdf")},
            data={"sayfa": "1"},
        )
        assert r.status_code == 200, r.text
        veri = r.json()
        assert veri["sayfa_sayisi"] == 1
        assert veri["renkler"], "vektor PDF renk dokumu uretmeli"
