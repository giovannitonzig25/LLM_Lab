# Handoff — Strumenti locali, HTTP e MCP (assistente-laboratorio)

Data: 2026-11-09. Scopo: riprendere in una nuova sessione di Claude Code senza rileggere la conversazione. Non duplica specifica e piano: li richiama.

## 1. Documenti approvati (definitivi)

| Documento | Percorso (da `assistente-laboratorio/`) |
|---|---|
| Specifica (approvata ed emendata il 2026-11-09) | `docs/superpowers/specs/2026-11-03-strumenti-http-mcp-design.md` |
| Piano (approvato il 2026-11-09), 16 task T0–T15 | `docs/superpowers/plans/2026-11-09-strumenti-http-mcp.md` |

Leggere il piano per intero prima di agire: contiene header, vincoli globali, focus della review, «Divergenze dalla specifica» e la «Procedura di ramo» P1–P6. Specifica e piano sono allineati (non ci sono punti aperti).

## 2. Decisioni finali da non rimettere in discussione

- **6 funzionalità, 11 strumenti:** locali (`converti_unita`, `calcola`), FastAPI (`giorni_lavorativi`, `calcola_scadenza`, `cerca_catalogo`, `dettaglio_catalogo`), FastMCP (`aggiungi_nota`, `elenca_note`, `elimina_nota`, `meteo`) più `orologio` esistente. Priorità alla prima integrazione MCP (ramo `feat/mcp-note`).
- **MCP:** solo Streamable HTTP; ponte sincrono sopra il client FastMCP con discovery reale; grafo e terminale non si riscrivono.
- **Conferma di `elimina_nota`:** non un parametro del modello. Il server espone `elimina_nota(id)` con `destructiveHint=True`; il ponte legge l'annotazione dalla discovery e chiede `[s/N]` nel terminale tramite una funzione `chiedi_conferma` prima di chiamare il server. Conferma chiesta anche prima di sapere se l'ID esiste. **Limite accettato e da documentare nel README:** il server da solo non protegge dalle chiamate di altri client MCP.
- **Avvio ridotto:** garantito dal programma Python quando MCP non è raggiungibile (avviso, solo strumenti locali), con attesa limitata all'avvio `MCP_ATTESA_AVVIO` (0 in locale, 20 in Compose). Compose: `depends_on: condition: service_started` (mai `service_healthy`; `required: false` non serve). Se il server MCP non riesce nemmeno a partire (per esempio porta occupata) `docker compose run --rm assistente` fallisce: procedura alternativa `docker compose run --rm --no-deps assistente`. La distinzione va spiegata nel README e verificata nelle prove reali.
- **Controlli di salute:** `server-mcp` con vera discovery MCP (`python -m assistente.verifica_mcp`), `servizi-http` con richiesta a `/salute`. La verifica finale in Docker richiede una vera discovery, non solo la porta aperta.
- **Dipendenze fissate (verificate con `pip install --dry-run`, Python 3.13):** `fastmcp==4.1.6`, `fastapi==0.162.2`, `uvicorn==0.54.0`, `httpx==0.28.1`.
- **Esecuzione:** nativa (`superpowers:executing-plans`), con review indipendente alla fine di ogni ramo (P4) e **approvazione dell'utente prima di ogni merge** (P5). Merge `--no-ff` su `dev`, nessun push, nessun merge su `main`.

## 3. Stato Git effettivo (verificato il 2026-11-09)

- Branch corrente `dev`, allineato a `origin/dev` (0 avanti, 0 indietro); esiste `main`; nessun altro branch. Ultimo commit `78e07a2`.
- **Nessun commit, branch, modifica a `CLAUDE.md` o codice è stato fatto in questa fase.**
- File **non tracciati** (tutti `??`):
  - `assistente-laboratorio/docs/superpowers/specs/2026-11-03-strumenti-http-mcp-design.md`
  - `assistente-laboratorio/docs/superpowers/plans/2026-11-09-strumenti-http-mcp.md`
  - `assistente-laboratorio/docs/superpowers/2026-11-09-handoff-strumenti-http-mcp.md` (questo file)
  - `LLM_Lez_5.pdf` (radice del repository, slide del corso; **non** metterlo in staging con T0 senza chiedere all'utente se versionarlo).
- Test esistenti: 48, devono restare verdi (`.\.venv\Scripts\python.exe -m pytest -v` da `assistente-laboratorio/`).
- Docker 29.2.0, Compose v5.0.2 installati. Nessun container o volume di prova rimasto.

## 4. Prossimo passo: T0 (solo documentazione, direttamente su `dev`)

T0 non è ancora stato eseguito né autorizzato in questa sessione. Nella nuova sessione, dopo che l'utente dà il via:
1. Leggere piano e specifica; `git status` e confermare lo stato del §3.
2. Applicare a `CLAUDE.md` i punti 1–4 e 6 della specifica §9 (il punto 5, struttura e comandi, si applica in T15). Tenere conto delle decisioni emendate (conferma nel terminale, `service_started`).
3. `git status`, controllo del diff, staging selettivo di: `CLAUDE.md`, specifica, piano, handoff (non il PDF). Commit `docs: aggiorna CLAUDE.md per strumenti HTTP e MCP` con la riga `Co-Authored-By` prevista.
4. Mostrare l'esito all'utente e **fermarsi**: T1 comincia con la Procedura di ramo (P1: `git switch -c feat/mcp-note` da `dev` pulito) solo su richiesta.

## 5. Avvertenze per chi riprende

- L'API di FastMCP 4.x non è nota: T1 passo 2 la verifica con la documentazione installata (creazione server, avvio HTTP `/mcp`, client, annotazioni `destructiveHint`).
- Il PDF `LLM_Lez_5.pdf` è stato letto dalla slide 25 alla 31 (le integrazioni di spec §10quater vengono da lì); le slide 1–24 non sono state esaminate.
- Convenzioni: PowerShell da `assistente-laboratorio/`, Conventional Commits in italiano, staging selettivo, `git status` e diff prima di ogni commit, prove reali distinte dai test simulati, esiti in `prove_reali/PROVE.md`.
