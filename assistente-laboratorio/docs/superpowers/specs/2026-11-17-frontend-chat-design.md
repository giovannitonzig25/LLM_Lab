# Step 8 — Front-end: interfaccia di chat (specifica)

Data: 2026-11-17. Stato: da approvare.

## Slide (LLM_Lez_6.pdf, p. 15)

> La tecnologia è libera. L'obiettivo è un'interfaccia di chat utilizzabile da chi non conosce il progetto, che comunica solo con il back-end.
>
> Indicazione per Claude Code: fornire il documento OpenAPI del back-end come contratto: Claude genera le chiamate da quella descrizione, senza indovinare gli endpoint.

Cosa realizzare:
1. Elenco delle chat, creazione di una nuova chat ed eliminazione.
2. Vista dei messaggi della chat e invio di una nuova domanda.
3. Stato di attesa durante la risposta ed errori mostrati in modo comprensibile.
4. Indirizzo del back-end da configurazione, non scritto nel codice.

Evidenze richieste:
- Conversazione completa dal browser, con uso di uno strumento.
- Una chat creata dall'interfaccia è ancora presente dopo il riavvio.
- Con l'agente spento l'interfaccia mostra l'errore senza bloccarsi.

## Obiettivo e confini

Una pagina web di chat, semplice e moderna, per chi non conosce il progetto. Parla **solo** con il back-end dello Step 7; non conosce agente, LM Studio né server MCP.

Fuori ambito: prompt MCP (`/prompts`, `/prompt`) nel front-end, modifica del titolo, autenticazione, streaming, back-end e front-end in Docker Compose (Step 9). Il back-end non si modifica.

## Decisioni approvate

1. **Tecnologia:** una pagina HTML + CSS + JavaScript semplice (`fetch`), senza framework JS, Node o compilazione, servita da un piccolo servizio FastAPI (`StaticFiles`). Nessuna dipendenza nuova.
   Scartati: React/Vue con Vite (Node e build), Jinja2 (dipendenza nuova, ricarica della pagina), Streamlit/Gradio (pesanti, modello di esecuzione proprio).
2. **Raggiungere il back-end: inoltro dal servizio del front-end.** La pagina chiama solo la propria origine (`/api/...`); il servizio inoltra metodo, percorso e corpo a `BACKEND_URL` e restituisce codice, corpo e `content-type` del back-end senza modificarli. Nessun CORS, back-end intatto.
   Scartato: CORS sul back-end (modifica del back-end, due variabili da tenere allineate, back-end esposto al browser).
3. **Regola di `CLAUDE.md`** (sezione «Confini»): la riga «Niente interfacce grafiche, servizi cloud o framework non concordati.» diventa:
   > Niente servizi cloud o framework non concordati. Unica interfaccia grafica ammessa: il front-end web dello Step 8, una pagina HTML, CSS e JavaScript semplice servita da FastAPI, senza framework JS, Node o compilazione, che comunica solo con il back-end delle chat.

   A fine lavoro, con approvazione, «Struttura e comandi» riceve la riga di `servizio_frontend/` e il comando di avvio.

## Contratto: OpenAPI del back-end

Le chiamate si scrivono dal documento OpenAPI reale (`crea_app(...).openapi()`, lo stesso servito su `http://127.0.0.1:8003/docs`), esportato in `docs/superpowers/specs/2026-11-17-openapi-backend.json` e mai modificato a mano. Percorsi usati dalla pagina, con prefisso `/api`:

| Operazione | Back-end | Successo | Errori |
|---|---|---|---|
| Elenco | `GET /chat` | 200 `[ChatInElenco]` | 503 |
| Nuova chat | `POST /chat` | 201 `ChatCreata` | 503 |
| Lettura | `GET /chat/{id}` | 200 `Chat` | 404, 503, 422 |
| Invio | `POST /chat/{id}/messaggi` `NuovoMessaggio` | 200 `RispostaMessaggio` | 404, 502, 503, 422 |
| Eliminazione | `DELETE /chat/{id}` | 204 | 404, 503, 422 |

Errori del back-end `{"errore": ...}`; il 422 di FastAPI ha invece `{"detail": ...}` (la pagina mostra un testo generico).

## Servizio `servizio_frontend`

- `src/assistente/servizio_frontend/`: `app.py` (`crea_app(backend: httpx.Client)`), `__main__.py`, `static/` (`index.html`, `app.js`, `stile.css`).
- `GET /` → `index.html`; `/static/...` → file statici.
- `/api/{percorso}` (GET, POST, DELETE) → inoltro a `BACKEND_URL/{percorso}`, con corpo e query invariati.
- Back-end non raggiungibile (errore di trasporto) → `503 {"errore": "Back-end non raggiungibile su <BACKEND_URL>"}`.
- Timeout come il back-end verso l'agente: connessione 10 s, lettura senza limite (un turno dura 1–3 minuti). La pagina non imposta timeout.
- Configurazione in `.env.example`: `BACKEND_URL` (predefinito `http://127.0.0.1:8003`), `FRONTEND_HOST` (`127.0.0.1`), `FRONTEND_PORT` (`8004`). Avvio: `python -m assistente.servizio_frontend`.

## Interfaccia

```
┌──────────────────┬──────────────────────────────────────────┐
│ + Nuova chat     │ Titolo della chat                        │
│──────────────────│──────────────────────────────────────────│
│ ▸ Ora a Tokyo  🗑 │            [Utente] Che ore sono a Tokyo?│
│   Note        🗑  │ [Assistente] A Tokyo sono le 21:04.      │
│   ...            │   strumenti: orologio                    │
│                  │ ⏳ L'assistente sta rispondendo…           │
│                  │ ⚠ Agente non raggiungibile su …   [×]    │
│                  │──────────────────────────────────────────│
│                  │ [ Scrivi una domanda…          ] [Invia] │
└──────────────────┴──────────────────────────────────────────┘
```

- **Elenco a sinistra** (dalla più recente), «Nuova chat», eliminazione con conferma del browser; selezione → vista dei messaggi.
- **Invio:** la domanda compare subito; durante l'attesa campo e pulsante disattivati e indicatore «L'assistente sta rispondendo…». A risposta arrivata si rilegge la chat e l'elenco (titolo e ordine aggiornati). Sotto la risposta, gli `strumenti_usati` in piccolo.
- **Conferma di `elimina_nota`:** se `conferme_richieste` non è vuota, una finestra mostra strumento e argomenti; «Conferma» ripete **la stessa domanda** con `conferme` = `conferme_richieste`; «Annulla» non invia nulla (il back-end non ha salvato nulla). La conferma la dà solo l'utente.
- **Errori:** riquadro rosso con il testo di `errore` (o un testo generico con il codice HTTP); l'interfaccia resta usabile e la domanda non inviata torna nel campo.
- Nessun indirizzo nel codice della pagina: solo percorsi relativi `/api/...`.

## Verifica

- Suite esistente verde; pochi test senza rete (`httpx.MockTransport`): pagina servita, inoltro di codice e corpo (anche 204 e 404), back-end non raggiungibile → 503 `{"errore": ...}`.
- Prove a mano nel browser, una volta, esiti in `prove_reali/PROVE.md`:
  - F1 conversazione completa con uso di uno strumento;
  - F2 chat creata dall'interfaccia presente dopo il riavvio di front-end e back-end (e del container `postgres` senza `-v`);
  - F3 agente spento: errore mostrato, interfaccia ancora utilizzabile;
  - F4 ciclo di conferma di `elimina_nota` dal browser.

## Lasciato a chi implementa

Aspetto grafico (colori, spaziature), testi dei messaggi, struttura interna di `app.js`.
