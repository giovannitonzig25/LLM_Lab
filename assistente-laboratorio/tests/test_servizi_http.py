import json
from datetime import date
from importlib import resources

import pytest
from fastapi.testclient import TestClient

from assistente.servizi_http.app import crea_app


@pytest.fixture()
def client():
    return TestClient(crea_app())


def test_salute(client):
    r = client.get("/salute")
    assert r.status_code == 200 and r.json() == {"stato": "ok"}


def test_giorni_lavorativi(client):
    r = client.get("/giorni-lavorativi", params={"da": "2026-11-02", "a": "2026-11-20"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["da"] == "2026-11-02" and corpo["a"] == "2026-11-20"
    assert corpo["giorni_lavorativi"] == 15
    assert "normativ" in corpo["nota"]


def test_giorni_lavorativi_esclude_festivita_nazionali(client):
    # 24-28/12/2026: 24 gio, 25 festa, 26 festa, 27 dom, 28 lun
    r = client.get("/giorni-lavorativi", params={"da": "2026-12-24", "a": "2026-12-28"})
    assert r.json()["giorni_lavorativi"] == 2


def test_scadenza(client):
    r = client.get("/scadenza", params={"da": "2026-11-09", "giorni": 10})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo == {**corpo, "da": "2026-11-09", "giorni": 10, "data_scadenza": "2026-11-23"}
    assert "normativ" in corpo["nota"]


def test_pasquetta_2027(client):
    # venerdì 26/3/2027 + 1 gg: 27-28 weekend/Pasqua, 29 Lunedì dell'Angelo, quindi martedì 30
    r = client.get("/scadenza", params={"da": "2027-03-26", "giorni": 1})
    assert r.json()["data_scadenza"] == "2027-03-30"


@pytest.mark.parametrize("params", [
    {"da": "2026-11-20", "a": "2026-11-02"},
    {"da": "2026-02-30", "a": "2026-03-02"},
    {"da": "2025-01-01", "a": "2026-01-10"},
    {"da": "2026-01-01", "a": "2028-01-01"},
    {"da": "2028-02-29", "a": "2028-03-01"},
    {"da": "domani", "a": "2026-03-01"},
    {"da": "2026-03-01"},
])
def test_giorni_lavorativi_input_non_validi(client, params):
    r = client.get("/giorni-lavorativi", params=params)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str) and r.json()["detail"]


@pytest.mark.parametrize("giorni", ["-1", "0", "100000", "366", "abc", "1.5", ""])
def test_scadenza_giorni_non_validi(client, giorni):
    r = client.get("/scadenza", params={"da": "2026-11-09", "giorni": giorni})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)


def test_scadenza_data_fuori_anni(client):
    assert client.get("/scadenza", params={"da": "2028-02-29", "giorni": 1}).status_code == 422
    assert client.get("/scadenza", params={"da": "2026-02-30", "giorni": 1}).status_code == 422
    assert client.get("/scadenza", params={"giorni": 1}).status_code == 422


def test_scadenza_oltre_gli_anni_coperti(client):
    # il risultato uscirebbe dal 2027: festività non note, quindi rifiuto
    r = client.get("/scadenza", params={"da": "2027-12-20", "giorni": 30})
    assert r.status_code == 422
    assert "2027" in r.json()["detail"]


def test_file_festivita_contiene_le_nazionali():
    testo = resources.files("assistente.servizi_http").joinpath("dati/festivita.json").read_text(encoding="utf-8")
    date_ = {date.fromisoformat(d) for d in json.loads(testo)}
    assert len(date_) == 24
    for d in [date(2026, 4, 5), date(2026, 4, 6), date(2027, 3, 28), date(2027, 3, 29),
              date(2026, 6, 2), date(2027, 12, 26)]:
        assert d in date_
