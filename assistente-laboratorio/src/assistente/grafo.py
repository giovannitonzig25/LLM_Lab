"""Grafo LangGraph: stato, nodi e instradamento."""
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, AnyMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

RISPOSTA_FISSA = "Risposta fissa dal grafo."


class Stato(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


def risposta_fissa(stato: Stato) -> dict:
    return {"messages": [AIMessage(RISPOSTA_FISSA)]}


def costruisci_grafo():
    grafo = StateGraph(Stato)
    grafo.add_node("risposta_fissa", risposta_fissa)
    grafo.add_edge(START, "risposta_fissa")
    grafo.add_edge("risposta_fissa", END)
    return grafo.compile()
