# Lezione 5 — Strumenti locali, HTTP (FastAPI) e MCP (FastMCP): specifica

Stato: **approvata dall'utente il 2026-11-09**, poi **emendata il 2026-11-09** su richiesta dell'utente (conferma di `elimina_nota` nel terminale, avvio ridotto in Compose: sezioni 5.3, 5.6, 5.7, 8, 10, 10ter, 10bis). Non committata. Nessun codice è stato scritto. Il piano è `docs/superpowers/plans/2026-11-09-strumenti-http-mcp.md`.
Le decisioni marcate **[Utente]** sono state prese dall'utente nel brainstorming; quelle marcate **[Scelta mia]** sono scelte dell'assistente, da correggere in lettura.

## 1. Intenzione

Estendere l'agente LangGraph esistente (LM Studio, modello locale `google/gemma-4-e2b`, strumento `orologio`) con sei funzionalità, per esercitarsi sulle tre tecniche di integrazione degli strumenti studiate nella Lezione 5:

1. funzioni Python locali, eseguite nel processo dell'agente;
2. servizi HTTP (FastAPI) richiamati da wrapper scritti a mano;
3. server MCP (FastMCP) collegati con un client MCP, con discovery e invocazione reali.

Il professore richiede almeno un'integrazione MCP funzionante; l'utente vuole realizzarle tutte e sei, dando priorità alla prima integrazione MCP, completa e verificata. Obiettivo: un progetto didattico solido e facile da spiegare, non il massimo di codice.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Obiettivi**
- Sei funzionalità, undici strumenti (con `orologio`), scelti dal modello in base alla domanda.
- Discovery MCP reale (nome, descrizione, schema ricevuti dal server).
- Ogni richiesta di strumento produce un `ToolMessage` con il `tool_call_id` corretto.
- Errori di strumento e di rete resi in testo chiaro al modello.
- Test automatici senza rete né modello; prove reali con LM Studio, Docker, FastAPI e MCP, documentate distinguendo simulato e provato.

**Non obiettivi**
- RAG, altri protocolli, interfacce grafiche, servizi cloud, framework non concordati.
- Persistenza della cronologia della conversazione (resta solo in memoria).
- Modalità stdio per MCP.
- Riscrittura asincrona dell'agente o del grafo.
- Autenticazione, pubblicazione di porte sulla rete locale, push o merge su `main`.

**Anti-obiettivi (sarebbe un fallimento anche se «funziona»)**
- Il grafo, il terminale o i test esistenti riscritti senza necessità.
- Un catalogo MCP copiato a mano nel client invece di una vera discovery.
- Uno strumento che esegue una cancellazione senza la conferma esplicita.
- Una risposta simulata presentata come prova del modello reale.
- Dati reali o personali nel catalogo di esempio.

## 3. Stato di partenza (verificato)

- Branch `dev` pulito e allineato a `origin/dev`; esiste `main`. 48 test passano (Python 3.13).
- `grafo.py`: `Stato` con `messages`; nodi `modello` e `strumenti`; `instrada` (strumenti se ci sono `tool_calls`, altrimenti fine); `costruisci_grafo(modello, strumenti: Sequence[BaseTool])`; ogni richiesta diventa `ToolMessage(tool_call_id=...)`; errori e strumenti sconosciuti diventano testo `Errore: ...`.
- `modello.py`: `ChatOpenAI` verso LM Studio con `bind_tools`. `config.py`: `LM_STUDIO_BASE_URL`, `LM_STUDIO_MODEL`, `MAX_PASSAGGI` (predefinito 6).
- `terminale.py`: ciclo sincrono, gestione di `GraphRecursionError`, `openai.OpenAIError`, Ctrl+C/Ctrl+D.
- Docker: un solo servizio `assistente`, immagine `python:3.13-slim`, LM Studio raggiunto con `host.docker.internal`.
- Dipendenze fissate: `langgraph`, `langchain-openai`, `tzdata`; `pytest` in `requirements-dev.txt`.
- Conseguenza: `costruisci_grafo` accetta già una lista di `BaseTool`; il grafo non va modificato per aggiungere strumenti.

## 4. Distribuzione delle funzionalità

**Scelta [Utente]: 2 locali, 2 FastAPI, 2 MCP.**

| Tecnica | Funzionalità | Strumenti esposti al modello |
|---|---|---|
| Già presente | Orologio | `orologio` |
| Python locale | Convertitore di unità | `converti_unita` |
| Python locale | Calcolatrice sicura | `calcola` |
| FastAPI | Giorni e scadenze | `giorni_lavorativi`, `calcola_scadenza` |
| FastAPI | Catalogo locale | `cerca_catalogo`, `dettaglio_catalogo` |
| FastMCP | Note persistenti (SQLite) | `aggiungi_nota`, `elenca_note`, `elimina_nota` |
| FastMCP | Meteo da API pubblica | `meteo` |

Totale: 6 funzionalità, 11 strumenti con l'orologio.

Criterio didattico: locale = funzioni pure e senza stato; HTTP = servizio con dati e ciclo di vita propri; MCP = capacità con stato o effetti esterni (database, rete).

**Alternative valutate e scartate**
- *Spostare «giorni e scadenze» tra le funzioni locali* (è calcolo puro, starebbe bene anche in locale) e dare a FastAPI un'altra funzionalità. **Scartata dall'utente**: l'obiettivo è esercitarsi con tutte e tre le tecniche; il servizio sarà un vero servizio HTTP riutilizzabile (date ISO, festività da file, validazione, casi limite).
- *Legare «giorni e scadenze» al catalogo* (per esempio scadenze di consegna dei materiali) per dare al servizio dati propri. **Scartata dall'utente**: le due funzionalità restano indipendenti, pur potendo condividere lo stesso server FastAPI.

## 5. Decisioni architetturali

### 5.1 Trasporto MCP

**Scelta [Utente]: solo Streamable HTTP**, con server MCP come servizio separato.

| Opzione | Vantaggi | Svantaggi | Esito |
|---|---|---|---|
| stdio | nessuna rete né porta; semplice in locale | in Docker il server vive nell'immagine dell'agente e SQLite nel suo container; il server è un'appendice, non un servizio; meno chiara la distinzione host/client/server | scartata |
| **Streamable HTTP** | server indipendente, servizio Compose con volume e controllo di salute; coerente con FastAPI; separazione visibile | un URL in più e un servizio in più | **scelta** |
| Entrambe | massima flessibilità | due percorsi di codice da mantenere e provare | scartata |

### 5.2 Client MCP e grafo sincrono

**Scelta [Utente]: ponte sincrono sopra il client FastMCP.** Grafo e terminale restano sincroni.

| Opzione | Vantaggi | Svantaggi | Esito |
|---|---|---|---|
| **A. Ponte sincrono** (`mcp_client.py`: `list_tools()` all'avvio, `BaseTool` costruiti dallo schema scoperto, chiamate che eseguono la parte asincrona in funzioni sincrone) | grafo, terminale e test invariati; nessuna dipendenza in più; meccanismo esplicito e spiegabile | una connessione per chiamata | **scelta** |
| B. `langchain-mcp-adapters` | discovery e strumenti già pronti | strumenti asincroni: grafo con `ainvoke`, terminale e test asincroni; dipendenza che nasconde il meccanismo | scartata |
| C. Tutto l'agente asincrono | pulita in astratto | riscrittura completa, contro il vincolo | scartata |

Condizioni **[Utente]**:
- discovery con `list_tools()`: nome, descrizione e schema vengono dal server; il catalogo non è riscritto a mano nel client;
- vero client MCP, con apertura e chiusura corrette di connessioni e ciclo asincrono;
- strumenti adattati al formato già usato dal grafo (`BaseTool`);
- gestione di timeout, server non disponibile, errori dello strumento, conversione del risultato in testo per il modello;
- risultato sempre associato al `tool_call_id` corretto;
- prima di considerare valido il ponte, una **verifica tecnica con un server FastMCP reale**, con chiamate ripetute (anche consecutive nello stesso turno e in turni successivi).

### 5.3 Server MCP non raggiungibile all'avvio

**Scelta [Utente]: avvio ridotto con avviso evidente.**

| Opzione | Vantaggi | Svantaggi | Esito |
|---|---|---|---|
| A. Blocco all'avvio (errore, codice 1) | semplice, prevedibile | un servizio spento toglie anche gli strumenti locali | scartata |
| **B. Avvio ridotto con avviso** | l'agente resta utilizzabile; il modello non vede strumenti inesistenti; nessun nuovo tentativo ai turni successivi (solo un'attesa limitata all'avvio, vedi sotto), nessun stato aggiuntivo | l'utente deve riavviare l'agente a server attivo | **scelta** |
| C. Nuovi tentativi a ogni turno | più comodo | stato e casi di test in più, comportamento meno prevedibile | scartata |

Dettagli: avviso tipo «Server MCP non raggiungibile su `<url>`: strumenti note e meteo non disponibili. Riavvia l'agente quando il server è attivo», e traccia nei log. Se il server cade a sessione avviata, la chiamata dà `Errore: ...` nel `ToolMessage`; un timeout è trattato allo stesso modo.

**Emendamento (2026-11-09, [Utente]) — Compose.** L'agente **non** dipende dal controllo di salute: `depends_on: server-mcp: condition: service_started` (mai `service_healthy`), perché il server MCP non disponibile non deve impedire l'avvio ridotto. Per evitare l'avviso falso quando il server è solo in ritardo, all'avvio la discovery è ripetuta per un tempo limitato (`MCP_ATTESA_AVVIO`, secondi; 0 in locale, 20 in Compose); scaduto il tempo, avviso e strumenti locali. Verificato con Compose v5.0.2: un server avviato ma non sano o uscito non blocca l'agente; un server che **non riesce a partire** (per esempio porta occupata) fa fallire `docker compose run --rm assistente`, mentre `docker compose run --rm --no-deps assistente` avvia l'agente ridotto (comando da documentare nel README). `required: false` è supportato ma non aggiunge nulla e non si usa.

### 5.4 Integrazione FastAPI

**Scelta [Utente]: wrapper scritti a mano con `httpx`.**

| Opzione | Vantaggi | Svantaggi | Esito |
|---|---|---|---|
| **A. Wrapper `@tool` manuali** in un modulo dedicato (`strumenti_http.py`), richieste sincrone con timeout, URL da variabile d'ambiente | distingue chiaramente HTTP tradizionale (catalogo noto all'agente) da MCP (strumenti scoperti); codice semplice e testabile | endpoint e parametri duplicati nell'agente | **scelta** |
| B. Strumenti generati da `/openapi.json` | meno codice ripetuto | seconda discovery che nasconde il confronto con MCP; più codice da spiegare e testare | scartata |

Gli strumenti HTTP sono sempre registrati (non c'è discovery): se il servizio è spento, l'errore compare alla chiamata come `Errore: servizio non raggiungibile ...`. Il servizio può avere più endpoint di quelli esposti al modello. Gli errori HTTP (422, 404, ...) sono tradotti in testo comprensibile.

### 5.5 Inventario degli strumenti

**Scelta [Utente]: 11 strumenti**, consapevole del rischio per il modello piccolo.

Proposta iniziale dell'assistente: 9 strumenti (senza `dettaglio_catalogo` ed `elimina_nota`; `cerca_catalogo` restituiva le schede complete). **L'utente ha aggiunto** `dettaglio_catalogo` (per verificare due chiamate consecutive: cerca, poi dettaglio) ed `elimina_nota` (cancellazione con conferma e gestione di ID inesistenti). Non eliminati preventivamente.

Regole per nomi e descrizioni **[Utente]**: chiari e distinguibili, nessuna moltiplicazione inutile. Descrizioni in italiano con un breve esempio d'uso; nessuna sovrapposizione (per esempio `giorni_lavorativi` dichiara di non servire per l'ora attuale). Nessuno strumento di servizio (per esempio «elenca strumenti»).

Se le prove reali mostrano difficoltà di selezione: prima si riformulano le descrizioni, poi (con l'utente) si valuta di semplificare l'inventario o aggiungere un prompt di sistema. Nessuna modifica arbitraria.

### 5.6 Conferma di `elimina_nota`

**Scelta [Utente], emendata il 2026-11-09: conferma esplicita dell'utente raccolta dall'applicazione nel terminale, indipendente dagli argomenti scelti dal modello.**

| Opzione | Vantaggi | Svantaggi | Esito |
|---|---|---|---|
| A. Parametro `conferma` verificato dal server | il grafo non cambia; la regola sta nel server | il modello può impostare `true` da solo: non è una protezione dell'utente | **scartata** (scelta originaria, ritenuta insufficiente dall'utente) |
| **B'. Conferma `[s/N]` nel terminale, richiesta dal ponte MCP prima della chiamata, guidata dall'annotazione `destructiveHint` ricevuta dalla discovery** | indipendente dal modello; grafo e terminale non cambiano struttura (la funzione di conferma gira dentro il nodo strumenti sincrono, nessun `interrupt`); nessun nome di strumento scritto a mano nel client | il server MCP da solo non protegge dalle chiamate di altri client; serve una piccola funzione di conferma passata dal terminale | **scelta** |
| C. Due passaggi con codice di conferma | più robusta di A | complessità doppia per un modello piccolo; il modello resta nel circuito | scartata |

Nota sulla scelta precedente: B era stata scartata perché si riteneva che servisse modificare grafo o nodo strumenti; la variante B' lo evita facendo la richiesta nel ponte.

Comportamento **[Utente]**: il server espone `elimina_nota(id)` con `destructiveHint=True` e **senza** parametro `conferma`. Il ponte legge l'annotazione dalla discovery (`StrumentoMcp.richiede_conferma`, conservata anche in `metadata["destructiveHint"]`; assente = `False`) e, prima di chiamare il server, invoca la funzione `chiedi_conferma` ricevuta dall'applicazione. Il terminale mostra `Confermi: elimina_nota {id: 3}? [s/N]` e legge la risposta con `input()`. Risposta diversa da `s`/`sì`, EOF, errore della funzione o funzione assente → il server **non viene chiamato** e il modello riceve `Errore: cancellazione non confermata dall'utente`. La conferma è chiesta **prima** di verificare se l'ID esiste (**[Utente]**: va bene); dopo la conferma un ID inesistente dà `Errore: nota <id> non trovata`, database invariato. Gli strumenti non annotati non chiedono mai conferma.

Limite documentato **[Utente]**: la protezione riguarda l'uso tramite il nostro agente; un altro client MCP collegato allo stesso server può cancellare senza conferma. Va scritto nel README.

Verifiche: test automatico in cui il modello (finto) chiede subito `elimina_nota` con `conferma=True` senza conferma dell'utente → nessuna cancellazione, `ToolMessage` corretto; test che l'annotazione sia acquisita dalla discovery e conservata nel `BaseTool`, e che gli altri strumenti non chiedano conferme; prova reale: «cancella la nota 3» mostra `[s/N]` nel terminale, `n` lascia la nota, `s` la cancella.

### 5.7 Organizzazione di Docker Compose

**Scelta [Utente]: un'immagine, tre servizi, volume con nome per SQLite.**

| Servizio | Ruolo | Avvio |
|---|---|---|
| `assistente` | agente da terminale (invariato) | `docker compose run --rm assistente` |
| `servizi-http` | FastAPI (date e catalogo) su uvicorn | automatico |
| `server-mcp` | FastMCP (note e meteo), Streamable HTTP | automatico |

| Opzione | Esito |
|---|---|
| **Un `Dockerfile` e un `requirements.txt`, tre comandi diversi** | **scelta** (semplice da mantenere; costo: l'immagine dell'agente contiene anche FastAPI/uvicorn) |
| Tre immagini o un `requirements` per servizio | scartata (più pulita in astratto, triplica la manutenzione) |

Dettagli **[Scelta mia]**: rete predefinita di Compose, servizi raggiunti per nome (per esempio `http://servizi-http:8000`, `http://server-mcp:8001/mcp`); porte pubblicate solo su `127.0.0.1`; variabili `SERVIZI_BASE_URL` e `MCP_URL` con valori locali (`localhost`) e valori Compose, sul modello di `LM_STUDIO_DOCKER_URL`; controlli di salute con un comando Python (l'immagine `slim` non ha `curl`), che per `server-mcp` esegue una **vera discovery MCP** (`python -m assistente.verifica_mcp`, non una semplice connessione TCP) e per `servizi-http` una richiesta HTTP a `/salute`; `assistente` dipende dai servizi solo con `service_started` (vedi 5.3); utente non root; volume con nome che sopravvive a `docker compose down` (si cancella solo con `down -v`, da scrivere nel README); festività e catalogo come file versionati nel codice, senza volume. LM Studio resta sull'host.

### 5.8 Ordine di lavoro e Git

**Scelta [Utente]**: ordine sotto; `git merge --no-ff`; il resto del processo come descritto dall'utente.

| # | Ramo | Contenuto |
|---|---|---|
| 0 | direttamente su `dev` | solo documentazione: specifica, piano, aggiornamento di `CLAUDE.md`, dopo l'approvazione di specifica **e** piano |
| 1 | `feat/mcp-note` | server FastMCP, SQLite, client e ponte sincrono, discovery, servizio Compose con volume, variabili d'ambiente, avvio ridotto. Strumenti `aggiungi_nota`, `elenca_note`, `elimina_nota` |
| 2 | `feat/mcp-meteo` | `meteo` nello stesso server |
| 3 | `feat/conversione-unita` | `converti_unita` |
| 4 | `feat/calcolatrice` | `calcola` |
| 5 | `feat/http-scadenze` | servizio FastAPI, festività da file, wrapper, servizio Compose; `giorni_lavorativi`, `calcola_scadenza` |
| 6 | `feat/http-catalogo` | endpoint del catalogo; `cerca_catalogo`, `dettaglio_catalogo` |
| 7 | verifica finale su `dev` | regressione completa, prove reali documentate, README aggiornato |

L'ordine tra 3 e 4 e tra 5 e 6 è intercambiabile; 1 viene prima e va completato e verificato prima del resto. Alternativa scartata: partire dalle funzioni locali (più semplici) — scartata perché l'utente dà priorità alla prima integrazione MCP richiesta dal professore.

**Primo ramo a incrementi [Utente]**: prima si verificano server FastMCP, discovery e invocazione reale di *un* primo strumento; solo dopo si aggiungono le altre operazioni sulle note, poi SQLite completo, Docker e test di integrazione. Il ramo entra in `dev` solo a funzionalità interamente verificata.

**Processo per ogni ramo [Utente]:** partenza da `dev` aggiornato → ramo `feat/<nome>` → solo la funzionalità prevista con i suoi test → test automatici → prove reali (LM Studio, Docker, FastAPI, MCP) → review che verifichi anche l'assenza di regressioni → approvazione dell'utente → `git merge --no-ff` su `dev` → verifica del risultato → eliminazione del ramo. `dev` resta funzionante dopo ogni integrazione. Nessun push, nessun merge su `main`, nessuna operazione distruttiva senza autorizzazione. Commit piccoli, Conventional Commits in italiano, staging selettivo, prima di ogni commit `git status` e controllo del diff.

## 6. Dettagli funzionali

Valori **[Scelta mia]** salvo dove indicato.

- **`converti_unita`**: valore numerico, unità di partenza e di arrivo. Categorie: lunghezza, massa, volume, temperatura. Unità sconosciuta o incompatibile → `Errore: ...` chiaro.
- **`calcola`**: espressioni con `+ - * / **`, parentesi e numeri, analizzate con il modulo `ast` (mai `eval`). Divisione per zero, sintassi non valida, nomi o chiamate non ammessi, espressioni o esponenti eccessivi → errori in testo.
- **`giorni_lavorativi` / `calcola_scadenza`** (servizio FastAPI) **[Utente]**: date ISO, festività da file locale, validazione degli input, casi limite (intervalli invertiti, date non valide, N negativo o enorme, weekend e festività). Il file delle festività è un JSON versionato. Dettagli come regola del weekend e anni coperti: da fissare nel piano.
- **Catalogo (servizio FastAPI)** **[Utente]**: circa 10 corsi di formazione ITS **fittizi**, in un JSON versionato; dati realistici ma inventati, nessun dato personale, non presentati come offerta formativa reale. Campi: codice identificativo univoco, titolo, settore formativo, sede, durata in ore, breve descrizione. `cerca_catalogo(query)`: ricerca testuale su titolo, settore e sede; elenco limitato con informazioni essenziali e codice. `dettaglio_catalogo(codice)`: tutti i campi di un corso. Gestiti: ricerca senza risultati, codice inesistente, parametri non validi. Il modello non deve inventare corsi assenti dal catalogo (interpretazione del messaggio troncato dell'utente, da confermare). Verifica richiesta: l'agente esegue due chiamate consecutive (cerca, poi dettaglio).
- **Note (server MCP)**: campi `id`, testo, data di creazione; percorso del database SQLite da variabile d'ambiente; operazioni `aggiungi_nota`, `elenca_note` (filtro di testo e limite facoltativi, vedi 10quater), `elimina_nota` (vedi 5.6). La persistenza è dei dati dello strumento: la cronologia della conversazione resta solo in memoria.
- **`meteo` (server MCP)**: Open-Meteo (senza chiave) **[Scelta mia]**; timeout e errori di rete in testo chiaro; test automatici con risposta simulata, prova reale a parte (anche da Docker).
- **Prompt di sistema**: nessuno all'inizio **[Scelta mia]**; si valuta solo se le prove reali lo giustificano, con l'utente.
- **Dipendenze nuove, versioni fissate**: `fastmcp`, `fastapi`, `uvicorn`, `httpx` (già presente come dipendenza indiretta di `openai`, ma da dichiarare), più ciò che serve ai test (per esempio il client di test di FastAPI). Le versioni esatte si fissano nel piano, verificando la compatibilità con Python 3.13 e con le versioni già fissate.
- **Log**: ogni richiesta e ogni esito di strumento compaiono nei log (come per l'orologio); per MCP anche la discovery (nomi degli strumenti scoperti) e le invocazioni, in modo verificabile **[Utente]**.

## 7. Cosa resta invariato

Struttura del grafo (nodo modello, nodo strumenti, instradamento condizionale), cronologia in memoria, limite ai passaggi (`MAX_PASSAGGI`), gestione di Ctrl+C e Ctrl+D, messaggi di errore del server del modello, strumento `orologio`, codice e test esistenti. Gli unici interventi attesi sul codice esistente sono: composizione della lista di strumenti nell'avvio (`terminale.py`/`strumenti.py`), nuove variabili in `config.py`, `Dockerfile`, `compose.yaml`, `.env.example`, `requirements.txt`, README.

## 8. Criteri di verifica

**Per ogni funzionalità**
- Test automatici senza rete né modello (strumenti con istante o rete controllati, `TestClient` per FastAPI, server FastMCP reale su porta libera per il ponte MCP).
- Prove reali con LM Studio, più formulazioni per ogni strumento, con le chiamate verificate nei log; Docker e servizi reali dove pertinenti.
- Review, con controllo dell'assenza di regressioni (suite completa, Docker).

**Verifica finale dell'agente completo (dopo le sei funzionalità)**
1. Tutte le nuove funzionalità disponibili e utilizzabili.
2. L'orologio continua a funzionare.
3. Il modello sceglie lo strumento giusto in domande diverse (una o più domande per strumento, con formulazioni differenti).
4. Discovery e invocazioni MCP reali, visibili nei log.
5. Risultati restituiti al modello e associati al `tool_call_id` corretto.
6. Errori di strumento e di rete gestiti in modo chiaro (servizio spento, timeout, input non valido, ID inesistente).
7. Cronologia, limite ai passaggi e interruzioni funzionano ancora.
8. Docker Compose avvia e fa usare il progetto secondo istruzioni documentate, con **vera discovery MCP in Docker** (non solo porta aperta) e **avvio ridotto verificato** con il server MCP fermo, in crash e non avviabile (`--no-deps`): l'agente parte, mostra l'avviso e usa `orologio`.
9. Test automatici e prove reali documentati, distinguendo **simulato** da **provato con il modello locale** (`prove_reali/PROVE.md`).

Criterio di accettazione sulla selezione: se il modello sbaglia lo strumento in due o più domande-tipo, si interviene sulle descrizioni (con l'utente) prima di aggiungere altro.

## 9. Modifiche proposte a `CLAUDE.md` (da applicare solo dopo approvazione di specifica e piano)

Conservare: obiettivo di base, qualità del codice (moduli piccoli), test, documentazione, Conventional Commits, staging selettivo, nessuna credenziale versionata, push solo su richiesta, approvazione di specifica e piano prima del codice, distinzione tra simulato e provato, resoconto di esiti e di ciò che resta da provare.

Cambiare:
1. «Confini»: consentire esplicitamente servizi HTTP con FastAPI e server/client MCP con FastMCP (solo Streamable HTTP); restano esclusi RAG e altre tecnologie non richieste dal laboratorio; sparisce «MCP … non anticiparli».
2. «Scelte tecniche»: dipendenze nuove concordate e fissate (`fastmcp`, `fastapi`, `uvicorn`, `httpx`); «nessuna persistenza» riferita alla cronologia; SQLite consentito per i dati delle note.
3. Docker Compose: più servizi (`assistente`, `servizi-http`, `server-mcp`); LM Studio resta sull'host e non va containerizzato.
4. «Git»: sostituire «lavorare nel branch corrente» con il flusso `dev` → `feat/<nome>` → `merge --no-ff` dopo approvazione → verifica → eliminazione del ramo; il resto invariato (nessun push né merge su `main` senza autorizzazione).
5. «Struttura e comandi»: aggiungere i nuovi moduli e i comandi verificati per avviare i servizi e le prove (solo quando esistono e funzionano).
6. Regola generale: strumenti scoperti da MCP mai riscritti a mano nel client; strumenti HTTP con wrapper scritti a mano.

## 10. Rischi noti

- **Modello piccolo con 11 strumenti**: possibili errori di selezione o argomenti sbagliati. Mitigazione: descrizioni chiare, prove con più formulazioni, intervento mirato solo dopo i risultati.
- **Ponte sincrono su client asincrono**: può dare problemi di cicli o chiusura delle connessioni. Mitigazione: verifica tecnica con server reale e chiamate ripetute, prima di costruire il resto.
- **Conferma di cancellazione**: garantita dall'applicazione nel terminale, non dal modello; non protegge dalle chiamate di altri client MCP (limite documentato, vedi 5.6).
- **Meteo**: dipende dalla rete e da un servizio esterno; i test automatici lo simulano.
- **Immagine Docker**: il codice è copiato nell'immagine; dopo ogni modifica serve `docker compose build` (già nelle limitazioni note del README).

## 10ter. Risposte dell'utente dopo la revisione

- ~~**[Utente]** Se in una prova reale il modello cancella una nota senza prima chiedere conferma (passa `conferma=true` al primo giro), il ramo `feat/mcp-note` è bloccato.~~ **Superata il 2026-11-09 (vedi 5.6):** la conferma non dipende più dal modello, quindi non esiste un parametro che il modello possa impostare da solo. Resta il vincolo che nessuna cancellazione avviene senza la conferma dell'utente nel terminale.
- **[Utente]** Confermato: il modello non deve inventare corsi assenti dal catalogo; se la ricerca non trova nulla, lo dice. (L'interpretazione in sezione 6 non è più «da confermare».)

## 10bis. Scelte aggiunte dopo la revisione (tutte **[Scelta mia]**, da correggere in lettura)

- **Test del ponte MCP nella suite normale.** Un server FastMCP reale avviato in locale (thread o processo, porta libera scelta dal sistema, solo `127.0.0.1`) conta come «senza rete»: non esce dal computer. Questi test fanno parte di `pytest` e non richiedono né modello né Internet. Il meteo resta simulato.
- **Avviso di avvio ridotto.** Se il server non risponde non c'è discovery, quindi l'avviso **non elenca nomi di strumenti**: dice solo «Server MCP non raggiungibile su `<url>`: gli strumenti MCP non sono disponibili. Riavvia l'agente quando il server è attivo». (Sostituisce l'esempio con «note e meteo» in 5.3, che avrebbe richiesto nomi scritti a mano.)
- **Avvio fuori da Docker.** Ogni servizio ha un punto d'ingresso eseguibile (per esempio `python -m assistente.server_mcp`, `python -m assistente.servizi_http`), avviato in una finestra PowerShell separata; README e `.env.example` coprono sia l'uso locale sia Compose, con solo comandi verificati.
- **Ramo 1 e Compose.** Il `compose.yaml` del ramo 1 contiene `assistente` e `server-mcp` (volume, controllo di salute con vera discovery MCP, `depends_on: service_started`; vedi 5.3 e 5.7). `servizi-http` e `SERVIZI_BASE_URL` arrivano nel ramo 5. Gli strumenti HTTP non esistono prima di quel ramo, quindi non servono registrazioni condizionali: ogni ramo aggiunge i propri strumenti alla lista composta all'avvio.
- **Campi del catalogo.** `cerca_catalogo` restituisce solo codice, titolo, settore e sede, con un massimo di risultati configurabile (parametro facoltativo, vedi 10quater); durata e descrizione compaiono solo in `dettaglio_catalogo`, così la seconda chiamata serve davvero.
- **Meteo.** `meteo` riceve il **nome della città**; il server MCP ricava le coordinate con la geocodifica di Open-Meteo (seconda chiamata esterna, interna al server) e poi legge il meteo. Città non trovata e errori di rete sono casi di errore da testare, con entrambe le chiamate simulate.

## 10quater. Integrazioni dal confronto con le slide 25–31 di `LLM_Lez_5.pdf` (tutte **[Scelta mia]**, da correggere in lettura)

**Note**
- Errori in testo (`Errore: ...`): testo vuoto o composto solo da spazi; testo oltre 500 caratteri; archivio SQLite non accessibile (nessuna modifica, nessun falso successo).
- `elenca_note(filtro?, limite?)`: ordinate dalla più recente; `limite` predefinito 20, intervallo 1–100, fuori intervallo → errore. Il filtro di testo resta facoltativo.
- Ogni modifica (aggiunta, cancellazione) produce una riga di log nel server, oltre ai log del client.
- Il file SQLite non va mai versionato: `*.db` (e la cartella dei dati) in `.gitignore` e `.dockerignore`; in Docker vive nel volume con nome.
- Casi da provare in modo esplicito: «Ricordami di consegnare il report venerdì» → **una sola** chiamata a `aggiungi_nota`; «Elimina la nota 99» → errore chiaro e database invariato; **riavvio** del server (e del container) → le note salvate restano.

**Meteo**
- Risultato: temperatura (°C), condizioni in italiano (dal codice meteo di Open-Meteo), ora di riferimento della misura, tutte con unità esplicite.
- Città ambigua: si usa il primo risultato della geocodifica, ma il risultato **dichiara** la città scelta (nome, regione, paese) e quanti altri candidati esistevano. Nessuna selezione silenziosa.
- Errori distinti, ciascuno con messaggio proprio e testato con risposte HTTP simulate: città non trovata; timeout; servizio non disponibile (HTTP 5xx); risposta non valida (JSON inatteso); rete assente (errore di trasporto), mai confusa con «città non trovata».

**Catalogo**
- `cerca_catalogo(query, max_risultati?)`: `max_risultati` facoltativo, predefinito 5, intervallo 1–10; fuori intervallo → errore chiaro (422 tradotto in testo). Sostituisce il «massimo 5» fisso.
- Nessuna *resource* MCP (catalogo completo con URI): non applicabile, perché il catalogo è un servizio FastAPI e non un server MCP. Resta fuori perimetro.
- Nei log delle prove reali si osserva quale strumento sceglie il modello tra `cerca_catalogo` e `dettaglio_catalogo` (descrizioni simili).

**Estensioni facoltative della slide 29**
- 02 (confronto del catalogo tra stdio e Streamable HTTP): non applicabile, stdio è scartato (5.1). Resta fuori perimetro.
- 03 (due server MCP collegati allo stesso agente) e 04 (prompt MCP riutilizzabile): **fuori perimetro**; il server è uno solo. Si potranno valutare dopo la verifica finale.

**Evidenze (slide 31)**
- Il ramo 1 include una **invocazione diretta** del server MCP, senza modello, con input noto e risultato verificato (primo incremento, prima di integrare nel grafo). Rimane un criterio esplicito di verifica per ogni strumento MCP.
- Se una prova reale fallisce, `PROVE.md` registra il punto esatto e la funzionalità non è dichiarata completata.

**Nomi e docente**
- I nomi degli strumenti restano in italiano (il PDF usa nomi inglesi, per esempio `add_note`, `get_weather`): scelta di coerenza con il progetto.
- **Punto aperto per l'utente:** il PDF presenta tutte le proposte come tool MCP e richiede una sola integrazione MCP; qui quattro funzionalità sono locali o FastAPI. Il requisito minimo è soddisfatto (note e meteo via MCP), ma la variante va eventualmente concordata con il docente.

## 11. Lasciato al piano

Versioni esatte delle dipendenze; struttura dei moduli e dei file (per esempio dove stanno il server MCP e il servizio FastAPI nella cartella `src/assistente/`); nomi esatti di variabili e porte; elenco preciso delle unità e dei corsi; regola dei weekend e anni delle festività; formato esatto di descrizioni e risposte; sequenza dei commit e dei test dentro ogni ramo.
