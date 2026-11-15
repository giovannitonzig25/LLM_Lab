"""Collegamento al modello servito da LM Studio (API compatibile OpenAI)."""
from collections.abc import Sequence

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from assistente.config import Config
from assistente.revisore import Valutazione
from assistente.router import Classificazione


def crea_modello(config: Config, strumenti: Sequence[BaseTool] = ()):
    # LM Studio non richiede una chiave, ma il client ne pretende una non vuota.
    modello = ChatOpenAI(base_url=config.base_url, api_key="lm-studio", model=config.modello, temperature=0)
    return modello.bind_tools(list(strumenti)) if strumenti else modello


def crea_client_router(config: Config) -> ChatOpenAI:
    """Client del Router: stesso server e modello dell'agente, senza strumenti e senza ragionamento."""
    return ChatOpenAI(
        base_url=config.base_url, api_key="lm-studio", model=config.modello, temperature=0, reasoning_effort="none"
    )


def crea_classificatore(config: Config):
    return crea_client_router(config).with_structured_output(Classificazione, method="json_schema", include_raw=True)


def crea_revisore(config: Config):
    """Revisore: client separato (nuova istanza) con le stesse impostazioni del Router, senza strumenti."""
    return crea_client_router(config).with_structured_output(Valutazione, method="json_schema", include_raw=True)
