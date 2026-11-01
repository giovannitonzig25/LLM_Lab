"""Interfaccia da terminale: ciclo domanda/risposta."""
from collections.abc import Callable

from langchain_core.messages import HumanMessage

from assistente.grafo import costruisci_grafo

USCITA = "esci"


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
        esito = grafo.invoke({"messages": [HumanMessage(domanda)]})
        scrivi(esito["messages"][-1].content)


def main() -> int:
    esegui_chat(costruisci_grafo(), lambda: input("Tu: "), print)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
