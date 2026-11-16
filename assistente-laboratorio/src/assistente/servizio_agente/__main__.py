"""Avvio: python -m assistente.servizio_agente (AGENTE_HOST, AGENTE_PORT; variabili dell'agente da .env)."""
import logging
import os
import sys

import httpx
import uvicorn

from assistente.agente import costruisci_agente
from assistente.config import Config, ErroreConfigurazione, carica_config
from assistente.mcp_client import ErroreMcp, elenca_prompt, ottieni_prompt, scopri_strumenti

from .app import crea_app

LOG = logging.getLogger("assistente.servizio_agente")


def controlla_mcp(config: Config) -> str:
    """"ok" se la discovery degli strumenti MCP risponde (stesso controllo di `verifica_mcp`)."""
    try:
        scopri_strumenti(config.mcp_url, config.mcp_timeout)
    except ErroreMcp as errore:
        return f"non raggiungibile: {errore}"
    return "ok"


def controlla_modello(config: Config) -> str:
    """"ok" se LM Studio risponde a GET /models ed elenca LM_STUDIO_MODEL."""
    url = config.base_url.rstrip("/") + "/models"
    try:
        risposta = httpx.get(url, timeout=5.0)
        risposta.raise_for_status()
        modelli = [m.get("id") for m in risposta.json().get("data", [])]
    except (httpx.HTTPError, ValueError, AttributeError) as errore:
        return f"non raggiungibile su {url}: {errore}"
    if config.modello not in modelli:
        return f"modello {config.modello!r} non elencato da {url}"
    return "ok"


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    try:
        config = carica_config()
    except ErroreConfigurazione as errore:
        print(errore, file=sys.stderr)
        return 1
    grafo, avvisi = costruisci_agente(config)
    for avviso in avvisi:
        LOG.warning("%s", avviso)
    app = crea_app(
        grafo, max_passaggi=config.max_passaggi, max_revisioni=config.max_revisioni,
        elenca=lambda: elenca_prompt(config.mcp_url, config.mcp_timeout),
        ottieni=lambda nome, argomenti: ottieni_prompt(config.mcp_url, nome, argomenti, config.mcp_timeout),
        stato_mcp=lambda: controlla_mcp(config),
        stato_modello=lambda: controlla_modello(config),
    )
    host = os.environ.get("AGENTE_HOST", "").strip() or "127.0.0.1"
    porta = int(os.environ.get("AGENTE_PORT", "").strip() or "8002")
    uvicorn.run(app, host=host, port=porta)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
