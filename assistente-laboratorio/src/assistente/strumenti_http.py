"""Strumenti che chiamano il servizio HTTP (FastAPI): wrapper `@tool` scritti a mano, richieste sincrone con timeout."""
import logging
from urllib.parse import quote

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
    """Crea `giorni_lavorativi`, `calcola_scadenza`, `cerca_catalogo` e `dettaglio_catalogo`. Nessuna discovery: sono sempre disponibili;
    se il servizio è spento lo strumento risponde `Errore: servizio non raggiungibile ...` alla chiamata.
    `client` è iniettabile per i test (trasporto finto)."""
    base = base_url.rstrip("/")
    http = client or httpx.Client()

    def chiama(
        percorso: str, parametri: dict, campi: dict[str, type], non_trovato: str | None = None
    ) -> tuple[dict | None, str | None]:
        """Restituisce (corpo, None) oppure (None, testo d'errore). `campi`: nome e tipo dei campi attesi;
        `non_trovato`: testo d'errore per un 404 (solo per le risorse identificate da un codice)."""
        LOG.info("richiesta GET %s %s", percorso, parametri)
        try:
            risposta = http.get(f"{base}{percorso}", params=parametri, timeout=timeout)
        except httpx.TimeoutException:
            return None, f"Errore: timeout dopo {timeout:g} s nella chiamata al servizio"
        except httpx.InvalidURL:
            return None, f"Errore: indirizzo del servizio non valido ({base!r}): controlla SERVIZI_BASE_URL"
        except httpx.RequestError:
            return None, f"Errore: servizio non raggiungibile su {base}"
        if risposta.status_code == 404 and non_trovato:
            return None, non_trovato
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
        if not isinstance(corpo, dict) or not all(isinstance(corpo.get(c), t) for c, t in campi.items()):
            return None, "Errore: risposta del servizio non valida"
        return corpo, None

    @tool
    def giorni_lavorativi(data_inizio: str, data_fine: str) -> str:
        """Conta i giorni lavorativi (esclusi sabati, domeniche e festività nazionali italiane 2026-2027) tra due date, estremi inclusi. Date nel formato AAAA-MM-GG. Esempio: "quanti giorni lavorativi tra il 2 e il 20 novembre 2026?" → data_inizio="2026-11-02", data_fine="2026-11-20". Non serve per l'ora attuale."""
        corpo, errore = chiama("/giorni-lavorativi", {"da": data_inizio, "a": data_fine},
                              {"da": str, "a": str, "giorni_lavorativi": int})
        if errore:
            return errore
        return f"Giorni lavorativi dal {corpo['da']} al {corpo['a']}: {corpo['giorni_lavorativi']}. {corpo.get('nota', '')}".strip()

    @tool
    def calcola_scadenza(data_inizio: str, giorni: int) -> str:
        """Calcola la data di scadenza dopo un numero di giorni lavorativi (esclusi weekend e festività nazionali italiane 2026-2027); il giorno di partenza non conta. Data nel formato AAAA-MM-GG, giorni da 1 a 365. Esempio: "scadenza a 10 giorni lavorativi dal 9 novembre 2026" → data_inizio="2026-11-09", giorni=10."""
        corpo, errore = chiama("/scadenza", {"da": data_inizio, "giorni": giorni},
                              {"da": str, "giorni": int, "data_scadenza": str})
        if errore:
            return errore
        return (
            f"Scadenza: {corpo['data_scadenza']} ({corpo['giorni']} giorni lavorativi dopo il {corpo['da']}). "
            f"{corpo.get('nota', '')}"
        ).strip()

    @tool
    def cerca_catalogo(query: str, max_risultati: int = 5) -> str:
        """Cerca corsi nel catalogo per parola chiave (titolo, settore o sede), senza distinguere maiuscole e accenti. Restituisce codice, titolo, settore e sede dei corsi trovati, non durata né descrizione (per quelli usa dettaglio_catalogo). Il catalogo è di esempio, con corsi fittizi. Esempio: "che corsi ci sono a Udine?" → query="Udine"."""
        corpo, errore = chiama("/catalogo", {"q": query, "max_risultati": max_risultati},
                              {"totale": int, "risultati": list})
        if errore:
            return errore
        righe = []
        for c in corpo["risultati"]:
            if not (isinstance(c, dict) and all(isinstance(c.get(k), str) for k in ("codice", "titolo", "settore", "sede"))):
                return "Errore: risposta del servizio non valida"
            righe.append(f"- {c['codice']}: {c['titolo']} ({c['settore']}, {c['sede']})")
        if corpo["totale"] == 0 or not righe:
            return f"Nessun corso trovato per {query!r}. {corpo.get('nota', '')}".strip()
        intestazione = f"Corsi trovati per {query!r}: {corpo['totale']}"
        if corpo["totale"] > len(righe):
            intestazione += f" (mostrati {len(righe)}: restringi la ricerca per vedere gli altri)"
        return "\n".join([intestazione + ".", *righe, corpo.get("nota", "")]).strip()

    @tool
    def dettaglio_catalogo(codice: str) -> str:
        """Restituisce tutti i dati di un corso del catalogo (titolo, settore, sede, durata in ore, descrizione) dato il suo codice, per esempio ITS-003. Usalo quando il codice è già noto; per cercare per parola chiave usa cerca_catalogo. Il catalogo è di esempio, con corsi fittizi. Esempio: "dimmi la durata del corso ITS-003" → codice="ITS-003"."""
        corpo, errore = chiama(
            f"/catalogo/{quote(codice.strip(), safe='')}", {},
            {"codice": str, "titolo": str, "settore": str, "sede": str, "durata_ore": int, "descrizione": str},
            non_trovato=f"Errore: corso {codice.strip()} non trovato",
        )
        if errore:
            return errore
        return (
            f"{corpo['codice']}: {corpo['titolo']}. Settore: {corpo['settore']}. Sede: {corpo['sede']}. "
            f"Durata: {corpo['durata_ore']} ore. Descrizione: {corpo['descrizione']} {corpo.get('nota', '')}"
        ).strip()

    giorni_lavorativi.handle_validation_error = _errore_argomenti(
        "giorni_lavorativi", "data_inizio e data_fine (testo AAAA-MM-GG)")
    calcola_scadenza.handle_validation_error = _errore_argomenti(
        "calcola_scadenza", "data_inizio (testo AAAA-MM-GG) e giorni (un intero)")
    cerca_catalogo.handle_validation_error = _errore_argomenti(
        "cerca_catalogo", "query (testo) e, facoltativo, max_risultati (un intero da 1 a 10)")
    dettaglio_catalogo.handle_validation_error = _errore_argomenti("dettaglio_catalogo", "codice (testo, per esempio ITS-003)")
    return [giorni_lavorativi, calcola_scadenza, cerca_catalogo, dettaglio_catalogo]
