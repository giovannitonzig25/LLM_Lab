"""Grafo LangGraph: stato, nodi e instradamento."""
import logging
from collections.abc import Sequence
from typing import Annotated, NotRequired, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from assistente.router import crea_nodo_router, testo_rifiuto

LOG = logging.getLogger("assistente.strumenti")
LOG_ROUTER = logging.getLogger("assistente.router")


class Stato(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    categoria: NotRequired[str]
    motivo: NotRequired[str]


def instrada_router(stato: Stato) -> str:
    """Dopo il Router: agente per le domande in ambito, rifiuto per quelle fuori ambito."""
    return "modello" if stato["categoria"] == "conversazione" else "rifiuto"


def instrada(stato: Stato) -> str:
    """Dopo il modello: strumenti se ha chiesto di eseguirne, altrimenti fine."""
    return "strumenti" if getattr(stato["messages"][-1], "tool_calls", None) else END


def costruisci_grafo(modello, strumenti: Sequence[BaseTool] = (), *, classificatore, ambito: str):
    per_nome = {strumento.name: strumento for strumento in strumenti}

    def nodo_modello(stato: Stato) -> dict:
        LOG_ROUTER.info("agente: chiamata al modello")
        return {"messages": [modello.invoke(stato["messages"])]}

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
    grafo.add_node("router", crea_nodo_router(classificatore, ambito))
    grafo.add_node("rifiuto", nodo_rifiuto)
    grafo.add_node("modello", nodo_modello)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_edge(START, "router")
    grafo.add_conditional_edges("router", instrada_router, ["modello", "rifiuto"])
    grafo.add_edge("rifiuto", END)
    grafo.add_conditional_edges("modello", instrada, ["strumenti", END])
    grafo.add_edge("strumenti", "modello")
    return grafo.compile()
