"""Meteo attuale da Open-Meteo (senza chiave): geocodifica del nome, poi lettura delle condizioni."""

import logging

import httpx

LOG = logging.getLogger("assistente.meteo")

URL_GEOCODIFICA = "https://geocoding-api.open-meteo.com/v1/search"
URL_PREVISIONE = "https://api.open-meteo.com/v1/forecast"
MAX_CARATTERI_CITTA = 100
MAX_CANDIDATI = 5  # parametro `count` della geocodifica

# Codici WMO usati da Open-Meteo, tradotti in italiano.
_CONDIZIONI = {
    0: "sereno",
    1: "prevalentemente sereno",
    2: "parzialmente nuvoloso",
    3: "coperto",
    45: "nebbia",
    48: "nebbia con brina",
    51: "pioggerella",
    53: "pioggerella",
    55: "pioggerella",
    56: "pioggerella gelata",
    57: "pioggerella gelata",
    61: "pioggia",
    63: "pioggia",
    65: "pioggia",
    66: "pioggia gelata",
    67: "pioggia gelata",
    71: "neve",
    73: "neve",
    75: "neve",
    77: "granelli di neve",
    80: "rovesci",
    81: "rovesci",
    82: "rovesci",
    85: "rovesci di neve",
    86: "rovesci di neve",
    95: "temporale",
    96: "temporale con grandine",
    99: "temporale con grandine",
}


class ErroreMeteo(Exception):
    """Errore leggibile (città non trovata, timeout, servizio o rete non disponibili...)."""


def _chiedi(client: httpx.Client, url: str, parametri: dict) -> dict:
    """GET con JSON in risposta; ogni guasto diventa un `ErroreMeteo` con messaggio proprio."""
    try:
        risposta = client.get(url, params=parametri)
    except httpx.TimeoutException as errore:
        raise ErroreMeteo("timeout: il servizio meteo non ha risposto in tempo") from errore
    except httpx.TransportError as errore:
        raise ErroreMeteo("rete non disponibile: impossibile raggiungere il servizio meteo") from errore
    if risposta.status_code >= 500:
        raise ErroreMeteo(f"servizio meteo non disponibile (HTTP {risposta.status_code})")
    if risposta.status_code >= 400:
        raise ErroreMeteo(f"richiesta rifiutata dal servizio meteo (HTTP {risposta.status_code})")
    try:
        dati = risposta.json()
    except ValueError as errore:
        raise ErroreMeteo("risposta non valida dal servizio meteo (JSON atteso)") from errore
    if not isinstance(dati, dict):
        raise ErroreMeteo("risposta non valida dal servizio meteo (struttura inattesa)")
    return dati


def _numero(valore) -> bool:
    return isinstance(valore, (int, float)) and not isinstance(valore, bool)


def _luogo(candidato: dict) -> str:
    nome = candidato["name"]
    dettagli = [d for d in (candidato.get("admin1"), candidato.get("country")) if d]
    return f"{nome} ({', '.join(dettagli)})" if dettagli else str(nome)


def leggi_meteo(citta: str, client: httpx.Client) -> str:
    """Temperatura, condizioni e ora di rilevazione. Solleva `ErroreMeteo` con un testo chiaro."""
    nome = citta.strip() if isinstance(citta, str) else ""
    if not nome:
        raise ErroreMeteo("indica il nome di una città")
    if len(nome) > MAX_CARATTERI_CITTA:
        raise ErroreMeteo(f"il nome della città supera {MAX_CARATTERI_CITTA} caratteri")

    geo = _chiedi(client, URL_GEOCODIFICA, {"name": nome, "count": MAX_CANDIDATI, "language": "it"})
    candidati = geo.get("results")
    if candidati is None or candidati == []:
        raise ErroreMeteo(f"città non trovata: {nome!r}")
    try:
        primo = candidati[0]
        luogo = _luogo(primo)
        latitudine, longitudine = primo["latitude"], primo["longitude"]
        if not (_numero(latitudine) and _numero(longitudine)):
            raise TypeError("coordinate non numeriche")
    except (KeyError, IndexError, TypeError) as errore:
        raise ErroreMeteo("risposta non valida dal servizio meteo (geocodifica)") from errore

    previsione = _chiedi(
        client,
        URL_PREVISIONE,
        {
            "latitude": latitudine,
            "longitude": longitudine,
            "current": "temperature_2m,weather_code",
            "timezone": "auto",
        },
    )
    try:
        attuale = previsione["current"]
        temperatura, codice, ora = attuale["temperature_2m"], attuale["weather_code"], attuale["time"]
        if not _numero(temperatura) or not _numero(codice) or not isinstance(ora, str):
            raise TypeError("valori inattesi")
    except (KeyError, TypeError) as errore:
        raise ErroreMeteo("risposta non valida dal servizio meteo (previsione)") from errore

    condizioni = _CONDIZIONI.get(int(codice), f"condizioni non classificate (codice {int(codice)})")
    risultato = f"{luogo}: {temperatura:g} °C, {condizioni}, rilevato il {ora.replace('T', ' ')}"
    altri = len(candidati) - 1
    if altri > 0:
        # Con l'elenco al limite richiesto (`count`) i candidati reali possono essere di più.
        quanti = f"almeno {altri}" if len(candidati) >= MAX_CANDIDATI else str(altri)
        risultato += f". Altri luoghi con lo stesso nome: {quanti} (ho usato il primo)"
    LOG.info("meteo letto: %s", risultato)
    return risultato
