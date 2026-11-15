"""Grafo LangGraph: stato, nodi e instradamento."""
import logging
from collections.abc import Sequence
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from assistente.revisore import contesto_agente, crea_nodo_revisore
from assistente.riassunto import crea_nodo_riassunto
from assistente.router import crea_nodo_router, testo_rifiuto

LOG = logging.getLogger("assistente.strumenti")
LOG_ROUTER = logging.getLogger("assistente.router")


class Stato(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    categoria: NotRequired[str]
    motivo: NotRequired[str]
    inizio_turno: NotRequired[int]  # indice della domanda del turno in corso (scritto dal Router)
    revisioni: NotRequired[int]  # correzioni richieste dal Revisore nel turno
    esito_revisione: NotRequired[str]  # approvata, da_correggere, limite, senza_revisione
    # Senza reducer: vale l'ultimo valore scritto. Assente equivale a "" (spec Step 3 §5.1).
    riassunto: NotRequired[str]


def instrada_router(stato: Stato) -> str:
    """Dopo il Router: agente per le domande in ambito, rifiuto per quelle fuori ambito."""
    return "modello" if stato["categoria"] == "conversazione" else "rifiuto"


def instrada(stato: Stato) -> str:
    """Dopo il modello: strumenti se ne ha chiesti; fine se la risposta è vuota; altrimenti Revisore."""
    ultimo = stato["messages"][-1]
    if getattr(ultimo, "tool_calls", None):
        return "strumenti"
    return END if not ultimo.text.strip() else "revisore"


def instrada_revisore(stato: Stato) -> str:
    """Dopo il Revisore: di nuovo all'agente solo se serve una correzione."""
    return "modello" if stato["esito_revisione"] == "da_correggere" else END


def costruisci_grafo(
    modello,
    strumenti: Sequence[BaseTool] = (),
    *,
    classificatore,
    ambito: str,
    revisore,
    max_revisioni: int,
    riassuntore,
    soglia_riassunto: int,
):
    per_nome = {strumento.name: strumento for strumento in strumenti}

    def nodo_modello(stato: Stato) -> dict:
        LOG_ROUTER.info("agente: chiamata al modello")
        # Cronologia completa nello stato; all'agente niente bozze e osservazioni dei turni precedenti (spec §9.3).
        return {"messages": [modello.invoke(contesto_agente(stato["messages"], stato["inizio_turno"]))]}

    def nodo_rifiuto(stato: Stato) -> dict:
        LOG_ROUTER.info("rifiuto: risposta fissa, agente non eseguito")
        return {"messages": [AIMessage(testo_rifiuto(ambito))]}

    def esegui(richiesta: dict) -> str:
        nome, argomenti = richiesta["name"], richiesta["args"]
        LOG.info("strumento richiesto: nome=%s argomenti=%s", nome, argomenti)
        if nome not in per_nome:
            risultato = f"Errore: strumento sconosciuto: {nome}"
        else:
            try:
                risultato = str(per_nome[nome].invoke(argomenti))
            except Exception as errore:
                risultato = f"Errore: {errore}"
        livello = logging.WARNING if risultato.startswith("Errore:") else logging.INFO
        LOG.log(livello, "strumento eseguito: nome=%s risultato=%s", nome, risultato)
        return risultato

    def nodo_strumenti(stato: Stato) -> dict:
        return {
            "messages": [
                ToolMessage(content=esegui(r), tool_call_id=r["id"], name=r["name"])
                for r in stato["messages"][-1].tool_calls
            ]
        }

    grafo = StateGraph(Stato)
    grafo.add_node("riassunto", crea_nodo_riassunto(riassuntore, soglia_riassunto, ambito))
    grafo.add_node("router", crea_nodo_router(classificatore, ambito))
    grafo.add_node("rifiuto", nodo_rifiuto)
    grafo.add_node("modello", nodo_modello)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_node("revisore", crea_nodo_revisore(revisore, max_revisioni))
    grafo.add_edge(START, "riassunto")
    grafo.add_edge("riassunto", "router")
    grafo.add_conditional_edges("router", instrada_router, ["modello", "rifiuto"])
    grafo.add_edge("rifiuto", END)
    grafo.add_conditional_edges("modello", instrada, ["strumenti", "revisore", END])
    grafo.add_edge("strumenti", "modello")
    grafo.add_conditional_edges("revisore", instrada_revisore, ["modello", END])
    return grafo.compile()
