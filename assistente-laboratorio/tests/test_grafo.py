from langchain_core.messages import AIMessage, HumanMessage

from assistente.grafo import RISPOSTA_FISSA, costruisci_grafo


def test_risposta_fissa_attraversa_il_grafo():
    esito = costruisci_grafo().invoke({"messages": [HumanMessage("Salve")]})

    assert [type(m) for m in esito["messages"]] == [HumanMessage, AIMessage]
    assert esito["messages"][-1].content == RISPOSTA_FISSA
