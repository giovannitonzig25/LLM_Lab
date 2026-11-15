"""Modelli scritti a mano per i test: nessuna rete, nessun modello reale."""
from langchain_core.messages import AIMessage, BaseMessage


class ModelloSimulato:
    def __init__(self, risposte: list[AIMessage | BaseException], ripeti_ultima: bool = False):
        self._risposte = list(risposte)
        self._ripeti_ultima = ripeti_ultima
        self.chiamate: list[list[BaseMessage]] = []

    def invoke(self, messaggi: list[BaseMessage]) -> AIMessage:
        self.chiamate.append(list(messaggi))
        if len(self._risposte) > 1 or not self._ripeti_ultima:
            risposta = self._risposte.pop(0)
        else:
            risposta = self._risposte[0]
        if isinstance(risposta, BaseException):
            raise risposta
        # Copia: un modello reale restituisce messaggi nuovi, e add_messages sostituisce quelli con lo stesso id.
        return risposta.model_copy(deep=True)


AMBITO_TEST = "Ambito di prova."


class ClassificatoreSimulato:
    """Sostituisce il classificatore del Router o il Revisore: restituisce la forma di `include_raw=True` o lancia un'eccezione."""

    def __init__(self, esiti: list, ripeti_ultima: bool = False):
        self._esiti = list(esiti)
        self._ripeti_ultima = ripeti_ultima
        self.chiamate: list[list[BaseMessage]] = []

    def invoke(self, messaggi: list[BaseMessage]):
        from assistente.revisore import Valutazione
        from assistente.router import Classificazione

        self.chiamate.append(list(messaggi))
        esito = self._esiti.pop(0) if len(self._esiti) > 1 or not self._ripeti_ultima else self._esiti[0]
        if isinstance(esito, BaseException):
            raise esito
        if isinstance(esito, (Classificazione, Valutazione)):
            return {"raw": AIMessage(""), "parsed": esito, "parsing_error": None}
        return esito


def in_ambito() -> ClassificatoreSimulato:
    from assistente.router import Classificazione

    return ClassificatoreSimulato([Classificazione(categoria="conversazione", motivo="richiesta in ambito")], True)


def fuori_ambito() -> ClassificatoreSimulato:
    from assistente.router import Classificazione

    return ClassificatoreSimulato([Classificazione(categoria="fuori_ambito", motivo="richiesta estranea")], True)


def valutazione(coerente: bool, motivo: str):
    from assistente.revisore import Valutazione

    return Valutazione(coerente=coerente, motivo=motivo)


def approva_sempre() -> ClassificatoreSimulato:
    return ClassificatoreSimulato([valutazione(True, "risposta completa")], True)


def rifiuta_sempre(motivo: str = "manca una parte della domanda") -> ClassificatoreSimulato:
    return ClassificatoreSimulato([valutazione(False, motivo)], True)
