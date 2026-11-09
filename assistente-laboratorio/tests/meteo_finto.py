"""Risposte Open-Meteo simulate: i test non escono mai in rete."""

import httpx

GEOCODIFICA = "geocoding-api.open-meteo.com"
PREVISIONE = "api.open-meteo.com"

ROMA = {"name": "Roma", "admin1": "Lazio", "country": "Italia", "latitude": 41.89, "longitude": 12.48}


def previsione(temperatura=18.4, codice=2, ora="2026-11-09T10:00"):
    return {
        "current_units": {"temperature_2m": "°C"},
        "current": {"time": ora, "temperature_2m": temperatura, "weather_code": codice},
    }


def client_finto(geocodifica=None, forecast=None, richieste=None) -> httpx.Client:
    """Client httpx con trasporto simulato. `geocodifica` e `forecast` sono dict JSON oppure
    funzioni `richiesta -> httpx.Response` (anche funzioni che sollevano). `richieste` raccoglie
    le richieste ricevute."""
    geocodifica = {"results": [ROMA]} if geocodifica is None else geocodifica
    forecast = previsione() if forecast is None else forecast

    def risposta(origine, richiesta):
        return origine(richiesta) if callable(origine) else httpx.Response(200, json=origine)

    def gestore(richiesta: httpx.Request) -> httpx.Response:
        if richieste is not None:
            richieste.append(richiesta)
        if richiesta.url.host == GEOCODIFICA:
            return risposta(geocodifica, richiesta)
        if richiesta.url.host == PREVISIONE:
            return risposta(forecast, richiesta)
        raise AssertionError(f"host inatteso: {richiesta.url.host}")

    return httpx.Client(transport=httpx.MockTransport(gestore), timeout=5.0)
