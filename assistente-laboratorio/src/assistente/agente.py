"""Agente: costruzione del grafo e turno, indipendenti dall'interfaccia (Step 6, spec §3).

Lo usano il servizio HTTP dell'agente e, attraverso l'API, la CLI. Nessuno stato tra un turno e l'altro:
cronologia e riassunto arrivano dal chiamante dentro una `Sessione` e tornano aggiornati.
"""
import logging
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

import openai
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.errors import GraphRecursionError

from assistente.config import Config
from assistente.grafo import costruisci_grafo
from assistente.mcp_client import leggi_resource
from assistente.modello import crea_classificatore, crea_modello, crea_revisore, crea_riassuntore
from assistente.preferenze import carica_preferenze
from assistente.strumenti import componi_strumenti

LOG = logging.getLogger("assistente.agente")
# Riassunto e Router consumano un passaggio ciascuno all'inizio di ogni turno (anche quando il Riassunto
# non comprime), il Revisore uno per ogni tentativo dell'agente.
PASSAGGI_RIASSUNTO = 1
PASSAGGI_ROUTER = 1
PASSAGGI_REVISORE = 1
MESSAGGIO_LIMITE = (
    "La richiesta non è stata completata: raggiunto il limite di {limite} passaggi. "
    "Puoi riprovare o riformulare la domanda."
)
ERRORE_SERVER = (
    "Non riesco a ottenere una risposta dal server del modello ({errore}). "
    "Controlla che LM Studio sia attivo e che LM_STUDIO_BASE_URL e LM_STUDIO_MODEL "
    "corrispondano a quanto elencato da GET /v1/models."
)
AVVISO_RISPOSTA_VUOTA = "(Il modello ha restituito una risposta vuota. Riprova o riformula la domanda.)"


def limite_ricorsione(max_passaggi: int, max_revisioni: int) -> int:
    """`recursion_limit` del turno (spec Step 2 §8, Step 3 §11): MAX_PASSAGGI è il budget nominale di ogni tentativo."""
    return PASSAGGI_RIASSUNTO + PASSAGGI_ROUTER + (max_revisioni + 1) * (max_passaggi + PASSAGGI_REVISORE)


@dataclass(frozen=True)
class Sessione:
    """Cronologia e riassunto della conversazione (spec Step 3 §5.2): immutabile, mai salvata su disco."""

    messaggi: tuple[BaseMessage, ...] = ()
    riassunto: str = ""


class ErroreModello(Exception):
    """Il server del modello non ha risposto: `codice` 503 se irraggiungibile, 502 per gli altri errori."""

    def __init__(self, messaggio: str, codice: int):
        super().__init__(messaggio)
        self.codice = codice


@dataclass(frozen=True)
class EsitoTurno:
    sessione: Sessione
    risposta: str
    strumenti_usati: tuple[dict, ...] = ()
    conferme_richieste: tuple[dict, ...] = ()
    limite: bool = False


# --- Conferme degli strumenti distruttivi, valide per la sola richiesta (spec §4.2) ---------------------


@dataclass
class _Conferme:
    ricevute: list[dict]
    richieste: list[dict] = field(default_factory=list)


_CONFERME: ContextVar[_Conferme | None] = ContextVar("conferme", default=None)


@contextmanager
def conferme_della_richiesta(conferme: Sequence[dict] = ()) -> Iterator[list[dict]]:
    """Rende disponibili le conferme del chiamante durante il turno; produce la lista di quelle richieste."""
    stato = _Conferme([{"strumento": c["strumento"], "argomenti": dict(c["argomenti"])} for c in conferme])
    gettone = _CONFERME.set(stato)
    try:
        yield stato.richieste
    finally:
        _CONFERME.reset(gettone)


def conferma_da_richiesta(nome: str, argomenti: dict) -> bool:
    """Vera solo se il chiamante ha confermato esattamente questo strumento con questi argomenti."""
    stato = _CONFERME.get()
    voce = {"strumento": nome, "argomenti": dict(argomenti)}
    if stato is None:
        return False
    if voce in stato.ricevute:
        return True
    if voce not in stato.richieste:
        stato.richieste.append(voce)
    return False


# --- Turno -------------------------------------------------------------------------------------------


def _strumenti_usati(messaggi: Sequence[BaseMessage], inizio: int) -> tuple[dict, ...]:
    return tuple(
        {"nome": chiamata["name"], "argomenti": chiamata["args"]}
        for m in messaggi[inizio:]
        if isinstance(m, AIMessage)
        for chiamata in m.tool_calls
    )


def esegui_turno_api(
    grafo,
    sessione: Sessione,
    nuovi: Sequence[BaseMessage],
    max_passaggi: int,
    *,
    max_revisioni: int,
    conferme: Sequence[dict] = (),
) -> EsitoTurno:
    """Esegue un turno con i messaggi `nuovi`. Solleva `ErroreModello` se il modello non risponde.

    La sessione ricevuta non viene mai modificata; con il limite di passaggi torna invariata.
    """
    try:
        with conferme_della_richiesta(conferme) as richieste:
            esito = grafo.invoke(
                # Copie: add_messages assegna gli id sugli oggetti ricevuti; la sessione non va mai toccata (§5.3).
                {
                    "messages": [*(m.model_copy() for m in sessione.messaggi), *(m.model_copy() for m in nuovi)],
                    "riassunto": sessione.riassunto,
                },
                config={"recursion_limit": limite_ricorsione(max_passaggi, max_revisioni)},
            )
    except GraphRecursionError:
        LOG.warning("limite di passaggi raggiunto (%s): turno scartato", max_passaggi)
        return EsitoTurno(sessione, MESSAGGIO_LIMITE.format(limite=max_passaggi), limite=True)
    except openai.APIConnectionError as errore:  # comprende il timeout
        raise ErroreModello(ERRORE_SERVER.format(errore=errore), 503) from errore
    except openai.OpenAIError as errore:
        raise ErroreModello(ERRORE_SERVER.format(errore=errore), 502) from errore
    messaggi = esito["messages"]
    # La cronologia può essere più corta di quella ricevuta: il Riassunto toglie i turni vecchi.
    nuova = Sessione(tuple(messaggi), esito.get("riassunto", sessione.riassunto))
    risposta = messaggi[-1].text
    return EsitoTurno(
        nuova,
        risposta if risposta.strip() else AVVISO_RISPOSTA_VUOTA,
        _strumenti_usati(messaggi, esito.get("inizio_turno", len(messaggi))),
        tuple(richieste),
    )


def esegui_turno_messaggi(
    grafo, sessione: Sessione, nuovi: Sequence[BaseMessage], max_passaggi: int, *, max_revisioni: int
) -> tuple[Sessione, str]:
    """Turno con i messaggi `nuovi`; se il modello non risponde restituisce la sessione ricevuta e il messaggio d'errore."""
    try:
        esito = esegui_turno_api(grafo, sessione, nuovi, max_passaggi, max_revisioni=max_revisioni)
    except ErroreModello as errore:
        return sessione, str(errore)
    return esito.sessione, esito.risposta


def esegui_turno(
    grafo, sessione: Sessione, domanda: str, max_passaggi: int, *, max_revisioni: int
) -> tuple[Sessione, str]:
    """Esegue il turno di una domanda scritta dall'utente."""
    return esegui_turno_messaggi(grafo, sessione, [HumanMessage(domanda)], max_passaggi, max_revisioni=max_revisioni)


def costruisci_agente(config: Config, **opzioni):
    """Strumenti (avvio ridotto compreso), preferenze, modelli e grafo; restituisce (grafo, avvisi).

    Gli strumenti distruttivi chiedono la conferma alle conferme della richiesta in corso (spec §4.2).
    `opzioni` passa a `componi_strumenti` (per esempio `scopri` nei test).
    """
    # Le preferenze si leggono una volta all'avvio, decise dall'host e non dal modello (spec Step 4 §6).
    strumenti, preferenze, avvisi = componi_strumenti(
        config,
        chiedi_conferma=conferma_da_richiesta,
        carica_preferenze=lambda: carica_preferenze(config, leggi_resource),
        **opzioni,
    )
    grafo = costruisci_grafo(
        crea_modello(config, strumenti), strumenti, classificatore=crea_classificatore(config), ambito=config.ambito,
        revisore=crea_revisore(config), max_revisioni=config.max_revisioni,
        riassuntore=crea_riassuntore(config), soglia_riassunto=config.soglia_riassunto, preferenze=preferenze,
    )
    return grafo, avvisi
