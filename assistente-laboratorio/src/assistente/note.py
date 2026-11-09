"""Archivio delle note su SQLite (usato dal server MCP)."""

import sqlite3
from collections.abc import Callable
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone

MAX_CARATTERI = 500
LIMITE_MIN, LIMITE_MAX = 1, 100


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
        try:
            connessione = sqlite3.connect(self._percorso)
            connessione.create_function("minuscolo", 1, str.casefold, deterministic=True)
            connessione.execute(
                "CREATE TABLE IF NOT EXISTS note ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "testo TEXT NOT NULL, creata TEXT NOT NULL)"
            )
            return connessione
        except sqlite3.Error as errore:
            raise ErroreNote("archivio non accessibile") from errore

    def aggiungi(self, testo: str) -> Nota:
        if not testo.strip():
            raise ErroreNote("il testo della nota è vuoto")
        if len(testo) > MAX_CARATTERI:
            raise ErroreNote(
                f"il testo della nota supera {MAX_CARATTERI} caratteri ({len(testo)})"
            )
        creata = self._adesso().astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        try:
            with closing(self._connetti()) as connessione, connessione:
                cursore = connessione.execute(
                    "INSERT INTO note (testo, creata) VALUES (?, ?)", (testo, creata)
                )
                return Nota(cursore.lastrowid, testo, creata)
        except sqlite3.Error as errore:
            raise ErroreNote("archivio non accessibile") from errore

    def elimina(self, id: int) -> None:
        try:
            with closing(self._connetti()) as connessione, connessione:
                cursore = connessione.execute("DELETE FROM note WHERE id = ?", (id,))
                trovata = cursore.rowcount > 0
        except sqlite3.Error as errore:
            raise ErroreNote("archivio non accessibile") from errore
        if not trovata:
            raise ErroreNote(f"nota {id} non trovata")

    def elenca(self, filtro: str | None = None, limite: int = 20) -> list[Nota]:
        """Note dalla più recente; `filtro` cerca il testo senza distinguere maiuscole."""
        if not LIMITE_MIN <= limite <= LIMITE_MAX:
            raise ErroreNote(f"limite deve essere tra {LIMITE_MIN} e {LIMITE_MAX}")
        condizione, parametri = "", []
        if filtro and filtro.strip():
            condizione = "WHERE instr(minuscolo(testo), minuscolo(?)) > 0 "
            parametri.append(filtro)
        try:
            with closing(self._connetti()) as connessione:
                righe = connessione.execute(
                    f"SELECT id, testo, creata FROM note {condizione}"
                    "ORDER BY id DESC LIMIT ?",
                    (*parametri, limite),
                ).fetchall()
        except sqlite3.Error as errore:
            raise ErroreNote("archivio non accessibile") from errore
        return [Nota(*riga) for riga in righe]
