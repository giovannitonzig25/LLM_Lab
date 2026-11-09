import httpx
import pytest

from assistente.meteo import ErroreMeteo, leggi_meteo
from meteo_finto import ROMA, client_finto, previsione


def test_risultato_con_unita_e_ora():
    richieste = []

    risultato = leggi_meteo("Roma", client_finto(richieste=richieste))

    assert risultato == "Roma (Lazio, Italia): 18.4 °C, parzialmente nuvoloso, rilevato il 2026-11-09 10:00"
    geo, meteo = richieste
    assert geo.url.params["name"] == "Roma"
    assert geo.url.params["count"] == "5"
    assert geo.url.params["language"] == "it"
    assert meteo.url.params["latitude"] == "41.89" and meteo.url.params["longitude"] == "12.48"
    assert meteo.url.params["current"] == "temperature_2m,weather_code"
    assert meteo.url.params["timezone"] == "auto"


def test_temperatura_negativa():
    assert "-3.2 °C" in leggi_meteo("Roma", client_finto(forecast=previsione(temperatura=-3.2, codice=73)))


def test_citta_ambigua_dichiarata():
    altra = {"name": "Roma", "admin1": "Texas", "country": "Stati Uniti", "latitude": 29.5, "longitude": -99.9}

    risultato = leggi_meteo("Roma", client_finto(geocodifica={"results": [ROMA, altra]}))

    assert risultato.startswith("Roma (Lazio, Italia): 18.4 °C")  # primo risultato, dichiarato
    assert "Altri luoghi con lo stesso nome: 1" in risultato


def test_localita_senza_regione():
    senza_regione = {"name": "Monaco", "country": "Monaco", "latitude": 43.7, "longitude": 7.4}

    risultato = leggi_meteo("Monaco", client_finto(geocodifica={"results": [senza_regione]}))

    assert risultato.startswith("Monaco (Monaco): ")


@pytest.mark.parametrize("citta", ["Forlì", "San Donà di Piave", "L'Aquila", "Città del Capo"])
def test_citta_con_accenti_e_spazi(citta):
    richieste = []

    leggi_meteo(citta, client_finto(richieste=richieste))

    assert richieste[0].url.params["name"] == citta


@pytest.mark.parametrize("codice, atteso", [
    (0, "sereno"), (2, "parzialmente nuvoloso"), (45, "nebbia"), (53, "pioggerella"),
    (63, "pioggia"), (73, "neve"), (81, "rovesci"), (95, "temporale"),
    (999, "condizioni non classificate (codice 999)"),
])
def test_codici_meteo_in_italiano(codice, atteso):
    assert f", {atteso}, " in leggi_meteo("Roma", client_finto(forecast=previsione(codice=codice)))


def messaggio_di_errore(**client):
    with pytest.raises(ErroreMeteo) as errore:
        leggi_meteo("Roma", client_finto(**client))
    return str(errore.value)


def solleva(errore):
    def gestore(richiesta):
        raise errore
    return gestore


def test_citta_non_trovata():
    assert "non trovata" in messaggio_di_errore(geocodifica={})
    assert "non trovata" in messaggio_di_errore(geocodifica={"results": []})


def test_timeout():
    assert "timeout" in messaggio_di_errore(geocodifica=solleva(httpx.ReadTimeout("lento")))
    assert "timeout" in messaggio_di_errore(forecast=solleva(httpx.ConnectTimeout("lento")))


@pytest.mark.parametrize("dove", ["geocodifica", "forecast"])
def test_servizio_non_disponibile(dove):
    messaggio = messaggio_di_errore(**{dove: lambda r: httpx.Response(503)})

    assert "non disponibile" in messaggio and "503" in messaggio


def test_richiesta_rifiutata_dal_servizio():
    messaggio = messaggio_di_errore(forecast=lambda r: httpx.Response(429))

    assert "429" in messaggio and "non trovata" not in messaggio


@pytest.mark.parametrize("client", [
    {"geocodifica": lambda r: httpx.Response(200, text="non è json")},
    {"geocodifica": {"results": [{"name": "Roma"}]}},  # mancano le coordinate
    {"geocodifica": {"results": "boh"}},
    {"forecast": {"foo": 1}},
    {"forecast": {"current": {"time": "2026-11-09T10:00"}}},  # mancano temperatura e codice
    {"forecast": {"current": {"time": "2026-11-09T10:00", "temperature_2m": "caldo", "weather_code": 2}}},
])
def test_risposta_non_valida(client):
    assert "risposta non valida" in messaggio_di_errore(**client)


def test_rete_assente_non_e_citta_non_trovata():
    messaggio = messaggio_di_errore(geocodifica=solleva(httpx.ConnectError("nessuna rete")))

    assert "rete" in messaggio and "non trovata" not in messaggio


def test_i_cinque_errori_hanno_messaggi_diversi():
    messaggi = {
        messaggio_di_errore(geocodifica={}),
        messaggio_di_errore(geocodifica=solleva(httpx.ReadTimeout("x"))),
        messaggio_di_errore(forecast=lambda r: httpx.Response(503)),
        messaggio_di_errore(forecast={"foo": 1}),
        messaggio_di_errore(geocodifica=solleva(httpx.ConnectError("x"))),
    }

    assert len(messaggi) == 5


@pytest.mark.parametrize("citta", ["", "   ", "x" * 101])
def test_nome_citta_non_valido_non_chiama_la_rete(citta):
    richieste = []

    with pytest.raises(ErroreMeteo):
        leggi_meteo(citta, client_finto(richieste=richieste))

    assert richieste == []


def test_altri_candidati_quando_l_elenco_e_al_limite_sono_almeno():
    cinque = [dict(ROMA, admin1=f"Regione {i}") for i in range(5)]  # count=5: l'elenco può essere troncato

    risultato = leggi_meteo("Roma", client_finto(geocodifica={"results": cinque}))

    assert "Altri luoghi con lo stesso nome: almeno 4" in risultato
