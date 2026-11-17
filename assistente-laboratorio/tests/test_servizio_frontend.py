"""Step 8: servizio del front-end (pagina e inoltro al back-end), senza rete, database o modello."""
import httpx
from fastapi.testclient import TestClient

from assistente.servizio_backend.app import crea_app as crea_app_backend
from assistente.servizio_frontend.app import crea_app
from archivio_memoria import ArchivioMemoria


def backend_finto(gestore):
    return httpx.Client(transport=httpx.MockTransport(gestore), base_url="http://backend:8003")


def test_pagina_servita():
    client = TestClient(crea_app(backend_finto(lambda r: httpx.Response(500))))

    pagina = client.get("/")
    assert pagina.status_code == 200
    assert pagina.headers["content-type"].startswith("text/html")
    assert client.get("/static/index.html").status_code == 200


def test_inoltro_al_backend_vero():
    agente = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(500)), base_url="http://agente:8002")
    backend = TestClient(crea_app_backend(ArchivioMemoria(), agente))
    client = TestClient(crea_app(backend))

    creata = client.post("/api/chat")
    assert creata.status_code == 201
    assert creata.json()["titolo"] == "Nuova chat"
    id = creata.json()["id"]
    assert [c["id"] for c in client.get("/api/chat").json()] == [id]

    eliminata = client.delete(f"/api/chat/{id}")
    assert eliminata.status_code == 204
    assert eliminata.content == b""
    letta = client.get(f"/api/chat/{id}")
    assert letta.status_code == 404
    assert letta.json() == {"errore": f"Chat {id} non trovata"}


def test_inoltro_corpo_e_codice():
    ricevute = []

    def gestore(richiesta):
        ricevute.append(richiesta)
        return httpx.Response(502, json={"errore": "Errore dell'agente: x"})

    client = TestClient(crea_app(backend_finto(gestore)))
    risposta = client.post("/api/chat/3/messaggi", json={"testo": "ciao", "conferme": []})

    assert risposta.status_code == 502
    assert risposta.json() == {"errore": "Errore dell'agente: x"}
    assert ricevute[0].method == "POST"
    assert ricevute[0].url.path == "/chat/3/messaggi"
    assert httpx.Response(200, content=ricevute[0].content).json() == {"testo": "ciao", "conferme": []}


def test_backend_non_raggiungibile():
    def gestore(richiesta):
        raise httpx.ConnectError("rifiutata", request=richiesta)

    client = TestClient(crea_app(backend_finto(gestore)))
    risposta = client.get("/api/chat")

    assert risposta.status_code == 503
    assert "Back-end non raggiungibile" in risposta.json()["errore"]
