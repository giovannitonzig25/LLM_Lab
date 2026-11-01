"""Interfaccia da terminale: ciclo domanda/risposta."""
import logging
import sys
from collections.abc import Callable

import openai
from langchain_core.messages import HumanMessage

from assistente.config import ErroreConfigurazione, carica_config
from assistente.grafo import costruisci_grafo
from assistente.modello import crea_modello

USCITA = "esci"
ERRORE_SERVER = (
    "Non riesco a ottenere una risposta dal server del modello ({errore}). "
    "Controlla che LM Studio sia attivo e che LM_STUDIO_BASE_URL e LM_STUDIO_MODEL "
    "corrispondano a quanto elencato da GET /v1/models."
)


def esegui_chat(grafo, leggi: Callable[[], str], scrivi: Callable[[str], None]) -> None:
    while True:
        try:
            domanda = leggi().strip()
        except (EOFError, KeyboardInterrupt):
            return
        if domanda == USCITA:
            return
        if not domanda:
            continue
        try:
            esito = grafo.invoke({"messages": [HumanMessage(domanda)]})
        except openai.OpenAIError as errore:
            scrivi(ERRORE_SERVER.format(errore=errore))
            continue
        scrivi(esito["messages"][-1].content)


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    try:
        config = carica_config()
    except ErroreConfigurazione as errore:
        print(errore, file=sys.stderr)
        return 1
    esegui_chat(costruisci_grafo(crea_modello(config)), lambda: input("Tu: "), print)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
