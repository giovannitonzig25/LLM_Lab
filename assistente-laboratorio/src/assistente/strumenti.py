"""Strumenti che il modello può chiedere al programma di eseguire."""
import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from langchain_core.tools import BaseTool, StructuredTool

from assistente.calcolatrice import calcola
from assistente.config import Config
from assistente.mcp_client import ErroreMcp, scopri_strumenti
from assistente.preferenze import PREFERENZE_PREDEFINITE, Preferenze
from assistente.strumenti_http import crea_strumenti_http
from assistente.unita import converti_unita

LOG = logging.getLogger("assistente.strumenti")

FUSO_PREDEFINITO = PREFERENZE_PREDEFINITE.fuso_orario


def adesso_utc() -> datetime:
    return datetime.now(UTC)


def _formatta_offset(istante: datetime) -> str:
    minuti = int(istante.utcoffset().total_seconds() // 60)
    segno = "+" if minuti >= 0 else "-"
    ore, resto = divmod(abs(minuti), 60)
    return f"UTC{segno}{ore:02d}:{resto:02d}"


def leggi_orologio(
    timezone: str | None = None, adesso: Callable[[], datetime] = adesso_utc, predefinito: str = FUSO_PREDEFINITO
) -> str:
    """Data e ora correnti nel fuso indicato. Non solleva eccezioni: un fuso non valido dà un testo `Errore: ...`."""
    if timezone is None or (isinstance(timezone, str) and not timezone.strip()):
        timezone = predefinito
    try:
        fuso = ZoneInfo(timezone)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        return f"Errore: fuso orario non valido: {timezone!r}. Usa un nome IANA, per esempio Europe/Rome o Asia/Tokyo."
    istante = adesso().astimezone(fuso)
    return f"{istante:%Y-%m-%d %H:%M:%S} ({timezone}, {_formatta_offset(istante)})"


def crea_orologio(fuso: str) -> BaseTool:
    """Strumento orologio con `fuso` come valore predefinito: il fuso della sessione (spec Step 4 §9)."""

    def orologio(timezone: str | None = fuso) -> str:
        return leggi_orologio(timezone, predefinito=fuso)

    return StructuredTool.from_function(
        orologio,
        name="orologio",
        description=(
            "Restituisce la data e l'ora correnti. `timezone` è un fuso orario IANA "
            f"(per esempio Europe/Rome, Asia/Tokyo); se omesso si usa {fuso}."
        ),
    )


orologio = crea_orologio(FUSO_PREDEFINITO)
STRUMENTI = [orologio, converti_unita, calcola]


AVVISO_MCP = (
    "Server MCP non raggiungibile su {url}: gli strumenti MCP non sono disponibili. "
    "Riavvia l'agente quando il server è attivo."
)


def componi_strumenti(
    config: Config,
    scopri: Callable[..., list[BaseTool]] = scopri_strumenti,
    dormi: Callable[[float], None] = time.sleep,
    adesso: Callable[[], float] = time.monotonic,
    chiedi_conferma: Callable[[str], bool] | None = None,
    carica_preferenze: Callable[[], Preferenze] | None = None,
) -> tuple[list[BaseTool], Preferenze, list[str]]:
    """Strumenti locali, HTTP (sempre presenti) e quelli scoperti via MCP; restituisce (strumenti, preferenze, avvisi).

    Ordine (spec Step 4 §6.3): discovery, poi `carica_preferenze()` (dopo l'eventuale attesa del server),
    poi l'orologio costruito con il fuso delle preferenze. Senza `carica_preferenze`: valori predefiniti.

    La discovery è ripetuta (pausa di 1 s) solo finché non è trascorsa l'attesa di avvio
    `mcp_attesa_avvio`; con attesa 0 c'è un solo tentativo. Se il server non risponde
    resta l'avvio ridotto (solo strumenti locali) con un avviso, senza altri tentativi.
    """
    # Gli strumenti HTTP sono sempre registrati: un servizio spento dà `Errore:` alla chiamata.
    http = crea_strumenti_http(config.servizi_base_url, config.servizi_timeout)
    inizio = adesso()
    while True:
        try:
            mcp, avvisi = scopri(config.mcp_url, config.mcp_timeout, chiedi_conferma=chiedi_conferma), []
            break
        except ErroreMcp as errore:
            if adesso() - inizio >= config.mcp_attesa_avvio:
                LOG.warning("discovery MCP fallita, avvio ridotto: %s", errore)
                mcp, avvisi = [], [AVVISO_MCP.format(url=config.mcp_url)]
                break
            dormi(1)
    preferenze = carica_preferenze() if carica_preferenze is not None else PREFERENZE_PREDEFINITE
    locali = [crea_orologio(preferenze.fuso_orario), converti_unita, calcola]
    return [*locali, *http, *mcp], preferenze, avvisi
