# Lezione 6, Step 4 — Resource MCP: preferenze dell'utente: specifica

Stato: **approvata il 2026-11-16**, dopo la review indipendente (§17). Brainstorming concluso il 2026-11-16 con sette decisioni approvate dall'utente. Le voci marcate **[Utente]** sono decisioni dell'utente; quelle marcate **[Scelta mia]** sono scelte del progettista, da controllare in lettura.

## 1. Intenzione

Lo Step 4 introduce la prima **resource MCP** del progetto. Finora il server MCP espone solo strumenti, che il modello decide di chiamare. Una resource è invece un dato che **l'applicazione host** decide di leggere: qui le preferenze dell'utente, lette all'avvio e messe in cima al prompt di sistema dell'agente.

L'obiettivo didattico (slide) è che **modificando il file delle preferenze il comportamento dell'agente cambi senza modificare il codice**.

La dimostrazione che l'utente ha in mente: **[Utente]**
1. apre `data/preferenze.json` con lingua italiano, fuso `Europe/Rome`, stile sintetico;
2. avvia l'agente: nei log si vede la lettura della resource, che non è una chiamata a uno strumento;
3. chiede «Che ore sono?» (l'agente usa Europe/Rome senza chiederlo) e una domanda in ambito (risposta in italiano, sintetica);
4. modifica solo il file: inglese, `America/New_York`, dettagliato;
5. avvia una nuova sessione: «Che ore sono?» usa New York; la domanda in ambito riceve una risposta in inglese e più dettagliata;
6. rende la resource non disponibile: l'agente continua a funzionare con le preferenze predefinite e lo segnala nei log.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Requisiti della slide** («Step 4 — Resource MCP: preferenze dell'utente», `../LLM_Lez_6.pdf`, pagina 8; testo verificato dall'utente il 2026-11-16):
1. Il server MCP espone la resource `utente://preferenze`, che contiene:
   - lingua delle risposte;
   - fuso orario predefinito;
   - stile delle risposte (sintetico o dettagliato).
2. L'applicazione host legge la resource **all'inizio di ogni sessione** e inserisce le preferenze **in cima al prompt di sistema**.
3. La resource **non** va esposta tra gli strumenti passati a `bind_tools`: la lettura la decide l'host, non il modello.
4. Se la resource non è disponibile, si usano **valori predefiniti** e la situazione viene **segnalata nei log**.

**Evidenze richieste dalla slide:**
- alla domanda «Che ore sono?» l'agente usa il fuso predefinito senza chiederlo (provare con `America/New_York`);
- modificando lingua o stile nel file delle preferenze, la sessione successiva risponde di conseguenza;
- la lettura della resource è visibile nei log, separata dalle chiamate ai tool.

**Requisiti aggiuntivi dell'utente:** **[Utente]**
- le preferenze valgono per l'intera sessione e vengono rilette all'avvio della successiva;
- compatibilità con Router, Revisore e Riassuntore degli Step 1–3;
- soluzione semplice e didattica, senza complessità non richiesta;
- i log distinguono chiaramente le preferenze lette dalla resource da quelle predefinite;
- il fallback delle preferenze non va confuso con la disponibilità degli strumenti MCP.

**Non obiettivi:**
- **Prompt MCP** (Step 5) e gli step successivi: agente come servizio HTTP, back-end con salvataggio delle chat, front-end, Compose per componente. **[Utente]**
- Modificare le preferenze dall'agente o dal terminale: il file si modifica a mano.
- Rileggere le preferenze durante la sessione.
- Tradurre i testi fissi dell'applicazione (rifiuto del Router, avvisi, conferme).
- Cambiare `NOTE_DB_PATH` o la gestione delle note.

**Anti-obiettivi** (sarebbe un fallimento anche se "funziona"):
- la resource diventa uno strumento che il modello può chiamare;
- il server MCP inventa preferenze quando il file manca;
- un problema delle preferenze fa partire l'agente in modo diverso da oggi per quanto riguarda gli strumenti, o maschera un problema degli strumenti MCP;
- valori predefiniti duplicati in più punti.

## 3. Architettura attuale (verificata su `dev`, `371d81a`, 636 test verdi)

- **Server MCP** (`server_mcp.py`, FastMCP 4.1.6, Streamable HTTP sulla porta 8001): solo strumenti (`aggiungi_nota`, `elenca_note`, `elimina_nota`, `meteo`); nessuna resource.
- **Client MCP** (`mcp_client.py`): ponte sincrono `_esegui` sopra il client asincrono; `scopri_strumenti` con `list_tools()`; errori di discovery come `ErroreMcp`.
- **Strumenti** (`strumenti.py`): `orologio` è un oggetto `@tool` fisso con `Europe/Rome` scritto sia come valore predefinito del parametro sia nella descrizione; `STRUMENTI = [orologio, converti_unita, calcola]`; `componi_strumenti` unisce locali, HTTP e MCP, con l'attesa di avvio `MCP_ATTESA_AVVIO` e l'avviso dell'avvio ridotto.
- **Agente** (`grafo.py`, `nodo_modello`): nessun prompt di sistema fisso. Con riassunto non vuoto riceve un `SystemMessage` temporaneo con la cornice B.1 dello Step 3; con riassunto vuoto la richiesta è identica a quella dello Step 2 (spec Step 3 §9.4).
- **Terminale** (`terminale.py`, `main()`): carica la configurazione, compone gli strumenti, costruisce il grafo, avvia la chat. I log vanno su stderr con il formato `%(levelname)s %(name)s: %(message)s`.
- **Docker** (`compose.yaml`): servizi `assistente`, `servizi-http`, `server-mcp`; le note nel volume `dati-note` montato su `/data` nel `server-mcp`. Il `Dockerfile` copia solo `requirements.txt`, `src/` e `prove_reali/`; `data/` è esclusa da `.gitignore` e `.dockerignore`.

### 3.1 Verifica della libreria (2026-11-16, FastMCP 4.1.6 installato)

Con uno script usa e getta, fuori dalla repository, su un server in memoria:
- `@server.resource("utente://preferenze", mime_type="application/json")` registra la resource; lo schema `utente://` è accettato;
- `list_tools()` **non** elenca la resource (lista vuota sul server di prova); `list_resources()` la elenca;
- `await client.read_resource("utente://preferenze")` restituisce una lista con un `TextResourceContents` (`.text` è il testo restituito dalla funzione, `.mimeType` è `application/json`);
- un'eccezione nella funzione della resource arriva al client come `mcp.shared.exceptions.MCPError` con il messaggio `Error reading resource 'utente://preferenze': <messaggio>`. Con un'eccezione generica il server registra anche il traceback: per questo la specifica usa `fastmcp.exceptions.ResourceError` (§5.1), il cui comportamento esatto nei log va verificato dal costruttore.

Il trasporto Streamable HTTP reale va verificato nei test con il server FastMCP su porta libera (§12).

## 4. Architettura nuova

```
Avvio (main del terminale)
  1. carica_config
  2. discovery strumenti MCP + HTTP (attesa MCP_ATTESA_AVVIO invariata)
  3. carica_preferenze  ── read_resource("utente://preferenze") ──► server MCP ── legge data/preferenze.json
       └─ fallback ai valori predefiniti (WARNING) se qualcosa non va
  4. orologio costruito con il fuso delle preferenze
  5. crea_modello(bind_tools: solo strumenti) + costruisci_grafo(..., preferenze)

Ogni chiamata all'agente
  [SystemMessage(preferenze + eventuale cornice del riassunto), *contesto_agente(...)]
```

Il grafo non cambia: nessun nodo nuovo, stessi archi, stessa formula del limite di passaggi (§11). **[Scelta mia]**

### 4.1 Moduli

| Modulo | Cambiamento |
|---|---|
| `preferenze.py` (nuovo) | `Preferenze`, valori predefiniti, validazione, `carica_preferenze`, testo del blocco per il prompt, logger `assistente.preferenze` |
| `server_mcp.py` | resource `utente://preferenze`; percorso da `PREFERENZE_PATH` |
| `mcp_client.py` | `leggi_resource(url, uri, timeout) -> str` |
| `strumenti.py` | `crea_orologio(fuso)`; composizione con l'orologio costruito con il fuso della sessione |
| `grafo.py` | `costruisci_grafo` riceve le preferenze; `nodo_modello` invia sempre un `SystemMessage` |
| `terminale.py` | `main()` legge le preferenze una volta, nell'ordine del §4 |
| `compose.yaml` | montaggio di `./data` in sola lettura nel `server-mcp`, `PREFERENZE_PATH` |
| `preferenze.example.json` (nuovo, radice del progetto) | esempio versionato |

Router (`router.py`), Revisore (`revisore.py`) e Riassunto (`riassunto.py`) **non cambiano**. **[Utente]**

## 5. Il file e la resource (decisione 1) [Utente]

### 5.1 Formato

JSON con tre chiavi in italiano:

```json
{
  "lingua": "italiano",
  "fuso_orario": "Europe/Rome",
  "stile": "sintetico"
}
```

- `preferenze.example.json` è versionato in Git, nella radice di `assistente-laboratorio/`, con esattamente questo contenuto.
- Il file reale è `data/preferenze.json`, escluso da Git (`data/` è già in `.gitignore`).
- Il README indica come crearlo, anche su un clone appena fatto, dove `data/` non esiste ancora (oggi la crea solo l'avvio del server MCP):
  ```powershell
  New-Item -ItemType Directory -Force data | Out-Null
  Copy-Item preferenze.example.json data\preferenze.json
  ```
  I comandi vanno verificati prima di finire nel README. **[Scelta mia]**

### 5.2 Percorso (decisioni 1 e 7) [Utente]

- Variabile d'ambiente `PREFERENZE_PATH`, letta dal server MCP, come `NOTE_DB_PATH`.
- Se è impostata (non vuota dopo `strip`), il valore si usa così com'è; un percorso relativo vale rispetto alla cartella corrente.
- Se manca, il percorso predefinito è `<radice del progetto>/data/preferenze.json`, con la radice calcolata dalla posizione del modulo (`Path(__file__).resolve().parents[2]` da `src/assistente/server_mcp.py`), **non** dalla cartella corrente. Funziona quindi da qualunque cartella venga avviato il server.
- `NOTE_DB_PATH` resta invariata.

### 5.3 La resource sul server (decisioni 2 e 3) [Utente]

- `crea_server` registra la resource `utente://preferenze` con `mime_type="application/json"` e una descrizione breve. **[Scelta mia]** `crea_server` riceve il percorso del file come parametro con nome **facoltativo** (`percorso_preferenze`), così:
  - i test nuovi usano un file temporaneo;
  - le chiamate esistenti con il solo archivio (in `test_server_mcp.py`, `test_mcp_client.py`, `test_terminale.py`, `test_verifica_mcp.py`) restano invariate;
  - se il parametro manca si usa il percorso predefinito del §5.2. Il file viene aperto solo quando qualcuno legge la resource, e i test esistenti non la leggono: non dipendono quindi dal file locale.
  - `main()` del server passa il percorso risolto da `PREFERENZE_PATH` o dal valore predefinito.
- **A ogni lettura** il server apre il file e restituisce il testo così com'è, senza interpretarlo né validarlo. Una modifica del file vale quindi dalla lettura successiva, senza riavviare il server.
- Il file si legge con codifica `utf-8-sig`: tollera il BOM che Blocco note e PowerShell 5.1 (`Out-File`, `Set-Content -Encoding utf8`) aggiungono su Windows. Il BOM viene rimosso prima di restituire il testo. **[Scelta mia]**
- Se il file non si può leggere (mancante, cartella al posto del file, permessi, codifica), il server solleva `ResourceError` con un messaggio breve che contiene il percorso e la causa. **Non restituisce mai preferenze predefinite.**
- Il server registra con il logger `assistente.server_mcp`:
  - INFO `resource utente://preferenze letta da <percorso>`;
  - WARNING `resource utente://preferenze non disponibile: <causa>`.
- All'avvio il messaggio INFO esistente del server riporta anche il percorso delle preferenze. **[Scelta mia]**

## 6. Lettura dall'host (decisione 3) [Utente]

### 6.1 Client MCP

`mcp_client.leggi_resource(url: str, uri: str, timeout: float) -> str`:
- apre un `Client(url, timeout=timeout)` dentro `asyncio.timeout(timeout)`, come `_elenca` e `_chiama`, e chiama `read_resource(uri)`;
- usa il ponte sincrono `_esegui`;
- restituisce il testo del primo contenuto testuale;
- qualunque errore (connessione impossibile, `MCPError`, timeout, nessun contenuto testuale) diventa `ErroreMcp` con un messaggio leggibile, ripulito con `_testo_errore`.

La funzione **non** crea un `BaseTool` e non è collegata a `scopri_strumenti`: la resource non può finire in `bind_tools`.

### 6.2 Quando

- **Una sola volta per sessione**, in `main()`, **dopo** la discovery degli strumenti (che contiene l'attesa `MCP_ATTESA_AVVIO`) e **prima** di costruire l'orologio, il modello e il grafo.
- **Un solo tentativo**, con `MCP_URL` e `MCP_TIMEOUT`. Nessuna attesa aggiuntiva: in Docker l'attesa della discovery basta.
- Le preferenze ottenute sono un valore **immutabile** (`dataclass(frozen=True)`) passato al grafo; non cambiano durante la sessione. La sessione successiva (un nuovo avvio) le rilegge.
- Se la discovery è fallita perché il server è spento, anche la lettura fallisce: compaiono **due avvisi distinti**, uno per gli strumenti (invariato) e uno per le preferenze (§8). Nessuno dei due dice nulla sull'altro. **[Utente]**

### 6.3 Ordine dei passi in `main()` e composizione degli strumenti

Le decisioni 3 e 4 impongono un ordine: la discovery (con la sua attesa) deve venire **prima** della lettura delle preferenze, e l'orologio, che dipende dal fuso, **dopo**. Oggi `componi_strumenti` crea in un colpo solo locali, HTTP e MCP.

Soluzione: la lettura delle preferenze avviene dentro la composizione, fra la discovery e la costruzione dell'elenco. Forma consigliata: `componi_strumenti(config, *, carica_preferenze, ...)` esegue la discovery, poi chiama `carica_preferenze()` (iniettato, così i test lo sostituiscono), poi costruisce l'elenco con `crea_orologio(preferenze.fuso_orario)` e restituisce `(strumenti, preferenze, avvisi)`. Il costruttore può scegliere un'altra forma purché rispetti l'ordine discovery → preferenze → orologio, mantenga `componi_strumenti` testabile senza rete e lasci invariato il comportamento dell'avvio ridotto. **[Scelta mia]**

## 7. Valori predefiniti e validazione (decisioni 2 e 5) [Utente]

### 7.1 Valori predefiniti

`lingua="italiano"`, `fuso_orario="Europe/Rome"`, `stile="sintetico"`.

- Definiti **in un solo punto**, in `preferenze.py` (`PREFERENZE_PREDEFINITE`). Il server non li conosce.
- `strumenti.FUSO_PREDEFINITO` resta come nome, ma prende il valore da `PREFERENZE_PREDEFINITE.fuso_orario`, così il fuso predefinito non è scritto due volte. **[Scelta mia]**
- Con i valori predefiniti il comportamento dell'orologio è identico a quello attuale.

### 7.2 Validazione campo per campo (solo nell'host)

Il testo ricevuto si interpreta con `json.loads`. Poi ogni chiave si valuta da sola; se manca o non è valida si usa il valore predefinito **solo per quella chiave**, con un WARNING che ne riporta il nome.

| Campo | Valido se | Valore usato |
|---|---|---|
| `lingua` | stringa; dopo `strip` non vuota, al massimo 40 caratteri, senza a capo né altri caratteri di controllo | il testo dopo `strip` |
| `fuso_orario` | stringa accettata da `ZoneInfo` (stesse eccezioni gestite da `leggi_orologio`) | il testo dopo `strip` |
| `stile` | stringa che, dopo `strip` e `lower`, vale `sintetico` o `dettagliato` | la forma minuscola |

- Il limite di 40 caratteri e il divieto di a capo esistono perché `lingua` finisce nel prompt di sistema. **[Utente]** per il limite; **[Scelta mia]** per i caratteri di controllo.
- **Chiavi in più:** ignorate, con un WARNING che le elenca (per esempio `"fuso"` al posto di `"fuso_orario"`).

### 7.3 Cause che portano a usare tutti i valori predefiniti

Ognuna con il proprio messaggio di WARNING:
1. server MCP non raggiungibile (`ErroreMcp` per connessione impossibile o timeout);
2. resource non leggibile (`ErroreMcp` con l'errore del server, per esempio file mancante);
3. testo che non è JSON valido;
4. JSON valido che non è un oggetto (per esempio una lista).

Le cause 1 e 2 si distinguono dal messaggio di `ErroreMcp`, che riporta l'errore originale; non servono classi d'errore diverse. **[Scelta mia]**

### 7.4 Nessuna eccezione verso l'avvio

`carica_preferenze` non solleva mai eccezioni: qualunque problema produce le preferenze predefinite (tutte o in parte) e uno o più WARNING. L'avvio prosegue sempre. **[Utente]**

## 8. Log (logger `assistente.preferenze`) [Utente]

Logger dedicato, distinto da `assistente.mcp` e `assistente.strumenti` (che registrano discovery e chiamate ai tool):
- INFO, a lettura riuscita: `resource utente://preferenze letta da <MCP_URL>`;
- WARNING per ogni causa del §7.3: `preferenze non disponibili (<causa>): uso i valori predefiniti`;
- WARNING per ogni campo non valido o mancante: `preferenza <campo> non valida (<motivo>): uso <valore predefinito>`;
- WARNING per le chiavi in più: `chiavi sconosciute ignorate: <elenco>`;
- **INFO finale, sempre presente:**
  ```
  preferenze della sessione: lingua=inglese (resource), fuso_orario=America/New_York (resource), stile=sintetico (predefinito)
  ```

Il formato esatto dei messaggi è lasciato al costruttore, purché contenga queste informazioni. Il valore non valido di `lingua` va riportato troncato a 40 caratteri, per non riversare nei log testi lunghi. **[Scelta mia]**

La riga INFO finale distingue a colpo d'occhio che cosa viene dal file e che cosa dai valori predefiniti, anche nel caso misto.

## 9. L'orologio con il fuso della sessione (decisione 4) [Utente]

- `strumenti.crea_orologio(fuso: str) -> BaseTool` costruisce lo strumento `orologio`:
  - stesso nome `orologio` e stesso parametro `timezone`;
  - valore predefinito del parametro: `fuso`;
  - descrizione: «Restituisce la data e l'ora correnti. `timezone` è un fuso orario IANA (per esempio Europe/Rome, Asia/Tokyo); se omesso si usa {fuso}.»
  - esecuzione: `leggi_orologio(timezone)`, con `None` o testo vuoto che diventano `fuso`.
- `leggi_orologio` riceve il fuso predefinito come parametro (oggi usa la costante `FUSO_PREDEFINITO`); la firma pubblica resta compatibile con i test esistenti. **[Scelta mia]**
- `STRUMENTI` resta, costruito con `crea_orologio(FUSO_PREDEFINITO)`, perché i test esistenti lo usano. **[Scelta mia]**
- Se l'utente chiede un altro fuso («Che ore sono a Tokyo?»), il modello passa `Asia/Tokyo` come oggi.
- Gli esempi di fuso nella descrizione restano fissi (Europe/Rome, Asia/Tokyo): sono esempi del formato, non il fuso predefinito. **[Scelta mia]**

## 10. Il prompt di sistema e la compatibilità con lo Step 3 (decisione 6) [Utente]

### 10.1 Agente

- `costruisci_grafo` riceve `preferenze: Preferenze` (parametro con nome, predefinito `PREFERENZE_PREDEFINITE`, così i test esistenti non cambiano). **[Scelta mia]** per il valore predefinito del parametro.
- `nodo_modello` invia **sempre** un solo `SystemMessage` in testa alla richiesta:
  - il blocco delle preferenze (Appendice A);
  - se il riassunto non è vuoto, una riga vuota e poi la cornice B.1 dello Step 3, **invariata**.
- Un solo messaggio di sistema, non due: alcuni modelli locali rifiutano più messaggi di sistema. **[Utente]**
- Il `SystemMessage` resta **temporaneo**: non entra in `messages`, non viene salvato nella sessione, non conta per la soglia e non arriva al riassuntore.
- **Cambiamento rispetto allo Step 3 §9.4:** con riassunto vuoto la richiesta all'agente non è più identica a quella dello Step 2, perché contiene il blocco delle preferenze. Il resto del §9.4 (Router e Revisore identici carattere per carattere) resta valido.

### 10.2 Router, Revisore, Riassuntore

Invariati:
- **Router:** classifica la domanda, che non cambia.
- **Revisore:** le istruzioni (validate con lo spike degli 11 casi) dicono già «Non giudichi stile, lunghezza, formattazione». Una risposta in inglese a una domanda in italiano dovrebbe restare coerente; lo verifica la prova reale R2. Se il Revisore la boccia, si applica la regola dei 2 tentativi (§14). **[Utente]**
- **Riassuntore:** continua a riassumere in italiano; il riassunto è contesto interno.

### 10.3 Limite dichiarato

Il rifiuto del Router è un testo fisso in italiano e resta in italiano anche con `lingua=inglese`. Lo stesso vale per avvisi e conferme dell'applicazione. **[Utente]**

## 11. Limite di passaggi

Nessun nodo nuovo: la formula `1 (Riassunto) + 1 (Router) + (MAX_REVISIONI + 1) × (MAX_PASSAGGI + 1)` e i valori misurati dello Step 3 restano invariati. I test del limite esistenti devono passare senza modifiche.

## 12. Test automatici (senza rete né modello)

I test esistenti si adattano solo dove il comportamento cambia per decisione approvata; il piano elenca ogni test toccato con la spiegazione. In particolare `test_riassunto.py` verifica oggi che con riassunto vuoto l'agente non riceva un `SystemMessage` e che con riassunto il primo messaggio sia esattamente la cornice B.1: queste asserzioni cambiano per effetto del §10.1.

Test richiesti, come minimo:

**Validazione (`preferenze.py`, funzioni pure)**
- File completo e valido: tre valori dalla resource.
- Ogni campo mancante o non valido, uno alla volta: predefinito solo per quel campo, WARNING con il nome del campo.
- `lingua`: vuota, solo spazi, 41 caratteri, con a capo, non stringa.
- `fuso_orario`: nome inesistente, testo vuoto, non stringa, percorso tipo `../x`.
- `stile`: `Dettagliato` e ` SINTETICO ` accettati e normalizzati; `dettagliatissimo` rifiutato.
- Chiavi in più: ignorate con WARNING.
- Testo non JSON e JSON non oggetto: tutti i predefiniti, WARNING con la causa.
- `ErroreMcp` dalla lettura: tutti i predefiniti, WARNING con la causa, nessuna eccezione.
- Riga INFO finale con l'origine corretta di ogni campo, anche nel caso misto.

**Prompt**
- Testo del blocco per `sintetico` e `dettagliato` (confronto con l'Appendice A).
- L'agente riceve un solo `SystemMessage` in testa: solo preferenze con riassunto vuoto; preferenze, riga vuota e cornice B.1 con riassunto.
- Il `SystemMessage` non entra nello stato né nella sessione e non conta per la soglia.
- Prompt di Router e Revisore identici a prima, con e senza preferenze non predefinite.

**Orologio**
- `crea_orologio("America/New_York")` senza argomenti: ora di New York (istante controllato).
- Con `timezone="Asia/Tokyo"`: ora di Tokyo.
- La descrizione contiene «se omesso si usa America/New_York».
- `STRUMENTI` e `leggi_orologio` senza fuso: Europe/Rome come oggi.

**Composizione e `bind_tools`**
- Ordine discovery → preferenze → orologio (con doppi che registrano le chiamate).
- Con discovery fallita: avviso degli strumenti invariato e preferenze comunque caricate (o in fallback) tramite il loro percorso.
- Gli strumenti passati a `crea_modello` non contengono nulla legato a `utente://preferenze` (nessuno strumento con nome o descrizione della resource) e sono gli stessi di prima più l'orologio con il fuso.

**Server e client reali (server FastMCP su porta libera, come i test MCP esistenti)**
- `leggi_resource` restituisce il testo del file temporaneo.
- Modifica del file fra due letture: la seconda lettura restituisce il nuovo testo, senza riavviare il server.
- File con BOM UTF-8: testo restituito senza BOM e interpretabile con `json.loads`.
- File mancante: `ErroreMcp` con il percorso nel messaggio.
- Server spento: `ErroreMcp`.
- `list_tools()` del server reale non contiene la resource; gli strumenti esistenti restano gli stessi quattro.

**Percorso**
- Senza `PREFERENZE_PATH` il percorso predefinito punta a `<radice>/data/preferenze.json` indipendentemente dalla cartella corrente.

## 13. Docker (decisione 7) [Utente]

- Nel servizio `server-mcp` di `compose.yaml`:
  - montaggio `./data:/preferenze:ro` (cartella, in sola lettura);
  - `PREFERENZE_PATH: /preferenze/preferenze.json`.
- Si monta la cartella e non il singolo file: con il singolo file, se manca sull'host Docker crea una cartella al suo posto, e gli editor che salvano sostituendo il file possono lasciare al container la versione precedente.
- Il container vede anche il `note.db` locale, in sola lettura e senza usarlo: le note in Docker restano nel volume `dati-note` su `/data`.
- Nessun container nuovo; `assistente` e `servizi-http` invariati; il controllo di salute `verifica_mcp` invariato.
- Il file va creato prima dell'avvio (README). Se manca, il server segnala l'errore e l'host usa i valori predefiniti.
- Una modifica del file sull'host vale dalla sessione successiva (`docker compose run --rm assistente`), senza `docker compose build` e senza riavviare `server-mcp`.

## 14. Prove reali (a mano, esiti in `prove_reali/PROVE.md`)

Con LM Studio e `google/gemma-4-e2b`, in locale con tre finestre PowerShell, `NOTE_DB_PATH` temporaneo, `PREFERENZE_PATH` su un file temporaneo o su `data/preferenze.json`. Per ogni prova si registrano i log rilevanti (`assistente.preferenze`, `assistente.strumenti`, `assistente.server_mcp`), la risposta e la latenza. Sviluppo pragmatico: al massimo 2 tentativi di correzione del comportamento del modello, poi si documenta il limite e si propone come procedere.

- **R1 — Preferenze iniziali** (`italiano`, `Europe/Rome`, `sintetico`): «Che ore sono?» → l'orologio restituisce l'ora di Roma senza che l'agente chieda il fuso; una domanda in ambito → risposta in italiano e breve. Nei log: lettura della resource (`assistente.preferenze`, `assistente.server_mcp`) separata dalle chiamate ai tool (`assistente.strumenti`).
- **R2 — File modificato** (`inglese`, `America/New_York`, `dettagliato`), nuova sessione senza toccare codice né server: «Che ore sono?» → ora di New York; la stessa domanda in ambito di R1 → risposta in inglese e più dettagliata. Si osserva se il Revisore approva la risposta in inglese.
- **R3 — Campo non valido** (`"stile": "dettagliatissimo"`): WARNING sul campo, riga INFO con `stile=sintetico (predefinito)` e gli altri due dalla resource.
- **R4 — File mancante:** WARNING con la causa, tre valori predefiniti, conversazione funzionante con tutti gli strumenti MCP.
- **R5 — Server MCP spento:** avviso degli strumenti (invariato) e WARNING delle preferenze, distinti; conversazione funzionante con strumenti locali e HTTP.
- **R6 — Docker:** `Copy-Item preferenze.example.json data\preferenze.json`, `docker compose build`, `docker compose run --rm assistente`, «Che ore sono?»; poi modifica del file sull'host e nuova `docker compose run --rm assistente` senza ricostruire: le preferenze cambiano. `.env` ripristinato dopo la prova.

Una risposta simulata non dimostra il comportamento del modello. Ciò che non si riesce a provare dal vivo va dichiarato in `PROVE.md`.

## 15. Criteri di accettazione

- Suite automatica verde, con i test del §12.
- Prove reali R1, R2, R4, R5 e R6 riuscite, oppure i fallimenti documentati e discussi con l'utente; R3 è un'osservazione da registrare.
- README aggiornato: file delle preferenze (creazione, formato, valori ammessi), `PREFERENZE_PATH`, valori predefiniti, log, montaggio Docker, limitazioni.
- `preferenze.example.json` versionato; `data/preferenze.json` mai in Git.
- `PROVE.md` con la sezione dello Step 4.
- `CLAUDE.md` aggiornato solo con autorizzazione esplicita, a fine Step (modulo `preferenze`, variabile `PREFERENZE_PATH`).
- Preservati: Router, Revisore e Riassunto con il loro fail-open; `Sessione` immutabile; conferma di `elimina_nota`; avvio ridotto senza servizi; strumenti MCP mai riscritti a mano.

## 16. Limitazioni e compromessi dichiarati

- Il rifiuto del Router, gli avvisi e le conferme restano in italiano qualunque sia `lingua`. **[Utente]**
- `lingua` è testo libero: il programma non verifica che sia una lingua reale; un valore strano arriva al modello così com'è. **[Utente]**
- Il rispetto di lingua e stile dipende dal modello locale: il programma garantisce solo il fuso dell'orologio senza argomenti. **[Utente]**
- Con il server spento la lettura delle preferenze fa un tentativo in più, che fallisce subito (al massimo `MCP_TIMEOUT`). **[Utente]**
- Le preferenze non si aggiornano durante la sessione: serve un nuovo avvio. **[Utente]**
- In Docker il `server-mcp` vede tutta la cartella `data/` dell'host in sola lettura, compreso il `note.db` locale. **[Utente]**
- Il prompt dell'agente si allunga di qualche riga a ogni chiamata.

## 17. Review indipendente della specifica (2026-11-16)

Un revisore senza il contesto della conversazione ha confrontato la specifica con il codice su `dev` e con FastMCP 4.1.6 installato. Non ha trovato contraddizioni sostanziali. Rilievi:

| Rilievo | Esito |
|---|---|
| Il `Dockerfile` copia anche `requirements.txt` | corretto al §3 |
| `crea_server` con un parametro nuovo romperebbe le chiamate esistenti | parametro facoltativo, §5.3 |
| `Copy-Item` fallisce se `data/` non esiste su un clone nuovo | aggiunto `New-Item`, §5.1 |
| Su Windows `ZoneInfo` accetterebbe nomi con maiuscole sbagliate (`america/new_york`), a differenza di Linux | **non confermato**: nel `.venv` del progetto `ZoneInfo("america/new_york")` solleva `ZoneInfoNotFoundError` (i dati vengono dal pacchetto `tzdata`). Nessuna modifica. |

## 18. Lasciato al costruttore

- Formato esatto dei messaggi di log, nei limiti dei §5.3 e §8.
- Nomi interni di `preferenze.py`, salvo `Preferenze`, `PREFERENZE_PREDEFINITE` e `carica_preferenze`.
- Forma esatta di `componi_strumenti`, nei limiti del §6.3.
- Descrizione testuale della resource sul server.

## Appendice A — Blocco delle preferenze nel prompt di sistema

```
Preferenze dell'utente (valide per tutta la sessione):
- Rispondi sempre in {lingua}.
- Fuso orario predefinito: {fuso_orario}. Usalo per data e ora quando l'utente non indica un altro fuso.
- Stile: {testo_stile}
```

`{testo_stile}`:
- `sintetico` → `risposte brevi ed essenziali, senza dettagli non richiesti.`
- `dettagliato` → `risposte complete, con spiegazioni ed esempi quando sono utili.`

Con riassunto non vuoto il `SystemMessage` è: blocco qui sopra, una riga vuota, cornice B.1 dello Step 3 invariata.
