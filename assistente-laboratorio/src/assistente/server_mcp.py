"""Server MCP (FastMCP, Streamable HTTP): strumenti per note e meteo, resource delle preferenze, prompt `spiega` e `riassumi_conversazione`.

Avvio: `python -m assistente.server_mcp` (variabili `NOTE_DB_PATH`, `PREFERENZE_PATH`, `MCP_HOST`, `MCP_PORT`).
"""

import asyncio
import logging
import os
import sys
from collections.abc import Mapping
from pathlib import Path

import httpx
from fastmcp import FastMCP
from fastmcp.exceptions import PromptError, ResourceError, ToolError

from assistente.meteo import ErroreMeteo, leggi_meteo
from assistente.note import ArchivioNote, ErroreNote

logger = logging.getLogger("assistente.server_mcp")

METEO_TIMEOUT = 10.0  # secondi, per ciascuna delle due richieste a Open-Meteo

# Radice del progetto calcolata dalla posizione del modulo, non dalla cartella corrente (spec Step 4 §5.2).
PERCORSO_PREFERENZE_PREDEFINITO = Path(__file__).resolve().parents[2] / "data" / "preferenze.json"


# Prompt dello Step 5: descrizioni (spec §5) e testi esatti dell'Appendice A della specifica.
DESCRIZIONE_SPIEGA = "Spiega un argomento al livello scelto: base, intermedio o avanzato (predefinito base)."
DESCRIZIONE_RIASSUMI = (
    "Riassume la conversazione della sessione in corso nello stile indicato, testo libero (predefinito breve)."
)
TESTO_SPIEGA = (
    "Spiega l'argomento «{argomento}» a livello {livello}. {guida_livello} "
    "Per questa risposta il livello richiesto prevale sullo stile indicato nelle preferenze."
)
GUIDE_LIVELLO = {
    "base": "Usa un linguaggio semplice, senza dare per scontate conoscenze precedenti, e aggiungi un esempio concreto.",
    "intermedio": "Presenta i concetti principali e la terminologia corretta, dando per scontate le basi.",
    "avanzato": "Entra nei dettagli tecnici, nei compromessi e nei casi limite.",
}
TESTO_RIASSUMI = (
    "Riassumi la nostra conversazione di questa sessione fino a questo momento, in questo stile: {stile}. "
    "Basati sul riassunto della conversazione precedente, se è presente, e sui messaggi che precedono questa richiesta. "
    "Riporta solo ciò che è stato davvero detto o fatto, compresi i risultati degli strumenti, "
    "senza aggiungere informazioni nuove. Non serve usare strumenti. "
    "Se non ci sono ancora turni da riassumere, dillo in una frase. "
    "Per questa risposta lo stile richiesto prevale sullo stile indicato nelle preferenze."
)


def percorso_preferenze(env: Mapping[str, str] = os.environ) -> Path:
    """`PREFERENZE_PATH` se impostata (un percorso relativo vale dalla cartella corrente), altrimenti il predefinito."""
    valore = env.get("PREFERENZE_PATH", "").strip()
    return Path(valore) if valore else PERCORSO_PREFERENZE_PREDEFINITO


def crea_server(
    archivio: ArchivioNote,
    client_http: httpx.Client | None = None,
    percorso_preferenze: str | Path | None = None,
) -> FastMCP:
    """Server MCP con note, meteo, la resource delle preferenze e i due prompt dello Step 5.

    `client_http` serve ai test per simulare Open-Meteo; `percorso_preferenze` per usare un file temporaneo.
    """
    server = FastMCP("note")
    client_meteo = client_http or httpx.Client(timeout=METEO_TIMEOUT)
    file_preferenze = Path(percorso_preferenze) if percorso_preferenze is not None else PERCORSO_PREFERENZE_PREDEFINITO

    @server.resource(
        "utente://preferenze",
        mime_type="application/json",
        description="Preferenze dell'utente (lingua, fuso orario predefinito, stile delle risposte), lette dal file.",
    )
    def preferenze() -> str:
        """Testo del file così com'è, riletto a ogni richiesta; nessun valore predefinito (spec Step 4 §5.3)."""
        try:
            # utf-8-sig: tollera il BOM di Blocco note e PowerShell 5.1.
            testo = file_preferenze.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeDecodeError) as errore:
            causa = f"{file_preferenze}: {getattr(errore, 'strerror', None) or errore}"
            logger.warning("resource utente://preferenze non disponibile: %s", causa)
            raise ResourceError(causa) from errore
        logger.info("resource utente://preferenze letta da %s", file_preferenze)
        return testo

    @server.tool(
        description=(
            "Salva una nota. "
            'Esempio: "ricordami di consegnare il report venerdì"'
        )
    )
    def aggiungi_nota(testo: str) -> str:
        try:
            nota = archivio.aggiungi(testo)
        except ErroreNote as errore:
            raise ToolError(str(errore)) from errore
        logger.info("nota aggiunta: id %s", nota.id)
        return f"Nota creata: id {nota.id}, data {nota.creata}"

    @server.tool(
        description=(
            "Elenca le note salvate, dalla più recente. `filtro` cerca una parola nel "
            "testo (facoltativo); `limite` è il numero massimo di note (1-100, predefinito 20). "
            'Esempio: "elenca le mie note" oppure "cerca le note sul report"'
        )
    )
    def elenca_note(filtro: str | None = None, limite: int = 20) -> str:
        try:
            note = archivio.elenca(filtro, limite)
        except ErroreNote as errore:
            raise ToolError(str(errore)) from errore
        if not note:
            return "Nessuna nota trovata."
        return "\n".join(f"id {n.id} | {n.creata} | {n.testo}" for n in note)

    @server.tool(
        description=(
            "Elimina la nota con l'id indicato. L'applicazione chiede conferma all'utente "
            'prima di cancellare. Esempio: "elimina la nota 3"'
        ),
        annotations={"destructiveHint": True},
    )
    def elimina_nota(id: int) -> str:
        """Cancella la nota senza altre verifiche.

        La conferma dell'utente non è qui: la chiede il client (il nostro agente, in base a
        `destructiveHint`). Altri client MCP possono cancellare senza conferma.
        """
        try:
            archivio.elimina(id)
        except ErroreNote as errore:
            raise ToolError(str(errore)) from errore
        logger.info("nota eliminata: id %s", id)
        return f"Nota {id} eliminata"

    @server.tool(
        description=(
            "Restituisce il meteo attuale (temperatura in °C e condizioni) di una città, "
            "dato il suo nome. Non serve per sapere che ora è. "
            'Esempio: "che tempo fa a Bologna?" oppure "piove a Forlì?"'
        )
    )
    def meteo(citta: str) -> str:
        try:
            return leggi_meteo(citta, client_meteo)
        except ErroreMeteo as errore:
            logger.warning("meteo non disponibile per %r: %s", citta, errore)
            raise ToolError(str(errore)) from errore

    # Prompt MCP (Step 5): li richiama l'utente con /prompt, mai il modello. Argomenti `str` semplici:
    # con Literal o Annotated FastMCP aggiunge alla descrizione un testo inglese automatico (spec §3.1).
    @server.prompt(description=DESCRIZIONE_SPIEGA)
    def spiega(argomento: str, livello: str = "base") -> str:
        if livello not in GUIDE_LIVELLO:
            raise PromptError(f"livello non valido: {livello} (valori ammessi: {', '.join(GUIDE_LIVELLO)})")
        return TESTO_SPIEGA.format(argomento=argomento, livello=livello, guida_livello=GUIDE_LIVELLO[livello])

    @server.prompt(description=DESCRIZIONE_RIASSUMI)
    def riassumi_conversazione(stile: str = "breve") -> str:
        return TESTO_RIASSUMI.format(stile=stile)

    return server


def main() -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    percorso = os.environ.get("NOTE_DB_PATH", "data/note.db")
    host = os.environ.get("MCP_HOST", "127.0.0.1")
    try:
        porta = int(os.environ.get("MCP_PORT", "8001"))
    except ValueError:
        print("MCP_PORT deve essere un numero intero", file=sys.stderr)
        return 1
    Path(percorso).parent.mkdir(parents=True, exist_ok=True)
    preferenze = percorso_preferenze()
    logger.info(
        "server MCP delle note su http://%s:%s/mcp (archivio %s, preferenze %s)", host, porta, percorso, preferenze
    )
    server = crea_server(ArchivioNote(percorso), percorso_preferenze=preferenze)
    asyncio.run(server.run_http_async(host=host, port=porta, path="/mcp", show_banner=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
