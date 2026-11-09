"""Ponte sincrono sopra il client FastMCP: discovery e invocazione degli strumenti MCP.

Chiamate FastMCP 4.1.6 effettivamente usate (verificate in T1/T2):
- `Client(url, timeout=<s>)` come `async with`; `await client.list_tools()` restituisce
  oggetti `Tool` con `name`, `description`, `input_schema` (JSON Schema) e `annotations`
  (`None` se assenti, altrimenti `ToolAnnotations` con `destructive_hint`).
- `await client.call_tool(nome, argomenti)`: restituisce un risultato con `content`
  (blocchi di testo); uno strumento che fallisce o argomenti non validi sollevano
  `fastmcp.exceptions.ToolError`; una connessione impossibile solleva `RuntimeError`.
Nome, descrizione e schema non sono mai scritti a mano qui: arrivano da `list_tools()`.
"""

import asyncio
import logging
import threading
from collections.abc import Callable, Coroutine
from typing import Any

from fastmcp import Client
from fastmcp.exceptions import ToolError
from langchain_core.tools import BaseTool

LOG = logging.getLogger("assistente.mcp")


class ErroreMcp(Exception):
    """Discovery MCP impossibile (server non raggiungibile, in ritardo o non valido)."""


def _esegui(coro: Coroutine[Any, Any, Any]) -> Any:
    """Esegue una coroutine da codice sincrono, anche se nel thread c'è già un ciclo attivo."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    esito: dict[str, Any] = {}

    def lavora() -> None:
        try:
            esito["valore"] = asyncio.run(coro)
        except BaseException as errore:  # rilanciata nel thread chiamante
            esito["errore"] = errore

    thread = threading.Thread(target=lavora)
    thread.start()
    thread.join()
    if "errore" in esito:
        raise esito["errore"]
    return esito["valore"]


def _testo_errore(errore: BaseException) -> str:
    righe = [r.strip() for r in str(errore).splitlines() if r.strip()]
    righe = [r for r in righe if not r.startswith("For further information")]
    return " ".join(righe) or type(errore).__name__


async def _chiama(url: str, nome: str, argomenti: dict, timeout: float) -> str:
    async with asyncio.timeout(timeout):
        async with Client(url, timeout=timeout) as client:
            risultato = await client.call_tool(nome, argomenti)
    testi = [blocco.text for blocco in risultato.content if hasattr(blocco, "text")]
    return "\n".join(testi)


class StrumentoMcp(BaseTool):
    """Strumento esposto da un server MCP; nome, descrizione e schema vengono dalla discovery."""

    name: str
    description: str
    args_schema: dict
    url: str
    timeout: float = 10.0
    richiede_conferma: bool = False
    chiedi_conferma: Callable[[str], bool] | None = None

    def _conferma_dell_utente(self, argomenti: dict) -> bool:
        """Chiede all'utente (fuori dal modello); solo un `True` esplicito vale come sì."""
        if self.chiedi_conferma is None:
            LOG.warning("conferma non disponibile: strumento=%s non eseguito", self.name)
            return False
        try:
            esito = self.chiedi_conferma(f"Confermi: {self.name} {argomenti}?") is True
        except Exception as errore:  # KeyboardInterrupt non è un Exception: risale
            LOG.warning("conferma fallita (%s): strumento=%s non eseguito", type(errore).__name__, self.name)
            return False
        LOG.info("conferma dell'utente: strumento=%s esito=%s", self.name, "sì" if esito else "no")
        return esito

    def _run(self, **argomenti: Any) -> str:
        LOG.info("invocazione: strumento=%s argomenti=%s", self.name, argomenti)
        if self.richiede_conferma and not self._conferma_dell_utente(argomenti):
            return "Errore: cancellazione non confermata dall'utente"
        try:
            risultato = _esegui(_chiama(self.url, self.name, argomenti, self.timeout))
        except (TimeoutError, asyncio.TimeoutError):
            risultato = f"Errore: timeout dopo {self.timeout:g} s"
        except ToolError as errore:
            risultato = f"Errore: {_testo_errore(errore)}"
        except Exception as errore:
            LOG.warning("server MCP non raggiungibile: %s", _testo_errore(errore))
            risultato = f"Errore: server MCP non raggiungibile su {self.url}"
        LOG.log(
            logging.WARNING if risultato.startswith("Errore:") else logging.INFO,
            "invocazione conclusa: strumento=%s risultato=%s", self.name, risultato,
        )
        return risultato


async def _elenca(url: str, timeout: float) -> list:
    async with asyncio.timeout(timeout):
        async with Client(url, timeout=timeout) as client:
            return await client.list_tools()


def scopri_strumenti(
    url: str,
    timeout: float = 10.0,
    chiedi_conferma: Callable[[str], bool] | None = None,
) -> list[BaseTool]:
    """Discovery reale: un `BaseTool` per ogni strumento pubblicato dal server.

    Gli strumenti con `destructiveHint` (letto dalla discovery, mai dal nome) chiedono
    conferma tramite `chiedi_conferma` prima di essere eseguiti.
    """
    try:
        scoperti = _esegui(_elenca(url, timeout))
    except Exception as errore:
        raise ErroreMcp(f"discovery impossibile su {url}: {_testo_errore(errore)}") from errore
    strumenti = []
    for t in scoperti:
        distruttivo = bool(t.annotations and t.annotations.destructive_hint)
        strumenti.append(
            StrumentoMcp(
                name=t.name,
                description=t.description or "",
                args_schema=t.input_schema,
                url=url,
                timeout=timeout,
                richiede_conferma=distruttivo,
                chiedi_conferma=chiedi_conferma,
                metadata={"destructiveHint": distruttivo},
            )
        )
    LOG.info("strumenti scoperti su %s: %s", url, [s.name for s in strumenti])
    return strumenti
