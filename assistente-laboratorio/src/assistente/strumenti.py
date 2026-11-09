"""Strumenti che il modello può chiedere al programma di eseguire."""
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import BaseTool, tool

from assistente.config import Config
from assistente.mcp_client import ErroreMcp, scopri_strumenti

LOG = logging.getLogger("assistente.strumenti")

FUSO_PREDEFINITO = "Europe/Rome"


def adesso_utc() -> datetime:
    return datetime.now(UTC)


def _formatta_offset(istante: datetime) -> str:
    minuti = int(istante.utcoffset().total_seconds() // 60)
    segno = "+" if minuti >= 0 else "-"
    ore, resto = divmod(abs(minuti), 60)
    return f"UTC{segno}{ore:02d}:{resto:02d}"


def leggi_orologio(timezone: str | None = None, adesso: Callable[[], datetime] = adesso_utc) -> str:
    """Data e ora correnti nel fuso indicato. Non solleva eccezioni: un fuso non valido dà un testo `Errore: ...`."""
    if timezone is None or (isinstance(timezone, str) and not timezone.strip()):
        timezone = FUSO_PREDEFINITO
    try:
        fuso = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return f"Errore: fuso orario non valido: {timezone!r}. Usa un nome IANA, per esempio Europe/Rome o Asia/Tokyo."
    istante = adesso().astimezone(fuso)
    return f"{istante:%Y-%m-%d %H:%M:%S} ({timezone}, {_formatta_offset(istante)})"


@tool
def orologio(timezone: str | None = FUSO_PREDEFINITO) -> str:
    """Restituisce la data e l'ora correnti. `timezone` è un fuso orario IANA (per esempio Europe/Rome, Asia/Tokyo); se omesso si usa Europe/Rome."""
    return leggi_orologio(timezone)


STRUMENTI = [orologio]


AVVISO_MCP = (
    "Server MCP non raggiungibile su {url}: gli strumenti MCP non sono disponibili. "
    "Riavvia l'agente quando il server è attivo."
)


def componi_strumenti(
    config: Config,
    scopri: Callable[..., list[BaseTool]] = scopri_strumenti,
    dormi: Callable[[float], None] = time.sleep,
    adesso: Callable[[], float] = time.monotonic,
) -> tuple[list[BaseTool], list[str]]:
    """Strumenti locali più quelli scoperti via MCP; restituisce (strumenti, avvisi).

    La discovery è ripetuta (pausa di 1 s) solo finché non è trascorsa l'attesa di avvio
    `mcp_attesa_avvio`; con attesa 0 c'è un solo tentativo. Se il server non risponde
    resta l'avvio ridotto (solo strumenti locali) con un avviso, senza altri tentativi.
    """
    inizio = adesso()
    while True:
        try:
            mcp = scopri(config.mcp_url, config.mcp_timeout)
            return [*STRUMENTI, *mcp], []
        except ErroreMcp as errore:
            if adesso() - inizio >= config.mcp_attesa_avvio:
                LOG.warning("discovery MCP fallita, avvio ridotto: %s", errore)
                return list(STRUMENTI), [AVVISO_MCP.format(url=config.mcp_url)]
            dormi(1)
