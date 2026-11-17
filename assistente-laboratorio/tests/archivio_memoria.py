"""Aiuto dei test (Step 7): stesso comportamento di `ArchivioPostgres`, senza database."""
import copy
from datetime import datetime, timedelta, timezone

from assistente.archivio import LUNGHEZZA_TITOLO, TITOLO_INIZIALE, ChatNonTrovata


class ArchivioMemoria:
    def __init__(self):
        self.chat: dict[int, dict] = {}
        self._prossimo = 1
        self._orologio = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)

    def _adesso(self) -> datetime:
        self._orologio += timedelta(seconds=1)  # istanti distinti: l'ordinamento è deterministico
        return self._orologio

    def _chat(self, id: int) -> dict:
        if id not in self.chat:
            raise ChatNonTrovata(id)
        return self.chat[id]

    def prepara(self) -> None:
        pass

    def crea_chat(self) -> dict:
        id, adesso = self._prossimo, self._adesso()
        self._prossimo += 1
        self.chat[id] = {"id": id, "titolo": TITOLO_INIZIALE, "creata_il": adesso, "aggiornata_il": adesso,
                         "riassunto": "", "cronologia": [], "messaggi": []}
        return {"id": id, "titolo": TITOLO_INIZIALE, "creata_il": adesso}

    def elenca_chat(self) -> list[dict]:
        ordinate = sorted(self.chat.values(), key=lambda c: (c["aggiornata_il"], c["id"]), reverse=True)
        return [{"id": c["id"], "titolo": c["titolo"],
                 "ultimo_messaggio_il": max((m["creato_il"] for m in c["messaggi"]), default=None)} for c in ordinate]

    def leggi_chat(self, id: int) -> dict:
        c = self._chat(id)
        return {"id": id, "titolo": c["titolo"], "messaggi": copy.deepcopy(c["messaggi"])}

    def stato_agente(self, id: int) -> tuple[list[dict], str]:
        c = self._chat(id)
        return copy.deepcopy(c["cronologia"]), c["riassunto"]

    def aggiungi_scambio(self, id: int, domanda: str, risposta: str, cronologia: list[dict], riassunto: str) -> None:
        c, adesso = self._chat(id), self._adesso()
        if not c["messaggi"]:
            c["titolo"] = domanda.strip()[:LUNGHEZZA_TITOLO]
        c["messaggi"] += [{"ruolo": "utente", "testo": domanda, "creato_il": adesso},
                          {"ruolo": "assistente", "testo": risposta, "creato_il": adesso}]
        c["cronologia"], c["riassunto"], c["aggiornata_il"] = copy.deepcopy(cronologia), riassunto, adesso

    def elimina_chat(self, id: int) -> None:
        self._chat(id)
        del self.chat[id]
