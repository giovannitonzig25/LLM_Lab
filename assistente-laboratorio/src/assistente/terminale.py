"""Interfaccia da terminale: ciclo domanda/risposta."""
import logging
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import openai
from langgraph.errors import GraphRecursionError
from langchain_core.messages import BaseMessage, HumanMessage

from assistente.config import ErroreConfigurazione, carica_config
from assistente.grafo import costruisci_grafo
from assistente.comandi import esegui_comando
from assistente.mcp_client import PromptMcp, elenca_prompt, leggi_resource, ottieni_prompt
from assistente.modello import crea_classificatore, crea_modello, crea_revisore, crea_riassuntore
from assistente.preferenze import carica_preferenze
from assistente.strumenti import componi_strumenti

LOG = logging.getLogger("assistente.terminale")
USCITA = "esci"
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


def chiedi_conferma(messaggio: str) -> bool:
    """Conferma di un'azione distruttiva, chiesta all'utente nel terminale (fuori dal modello)."""
    try:
        return input(f"{messaggio} [s/N]: ").strip().lower() in {"s", "si", "sì"}
    except EOFError:
        return False


AVVISO_RISPOSTA_VUOTA = "(Il modello ha restituito una risposta vuota. Riprova o riformula la domanda.)"


def limite_ricorsione(max_passaggi: int, max_revisioni: int) -> int:
    """`recursion_limit` del turno (spec Step 2 §8, Step 3 §11): MAX_PASSAGGI è il budget nominale di ogni tentativo."""
    return PASSAGGI_RIASSUNTO + PASSAGGI_ROUTER + (max_revisioni + 1) * (max_passaggi + PASSAGGI_REVISORE)


@dataclass(frozen=True)
class Sessione:
    """Cronologia e riassunto della sessione in corso (spec Step 3 §5.2): immutabile, mai salvata su disco."""

    messaggi: tuple[BaseMessage, ...] = ()
    riassunto: str = ""


def esegui_turno(
    grafo, sessione: Sessione, domanda: str, max_passaggi: int, *, max_revisioni: int
) -> tuple[Sessione, str]:
    """Esegue il turno di una domanda scritta dall'utente."""
    return esegui_turno_messaggi(grafo, sessione, [HumanMessage(domanda)], max_passaggi, max_revisioni=max_revisioni)


def esegui_turno_messaggi(
    grafo, sessione: Sessione, nuovi: Sequence[BaseMessage], max_passaggi: int, *, max_revisioni: int
) -> tuple[Sessione, str]:
    """Esegue un turno con i messaggi `nuovi` (una domanda o i messaggi di un prompt MCP, spec Step 5 §10.1).

    Se fallisce restituisce la sessione ricevuta, lo stesso oggetto (spec Step 3 §5.3).
    """
    try:
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
        return sessione, MESSAGGIO_LIMITE.format(limite=max_passaggi)
    except openai.OpenAIError as errore:
        return sessione, ERRORE_SERVER.format(errore=errore)
    # La cronologia può essere più corta di quella ricevuta: il Riassunto toglie i turni vecchi.
    nuova = Sessione(tuple(esito["messages"]), esito.get("riassunto", sessione.riassunto))
    risposta = esito["messages"][-1].text
    return nuova, risposta if risposta.strip() else AVVISO_RISPOSTA_VUOTA


def ripulisci_input(testo: str) -> str:
    """Sostituisce con U+FFFD i byte non validi in UTF-8 che `input()` conserva come surrogati
    (stdin con `surrogateescape`): non sarebbero codificabili nella richiesta al modello.
    Un surrogato che stdin non produce viene invece sostituito con `?`."""
    try:
        return testo.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
    except UnicodeEncodeError:  # surrogato che stdin non produce (per esempio uno isolato nell'intervallo alto)
        return testo.encode("utf-8", errors="replace").decode("utf-8")


def esegui_chat(
    grafo,
    max_passaggi: int,
    leggi: Callable[[], str],
    scrivi: Callable[[str], None],
    *,
    max_revisioni: int,
    elenca: Callable[[], Sequence[PromptMcp]] | None = None,
    ottieni: Callable[[str, dict[str, str]], list[tuple[str, str]]] | None = None,
) -> None:
    """Ciclo della chat. Le righe che iniziano con `/` sono comandi (Step 5): non vanno mai al modello così come sono."""
    sessione = Sessione()  # nessuna persistenza tra esecuzioni
    while True:
        try:
            domanda = ripulisci_input(leggi()).strip()
            if domanda == USCITA:
                return
            if not domanda:
                continue
            if domanda.startswith("/"):
                righe, messaggi = esegui_comando(domanda, elenca, ottieni)
                for riga in righe:
                    scrivi(riga)
                if not messaggi:
                    continue
                sessione, testo = esegui_turno_messaggi(
                    grafo, sessione, messaggi, max_passaggi, max_revisioni=max_revisioni
                )
            else:
                sessione, testo = esegui_turno(grafo, sessione, domanda, max_passaggi, max_revisioni=max_revisioni)
        except (EOFError, KeyboardInterrupt):
            return
        scrivi(testo)


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    try:
        config = carica_config()
    except ErroreConfigurazione as errore:
        print(errore, file=sys.stderr)
        return 1
    # Le preferenze si leggono una volta per sessione, decise dall'host e non dal modello (spec Step 4 §6).
    strumenti, preferenze, avvisi = componi_strumenti(
        config, chiedi_conferma=chiedi_conferma, carica_preferenze=lambda: carica_preferenze(config, leggi_resource)
    )
    for avviso in avvisi:
        print(avviso, file=sys.stderr)
    grafo = costruisci_grafo(
        crea_modello(config, strumenti), strumenti, classificatore=crea_classificatore(config), ambito=config.ambito,
        revisore=crea_revisore(config), max_revisioni=config.max_revisioni,
        riassuntore=crea_riassuntore(config), soglia_riassunto=config.soglia_riassunto, preferenze=preferenze,
    )
    # Lo stesso valore va al grafo (Revisore) e al turno (recursion_limit): spec §17.
    # Prompt MCP (Step 5): discovery al momento del comando, con URL e timeout degli strumenti MCP.
    esegui_chat(
        grafo, config.max_passaggi, lambda: input("Tu: "), print, max_revisioni=config.max_revisioni,
        elenca=lambda: elenca_prompt(config.mcp_url, config.mcp_timeout),
        ottieni=lambda nome, argomenti: ottieni_prompt(config.mcp_url, nome, argomenti, config.mcp_timeout),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
