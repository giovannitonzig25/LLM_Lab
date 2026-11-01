from langchain_core.messages import AIMessage, HumanMessage

from assistente.grafo import costruisci_grafo
from finti import ModelloSimulato


def test_il_nodo_modello_usa_il_modello_iniettato():
    modello = ModelloSimulato([AIMessage("Ciao")])

    esito = costruisci_grafo(modello).invoke({"messages": [HumanMessage("Salve")]})

    assert esito["messages"][-1].content == "Ciao"
    assert len(modello.chiamate) == 1
