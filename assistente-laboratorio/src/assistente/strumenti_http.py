"""Strumenti che chiamano il servizio HTTP (FastAPI): wrapper `@tool` scritti a mano, richieste sincrone con timeout."""
import logging

import httpx
from langchain_core.tools import BaseTool, tool

LOG = logging.getLogger("assistente.http")


def _errore_argomenti(nome: str, attesi: str):
    def gestore(errore: Exception) -> str:
        campi = sorted({str(e["loc"][0]) for e in errore.errors() if e.get("loc")})
        dettaglio = f" Controlla: {', '.join(campi)}." if campi else ""
        return f"Errore: argomenti non validi per {nome}: servono {attesi}.{dettaglio}"

    return gestore


def crea_strumenti_http(base_url: str, timeout: float, client: httpx.Client | None = None) -> list[BaseTool]:
    """Crea `giorni_lavorativi` e `calcola_scadenza`. Nessuna discovery: sono sempre disponibili;
    se il servizio è spento lo strumento risponde `Errore: servizio non raggiungibile ...` alla chiamata.
    `client` è iniettabile per i test (trasporto finto)."""
    base = base_url.rstrip("/")
    http = client or httpx.Client()

    def chiama(percorso: str, parametri: dict, campo: str) -> tuple[dict | None, str | None]:
        """Restituisce (corpo, None) oppure (None, testo d'errore)."""
        LOG.info("richiesta GET %s %s", percorso, parametri)
        try:
            risposta = http.get(f"{base}{percorso}", params=parametri, timeout=timeout)
        except httpx.TimeoutException:
            return None, f"Errore: timeout dopo {timeout:g} s nella chiamata al servizio"
        except httpx.RequestError:
            return None, f"Errore: servizio non raggiungibile su {base}"
        if risposta.status_code == 422:
            try:
                dettaglio = risposta.json()["detail"]
            except (ValueError, KeyError, TypeError):
                dettaglio = "richiesta rifiutata dal servizio"
            return None, f"Errore: {dettaglio}"
        if risposta.status_code != 200:
            return None, f"Errore: il servizio ha risposto con HTTP {risposta.status_code}"
        try:
            corpo = risposta.json()
        except ValueError:
            corpo = None
        if not isinstance(corpo, dict) or campo not in corpo:
            return None, "Errore: risposta del servizio non valida"
        return corpo, None

    @tool
    def giorni_lavorativi(data_inizio: str, data_fine: str) -> str:
        """Conta i giorni lavorativi (esclusi sabati, domeniche e festività nazionali italiane 2026-2027) tra due date, estremi inclusi. Date nel formato AAAA-MM-GG. Esempio: "quanti giorni lavorativi tra il 2 e il 20 novembre 2026?" → data_inizio="2026-11-02", data_fine="2026-11-20". Non serve per l'ora attuale."""
        corpo, errore = chiama("/giorni-lavorativi", {"da": data_inizio, "a": data_fine}, "giorni_lavorativi")
        if errore:
            return errore
        return f"Giorni lavorativi dal {corpo['da']} al {corpo['a']}: {corpo['giorni_lavorativi']}. {corpo.get('nota', '')}".strip()

    @tool
    def calcola_scadenza(data_inizio: str, giorni: int) -> str:
        """Calcola la data di scadenza dopo un numero di giorni lavorativi (esclusi weekend e festività nazionali italiane 2026-2027); il giorno di partenza non conta. Data nel formato AAAA-MM-GG, giorni da 1 a 365. Esempio: "scadenza a 10 giorni lavorativi dal 9 novembre 2026" → data_inizio="2026-11-09", giorni=10."""
        corpo, errore = chiama("/scadenza", {"da": data_inizio, "giorni": giorni}, "data_scadenza")
        if errore:
            return errore
        return (
            f"Scadenza: {corpo['data_scadenza']} ({corpo['giorni']} giorni lavorativi dopo il {corpo['da']}). "
            f"{corpo.get('nota', '')}"
        ).strip()

    giorni_lavorativi.handle_validation_error = _errore_argomenti(
        "giorni_lavorativi", "data_inizio e data_fine (testo AAAA-MM-GG)")
    calcola_scadenza.handle_validation_error = _errore_argomenti(
        "calcola_scadenza", "data_inizio (testo AAAA-MM-GG) e giorni (un intero)")
    return [giorni_lavorativi, calcola_scadenza]
