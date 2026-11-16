# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti». La cartella del progetto è `assistente-laboratorio/`; specifica e piano sono in `docs/superpowers/`.

## Struttura e comandi (da `assistente-laboratorio/`, PowerShell)

- `src/assistente/`: `config` (incluso `AMBITO_AGENTE`, obbligatoria, e `SOGLIA_RIASSUNTO`), `modello` (LM Studio: agente, classificatore del Router, Revisore e riassuntore), `grafo` (LangGraph: riassunto → router → agente o rifiuto; agente → revisore → fine o correzione), `router` (Router di ambito: contesto, prompt, rifiuto fisso, fail-open), `revisore` (Revisore della risposta: giudizio, osservazione, contesto dell'agente, limite `MAX_REVISIONI`), `riassunto` (Riassunto della cronologia: turni, trascrizione, prompt, nodo con fail-open), `preferenze` (preferenze dell'utente lette dalla resource MCP `utente://preferenze` all'avvio: validazione campo per campo, valori predefiniti, testo in cima al prompt di sistema dell'agente), `agente` (`Sessione` immutabile, turno con strumenti usati e conferme richieste, `ErroreModello` 503/502, costruzione del grafo; conferme degli strumenti distruttivi valide per la sola richiesta), `servizio_agente/` (API FastAPI senza stato, porta 8002: `POST /chat`, `GET /stato`, `GET /prompts`, `POST /prompts/{nome}`, OpenAPI su `/docs`), `terminale` (CLI client dell'API via `httpx`, `AGENTE_URL`: conserva la `Sessione`, chiede le conferme e ripete il turno; le righe che iniziano con `/` sono comandi, mai inviate al modello così come sono), `comandi` (comandi `/prompts` e `/prompt nome argomento=valore`: scomposizione con sole virgolette doppie, controllo degli argomenti rispetto a `prompts/list` prima del modello, conversione dei messaggi del prompt in domanda del turno); strumenti locali `strumenti` (orologio e composizione di tutti gli strumenti all'avvio), `unita` (`converti_unita`), `calcolatrice` (`calcola`); client MCP `mcp_client` (ponte sincrono con discovery e conferma per `destructiveHint`; `elenca_prompt` e `ottieni_prompt` al momento del comando, mai in `bind_tools`) e `verifica_mcp` (controllo di salute); server MCP `server_mcp` (strumenti, resource `utente://preferenze`, prompt `spiega` e `riassumi_conversazione`, file da `PREFERENZE_PATH`, predefinito `data/preferenze.json`), `note` (SQLite), `meteo`; strumenti HTTP `strumenti_http` (wrapper `@tool`) e servizio FastAPI `servizi_http/` (`app`, `scadenze`, `catalogo`, `dati/*.json`).
- `tests/`: test automatici senza rete né modello (server FastMCP reale su porta libera ammesso). `prove_reali/`: prove con LM Studio e Docker, a mano, con gli esiti in `PROVE.md`.
- Dipendenze: `requirements.txt` (esecuzione) e `requirements-dev.txt` (aggiunge `pytest`), versioni fissate.
- Test: `.\.venv\Scripts\python.exe -m pytest -v`.
- Preferenze: `New-Item -ItemType Directory -Force data | Out-Null; Copy-Item preferenze.example.json data\preferenze.json` (file reale mai in Git). In Compose `server-mcp` monta `./data` in sola lettura su `/preferenze`.
- Avvio locale (variabili da `.env`, vedi README), con `$env:PYTHONPATH = "src"` e quattro finestre PowerShell: `.\.venv\Scripts\python.exe -m assistente.server_mcp` (porta 8001), `.\.venv\Scripts\python.exe -m assistente.servizi_http` (porta 8000), `.\.venv\Scripts\python.exe -m assistente.servizio_agente` (porta 8002), `.\.venv\Scripts\python.exe -m assistente.terminale` (CLI; senza agente esce con codice 1). Se i servizi sono spenti l'agente parte lo stesso: senza MCP solo strumenti locali e HTTP (avviso), con il servizio HTTP spento gli strumenti rispondono `Errore:`.
- Avvio con Docker: `docker compose build` (dopo ogni modifica a `src/`), poi `docker compose run --rm assistente`; avvio ridotto se un servizio non parte: `docker compose up -d --no-deps agente`, poi `docker compose run --rm --no-deps assistente`; pulizia `docker compose down -v`.

## Obiettivo

Un'applicazione da terminale in Python che conversa con un modello locale e:

- organizza il flusso in un grafo LangGraph esplicito (stato, nodi, instradamento riconoscibili);  
- usa un modello servito da LM Studio, che resta sul computer host;  
- conserva la cronologia della conversazione per la durata della sessione (nessuna persistenza);  
- offre uno strumento orologio con fuso orario esplicito, richiesto dal modello tramite tool calling ed eseguito davvero dal programma;  
- si avvia anche con Docker Compose.

## Confini

- Implementare solo i requisiti concordati. Sono consentiti servizi HTTP con FastAPI e server/client MCP con FastMCP (solo Streamable HTTP, niente stdio), come da specifica `docs/superpowers/specs/2026-11-03-strumenti-http-mcp-design.md` e piano collegato. Restano esclusi RAG, workflow e ogni altra tecnologia non richiesta dal laboratorio: non anticiparli.  
- Niente interfacce grafiche, servizi cloud o framework non concordati.  
- Lavorare solo dentro `assistente-laboratorio/`. La repository contiene altre lezioni: non leggerle per copiarne il codice e non modificarle.  
- Nessun worktree nuovo se non richiesto. Per i branch vale il flusso descritto in «Git».

## Scelte tecniche

- Python, codice sincrono e moduli piccoli, con una separazione semplice tra grafo, collegamento al modello, strumenti e interfaccia da terminale.  
- LM Studio sull'host, raggiunto tramite la sua API compatibile con OpenAI.  
- Indirizzo del server e identificativo del modello solo da variabili d'ambiente. L'identificativo è quello restituito dal server (`GET /v1/models`), mai inventato.  
- Un file di configurazione di esempio senza credenziali; il file reale resta fuori da Git.  
- Docker Compose con più servizi (`assistente`, `servizi-http`, `server-mcp`); LM Studio resta sull'host e non va containerizzato.  
- Dipendenze motivate, concordate e con versioni fissate; quelle nuove concordate sono `fastmcp`, `fastapi`, `uvicorn`, `httpx`.  
- «Nessuna persistenza» vale per la cronologia della conversazione. SQLite è consentito solo per i dati delle note (mai versionato).  
- Strumenti scoperti tramite MCP: mai riscritti a mano nel client (nome, descrizione e schema vengono dalla discovery). Strumenti HTTP: wrapper `@tool` scritti a mano.  
- Nessuno strumento cancella dati senza una conferma dell'utente raccolta dall'applicazione (terminale), indipendente da ciò che il modello scrive negli argomenti.  
- Comandi documentati anche per PowerShell (Windows).

## Metodo: Superpowers

Workflow rapido (dal 2026-11-17), solo quattro fasi:

- **Brainstorming:** requisiti della slide e solo le decisioni davvero necessarie; niente microdecisioni o lunghe discussioni su casi limite; sempre la soluzione più semplice compatibile con il progetto.  
- **Specifica:** sintetica, con le decisioni approvate, da sottopormi; niente review indipendenti o esperimenti esplorativi.  
- **Piano:** pochi task concreti e ordinati, nessun task dedicato solo a test, benchmark, spike o review; attendere la mia approvazione.  
- **Implementazione:** solo i task approvati, senza funzionalità non richieste. Un errore concreto si corregge senza nuovo brainstorming.  
- Non scrivere codice prima che io abbia approvato la specifica e poi il piano. Salvare specifica e piano in `assistente-laboratorio/docs/superpowers/`.  
- Esclusi: spike sul modello locale, prove ripetute con il modello per ogni scenario, review indipendenti obbligatorie, fasi separate di test e validazione, benchmark, lunghi cicli di correzione dei prompt, documentazione dettagliata dei casi limite.

## Test e verifiche

- TDD non obbligatorio e nessuna nuova suite per ogni modifica; la suite esistente (senza modello attivo) resta e non va rotta.  
- Verifica limitata a un controllo funzionale essenziale: il codice parte e la funzione principale è utilizzabile; niente batterie di test ripetute né lunghe prove con il modello locale.  
- Nel resoconto indicare che cosa è stato eseguito, con quale esito, e che cosa resta da provare.

## Git

- Conventional Commits in italiano, per esempio `feat(grafo): ...`, `test(strumenti): ...`, `docs: ...`.  
- Prima di ogni commit: `git status`, controllo del diff, staging selettivo dei soli file pertinenti.  
- Mai versionare credenziali, `.env`, ambienti virtuali, cache o pesi dei modelli.  
- Flusso dei rami: `dev` → `feat/<nome>` → review indipendente → mia approvazione esplicita → `git merge --no-ff` su `dev` → suite verde → eliminazione del ramo. Nessun merge su `main` senza mia autorizzazione.  
- Push soltanto su mia richiesta.

## Documentazione

- Tenere aggiornato il README con configurazione, avvio, test e diagnosi, riportando solo comandi verificati.  
- Aggiornare questo file quando cambiano convenzioni stabili (struttura, comandi di test, regole di lavoro), non per annotare l'avanzamento.