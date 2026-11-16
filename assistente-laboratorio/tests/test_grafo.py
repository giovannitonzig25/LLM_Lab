from langchain_core.messages import AIMessage, HumanMessage

from assistente.grafo import costruisci_grafo
from assistente.config import SOGLIA_RIASSUNTO_PREDEFINITA
from finti import riassuntore_inerte
from finti import AMBITO_TEST, ModelloSimulato, approva_sempre, in_ambito


def test_il_nodo_modello_usa_il_modello_iniettato():
    modello = ModelloSimulato([AIMessage("Ciao")])

    esito = costruisci_grafo(modello, classificatore=in_ambito(), ambito=AMBITO_TEST, revisore=approva_sempre(), max_revisioni=1, riassuntore=riassuntore_inerte(), soglia_riassunto=SOGLIA_RIASSUNTO_PREDEFINITA).invoke({"messages": [HumanMessage("Salve")]})

    assert esito["messages"][-1].content == "Ciao"
    assert len(modello.chiamate) == 1


# --- Step 4: preferenze in cima al prompt di sistema dell'agente ---
from langchain_core.messages import SystemMessage

import assistente.preferenze as modulo_preferenze
from assistente.preferenze import PREFERENZE_PREDEFINITE, Preferenze
from assistente.riassunto import CORNICE_AGENTE

NEW_YORK = Preferenze("inglese", "America/New_York", "dettagliato")


def grafo_con(preferenze, modello=None, classificatore=None, revisore=None):
    modello = modello or ModelloSimulato([AIMessage("Ciao")])
    grafo = costruisci_grafo(
        modello, classificatore=classificatore or in_ambito(), ambito=AMBITO_TEST, revisore=revisore or approva_sempre(),
        max_revisioni=1, riassuntore=riassuntore_inerte(), soglia_riassunto=SOGLIA_RIASSUNTO_PREDEFINITA,
        preferenze=preferenze,
    )
    return grafo, modello


def test_agente_riceve_un_solo_system_message_con_le_preferenze():
    grafo, modello = grafo_con(NEW_YORK)

    grafo.invoke({"messages": [HumanMessage("Salve")]})

    [richiesta] = modello.chiamate
    assert [type(m) for m in richiesta] == [SystemMessage, HumanMessage]
    assert richiesta[0].content == modulo_preferenze.testo_prompt(NEW_YORK)


def test_system_message_con_riassunto_unisce_preferenze_e_cornice():
    grafo, modello = grafo_con(NEW_YORK)

    grafo.invoke({"messages": [HumanMessage("Salve")], "riassunto": "R"})

    [richiesta] = modello.chiamate
    assert sum(isinstance(m, SystemMessage) for m in richiesta) == 1
    assert richiesta[0].content == modulo_preferenze.testo_prompt(NEW_YORK) + "\n\n" + CORNICE_AGENTE.format(riassunto="R")


def test_system_message_non_entra_nello_stato():
    grafo, _ = grafo_con(NEW_YORK)

    esito = grafo.invoke({"messages": [HumanMessage("Salve")]})

    assert not any(isinstance(m, SystemMessage) for m in esito["messages"])


def test_router_e_revisore_non_vedono_le_preferenze():
    prompt = {}
    for preferenze in (PREFERENZE_PREDEFINITE, NEW_YORK):
        classificatore, revisore = in_ambito(), approva_sempre()
        grafo, _ = grafo_con(preferenze, classificatore=classificatore, revisore=revisore)
        grafo.invoke({"messages": [HumanMessage("Salve")]})
        prompt[preferenze] = [m.content for chiamata in classificatore.chiamate + revisore.chiamate for m in chiamata]

    assert prompt[NEW_YORK] == prompt[PREFERENZE_PREDEFINITE]
    assert not any("Preferenze dell'utente" in testo for testo in prompt[NEW_YORK])
