"""API HTTP dell'agente (Step 6, spec §4): senza stato, la conversazione arriva e torna con ogni richiesta."""
import logging
import time
from collections.abc import Callable, Sequence
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage, messages_from_dict, messages_to_dict
from pydantic import BaseModel, Field, model_validator

from assistente.agente import ErroreModello, Sessione, esegui_turno_api
from assistente.comandi import ErroreComando, converti_messaggi
from assistente.mcp_client import ErroreMcp, PromptMcp

LOG = logging.getLogger("assistente.servizio_agente")
NON_CONFIGURATO = "non configurato"
PROMPT_NON_CONFIGURATI = "client non configurato."


class Conferma(BaseModel):
    strumento: str
    argomenti: dict[str, Any] = Field(default_factory=dict)


class MessaggioPrompt(BaseModel):
    ruolo: str
    testo: str


class RichiestaChat(BaseModel):
    messaggio: str | None = Field(None, description="Domanda dell'utente (alternativa a `messaggi`).")
    messaggi: list[MessaggioPrompt] | None = Field(
        None, description="Messaggi di un prompt MCP, l'ultimo dell'utente (alternativa a `messaggio`)."
    )
    cronologia: list[dict[str, Any]] = Field(
        default_factory=list, description="Messaggi precedenti, serializzati con `messages_to_dict` di LangChain."
    )
    riassunto: str = ""
    conferme: list[Conferma] = Field(
        default_factory=list, description="Strumenti distruttivi confermati dall'utente per questa richiesta."
    )

    @model_validator(mode="after")
    def _uno_solo(self):
        if (self.messaggio is None) == (self.messaggi is None):
            raise ValueError("serve esattamente uno tra `messaggio` e `messaggi`")
        return self


class StrumentoUsato(BaseModel):
    nome: str
    argomenti: dict[str, Any]


class RispostaChat(BaseModel):
    risposta: str
    cronologia: list[dict[str, Any]]
    riassunto: str
    strumenti_usati: list[StrumentoUsato]
    conferme_richieste: list[Conferma]


class Errore(BaseModel):
    errore: str


class ArgomentoPromptApi(BaseModel):
    nome: str
    descrizione: str
    obbligatorio: bool


class PromptApi(BaseModel):
    nome: str
    descrizione: str
    argomenti: list[ArgomentoPromptApi]


class RichiestaPrompt(BaseModel):
    argomenti: dict[str, str] = Field(default_factory=dict)


def _errore(codice: int, testo: str) -> JSONResponse:
    return JSONResponse(status_code=codice, content={"errore": testo})


def crea_app(
    grafo,
    *,
    max_passaggi: int,
    max_revisioni: int,
    elenca: Callable[[], Sequence[PromptMcp]] | None = None,
    ottieni: Callable[[str, dict[str, str]], list[tuple[str, str]]] | None = None,
    stato_mcp: Callable[[], str] | None = None,
    stato_modello: Callable[[], str] | None = None,
) -> FastAPI:
    """App FastAPI dell'agente; dipendenze iniettate (nei test: grafo simulato, MCP finto)."""
    app = FastAPI(
        title="Agente del laboratorio",
        description="L'agente LangGraph come servizio HTTP senza stato: cronologia e riassunto arrivano e tornano.",
    )
    errori = {503: {"model": Errore}, 502: {"model": Errore}}

    @app.post("/chat", response_model=RispostaChat, responses=errori)
    def chat(richiesta: RichiestaChat):
        """Un turno della conversazione: risposta, cronologia aggiornata, strumenti usati e conferme richieste."""
        if richiesta.messaggio is not None:
            nuovi = [HumanMessage(richiesta.messaggio)]
        else:
            try:
                nuovi = converti_messaggi([(m.ruolo, m.testo) for m in richiesta.messaggi])
            except ErroreComando as errore:
                return _errore(422, str(errore))
        try:
            sessione = Sessione(tuple(messages_from_dict(richiesta.cronologia)), richiesta.riassunto)
        except (KeyError, TypeError, ValueError) as errore:
            return _errore(422, f"cronologia non valida: {errore}")
        inizio = time.monotonic()
        try:
            esito = esegui_turno_api(
                grafo, sessione, nuovi, max_passaggi, max_revisioni=max_revisioni,
                conferme=[c.model_dump() for c in richiesta.conferme],
            )
        except ErroreModello as errore:
            LOG.warning("turno: esito=errore codice=%s durata=%.1fs", errore.codice, time.monotonic() - inizio)
            return _errore(errore.codice, str(errore))
        LOG.info(
            "turno: esito=%s strumenti=%s conferme_richieste=%s durata=%.1fs",
            "limite" if esito.limite else "risposta",
            [s["nome"] for s in esito.strumenti_usati],
            [c["strumento"] for c in esito.conferme_richieste],
            time.monotonic() - inizio,
        )
        return RispostaChat(
            risposta=esito.risposta,
            cronologia=messages_to_dict(list(esito.sessione.messaggi)),
            riassunto=esito.sessione.riassunto,
            strumenti_usati=list(esito.strumenti_usati),
            conferme_richieste=list(esito.conferme_richieste),
        )

    @app.get("/prompts", response_model=list[PromptApi], responses={503: {"model": Errore}})
    def prompts():
        """Prompt pubblicati dal server MCP (discovery al momento della richiesta)."""
        if elenca is None:
            return _errore(503, PROMPT_NON_CONFIGURATI)
        try:
            trovati = elenca()
        except ErroreMcp as errore:
            return _errore(503, str(errore))
        return [
            PromptApi(
                nome=p.nome, descrizione=p.descrizione,
                argomenti=[ArgomentoPromptApi(nome=a.nome, descrizione=a.descrizione, obbligatorio=a.obbligatorio)
                           for a in p.argomenti],
            )
            for p in trovati
        ]

    @app.post("/prompts/{nome}", response_model=list[MessaggioPrompt], responses={503: {"model": Errore}})
    def prompt(nome: str, richiesta: RichiestaPrompt):
        """Messaggi compilati dal server MCP per il prompt `nome`."""
        if ottieni is None:
            return _errore(503, PROMPT_NON_CONFIGURATI)
        try:
            coppie = ottieni(nome, richiesta.argomenti)
        except ErroreMcp as errore:
            return _errore(503, str(errore))
        return [MessaggioPrompt(ruolo=ruolo, testo=testo) for ruolo, testo in coppie]

    @app.get("/stato", responses={503: {"description": "Almeno un componente non raggiungibile"}})
    def stato():
        """Raggiungibilità di agente, server MCP e modello: 200 solo se tutto è raggiungibile."""
        componenti = {
            "agente": "ok",
            "mcp": stato_mcp() if stato_mcp else NON_CONFIGURATO,
            "modello": stato_modello() if stato_modello else NON_CONFIGURATO,
        }
        codice = 200 if all(v == "ok" for v in componenti.values()) else 503
        if codice != 200:
            LOG.warning("stato: %s", componenti)
        return JSONResponse(status_code=codice, content=componenti)

    return app
