# Assistente del laboratorio: specifica

Data: 2026-11-01. Stato: **completa, in attesa di approvazione dell'utente**.

## Intento

Un'applicazione da terminale in Python che conversa con un modello locale servito da LM Studio. Il flusso è un grafo LangGraph esplicito. Il modello può chiedere uno strumento orologio, che il programma esegue davvero. Il progetto è la base delle lezioni successive: deve restare piccolo e leggibile.

Il progetto è riuscito quando, da `docker compose run --rm`, si conversa con `google/gemma-4-e2b` in esecuzione sull'host e si osserva nei log che il modello ha richiesto lo strumento e il programma l'ha eseguito.

## Obiettivi

1. Chat da terminale: domanda da `input()`, risposta stampata, uscita con `esci` o Ctrl+C.
2. Grafo LangGraph con stato, nodi e instradamento riconoscibili.
3. Cronologia mantenuta per la sessione, solo in memoria.
4. Strumento orologio richiesto dal modello via tool calling ed eseguito dal programma; il risultato torna al modello, che produce la risposta finale.
5. Chiamate allo strumento visibili nei log; numero di passaggi del grafo limitato.
6. Avvio in Docker con Docker Compose; LM Studio resta sull'host.
7. Test automatici senza modello; prove reali separate e attivate esplicitamente; README aggiornato.

## Non obiettivi e anti-obiettivi

- Niente MCP, RAG, altri strumenti, workflow, interfacce grafiche o web, servizi cloud, persistenza.
- Niente streaming delle risposte (scelta mia: con il tool calling complica il grafo senza dare valore ora).
- Non containerizzare LM Studio.
- Anti-obiettivo: una risposta con un'ora plausibile scritta dal modello senza aver chiamato lo strumento non conta come successo. Una risposta simulata nei test non dimostra che il modello locale usi lo strumento.

## Decisioni dell'utente

- Modello: `google/gemma-4-e2b` in LM Studio; l'identificativo reale si legge da `GET /v1/models`, mai assunto.
- Docker Desktop; collegamento all'host con `host.docker.internal`, da verificare davvero.
- Un solo servizio Compose, avviato con `docker compose run --rm`.
- Grafo a due nodi (modello, strumenti) con arco condizionale; dopo lo strumento si torna al modello.
- Strumento orologio con parametro `timezone` (fuso IANA), predefinito `Europe/Rome`. Valori non validi gestiti con errore chiaro. Il risultato contiene data, ora, nome del fuso e offset.
- Nessun branch o worktree nuovo, nessun push, nessuna modifica alle altre lezioni.
- Approvazione esplicita di specifica e piano prima di scrivere codice.

## Progetto

### Struttura (tutta in `assistente-laboratorio/`)

```
src/assistente/
  config.py       lettura variabili d'ambiente
  modello.py      collegamento a LM Studio (API compatibile OpenAI)
  strumenti.py    strumento orologio e registro degli strumenti
  grafo.py        stato, nodi, instradamento, costruzione del grafo
  terminale.py    ciclo input()/stampa e punto d'ingresso
tests/            test automatici senza modello
prove_reali/      prove con LM Studio e Docker, mai eseguite dai test
docs/superpowers/ specifica e piano
Dockerfile, compose.yaml, .env.example, requirements.txt, README.md, .gitignore
```

I nomi dei file sono una mia proposta; la separazione grafo / modello / strumenti / terminale è richiesta da `CLAUDE.md`.

### Grafo

- **Stato:** lista di messaggi (`messages`, con riduttore che accoda).
- **Nodo `modello`:** invia la cronologia al modello con gli strumenti dichiarati e aggiunge la risposta.
- **Nodo `strumenti`:** per ogni richiesta di strumento nell'ultimo messaggio esegue la funzione, registra il log e aggiunge un messaggio-risultato con lo stesso identificativo di chiamata.
- **Instradamento dopo `modello`:** se l'ultimo messaggio contiene richieste di strumento va a `strumenti`, altrimenti termina. Dopo `strumenti` torna a `modello`.
- **Limite:** `MAX_PASSAGGI` è il `recursion_limit` di LangGraph, cioè il numero di passaggi (super-step) del grafo, non di richieste di strumento (mia scelta). Predefinito 6, come valore iniziale configurabile: non si assume quanti giri di strumento garantisca, il comportamento si misura nei test. Superato il limite l'app stampa un messaggio chiaro e la conversazione prosegue. **Turno interrotto (decisione dell'utente):** l'intero turno viene scartato e la cronologia torna allo stato valido precedente alla domanda. L'app avvisa che la richiesta non è stata completata e che si può riprovare o riformulare. Nessun messaggio parziale né richiesta di strumento senza risultato resta nella cronologia. Realizzazione: il terminale conserva la cronologia validata e la aggiorna solo quando il grafo termina senza errore.
- **Modello iniettabile:** la costruzione del grafo riceve il modello come argomento; `modello.py` espone la funzione che crea quello reale. I test passano un finto modello scritto a mano (mia scelta).
- **Cronologia:** il ciclo del terminale tiene la lista dei messaggi della sessione e la passa al grafo a ogni domanda. Nessun checkpointer su disco.

### Strumento orologio

- Nome e descrizione chiari per il modello; un parametro `timezone` (testo, fuso IANA), predefinito `Europe/Rome`.
- Risultato in forma leggibile e inequivocabile, per esempio `2026-11-01 15:04:05 (Europe/Rome, UTC+01:00)`.
- `timezone` vuoto, nullo o assente: si usa `Europe/Rome` (mia scelta, i modelli piccoli passano spesso valori vuoti).
- Fuso non valido: nessuna eccezione verso il grafo; l'esito è un messaggio d'errore chiaro restituito al modello come risultato dello strumento e loggato come errore.
- L'istante corrente è iniettabile (funzione o orologio passato come argomento) per test deterministici.
- Dipendenza `tzdata` (mia proposta, da concordare): necessaria a `zoneinfo` su Windows e nelle immagini Docker slim.

### Configurazione

- Variabili d'ambiente: `LM_STUDIO_BASE_URL`, `LM_STUDIO_MODEL`, `MAX_PASSAGGI`. Nessun valore predefinito per indirizzo e modello: se mancano, messaggio chiaro e uscita.
- `.env.example` senza credenziali; `.env` reale fuori da Git. Compose legge `.env`; in Docker l'indirizzo è `http://host.docker.internal:1234/v1`, in locale `http://localhost:1234/v1`.
- Nessun controllo all'avvio dell'identificativo del modello: se il server rifiuta il modello o non risponde, l'errore compare alla prima domanda con un messaggio chiaro che rimanda a `GET /v1/models` (mia scelta, per restare semplici). La verifica dell'identificativo è un passo delle prove reali.
- Ambiente virtuale in `assistente-laboratorio/.venv`, con `requirements.txt` e `.gitignore` propri del progetto; la `.venv` e il `requirements.txt` della radice non si toccano (mia scelta).
- Se la porta del server LM Studio è diversa da 1234, è un parametro dell'utente, non una decisione di progetto.

### Log

Modulo `logging` standard su stderr. Una riga per ogni richiesta di strumento (nome, argomenti), una per ogni esito (risultato o errore) e una per il superamento del limite. Livello INFO predefinito; il testo della chat resta su stdout.

### Docker

- Immagine Python sottile; installa `requirements.txt`; esegue come utente non root (mia scelta).
- `compose.yaml` con un solo servizio, `stdin_open` e `tty`, `env_file: .env`. Su Docker Desktop `host.docker.internal` è già risolto; `extra_hosts` si aggiunge solo se la prova reale lo richiede.
- `.dockerignore` che esclude `.env`, `.venv`, cache e `.git`.
- Avvio: `docker compose run --rm assistente`.

### Test e prove

**Automatici (nessun modello, nessuna rete):**
- strumento orologio con istante fisso: Roma, Tokyo, predefinito, fuso non valido, presenza dell'offset;
- instradamento: con e senza richiesta di strumento;
- grafo con modello simulato: percorso diretto, percorso con strumento, risultato restituito al modello, cronologia che cresce tra due domande;
- limite di passaggi superato (modello simulato che chiede lo strumento all'infinito): la cronologia precedente è preservata, nessun messaggio parziale o richiesta di strumento senza risultato resta, il messaggio all'utente è chiaro e una nuova domanda successiva funziona;
- configurazione: variabili mancanti, `MAX_PASSAGGI` non valido;
- log dello strumento (cattura dei log).

**Reali (separate, esplicite, non eseguite dai test automatici):**
1. LM Studio: server attivo, `GET /v1/models`, identificativo del modello usato.
2. Locale con `.venv`: «Mi chiamo Marco» → «Come mi chiamo?»; «Che ora è a Tokyo?» con riga di log dello strumento; server fermo e ripristinato.
3. Docker: `docker compose run --rm assistente`, raggiungibilità di `host.docker.internal`, stesse domande.
4. Se `gemma-4-e2b` non chiama lo strumento in modo affidabile, la prova lo riporta così com'è: non si nasconde con trucchi (per esempio forzare la chiamata).

Il resoconto finale dice cosa è stato eseguito, con quale esito, e cosa resta da provare.

### Dipendenze

Da concordare nel piano, versioni fissate dopo verifica in `.venv` (mia proposta): `langgraph`, `langchain-openai` (con `langchain-core` come dipendenza), `tzdata`, `pytest` per i test. Non si aggiunge altro senza accordo.

## Git e documentazione

Conventional Commits in italiano, un incremento verificato per commit, `git status` e diff prima di ogni commit, staging selettivo. README con configurazione, avvio, test e diagnosi, solo con comandi verificati. `CLAUDE.md` aggiornato solo se cambiano struttura o comandi di test stabili.

## Lasciato a chi costruisce

Nomi interni, testo dei messaggi d'errore, formato esatto dei log, versione di Python e delle librerie, forma dei test simulati.
