"""Interfaccia da terminale: client dell'API dell'agente (Step 6, spec §3).

La CLI conserva la `Sessione` (cronologia e riassunto, mai su disco) e la manda all'agente a ogni turno;
il grafo gira solo nel servizio dell'agente.
"""
import logging
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass

import httpx
from langchain_core.messages import BaseMessage, messages_from_dict, messages_to_dict

from assistente.agente import Sessione
from assistente.comandi import esegui_comando
from assistente.mcp_client import ArgomentoPrompt, ErroreMcp, PromptMcp

LOG = logging.getLogger("assistente.terminale")
USCITA = "esci"
AGENTE_URL_PREDEFINITO = "http://localhost:8002"
NON_RAGGIUNGIBILE = "Agente non raggiungibile su {url}: avvia `python -m assistente.servizio_agente` o controlla AGENTE_URL."
# I turni possono durare minuti con un modello locale: nessun limite sulla lettura della risposta.
TIMEOUT = httpx.Timeout(10.0, read=None)


def chiedi_conferma(messaggio: str) -> bool:
    """Conferma di un'azione distruttiva, chiesta all'utente nel terminale (fuori dal modello)."""
    try:
        return input(f"{messaggio} [s/N]: ").strip().lower() in {"s", "si", "sì"}
    except EOFError:
        return False


class ErroreAgente(Exception):
    """L'agente non ha risposto al turno; il messaggio è il testo da mostrare all'utente."""


@dataclass(frozen=True)
class EsitoChat:
    sessione: Sessione
    risposta: str
    conferme_richieste: tuple[dict, ...] = ()


def _testo_errore(risposta: httpx.Response) -> str:
    try:
        corpo = risposta.json()
    except ValueError:
        return f"errore HTTP {risposta.status_code}"
    if isinstance(corpo, dict) and isinstance(corpo.get("errore"), str):
        return corpo["errore"]
    return f"errore HTTP {risposta.status_code}: {corpo}"


class ClientAgente:
    """Chiamate all'API dell'agente su un `httpx.Client` già configurato con `base_url`."""

    def __init__(self, http: httpx.Client):
        self.http = http

    def _invia(self, metodo: str, percorso: str, **opzioni) -> httpx.Response:
        try:
            return self.http.request(metodo, percorso, **opzioni)
        except httpx.TransportError as errore:
            LOG.warning("agente non raggiungibile: %s", errore)
            raise ErroreAgente(NON_RAGGIUNGIBILE.format(url=self.http.base_url)) from errore

    def chat(
        self,
        sessione: Sessione,
        *,
        messaggio: str | None = None,
        messaggi: Sequence[tuple[str, str]] | None = None,
        conferme: Sequence[dict] = (),
    ) -> EsitoChat:
        corpo = {
            "cronologia": messages_to_dict(list(sessione.messaggi)),
            "riassunto": sessione.riassunto,
            "conferme": list(conferme),
        }
        if messaggi is not None:
            corpo["messaggi"] = [{"ruolo": ruolo, "testo": testo} for ruolo, testo in messaggi]
        else:
            corpo["messaggio"] = messaggio
        risposta = self._invia("POST", "/chat", json=corpo)
        if risposta.status_code != 200:
            raise ErroreAgente(_testo_errore(risposta))
        dati = risposta.json()
        return EsitoChat(
            Sessione(tuple(messages_from_dict(dati["cronologia"])), dati["riassunto"]),
            dati["risposta"],
            tuple(dati["conferme_richieste"]),
        )

    def _prompt(self, metodo: str, percorso: str, **opzioni):
        try:
            risposta = self._invia(metodo, percorso, **opzioni)
        except ErroreAgente as errore:
            raise ErroreMcp(str(errore)) from errore
        if risposta.status_code != 200:
            raise ErroreMcp(_testo_errore(risposta))
        return risposta.json()

    def elenca_prompt(self) -> tuple[PromptMcp, ...]:
        return tuple(
            PromptMcp(
                nome=p["nome"], descrizione=p["descrizione"],
                argomenti=tuple(ArgomentoPrompt(a["nome"], a["descrizione"], a["obbligatorio"]) for a in p["argomenti"]),
            )
            for p in self._prompt("GET", "/prompts")
        )

    def ottieni_prompt(self, nome: str, argomenti: dict[str, str]) -> list[tuple[str, str]]:
        dati = self._prompt("POST", f"/prompts/{nome}", json={"argomenti": argomenti})
        return [(m["ruolo"], m["testo"]) for m in dati]

    def stato(self) -> tuple[int, dict]:
        """Codice e corpo di GET /stato; solleva `ErroreAgente` se l'agente non risponde."""
        risposta = self._invia("GET", "/stato")
        try:
            return risposta.status_code, risposta.json()
        except ValueError:
            return risposta.status_code, {}


def _coppie(messaggi: Sequence[BaseMessage]) -> list[tuple[str, str]]:
    return [("user" if m.type == "human" else "assistant", m.text) for m in messaggi]


def esegui_turno_client(
    client: ClientAgente,
    sessione: Sessione,
    chiedi: Callable[[str], bool],
    *,
    messaggio: str | None = None,
    messaggi: Sequence[tuple[str, str]] | None = None,
) -> tuple[Sessione, str]:
    """Un turno attraverso l'API. Se l'agente chiede conferme e l'utente ne approva almeno una, il turno
    si ripete dalla stessa sessione con le conferme (spec §4.2). Su errore restituisce la sessione ricevuta."""
    conferme: list[dict] = []
    while True:
        try:
            esito = client.chat(sessione, messaggio=messaggio, messaggi=messaggi, conferme=conferme)
        except ErroreAgente as errore:
            return sessione, str(errore)
        approvate = [
            c for c in esito.conferme_richieste
            if c not in conferme and chiedi(f"Confermi: {c['strumento']} {c['argomenti']}?")
        ]
        if not approvate:
            return esito.sessione, esito.risposta
        conferme.extend(approvate)


def ripulisci_input(testo: str) -> str:
    """Sostituisce con U+FFFD i byte non validi in UTF-8 che `input()` conserva come surrogati
    (stdin con `surrogateescape`): non sarebbero codificabili nella richiesta al modello.
    Un surrogato che stdin non produce viene invece sostituito con `?`."""
    try:
        return testo.encode("utf-8", errors="surrogateescape").decode("utf-8", errors="replace")
    except UnicodeEncodeError:  # surrogato che stdin non produce (per esempio uno isolato nell'intervallo alto)
        return testo.encode("utf-8", errors="replace").decode("utf-8")


def esegui_chat(
    client: ClientAgente,
    leggi: Callable[[], str],
    scrivi: Callable[[str], None],
    *,
    chiedi: Callable[[str], bool] = chiedi_conferma,
) -> None:
    """Ciclo della chat. Le righe che iniziano con `/` sono comandi (Step 5): non vanno mai al modello così come sono."""
    sessione = Sessione()  # nessuna persistenza tra esecuzioni
    while True:
        try:
            domanda = ripulisci_input(leggi()).strip()
            if domanda == USCITA:
                return
            if not domanda:
                continue
            if domanda.startswith("/"):
                righe, messaggi = esegui_comando(domanda, client.elenca_prompt, client.ottieni_prompt)
                for riga in righe:
                    scrivi(riga)
                if not messaggi:
                    continue
                sessione, testo = esegui_turno_client(client, sessione, chiedi, messaggi=_coppie(messaggi))
            else:
                sessione, testo = esegui_turno_client(client, sessione, chiedi, messaggio=domanda)
        except (EOFError, KeyboardInterrupt):
            return
        scrivi(testo)


def main(crea_http: Callable[..., httpx.Client] = httpx.Client) -> int:
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # una riga per richiesta coprirebbe la chat
    url = os.environ.get("AGENTE_URL", "").strip() or AGENTE_URL_PREDEFINITO
    with crea_http(base_url=url, timeout=TIMEOUT) as http:
        client = ClientAgente(http)
        try:
            codice, componenti = client.stato()
        except ErroreAgente as errore:
            print(errore, file=sys.stderr)
            return 1
        if codice != 200:
            print(f"Avviso: agente avviato ma non tutto è raggiungibile: {componenti}", file=sys.stderr)
        esegui_chat(client, lambda: input("Tu: "), print)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
