"""Archivio delle chat del back-end (Step 7): solo accesso a PostgreSQL, SQL scritto a mano.

`cronologia` e `riassunto` sono lo stato dell'agente: si salvano e si rileggono così come sono.
"""
from contextlib import contextmanager
from typing import Any, Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

TITOLO_INIZIALE = "Nuova chat"
LUNGHEZZA_TITOLO = 50

SCHEMA = """
CREATE TABLE IF NOT EXISTS chat (
    id SERIAL PRIMARY KEY,
    titolo TEXT NOT NULL,
    creata_il TIMESTAMPTZ NOT NULL DEFAULT now(),
    aggiornata_il TIMESTAMPTZ NOT NULL DEFAULT now(),
    riassunto TEXT NOT NULL DEFAULT '',
    cronologia JSONB NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS messaggi (
    id SERIAL PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chat(id) ON DELETE CASCADE,
    ruolo TEXT NOT NULL CHECK (ruolo IN ('utente', 'assistente')),
    testo TEXT NOT NULL,
    creato_il TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messaggi_chat_id ON messaggi (chat_id);
"""


class ChatNonTrovata(Exception):
    """La chat richiesta non esiste."""


class ErroreDatabase(Exception):
    """PostgreSQL non raggiungibile o non utilizzabile."""


class ArchivioPostgres:
    def __init__(self, database_url: str):
        self.database_url = database_url

    @contextmanager
    def _connessione(self) -> Iterator[psycopg.Connection]:
        """Una connessione per operazione; esce con commit, o rollback se c'è un'eccezione."""
        try:
            with psycopg.connect(self.database_url, row_factory=dict_row, connect_timeout=5) as conn:
                yield conn
        except psycopg.OperationalError as errore:
            raise ErroreDatabase(str(errore)) from errore

    @staticmethod
    def _verifica(conn: psycopg.Connection, id: int) -> None:
        if conn.execute("SELECT 1 FROM chat WHERE id = %s", (id,)).fetchone() is None:
            raise ChatNonTrovata(id)

    def prepara(self) -> None:
        with self._connessione() as conn:
            conn.execute(SCHEMA)

    def crea_chat(self) -> dict[str, Any]:
        with self._connessione() as conn:
            return conn.execute(
                "INSERT INTO chat (titolo) VALUES (%s) RETURNING id, titolo, creata_il", (TITOLO_INIZIALE,)
            ).fetchone()

    def elenca_chat(self) -> list[dict[str, Any]]:
        with self._connessione() as conn:
            return conn.execute(
                """SELECT c.id, c.titolo, max(m.creato_il) AS ultimo_messaggio_il
                   FROM chat c LEFT JOIN messaggi m ON m.chat_id = c.id
                   GROUP BY c.id ORDER BY c.aggiornata_il DESC, c.id DESC"""
            ).fetchall()

    def leggi_chat(self, id: int) -> dict[str, Any]:
        with self._connessione() as conn:
            chat = conn.execute("SELECT id, titolo FROM chat WHERE id = %s", (id,)).fetchone()
            if chat is None:
                raise ChatNonTrovata(id)
            chat["messaggi"] = conn.execute(
                "SELECT ruolo, testo, creato_il FROM messaggi WHERE chat_id = %s ORDER BY creato_il, id", (id,)
            ).fetchall()
            return chat

    def stato_agente(self, id: int) -> tuple[list[dict[str, Any]], str]:
        with self._connessione() as conn:
            riga = conn.execute("SELECT cronologia, riassunto FROM chat WHERE id = %s", (id,)).fetchone()
            if riga is None:
                raise ChatNonTrovata(id)
            return riga["cronologia"], riga["riassunto"]

    def aggiungi_scambio(
        self, id: int, domanda: str, risposta: str, cronologia: list[dict[str, Any]], riassunto: str
    ) -> None:
        """Domanda, risposta e stato dell'agente in un'unica transazione."""
        with self._connessione() as conn:
            self._verifica(conn, id)
            prima = conn.execute("SELECT 1 FROM messaggi WHERE chat_id = %s LIMIT 1", (id,)).fetchone() is None
            conn.execute(
                "INSERT INTO messaggi (chat_id, ruolo, testo) VALUES (%s, 'utente', %s), (%s, 'assistente', %s)",
                (id, domanda, id, risposta),
            )
            conn.execute(
                """UPDATE chat SET cronologia = %s, riassunto = %s, aggiornata_il = now(),
                   titolo = CASE WHEN %s THEN %s ELSE titolo END WHERE id = %s""",
                (Jsonb(cronologia), riassunto, prima, domanda.strip()[:LUNGHEZZA_TITOLO], id),
            )

    def elimina_chat(self, id: int) -> None:
        with self._connessione() as conn:
            if conn.execute("DELETE FROM chat WHERE id = %s", (id,)).rowcount == 0:
                raise ChatNonTrovata(id)
