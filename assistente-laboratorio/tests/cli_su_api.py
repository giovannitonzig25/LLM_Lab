"""Aiuto dei test (Step 6): la CLI parla con l'API vera dell'agente, servita in memoria da TestClient."""
from fastapi.testclient import TestClient

from assistente.servizio_agente.app import crea_app
from assistente.terminale import ClientAgente, esegui_chat


def client_su_grafo(grafo, max_passaggi=6, max_revisioni=1, **dipendenze) -> ClientAgente:
    """`dipendenze`: elenca, ottieni, stato_mcp, stato_modello di `crea_app`."""
    app = crea_app(grafo, max_passaggi=max_passaggi, max_revisioni=max_revisioni, **dipendenze)
    return ClientAgente(TestClient(app))


def chat_su_grafo(grafo, leggi, scrivi, *, max_passaggi=6, max_revisioni=1, chiedi=lambda messaggio: False, **dipendenze):
    """Equivalente dell'`esegui_chat(grafo, ...)` di prima dello Step 6, ma attraverso l'API."""
    esegui_chat(client_su_grafo(grafo, max_passaggi, max_revisioni, **dipendenze), leggi, scrivi, chiedi=chiedi)
