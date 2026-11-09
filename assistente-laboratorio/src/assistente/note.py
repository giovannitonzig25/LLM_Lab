"""Archivio delle note su SQLite (usato dal server MCP)."""

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone


def adesso_utc() -> datetime:
    return datetime.now(timezone.utc)


class ErroreNote(Exception):
    """Errore dell'archivio delle note, con messaggio leggibile."""


@dataclass(frozen=True)
class Nota:
    id: int
    testo: str
    creata: str  # YYYY-MM-DD HH:MM:SS, UTC


class ArchivioNote:
    def __init__(
        self, percorso: str, adesso: Callable[[], datetime] = adesso_utc
    ) -> None:
        self._percorso = percorso
        self._adesso = adesso

    def _connetti(self) -> sqlite3.Connection:
        connessione = sqlite3.connect(self._percorso)
        connessione.execute(
            "CREATE TABLE IF NOT EXISTS note ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "testo TEXT NOT NULL, creata TEXT NOT NULL)"
        )
        return connessione

    def aggiungi(self, testo: str) -> Nota:
        creata = self._adesso().astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        connessione = self._connetti()
        try:
            with connessione:
                cursore = connessione.execute(
                    "INSERT INTO note (testo, creata) VALUES (?, ?)", (testo, creata)
                )
            return Nota(cursore.lastrowid, testo, creata)
        finally:
            connessione.close()
