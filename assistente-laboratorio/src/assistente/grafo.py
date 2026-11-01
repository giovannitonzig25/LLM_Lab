"""Grafo LangGraph: stato, nodi e instradamento."""
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

class Stato(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def costruisci_grafo(modello):
    def nodo_modello(stato: Stato) -> dict:
        return {"messages": [modello.invoke(stato["messages"])]}

    grafo = StateGraph(Stato)
    grafo.add_node("modello", nodo_modello)
    grafo.add_edge(START, "modello")
    grafo.add_edge("modello", END)
    return grafo.compile()
