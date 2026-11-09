"""Interfaccia da terminale: ciclo domanda/risposta."""
import logging
import sys
from collections.abc import Callable

import openai
from langgraph.errors import GraphRecursionError
from langchain_core.messages import BaseMessage, HumanMessage

from assistente.config import ErroreConfigurazione, carica_config
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello
from assistente.strumenti import componi_strumenti

LOG = logging.getLogger("assistente.terminale")
USCITA = "esci"
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


def esegui_turno(grafo, cronologia: list[BaseMessage], domanda: str, max_passaggi: int) -> tuple[list[BaseMessage], str]:
    """Esegue un turno. Se fallisce restituisce la cronologia ricevuta, invariata."""
    try:
        esito = grafo.invoke(
            {"messages": [*cronologia, HumanMessage(domanda)]},
            config={"recursion_limit": max_passaggi},
        )
    except GraphRecursionError:
        LOG.warning("limite di passaggi raggiunto (%s): turno scartato", max_passaggi)
        return cronologia, MESSAGGIO_LIMITE.format(limite=max_passaggi)
    except openai.OpenAIError as errore:
        return cronologia, ERRORE_SERVER.format(errore=errore)
    risposta = esito["messages"][-1].text
    return esito["messages"], risposta if risposta.strip() else AVVISO_RISPOSTA_VUOTA


def esegui_chat(grafo, max_passaggi: int, leggi: Callable[[], str], scrivi: Callable[[str], None]) -> None:
    cronologia: list[BaseMessage] = []
    while True:
        try:
            domanda = leggi().strip()
            if domanda == USCITA:
                return
            if not domanda:
                continue
            cronologia, testo = esegui_turno(grafo, cronologia, domanda, max_passaggi)
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
    esegui_chat(costruisci_grafo(crea_modello(config, strumenti), strumenti), config.max_passaggi, lambda: input("Tu: "), print)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
