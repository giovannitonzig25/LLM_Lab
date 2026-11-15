"""Interfaccia da terminale: ciclo domanda/risposta."""
import logging
import sys
from collections.abc import Callable

import openai
from langgraph.errors import GraphRecursionError
from langchain_core.messages import BaseMessage, HumanMessage

from assistente.config import ErroreConfigurazione, carica_config
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_classificatore, crea_modello, crea_revisore
from assistente.strumenti import componi_strumenti

LOG = logging.getLogger("assistente.terminale")
USCITA = "esci"
# Il Router consuma un passaggio all'inizio di ogni turno, il Revisore uno per ogni tentativo dell'agente.
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
    """`recursion_limit` del turno (spec Step 2 §8): MAX_PASSAGGI è il budget nominale di ogni tentativo."""
    return PASSAGGI_ROUTER + (max_revisioni + 1) * (max_passaggi + PASSAGGI_REVISORE)


def esegui_turno(
    grafo, cronologia: list[BaseMessage], domanda: str, max_passaggi: int, *, max_revisioni: int
) -> tuple[list[BaseMessage], str]:
    """Esegue un turno. Se fallisce restituisce la cronologia ricevuta, invariata."""
    try:
        esito = grafo.invoke(
            {"messages": [*cronologia, HumanMessage(domanda)]},
            config={"recursion_limit": limite_ricorsione(max_passaggi, max_revisioni)},
        )
    except GraphRecursionError:
        LOG.warning("limite di passaggi raggiunto (%s): turno scartato", max_passaggi)
        return cronologia, MESSAGGIO_LIMITE.format(limite=max_passaggi)
    except openai.OpenAIError as errore:
        return cronologia, ERRORE_SERVER.format(errore=errore)
    risposta = esito["messages"][-1].text
    return esito["messages"], risposta if risposta.strip() else AVVISO_RISPOSTA_VUOTA


def ripulisci_input(testo: str) -> str:
    """Sostituisce con U+FFFD i byte non validi in UTF-8 che `input()` conserva come surrogati
    (stdin con `surrogateescape`): non sarebbero codificabili nella richiesta al modello.
    Un surrogato che stdin non produce viene invece sostituito con `?`."""
    try:
        return testo.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
    except UnicodeEncodeError:  # surrogato che stdin non produce (per esempio uno isolato nell'intervallo alto)
        return testo.encode("utf-8", errors="replace").decode("utf-8")


def esegui_chat(
    grafo, max_passaggi: int, leggi: Callable[[], str], scrivi: Callable[[str], None], *, max_revisioni: int
) -> None:
    cronologia: list[BaseMessage] = []
    while True:
        try:
            domanda = ripulisci_input(leggi()).strip()
            if domanda == USCITA:
                return
            if not domanda:
                continue
            cronologia, testo = esegui_turno(grafo, cronologia, domanda, max_passaggi, max_revisioni=max_revisioni)
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
    strumenti, avvisi = componi_strumenti(config, chiedi_conferma=chiedi_conferma)
    for avviso in avvisi:
        print(avviso, file=sys.stderr)
    grafo = costruisci_grafo(
        crea_modello(config, strumenti), strumenti, classificatore=crea_classificatore(config), ambito=config.ambito,
        revisore=crea_revisore(config), max_revisioni=config.max_revisioni,
    )
    # Lo stesso valore va al grafo (Revisore) e al turno (recursion_limit): spec §17.
    esegui_chat(grafo, config.max_passaggi, lambda: input("Tu: "), print, max_revisioni=config.max_revisioni)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
