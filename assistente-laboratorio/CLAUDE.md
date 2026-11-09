# Assistente del laboratorio

Progetto del corso «Deep Learning e LLM: costruire chatbot e agenti». La cartella del progetto è `assistente-laboratorio/`; specifica e piano sono in `docs/superpowers/`.

## Struttura e comandi (da `assistente-laboratorio/`, PowerShell)

- `src/assistente/`: `config`, `modello` (LM Studio), `strumenti` (orologio), `grafo` (LangGraph), `terminale`. `tests/`: test automatici senza rete né modello. `prove_reali/`: prove con LM Studio e Docker, a mano.
- Dipendenze: `requirements.txt` (esecuzione) e `requirements-dev.txt` (aggiunge `pytest`), versioni fissate.
- Test: `.\.venv\Scripts\python.exe -m pytest -v`.
- Avvio locale (variabili da `.env`, vedi README): `$env:PYTHONPATH = "src"; .\.venv\Scripts\python.exe -m assistente.terminale`.
- Avvio con Docker: `docker compose run --rm assistente`.

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

- Usare le skill di Superpowers per brainstorming, specifica, piano, implementazione e verifica.  
- Non scrivere codice prima che io abbia approvato la specifica e poi il piano.  
- Salvare specifica e piano in `assistente-laboratorio/docs/superpowers/`.  
- Procedere per incrementi piccoli, ciascuno verificato prima del commit.

## Test e verifiche

- Test automatici ripetibili che non richiedono un modello attivo (grafo, cronologia, instradamento, strumento con istante controllato).  
- Prove reali con LM Studio e con Docker tenute separate e attivate esplicitamente.  
- Una risposta simulata non dimostra che il modello locale sappia usare lo strumento.  
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