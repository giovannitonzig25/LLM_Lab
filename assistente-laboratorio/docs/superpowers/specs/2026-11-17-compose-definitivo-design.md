# Step 9 — Docker Compose: un container per componente (specifica)

Data: 2026-11-17. Stato: da approvare.

## Slide (LLM_Lez_6.pdf, p. 16)

> Front-end, back-end, agente e database hanno ciascuno il proprio container. LM Studio resta sull'host, come nella lezione 4.
>
> Obiettivo: un solo comando avvia l'intera applicazione, pronta all'uso dal browser.

Cosa realizzare:
1. Quattro servizi in `compose.yaml`: tre con il proprio Dockerfile e PostgreSQL con l'immagine ufficiale.
2. Rete: il browser raggiunge il front-end; le chiamate API arrivano al back-end, tramite porta pubblicata o proxy; l'agente non è esposto.
3. Volume per i dati di PostgreSQL; credenziali in `.env` escluso da Git; back-end avviato a database pronto.
4. L'agente raggiunge LM Studio con `host.docker.internal`; i server MCP stdio partono nel suo container.

Evidenze richieste:
- `docker compose up` avvia i quattro servizi; `docker compose ps` li mostra attivi.
- Chat dal browser con uno strumento, visibile nei log dell'agente.
- Dopo `docker compose down` e `docker compose up`, le chat sono ancora presenti.

## Obiettivo e confini

`docker compose up -d` avvia l'applicazione completa; il browser apre `http://127.0.0.1:8004`. Architettura:

```
browser ──▶ frontend (8004, pubblicata) ──/api──▶ backend ──▶ agente ──▶ LM Studio (host.docker.internal:1234)
                                                     │           ├──▶ server-mcp   (interno)
                                                     └──▶ postgres └──▶ servizi-http (interno)
```

Si parte dall'attuale `compose.yaml` con il cambiamento minimo. **Nessuna modifica a `src/`**, nessuna dipendenza o immagine nuova (`python:3.13-slim` e `postgres:17.6` già in uso). Restano invariati: contratti di front-end, back-end e agente; Router, Revisore e Riassunto con il fail-open; `Sessione` immutabile; conferma di `elimina_nota` data dall'utente (front-end e CLI); CLI con `/prompts` e `/prompt`; avvio ridotto; avvio locale senza Docker.

## Decisioni approvate

1. **Quattro componenti principali più due servizi interni per gli strumenti.** Si aggiungono `backend` e `frontend`; `agente` e `postgres` restano. `server-mcp` e `servizi-http` restano container separati, raggiungibili solo dalla rete interna di Compose (nessuna porta sull'host).
   **Scostamento dichiarato dalla slide (punto 4, «server MCP stdio nel container dell'agente»):** il progetto usa FastMCP solo Streamable HTTP per scelta approvata (`CLAUDE.md`, specifica `2026-11-03-strumenti-http-mcp-design.md`). Lo scopo del requisito, strumenti accessibili solo all'agente e mai esposti, è rispettato dalla rete interna. `docker compose ps` mostra quindi sei servizi: i quattro della slide più i due degli strumenti.
   Scartati: passaggio a stdio con server lanciato dall'agente (cambia codice collaudato, viola `CLAUDE.md`); più processi in un solo container (fragile, nessun vantaggio).
2. **Tre Dockerfile, uno per componente.** Il `Dockerfile` attuale resta invariato ed è quello dell'agente (usato anche da `server-mcp`, `servizi-http` e `assistente`). Nuovi `Dockerfile.backend` e `Dockerfile.frontend`: stessa base `python:3.13-slim`, stesso `requirements.txt`, solo `COPY src`, utente non root, `CMD` del proprio modulo.
   Scartato: un solo Dockerfile per tutti (contraddice il punto 1 della slide).
3. **CLI su richiesta.** Il servizio `assistente` riceve `profiles: ["cli"]`: `docker compose up` non lo avvia; `docker compose run --rm assistente` funziona come prima.
   *Correzione in implementazione (errore concreto):* con il profilo, `docker compose build` non ricostruiva l'immagine di `assistente`, rimasta anteriore allo Step 6. `assistente` usa quindi l'immagine dell'agente (`image: assistente-laboratorio-agente`, `pull_policy: never`; stesso Dockerfile), costruita da `docker compose build`.
4. **Porte e indirizzi interni.**

   | Servizio | Porta sull'host | Variabili in `compose.yaml` |
   |---|---|---|
   | `frontend` | `127.0.0.1:8004` | `BACKEND_URL=http://backend:8003`, `FRONTEND_HOST=0.0.0.0` |
   | `backend` | nessuna | `AGENTE_URL=http://agente:8002`, `BACKEND_HOST=0.0.0.0`, `DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}` |
   | `agente` | nessuna (era `8002`) | invariate (`host.docker.internal` per LM Studio) |
   | `server-mcp`, `servizi-http` | nessuna (erano `8001`, `8000`) | invariate |
   | `postgres` | `127.0.0.1:5433` invariata | invariate; serve anche all'avvio locale del back-end |

   `DATABASE_URL` è composta in Compose dalle variabili `POSTGRES_*` di `.env`: nessuna credenziale scritta nel file Compose, nessuna variabile nuova. Il `DATABASE_URL` di `.env` (con `127.0.0.1:5433`) resta per l'avvio locale.

## Decisioni proposte (da correggere nella revisione)

- **Ordine di avvio:** `backend` dipende da `postgres` con `service_healthy` (database pronto, come chiede la slide) e da `agente` con `service_started`; `frontend` dipende da `backend` con `service_started`. Le dipendenze dell'agente restano `service_started` (avvio ridotto).
- **`env_file`:** `backend` usa `env_file: .env` (servono `POSTGRES_*` per l'interpolazione e restano le variabili facoltative); i valori Docker in `environment` prevalgono su quelli locali di `.env`. `frontend` non ha bisogno di `.env`.
- **Nessun timeout nuovo:** back-end e front-end hanno già `read=None` verso agente e back-end; nessun healthcheck per `backend` e `frontend` (non richiesti dalla slide).
- **Documentazione:** README (sezione «Avvio con Docker Compose»: comando unico, porte, CLI con profilo, `down` senza `-v`); `.env.example` solo se serve un commento; a fine lavoro, con autorizzazione, i comandi Docker di `CLAUDE.md`.

## Verifica

- Suite esistente verde (`pytest`, senza Docker) e `docker compose config`.
- Evidenze della slide, una volta, con esiti in `prove_reali/PROVE.md`:
  - **C1:** `docker compose build`, `docker compose up -d`, `docker compose ps` con i servizi attivi; agente non raggiungibile da `127.0.0.1:8002`.
  - **C2:** dal browser `http://127.0.0.1:8004`, una chat con uno strumento (per esempio l'orologio), verificata in `docker compose logs agente`.
  - **C3:** `docker compose down` (senza `-v`) e `docker compose up -d`; la chat di C2 e quelle di prova già nel volume `dati-postgres` sono ancora presenti.
- Controllo essenziale: `docker compose run --rm assistente` parte e risponde.

Resta fuori: il ciclo di conferma di `elimina_nota` dal browser in Compose si prova solo se il tempo lo consente (il codice non cambia).
