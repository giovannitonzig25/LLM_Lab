"""API del back-end (Step 7, spec «API» ed «Errori»).

Il back-end conserva `cronologia` e `riassunto` dell'agente senza interpretarli: nessuna logica LangGraph qui.
In caso di errore non si salva nulla; domanda e risposta si salvano insieme solo dopo la risposta dell'agente.
"""
import logging
from datetime import datetime
from typing import Any

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from assistente.archivio import ChatNonTrovata, ErroreDatabase

LOG = logging.getLogger("assistente.servizio_backend")
DATABASE_NON_RAGGIUNGIBILE = "Database non raggiungibile"


class Conferma(BaseModel):
    strumento: str
    argomenti: dict[str, Any] = Field(default_factory=dict)


class StrumentoUsato(BaseModel):
    nome: str
    argomenti: dict[str, Any]


class ChatCreata(BaseModel):
    id: int
    titolo: str
    creata_il: datetime


class ChatInElenco(BaseModel):
    id: int
    titolo: str
    ultimo_messaggio_il: datetime | None


class Messaggio(BaseModel):
    ruolo: str
    testo: str
    creato_il: datetime


class Chat(BaseModel):
    id: int
    titolo: str
    messaggi: list[Messaggio]


class NuovoMessaggio(BaseModel):
    testo: str = Field(min_length=1, description="Domanda dell'utente.")
    conferme: list[Conferma] = Field(
        default_factory=list,
        description="Strumenti distruttivi confermati dall'utente: si ripete la stessa domanda con le "
        "`conferme_richieste` della risposta precedente.",
    )


class RispostaMessaggio(BaseModel):
    risposta: str
    strumenti_usati: list[StrumentoUsato]
    conferme_richieste: list[Conferma] = Field(
        description="Se non è vuota, nulla è stato salvato: chiedere all'utente e ripetere la domanda con `conferme`."
    )


class Errore(BaseModel):
    errore: str


def _errore(codice: int, testo: str) -> JSONResponse:
    return JSONResponse(status_code=codice, content={"errore": testo})


def _testo_errore(risposta: httpx.Response) -> str:
    try:
        return str(risposta.json()["errore"])
    except (ValueError, KeyError, TypeError):
        return f"HTTP {risposta.status_code}"


def crea_app(archivio, agente: httpx.Client) -> FastAPI:
    """App del back-end; `archivio` come `ArchivioPostgres`, `agente` con `base_url` dell'agente HTTP."""
    app = FastAPI(
        title="Back-end dell'assistente",
        description="Unico punto di contatto del front-end: gestisce le chat, le salva in PostgreSQL e "
        "inoltra le domande all'agente. Errori nel formato `{\"errore\": ...}`; in caso di errore nulla è salvato.",
    )
    non_trovata = {404: {"model": Errore, "description": "Chat inesistente"}}
    database = {503: {"model": Errore, "description": "Database non raggiungibile"}}

    @app.exception_handler(ChatNonTrovata)
    def _chat_non_trovata(request: Request, errore: ChatNonTrovata):
        return _errore(404, f"Chat {errore.args[0]} non trovata")

    @app.exception_handler(ErroreDatabase)
    def _database(request: Request, errore: ErroreDatabase):
        LOG.warning("database: %s", errore)
        return _errore(503, DATABASE_NON_RAGGIUNGIBILE)

    @app.post("/chat", status_code=201, response_model=ChatCreata, responses=database)
    def crea():
        """Crea una chat vuota e ne restituisce l'identificativo."""
        return archivio.crea_chat()

    @app.get("/chat", response_model=list[ChatInElenco], responses=database)
    def elenca():
        """Chat con titolo e data dell'ultimo messaggio, dalla più recente."""
        return archivio.elenca_chat()

    @app.get("/chat/{id}", response_model=Chat, responses=non_trovata | database)
    def leggi(id: int):
        """Messaggi della chat in ordine cronologico."""
        return archivio.leggi_chat(id)

    @app.post(
        "/chat/{id}/messaggi",
        response_model=RispostaMessaggio,
        responses=non_trovata | {
            502: {"model": Errore, "description": "L'agente ha risposto con un errore"},
            503: {"model": Errore, "description": "Agente non raggiungibile, modello spento o database non raggiungibile"},
        },
    )
    def invia(id: int, messaggio: NuovoMessaggio):
        """Inoltra la domanda all'agente; salva domanda e risposta solo se l'agente risponde senza chiedere conferme."""
        cronologia, riassunto = archivio.stato_agente(id)
        corpo = {
            "messaggio": messaggio.testo,
            "cronologia": cronologia,
            "riassunto": riassunto,
            "conferme": [c.model_dump() for c in messaggio.conferme],
        }
        try:
            risposta = agente.post("/chat", json=corpo)
        except httpx.TransportError as errore:
            LOG.warning("agente non raggiungibile: %s", errore)
            return _errore(503, f"Agente non raggiungibile su {agente.base_url}")
        if risposta.status_code == 503:
            return _errore(503, _testo_errore(risposta))
        if risposta.status_code != 200:
            return _errore(502, f"Errore dell'agente: {_testo_errore(risposta)}")
        esito = risposta.json()
        if not esito["conferme_richieste"]:
            archivio.aggiungi_scambio(id, messaggio.testo, esito["risposta"], esito["cronologia"], esito["riassunto"])
        return esito

    @app.delete("/chat/{id}", status_code=204, responses=non_trovata | database)
    def elimina(id: int):
        """Elimina la chat e i suoi messaggi."""
        archivio.elimina_chat(id)
        return Response(status_code=204)

    return app
