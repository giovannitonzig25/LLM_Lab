"""Catalogo: API FastAPI e strumenti HTTP (cerca_catalogo, dettaglio_catalogo)."""
import httpx
import pytest
from fastapi.testclient import TestClient

from assistente.servizi_http.app import crea_app
from assistente.strumenti_http import crea_strumenti_http

NOTA = "Catalogo di esempio: corsi fittizi."


@pytest.fixture()
def client():
    return TestClient(crea_app())


# --- API ---
def test_catalogo_ricerca(client):
    r = client.get("/catalogo", params={"q": "udine"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["totale"] >= 3 and 1 <= len(corpo["risultati"]) <= 5
    assert all(set(x) == {"codice", "titolo", "settore", "sede"} for x in corpo["risultati"])
    assert all(x["sede"] == "Udine" for x in corpo["risultati"])
    assert "fittizi" in corpo["nota"]


def test_catalogo_max_risultati(client):
    corpo = client.get("/catalogo", params={"q": "udine", "max_risultati": 2}).json()
    assert len(corpo["risultati"]) == 2 and corpo["totale"] > 2


def test_catalogo_senza_risultati(client):
    r = client.get("/catalogo", params={"q": "astrofisica"})
    assert r.status_code == 200 and r.json()["totale"] == 0 and r.json()["risultati"] == []


@pytest.mark.parametrize("params", [
    {}, {"q": ""}, {"q": "   "}, {"q": "x" * 101},
    {"q": "udine", "max_risultati": 0}, {"q": "udine", "max_risultati": 11},
    {"q": "udine", "max_risultati": "abc"}, {"q": "udine", "max_risultati": ""},
])
def test_catalogo_input_non_validi(client, params):
    r = client.get("/catalogo", params=params)
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str) and r.json()["detail"]


def test_dettaglio_corso(client):
    r = client.get("/catalogo/ITS-003")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["codice"] == "ITS-003"
    assert {"titolo", "settore", "sede", "durata_ore", "descrizione"} <= set(corpo)
    assert "fittizi" in corpo["nota"]
    assert client.get("/catalogo/its-003").json()["codice"] == "ITS-003"


def test_dettaglio_inesistente_404(client):
    r = client.get("/catalogo/ITS-999")
    assert r.status_code == 404 and "ITS-999" in r.json()["detail"]


# --- strumenti ---
BASE = "http://servizi:8000"
RICERCA = {"totale": 3, "nota": NOTA, "risultati": [
    {"codice": "ITS-001", "titolo": "Sviluppo software", "settore": "Informatica", "sede": "Udine"},
    {"codice": "ITS-003", "titolo": "Analisi dei dati", "settore": "Informatica", "sede": "Udine"},
]}
DETTAGLIO = {"codice": "ITS-003", "titolo": "Analisi dei dati", "settore": "Informatica", "sede": "Udine",
             "durata_ore": 1600, "descrizione": "Corso di esempio.", "nota": NOTA}


def costruisci(gestore):
    richieste = []

    def con_registro(richiesta):
        richieste.append(richiesta)
        return gestore(richiesta)

    client = httpx.Client(transport=httpx.MockTransport(con_registro))
    return {t.name: t for t in crea_strumenti_http(BASE, 3.0, client=client)}, richieste


def test_nomi_e_descrizioni_distinte():
    strumenti, _ = costruisci(lambda r: httpx.Response(200, json=RICERCA))
    assert {"cerca_catalogo", "dettaglio_catalogo"} <= set(strumenti)
    assert "parola chiave" in strumenti["cerca_catalogo"].description
    assert "codice" in strumenti["dettaglio_catalogo"].description
    assert "query" in strumenti["cerca_catalogo"].args and "max_risultati" in strumenti["cerca_catalogo"].args


def test_cerca_catalogo_richiesta_e_risultato():
    strumenti, richieste = costruisci(lambda r: httpx.Response(200, json=RICERCA))
    testo = strumenti["cerca_catalogo"].invoke({"query": "Udine"})
    r = richieste[0]
    assert r.url.path == "/catalogo" and dict(r.url.params) == {"q": "Udine", "max_risultati": "5"}
    assert "ITS-001" in testo and "ITS-003" in testo and "Udine" in testo and "fittizi" in testo
    assert "1600" not in testo and "Corso di esempio" not in testo


def test_cerca_catalogo_dichiara_i_risultati_non_mostrati():
    strumenti, _ = costruisci(lambda r: httpx.Response(200, json={**RICERCA, "totale": 7}))
    testo = strumenti["cerca_catalogo"].invoke({"query": "Udine", "max_risultati": 2})
    assert "7" in testo and "2" in testo


def test_cerca_catalogo_nessun_risultato():
    corpo = {"totale": 0, "risultati": [], "nota": NOTA}
    strumenti, _ = costruisci(lambda r: httpx.Response(200, json=corpo))
    testo = strumenti["cerca_catalogo"].invoke({"query": "astrofisica"})
    assert testo.startswith("Nessun corso trovato") and "astrofisica" in testo
    assert not testo.startswith("Errore")


def test_dettaglio_catalogo_richiesta_e_risultato():
    strumenti, richieste = costruisci(lambda r: httpx.Response(200, json=DETTAGLIO))
    testo = strumenti["dettaglio_catalogo"].invoke({"codice": "ITS-003"})
    assert richieste[0].url.path == "/catalogo/ITS-003"
    assert "1600" in testo and "Analisi dei dati" in testo and "Corso di esempio." in testo and "fittizi" in testo


def test_dettaglio_catalogo_inesistente():
    strumenti, _ = costruisci(lambda r: httpx.Response(404, json={"detail": "Corso ITS-999 non trovato."}))
    assert strumenti["dettaglio_catalogo"].invoke({"codice": "ITS-999"}) == "Errore: corso ITS-999 non trovato"


def test_dettaglio_catalogo_codice_con_caratteri_speciali_e_codificato():
    strumenti, richieste = costruisci(lambda r: httpx.Response(404, json={"detail": "x"}))
    strumenti["dettaglio_catalogo"].invoke({"codice": "../salute"})
    percorso = richieste[0].url.raw_path.decode()
    assert percorso.startswith("/catalogo/") and percorso.count("/") == 2


def test_catalogo_errori_del_servizio():
    strumenti, _ = costruisci(lambda r: httpx.Response(422, json={"detail": "Parametro q mancante."}))
    assert strumenti["cerca_catalogo"].invoke({"query": "x"}) == "Errore: Parametro q mancante."

    def spento(richiesta):
        raise httpx.ConnectError("no")

    strumenti, _ = costruisci(spento)
    assert strumenti["cerca_catalogo"].invoke({"query": "x"}).startswith("Errore: servizio non raggiungibile")
    assert strumenti["dettaglio_catalogo"].invoke({"codice": "ITS-001"}).startswith(
        "Errore: servizio non raggiungibile")


def test_catalogo_risposte_non_valide():
    incompleta = {"totale": 1, "risultati": [{"codice": "A"}]}
    strumenti, _ = costruisci(lambda r: httpx.Response(200, json=incompleta))
    assert strumenti["cerca_catalogo"].invoke({"query": "x"}).startswith("Errore: risposta del servizio non valida")
    strumenti, _ = costruisci(lambda r: httpx.Response(200, json={"codice": "A"}))
    assert strumenti["dettaglio_catalogo"].invoke({"codice": "A"}).startswith(
        "Errore: risposta del servizio non valida")


def test_cerca_catalogo_argomenti_sbagliati_danno_errore_chiaro():
    strumenti, richieste = costruisci(lambda r: httpx.Response(200, json=RICERCA))
    testo = strumenti["cerca_catalogo"].invoke({"query": "x", "max_risultati": "tanti"})
    assert testo.startswith("Errore:") and "cerca_catalogo" in testo and "\n" not in testo and richieste == []


@pytest.mark.parametrize("nota", [None, 5, ["x"]])
def test_nota_non_testuale_non_solleva(nota):
    strumenti, _ = costruisci(lambda r: httpx.Response(200, json={**RICERCA, "nota": nota}))
    testo = strumenti["cerca_catalogo"].invoke({"query": "Udine"})
    assert "ITS-001" in testo and not testo.startswith("Errore")
    strumenti, _ = costruisci(lambda r: httpx.Response(200, json={**RICERCA, "totale": 0, "risultati": [], "nota": nota}))
    assert strumenti["cerca_catalogo"].invoke({"query": "x"}).startswith("Nessun corso trovato")
    strumenti, _ = costruisci(lambda r: httpx.Response(200, json={**DETTAGLIO, "nota": nota}))
    assert "1600" in strumenti["dettaglio_catalogo"].invoke({"codice": "ITS-003"})


@pytest.mark.parametrize("codice", ["", "   ", "."])
def test_dettaglio_con_codice_vuoto_dice_che_manca_senza_chiamare_il_servizio(codice):
    strumenti, richieste = costruisci(lambda r: httpx.Response(200, json=DETTAGLIO))
    testo = strumenti["dettaglio_catalogo"].invoke({"codice": codice})
    assert testo.startswith("Errore:") and "codice" in testo and richieste == []
