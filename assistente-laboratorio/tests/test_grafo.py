from langchain_core.messages import AIMessage, HumanMessage

from assistente.grafo import costruisci_grafo
from finti import AMBITO_TEST, ModelloSimulato, approva_sempre, in_ambito


def test_il_nodo_modello_usa_il_modello_iniettato():
    modello = ModelloSimulato([AIMessage("Ciao")])

    esito = costruisci_grafo(modello, classificatore=in_ambito(), ambito=AMBITO_TEST, revisore=approva_sempre(), max_revisioni=1).invoke({"messages": [HumanMessage("Salve")]})

    assert esito["messages"][-1].content == "Ciao"
    assert len(modello.chiamate) == 1
