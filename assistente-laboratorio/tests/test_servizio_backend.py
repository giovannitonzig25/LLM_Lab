"""Step 7: back-end delle chat con archivio in memoria e agente simulato (nessun database, modello o rete)."""
import httpx
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from assistente.agente import conferma_da_richiesta
from assistente.archivio import ErroreDatabase
from assistente.servizio_agente.app import crea_app as crea_app_agente
from assistente.servizio_backend.app import crea_app
from archivio_memoria import ArchivioMemoria
from test_servizio_agente import chiamata, grafo_con


def agente_simulato(risposte, strumenti=()):
    """L'API vera dell'agente, servita in memoria, con il grafo simulato."""
    grafo, modello = grafo_con(risposte, strumenti)
    return TestClient(crea_app_agente(grafo, max_passaggi=6, max_revisioni=1)), modello


def agente_finto(gestore):
    return httpx.Client(transport=httpx.MockTransport(gestore), base_url="http://agente:8002")


def backend(agente, archivio=None):
    archivio = archivio or ArchivioMemoria()
    return TestClient(crea_app(archivio, agente)), archivio


def test_crea_elenca_leggi_elimina():
    client, _ = backend(agente_finto(lambda r: httpx.Response(500)))

    creata = client.post("/chat")
    assert creata.status_code == 201
    id = creata.json()["id"]
    assert client.get("/chat").json() == [{"id": id, "titolo": "Nuova chat", "ultimo_messaggio_il": None}]
    assert client.get(f"/chat/{id}").json() == {"id": id, "titolo": "Nuova chat", "messaggi": []}

    assert client.delete(f"/chat/{id}").status_code == 204
    assert client.get(f"/chat/{id}").status_code == 404
    assert client.get("/chat").json() == []


def test_messaggio_salvato_e_titolo():
    agente, _ = agente_simulato([AIMessage("Ciao Marco!"), AIMessage("Bene, grazie.")])
    client, _ = backend(agente)
    id = client.post("/chat").json()["id"]

    risposta = client.post(f"/chat/{id}/messaggi", json={"testo": "  Mi chiamo Marco  "})
    client.post(f"/chat/{id}/messaggi", json={"testo": "Come stai?"})

    assert risposta.status_code == 200
    assert risposta.json() == {"risposta": "Ciao Marco!", "strumenti_usati": [], "conferme_richieste": []}
    chat = client.get(f"/chat/{id}").json()
    assert chat["titolo"] == "Mi chiamo Marco"
    assert [(m["ruolo"], m["testo"]) for m in chat["messaggi"]] == [
        ("utente", "  Mi chiamo Marco  "), ("assistente", "Ciao Marco!"),
        ("utente", "Come stai?"), ("assistente", "Bene, grazie."),
    ]
    assert client.get("/chat").json()[0]["ultimo_messaggio_il"] == chat["messaggi"][-1]["creato_il"]


def test_titolo_troncato_e_chat_recente_in_cima():
    agente, _ = agente_simulato([AIMessage("a"), AIMessage("b")])
    client, _ = backend(agente)
    prima, seconda = client.post("/chat").json()["id"], client.post("/chat").json()["id"]

    client.post(f"/chat/{prima}/messaggi", json={"testo": "x" * 80})

    elenco = client.get("/chat").json()
    assert [c["id"] for c in elenco] == [prima, seconda]
    assert elenco[0]["titolo"] == "x" * 50


def test_seconda_domanda_riceve_la_cronologia():
    agente, modello = agente_simulato([AIMessage("Piacere, Marco"), AIMessage("Ti chiami Marco")])
    client, _ = backend(agente)
    id = client.post("/chat").json()["id"]

    client.post(f"/chat/{id}/messaggi", json={"testo": "Mi chiamo Marco"})
    client.post(f"/chat/{id}/messaggi", json={"testo": "Come mi chiamo?"})

    assert [m.content for m in modello.chiamate[1][1:]] == ["Mi chiamo Marco", "Piacere, Marco", "Come mi chiamo?"]


cancellate = []


def cancella(id: int) -> str:
    """Strumento distruttivo di prova: chiede la conferma della richiesta come gli strumenti MCP."""
    if not conferma_da_richiesta("cancella", {"id": id}):
        return "Errore: cancellazione non confermata dall'utente"
    cancellate.append(id)
    return "cancellata"


def test_conferma_non_salva_poi_salva():
    cancellate.clear()
    risposte = [chiamata("cancella", {"id": 3}), AIMessage("Non confermata"), chiamata("cancella", {"id": 3}), AIMessage("Fatto")]
    agente, _ = agente_simulato(risposte, [StructuredTool.from_function(cancella)])
    client, _ = backend(agente)
    id = client.post("/chat").json()["id"]

    primo = client.post(f"/chat/{id}/messaggi", json={"testo": "cancella la nota 3"}).json()
    assert primo["conferme_richieste"] == [{"strumento": "cancella", "argomenti": {"id": 3}}]
    assert cancellate == [] and client.get(f"/chat/{id}").json()["messaggi"] == []

    secondo = client.post(
        f"/chat/{id}/messaggi", json={"testo": "cancella la nota 3", "conferme": primo["conferme_richieste"]}
    ).json()
    assert cancellate == [3] and secondo["risposta"] == "Fatto"
    assert [m["testo"] for m in client.get(f"/chat/{id}").json()["messaggi"]] == ["cancella la nota 3", "Fatto"]


def _solleva_connessione(richiesta):
    raise httpx.ConnectError("connessione rifiutata", request=richiesta)


def test_agente_spento_503_e_chat_invariata():
    client, archivio = backend(agente_finto(_solleva_connessione))
    id = client.post("/chat").json()["id"]

    risposta = client.post(f"/chat/{id}/messaggi", json={"testo": "Ciao"})

    assert risposta.status_code == 503
    assert risposta.json() == {"errore": "Agente non raggiungibile su http://agente:8002"}
    assert archivio.leggi_chat(id)["messaggi"] == [] and archivio.stato_agente(id) == ([], "")


def test_modello_spento_503_con_il_messaggio_dell_agente():
    client, _ = backend(agente_finto(lambda r: httpx.Response(503, json={"errore": "LM Studio non raggiungibile"})))
    id = client.post("/chat").json()["id"]

    risposta = client.post(f"/chat/{id}/messaggi", json={"testo": "Ciao"})

    assert (risposta.status_code, risposta.json()) == (503, {"errore": "LM Studio non raggiungibile"})


def test_agente_in_errore_502_e_chat_invariata():
    client, archivio = backend(agente_finto(lambda r: httpx.Response(502, json={"errore": "risposta non valida"})))
    id = client.post("/chat").json()["id"]

    risposta = client.post(f"/chat/{id}/messaggi", json={"testo": "Ciao"})

    assert (risposta.status_code, risposta.json()) == (502, {"errore": "Errore dell'agente: risposta non valida"})
    assert archivio.leggi_chat(id)["messaggi"] == []


def test_chat_inesistente_404():
    client, _ = backend(agente_finto(lambda r: httpx.Response(500)))

    for risposta in (client.get("/chat/99"), client.post("/chat/99/messaggi", json={"testo": "x"}), client.delete("/chat/99")):
        assert (risposta.status_code, risposta.json()) == (404, {"errore": "Chat 99 non trovata"})


def test_testo_vuoto_422():
    client, _ = backend(agente_finto(lambda r: httpx.Response(500)))
    id = client.post("/chat").json()["id"]

    assert client.post(f"/chat/{id}/messaggi", json={"testo": ""}).status_code == 422


class ArchivioSpento(ArchivioMemoria):
    def elenca_chat(self):
        raise ErroreDatabase("connessione rifiutata")


def test_database_spento_503():
    client, _ = backend(agente_finto(lambda r: httpx.Response(500)), ArchivioSpento())

    risposta = client.get("/chat")

    assert (risposta.status_code, risposta.json()) == (503, {"errore": "Database non raggiungibile"})


def test_openapi_elenca_i_percorsi():
    client, _ = backend(agente_finto(lambda r: httpx.Response(500)))

    percorsi = client.get("/openapi.json").json()["paths"]

    assert {"/chat", "/chat/{id}", "/chat/{id}/messaggi"} <= set(percorsi)
    assert {"404", "502", "503"} <= set(percorsi["/chat/{id}/messaggi"]["post"]["responses"])
