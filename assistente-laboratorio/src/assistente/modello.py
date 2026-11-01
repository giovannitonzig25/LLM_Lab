"""Collegamento al modello servito da LM Studio (API compatibile OpenAI)."""
from collections.abc import Sequence

from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI

from assistente.config import Config


def crea_modello(config: Config, strumenti: Sequence[BaseTool] = ()):
    # LM Studio non richiede una chiave, ma il client ne pretende una non vuota.
    modello = ChatOpenAI(base_url=config.base_url, api_key="lm-studio", model=config.modello, temperature=0)
    return modello.bind_tools(list(strumenti)) if strumenti else modello
