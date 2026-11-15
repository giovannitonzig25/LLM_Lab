import logging

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from assistente.grafo import costruisci_grafo
from assistente.config import SOGLIA_RIASSUNTO_PREDEFINITA
from finti import riassuntore_inerte
from assistente.strumenti import STRUMENTI
from assistente.terminale import esegui_chat, esegui_turno
from finti import AMBITO_TEST, ModelloSimulato, approva_sempre, in_ambito

CHIEDE_ORA = AIMessage(content="", tool_calls=[{"id": "c1", "name": "orologio", "args": {}}])


class ModelloCondizionale:
    """Chiede lo strumento all'infinito per la domanda «loop», risponde «Ok» a tutte le altre."""

    def invoke(self, messaggi):
        ultimo = messaggi[-1]
        if isinstance(ultimo, ToolMessage) or ultimo.content == "loop":
            return CHIEDE_ORA.model_copy(deep=True)
        return AIMessage("Ok")


def grafo_in_loop():
    return costruisci_grafo(ModelloCondizionale(), STRUMENTI, classificatore=in_ambito(), ambito=AMBITO_TEST, revisore=approva_sempre(), max_revisioni=1, riassuntore=riassuntore_inerte(), soglia_riassunto=SOGLIA_RIASSUNTO_PREDEFINITA)


def test_limite_ripristina_la_cronologia():
    precedente = [HumanMessage("Ciao"), AIMessage("Salve")]

    cronologia, _ = esegui_turno(grafo_in_loop(), precedente, "loop", 6, max_revisioni=1)

    assert cronologia == precedente


def test_nessun_messaggio_parziale_resta():
    cronologia, _ = esegui_turno(grafo_in_loop(), [], "loop", 6, max_revisioni=1)

    assert cronologia == []
    assert not any(isinstance(m, ToolMessage) or getattr(m, "tool_calls", None) for m in cronologia)


def test_messaggio_chiaro_all_utente():
    _, testo = esegui_turno(grafo_in_loop(), [], "loop", 6, max_revisioni=1)

    assert "non è stata completata" in testo
    assert "riprovare" in testo and "riformulare" in testo


def test_la_chat_continua_dopo_il_limite():
    righe = iter(["loop", "Una domanda normale", "esci"])
    stampato = []

    esegui_chat(grafo_in_loop(), 6, lambda: next(righe), stampato.append, max_revisioni=1)

    assert "non è stata completata" in stampato[0]
    assert stampato[1] == "Ok"


def test_log_del_limite(caplog):
    with caplog.at_level(logging.WARNING, logger="assistente.terminale"):
        esegui_turno(grafo_in_loop(), [], "loop", 6, max_revisioni=1)

    assert any("limite" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize(
    ("limite", "max_revisioni", "chiamate_al_modello", "strumenti_eseguiti"),
    # Valori osservati con LangGraph 1.2.19, non dedotti: vedi README. Con il Revisore (Step 2, spec §8)
    # il ciclo esegue limite_ricorsione(limite, max_revisioni) passaggi: Riassunto e Router (spec Step 3 §11)
    # più chiamate al modello e strumenti alternati (il Revisore non viene mai raggiunto). Il passaggio del
    # Riassunto compensa quello in più della formula: valori invariati. Nello Step 1 erano (2, 1, 1) e (6, 3, 3).
    [(2, 1, 3, 3), (6, 1, 7, 7), (2, 0, 2, 1), (6, 0, 4, 3)],
)
def test_caratterizza_il_limite_di_passaggi(caplog, limite, max_revisioni, chiamate_al_modello, strumenti_eseguiti):
    modello = ModelloSimulato([CHIEDE_ORA], ripeti_ultima=True)
    grafo = costruisci_grafo(
        modello, STRUMENTI, classificatore=in_ambito(), ambito=AMBITO_TEST, revisore=approva_sempre(),
        max_revisioni=max_revisioni, riassuntore=riassuntore_inerte(), soglia_riassunto=SOGLIA_RIASSUNTO_PREDEFINITA,
    )

    with caplog.at_level(logging.INFO, logger="assistente.strumenti"):
        esegui_turno(grafo, [], "Che ora è?", limite, max_revisioni=max_revisioni)

    eseguiti = [r for r in caplog.records if "eseguito" in r.getMessage()]
    assert (len(modello.chiamate), len(eseguiti)) == (chiamate_al_modello, strumenti_eseguiti)
