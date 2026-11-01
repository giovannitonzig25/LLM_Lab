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
