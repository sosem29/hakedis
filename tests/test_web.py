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
