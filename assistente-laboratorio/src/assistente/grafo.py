"""Grafo LangGraph: stato, nodi e instradamento."""
import logging
from collections.abc import Sequence
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

LOG = logging.getLogger("assistente.strumenti")


class Stato(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def instrada(stato: Stato) -> str:
    """Dopo il modello: strumenti se ha chiesto di eseguirne, altrimenti fine."""
    return "strumenti" if getattr(stato["messages"][-1], "tool_calls", None) else END


def costruisci_grafo(modello, strumenti: Sequence[BaseTool] = ()):
    per_nome = {strumento.name: strumento for strumento in strumenti}

    def nodo_modello(stato: Stato) -> dict:
        return {"messages": [modello.invoke(stato["messages"])]}

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
    grafo.add_node("modello", nodo_modello)
    grafo.add_node("strumenti", nodo_strumenti)
    grafo.add_edge(START, "modello")
    grafo.add_conditional_edges("modello", instrada, ["strumenti", END])
    grafo.add_edge("strumenti", "modello")
    return grafo.compile()
