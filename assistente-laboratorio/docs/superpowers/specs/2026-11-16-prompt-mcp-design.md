# Lezione 6, Step 5 — Prompt MCP: comandi riusabili nella CLI: specifica

Stato: **approvata il 2026-11-16**, dopo il builder check (§17). Brainstorming concluso il 2026-11-16 con otto decisioni approvate dall'utente, più la modifica alla decisione 3 dopo il builder check (§17). Le voci marcate **[Utente]** sono decisioni dell'utente; quelle marcate **[Scelta mia]** sono scelte del progettista, da controllare in lettura.

## 1. Intenzione

Lo Step 5 introduce i primi **prompt MCP** del progetto. Uno strumento lo sceglie il modello; una resource (Step 4) la legge l'host da solo all'avvio; un prompt lo richiama **l'utente**, in modo esplicito, con un comando della CLI. Il server conserva il modello di istruzioni con i suoi argomenti; l'host lo elenca, lo compila tramite il server e manda i messaggi ottenuti al grafo **come qualsiasi altra domanda**.

La dimostrazione attesa:
1. l'utente scrive `/prompts` e vede nome, descrizione e argomenti dei due prompt, presi dal server;
2. scrive `/prompt spiega argomento="Model Context Protocol" livello=base`: il terminale mostra il testo compilato, il log registra prompt, argomenti e messaggi, e l'agente risponde a livello base passando per Router e Revisore;
3. dopo qualche turno scrive `/prompt riassumi_conversazione` e ottiene il riassunto della sessione in corso;
4. una richiesta con un argomento mancante o sconosciuto viene bloccata dall'host, senza alcuna chiamata al modello.

## 2. Obiettivi, non obiettivi, anti-obiettivi

**Testo della slide** («Step 5 — Prompt: comandi riusabili nella CLI», `../LLM_Lez_6.pdf`, pagina 10; testo recuperato e fornito dall'utente il 2026-11-16):

> Il server MCP espone due prompt generici. La CLI li elenca e permette all'utente di richiamarli. MCP non prevede un comando standard: i comandi li definisce la vostra CLI.

**Obiettivo:** «Un prompt richiamato dall'utente passa dal grafo come qualsiasi altra domanda, compresi router, strumenti e revisore.»

**Cosa realizzare:**
1. Prompt `spiega(argomento, livello)` e `riassumi_conversazione(stile)`.
2. Comando `/prompts` con nome, descrizione e argomenti di ogni prompt.
3. Comando `/prompt nome argomento=valore`: i messaggi ottenuti si aggiungono alla cronologia e vanno al grafo.
4. Controllo nell'host rispetto a `prompts/list`: argomenti obbligatori mancanti o sconosciuti bloccano la richiesta, senza chiamare il modello.

**Evidenze richieste:**
- `/prompt spiega argomento="Model Context Protocol" livello=base`: risposta adeguata al livello.
- `riassumi_conversazione` riassume i turni della sessione corrente.
- Log con prompt richiamato, argomenti e messaggi ottenuti dal server.

**Slide introduttiva (contesto):** un prompt MCP è un modello di istruzioni con argomenti, salvato sul server e condiviso dai client; lo richiama esplicitamente l'utente; il server espone nome, descrizione e argomenti; l'host elenca i prompt e li mostra come comandi; quando l'utente seleziona un prompt, l'host ottiene dal server i messaggi compilati e li passa al grafo. Esempio della slide: `@mcp.prompt` con `spiega(argomento: str, livello: str = "base")`, livelli base, intermedio, avanzato.

**Requisiti aggiuntivi dell'utente:** **[Utente]**
- soluzioni pragmatiche, semplici e coerenti con l'architettura attuale; nessuna riscrittura di componenti funzionanti;
- i prompt MCP non vanno mai in `bind_tools`; nome, descrizione e argomenti vengono dalla discovery, mai scritti a mano nel client;
- da preservare: Router, Revisore, Riassunto con il loro fail-open; un solo `SystemMessage` temporaneo; `Sessione` immutabile; conferma di `elimina_nota`; avvio ridotto senza servizi; preferenze dello Step 4.

**Non obiettivi:** agente come servizio HTTP, back-end con salvataggio delle chat, front-end, Compose per componente (step successivi); altri comandi della CLI oltre a `/prompts` e `/prompt`; completamento automatico o menu interattivi; cache dei prompt.

**Anti-obiettivi** (sarebbe un fallimento anche se funzionasse):
- un prompt che salta Router o Revisore, o un percorso del grafo dedicato ai prompt;
- nomi, descrizioni, argomenti o livelli ammessi scritti a mano nel client;
- un prompt passato al modello come strumento;
- una richiesta non valida che arriva comunque al modello o modifica la cronologia.

## 3. Architettura attuale (verificata su `dev`, `b1d884f`, 696 test verdi)

Avvio: `componi_strumenti` (discovery MCP, preferenze dalla resource, orologio) → `crea_modello(bind_tools: solo strumenti)` → `costruisci_grafo`. Turno: `START → riassunto → router → (modello ⇄ strumenti → revisore) | rifiuto → END`. Il terminale (`esegui_chat`) legge righe con `input("Tu: ")`; `esci` termina; non esistono altri comandi. La cronologia vive nella `Sessione` immutabile; `esegui_turno` passa copie dei messaggi e, se il turno fallisce, restituisce lo stesso oggetto `Sessione`.

Il grafo individua la domanda del turno come **l'ultimo `HumanMessage` che non è un'osservazione del Revisore** (Router: `_indice_domanda_attuale`; Revisore: `inizio_turno` scritto dal Router; Riassunto: `inizi_turni`).

### 3.1 Verifica della libreria (2026-11-16, FastMCP 4.1.6 installato, script usa e getta fuori dalla repository)

- `Client.list_prompts(max_pages=250) -> list[mcp.types.Prompt]`: ogni `Prompt` ha `name`, `description`, `arguments` (lista di `PromptArgument` con `name`, `description`, `required`).
- `Client.get_prompt(name, arguments=None, *, version=None, meta=None) -> GetPromptResult`: `messages` è una lista di `PromptMessage` con `role` (`"user"` o `"assistant"`) e `content` (`TextContent` con `.text` per i prompt testuali). Una funzione `@server.prompt` che restituisce `str` produce **un solo messaggio `user`**.
- Argomento obbligatorio mancante: il server rifiuta (`MCPError: Missing required arguments: {...}`).
- **Argomento sconosciuto: il server lo ignora in silenzio** e compila il prompt. Il controllo nell'host è quindi necessario.
- Un `PromptError` sollevato dalla funzione del prompt arriva al client come errore con il messaggio originale (`MCPError: livello non valido: esperto`); il server registra un errore («Error rendering prompt»).
- Argomenti tipizzati `Literal[...]` o `Annotated[str, Field(description=...)]`: FastMCP aggiunge alla descrizione dell'argomento un testo inglese automatico («Provide a value matching the following JSON schema…»). Con argomenti `str` semplici la descrizione dell'argomento è `None`.

Verifiche fatte con un `Client` in memoria. Il comportamento sul trasporto Streamable HTTP (classe dell'eccezione lato client) va confermato dal primo test di `mcp_client` (§12.2).

## 4. Architettura nuova

```
Riga dell'utente (terminale.esegui_chat)
  "esci"            → fine
  inizia con "/"    → comandi (mai al modello così com'è)
     /prompts       → elenca_prompt (list_prompts)            → stampa elenco
     /prompt ...    → scomponi riga → elenca_prompt → controlla_richiesta
                       ├─ problemi → messaggio, nessun turno, Sessione invariata
                       └─ ok → ottieni_prompt (get_prompt) → converti in messaggi
                              → stampa "[prompt nome] testo" → esegui_turno_messaggi → grafo invariato
  altrimenti        → esegui_turno (domanda normale, come oggi)
```

Il grafo, lo stato, i nodi, l'instradamento, il limite di passaggi, `preferenze.py`, `strumenti.py` e Docker Compose **non cambiano**.

### 4.1 Moduli

| Modulo | Modifica |
|---|---|
| `server_mcp.py` | due `@server.prompt` in `crea_server` (§5) |
| `mcp_client.py` | `PromptMcp`, `ArgomentoPrompt`, `elenca_prompt`, `ottieni_prompt` (§6) |
| `comandi.py` (nuovo) | funzioni pure: scomposizione della riga, controllo, formato di `/prompts`, conversione dei messaggi (§7–§9) |
| `terminale.py` | smistamento dei comandi in `esegui_chat`, `esegui_turno_messaggi`, collegamento in `main` (§10) |

## 5. I prompt sul server (decisioni 1, 6, 7) [Utente]

In `crea_server`, accanto a strumenti e resource (che non cambiano), due `@server.prompt` con `description` esplicita in italiano. Argomenti di tipo `str` semplice, senza descrizione propria (§3.1): tutto ciò che serve all'utente sta nella descrizione del prompt. Ogni prompt restituisce **un solo messaggio `user`** (la funzione restituisce `str`). I testi esatti sono nell'Appendice A.

### 5.1 `spiega(argomento: str, livello: str = "base")`

- Descrizione: «Spiega un argomento al livello scelto: base, intermedio o avanzato (predefinito base).»
- `argomento` obbligatorio, `livello` facoltativo con predefinito `"base"`.
- Il server controlla `livello`: se non è esattamente `base`, `intermedio` o `avanzato` solleva `PromptError("livello non valido: <valore> (valori ammessi: base, intermedio, avanzato)")`. **[Scelta mia]** confronto esatto, senza normalizzare maiuscole o spazi: il messaggio d'errore indica i valori corretti.
- Il significato dei livelli (guida) sta solo sul server (Appendice A).

### 5.2 `riassumi_conversazione(stile: str = "breve")`

- Descrizione **[Scelta mia]**: «Riassume la conversazione della sessione in corso nello stile indicato, testo libero (predefinito breve).»
- `stile` facoltativo, testo libero, predefinito `"breve"` (sulla slide non c'è un predefinito: scelta approvata nella decisione 1). Il server non lo controlla.
- Il server non vede la conversazione: il prompt chiede all'agente di riassumere ciò che ha nel proprio contesto (§11.2).

### 5.3 Log del server

Nessun log aggiuntivo richiesto **[Scelta mia]**: l'evidenza del richiamo sta nei log dell'host (§6.3). L'errore che FastMCP registra per un `PromptError` resta com'è (limite §16).

## 6. Recupero dei prompt dall'host (decisione 2) [Utente]

### 6.1 Client MCP

In `mcp_client.py`, sullo stesso schema di `leggi_resource`: ponte `_esegui`, `asyncio.timeout(timeout)`, `Client(url, timeout=timeout)`, ogni eccezione convertita in `ErroreMcp` con il testo ripulito da `_testo_errore`.

```python
@dataclass(frozen=True)
class ArgomentoPrompt:
    nome: str
    descrizione: str      # "" se il server non la fornisce
    obbligatorio: bool    # PromptArgument.required; None vale False

@dataclass(frozen=True)
class PromptMcp:
    nome: str
    descrizione: str      # "" se assente
    argomenti: tuple[ArgomentoPrompt, ...]   # () se il server non ne dichiara

def elenca_prompt(url: str, timeout: float = 10.0) -> tuple[PromptMcp, ...]: ...
def ottieni_prompt(url: str, nome: str, argomenti: dict[str, str], timeout: float = 10.0) -> list[tuple[str, str]]: ...
```

- `elenca_prompt` copia i campi da `list_prompts()`, nell'ordine del server. Niente è scritto a mano.
- `ottieni_prompt` restituisce i messaggi come coppie `(ruolo, testo)`, con il ruolo così come arriva (`"user"`, `"assistant"`). Un messaggio il cui contenuto non ha `.text` (immagine, resource incorporata) → `ErroreMcp("messaggio non testuale nel prompt <nome>")`.
- Messaggi d'errore **[Scelta mia]**: `elenca_prompt` → `ErroreMcp(f"discovery dei prompt impossibile su {url}: {testo}")`; `ottieni_prompt` → `ErroreMcp(f"prompt {nome} non ottenuto da {url}: {testo}")`, dove `testo` per un rifiuto del server è il suo messaggio (es. «livello non valido: esperto (valori ammessi: …)»).
- Nessuna delle due funzioni produce strumenti: i prompt non arrivano mai a `componi_strumenti` né a `bind_tools`.

### 6.2 Quando

Discovery **al momento del comando**, nessuna cache, nessuna modifica all'avvio:
- `/prompts` chiama `elenca_prompt`;
- `/prompt` chiama `elenca_prompt` (per il controllo, §8) e, se il controllo passa, `ottieni_prompt`.

L'avvio ridotto resta identico; se il server MCP parte dopo l'agente, i prompt diventano disponibili senza riavviare. URL e timeout sono `config.mcp_url` e `config.mcp_timeout`, gli stessi degli strumenti MCP.

### 6.3 Log (logger `assistente.mcp`) — evidenza della slide

- `INFO prompt scoperti su <url>: [nomi]` dopo ogni `elenca_prompt` riuscito;
- `INFO prompt richiamato: nome=<nome> argomenti=<dict>` prima di `get_prompt`;
- `INFO prompt ottenuto: nome=<nome> messaggi=[(ruolo, testo), ...]` dopo `get_prompt`;
- `WARNING` con il testo dell'`ErroreMcp` quando una delle due chiamate fallisce.

## 7. Comandi della CLI (decisione 3) [Utente]

### 7.1 Riconoscimento

In `esegui_chat`, dopo `ripulisci_input(...).strip()`, il controllo di `esci` e quello della riga vuota (invariati), **prima** di `esegui_turno`: se la riga inizia con `/` è un comando e non va mai al modello così com'è. Il nome del comando è il primo blocco separato da spazi, confrontato in modo sensibile alle maiuscole:
- `/prompts` (nient'altro sulla riga) → elenco (§7.3);
- `/prompt` → richiamo (§7.2);
- `/prompts` seguito da altro testo (`/prompts x`) → «Uso: /prompts» **[Scelta mia]**;
- qualsiasi altro nome → «Comando sconosciuto. Comandi disponibili: /prompts, /prompt nome argomento=valore».

In tutti questi casi la `Sessione` resta lo stesso oggetto se non parte un turno. **Conseguenza dichiarata:** una domanda che inizia con `/` non arriva più al modello.

### 7.2 Scomposizione di `/prompt`

Funzione pura `scomponi_richiesta(riga) -> (nome, argomenti)` oppure un errore d'uso. Usa `shlex.shlex(riga, posix=True)` configurato così (decisione 3, modificata dopo il builder check) **[Utente]**: `whitespace_split = True`, `quotes = '"'` (solo le virgolette doppie delimitano un valore), `escape = ''` (nessun carattere di escape), `commenters = ''` (nessun commento). Verificato con una sonda il 2026-11-16:
- `argomento="Model Context Protocol"` → valore `Model Context Protocol`, senza virgolette;
- `argomento=dell'MCP` e `argomento="l'intelligenza artificiale"` → apostrofo conservato;
- `argomento=C:\cartella\file` → barre rovesciate conservate;
- `#` è un carattere normale.

Le virgolette singole non delimitano valori. Danno un messaggio d'uso e nessuna chiamata al server:
- virgolette doppie non chiuse (`ValueError` di `shlex`);
- nome del prompt mancante (`/prompt` da solo);
- un elemento dopo il nome senza `=`, o con la chiave vuota (`=valore`);
- una chiave ripetuta.

Si divide sul primo `=`: `a=b=c` dà chiave `a`, valore `b=c`. I valori restano stringhe. Un valore vuoto (`livello=`) è ammesso qui e giudicato in §8.

Messaggio d'uso generico **[Scelta mia]**: «Uso: /prompt nome argomento=valore … (valori con spazi tra virgolette doppie). Usa /prompts per l'elenco.», preceduto dalla causa (es. «Virgolette non chiuse.»).

### 7.3 Formato di `/prompts`

Costruito solo dai `PromptMcp` restituiti da `elenca_prompt`:

```
Prompt disponibili:
/prompt spiega — Spiega un argomento al livello scelto: base, intermedio o avanzato (predefinito base).
    argomento (obbligatorio)
    livello (facoltativo)
/prompt riassumi_conversazione — Riassume la conversazione della sessione in corso nello stile indicato, testo libero (predefinito breve).
    stile (facoltativo)
```

- Se l'argomento ha una descrizione non vuota, si aggiunge dopo la parentesi: `argomento (obbligatorio): <descrizione>`.
- Se la descrizione del prompt è vuota, la riga termina col nome (niente trattino).
- Nessun prompt: «Nessun prompt disponibile.»
- Errore di `elenca_prompt`: «Prompt MCP non disponibili: <testo dell'ErroreMcp>».

## 8. Controllo degli argomenti nell'host (decisione 4) [Utente]

Funzione pura `controlla_richiesta(prompts, nome, argomenti) -> list[str]` in `comandi.py`, applicata ai `PromptMcp` appena restituiti da `elenca_prompt`. Elenco vuoto = via libera.

- **Prompt sconosciuto** (nome non presente): «Prompt sconosciuto: <nome>. Usa /prompts per l'elenco.» (unico problema riportato in questo caso).
- **Argomenti obbligatori mancanti** (`obbligatorio=True` e chiave assente): «Argomenti obbligatori mancanti: <nomi>.»
- **Argomenti sconosciuti** (chiave non dichiarata): «Argomenti sconosciuti: <nomi>. Argomenti accettati: <nomi dichiarati>.» (se il prompt non ne dichiara: «Argomenti accettati: nessuno.»)
- **Valore vuoto o di soli spazi**, anche per argomenti facoltativi: «Valore vuoto per: <nomi>.» Chi vuole il predefinito omette l'argomento.

Tutti i problemi si riportano insieme, nell'ordine dei punti sopra, e il messaggio termina con la riga d'uso del prompt costruita dalla discovery: `Uso: /prompt spiega argomento=… [livello=…]` (obbligatori senza parentesi, facoltativi tra parentesi quadre, nell'ordine dichiarato dal server). I nomi negli elenchi seguono l'ordine della riga dell'utente (sconosciuti, vuoti) o del server (mancanti) **[Scelta mia]**.

Se un controllo fallisce: nessuna chiamata a `get_prompt`, nessun turno, nessun modello, `Sessione` invariata; log `WARNING` sul logger `assistente.comandi` con nome, argomenti e problemi **[Scelta mia: logger]**.

**Non controllato nell'host:** il contenuto dei valori. I livelli ammessi di `spiega` li conosce solo il server (§5.1). Un rifiuto del server arriva come `ErroreMcp` da `ottieni_prompt`; la CLI stampa «Prompt non eseguito: <testo dell'ErroreMcp>» e non parte nessun turno.

## 9. Conversione dei messaggi (decisione 5) [Utente]

Funzione pura `converti_messaggi(coppie) -> list[BaseMessage]` in `comandi.py`:
- `"user"` → `HumanMessage(testo)`; `"assistant"` → `AIMessage(testo)`;
- nessun `additional_kwargs` speciale **[Scelta mia]**: il messaggio è una domanda come le altre;
- elenco vuoto, ruolo diverso dai due, oppure ultimo messaggio non `user` → errore: la CLI stampa «Prompt non utilizzabile: l'ultimo messaggio non è dell'utente.» (o «…: nessun messaggio.» / «…: ruolo non riconosciuto: <ruolo>.») e non parte nessun turno.

L'ultimo `HumanMessage` diventa la domanda del turno per Router, Revisore e Riassunto. Eventuali messaggi precedenti dello stesso prompt entrano nella cronologia prima della domanda e sono visti come contesto.

## 10. Terminale (decisioni 3 e 5) [Utente]

### 10.1 `esegui_turno_messaggi`

```python
def esegui_turno_messaggi(grafo, sessione, nuovi: Sequence[BaseMessage], max_passaggi, *, max_revisioni) -> tuple[Sessione, str]
def esegui_turno(grafo, sessione, domanda: str, max_passaggi, *, max_revisioni):
    return esegui_turno_messaggi(grafo, sessione, [HumanMessage(domanda)], max_passaggi, max_revisioni=max_revisioni)
```

`esegui_turno_messaggi` contiene il corpo attuale di `esegui_turno` con `[*copie della sessione, *copie di nuovi]` al posto di `[*copie, HumanMessage(domanda)]`. Tutto il resto resta: copie con `model_copy()`, `recursion_limit`, gestione di `GraphRecursionError` e `openai.OpenAIError`, la stessa `Sessione` restituita in caso di fallimento (i messaggi del prompt non entrano nella cronologia), avviso di risposta vuota. La firma di `esegui_turno` non cambia.

### 10.2 `esegui_chat`

Nuovi parametri keyword-only, con predefinito `None`: `elenca: Callable[[], tuple[PromptMcp, ...]] | None` e `ottieni: Callable[[str, dict[str, str]], list[tuple[str, str]]] | None`. In `main` sono `lambda: elenca_prompt(config.mcp_url, config.mcp_timeout)` e `lambda nome, arg: ottieni_prompt(config.mcp_url, nome, arg, config.mcp_timeout)`. Con `None` i comandi rispondono «Prompt MCP non disponibili: client non configurato.» **[Scelta mia]** (serve ai test esistenti, che non passano i parametri).

Per un `/prompt` valido, prima del turno il terminale stampa con `scrivi` una riga per messaggio: `[prompt <nome>] <testo>` per i messaggi `user`, `[prompt <nome>, assistente] <testo>` per quelli `assistant` **[Scelta mia]**; poi esegue `esegui_turno_messaggi` e stampa la risposta come per una domanda normale.

`EOFError` e `KeyboardInterrupt` durante un comando terminano la chat come oggi (il blocco `try` esistente li copre). Un `ErroreMcp` non interrompe mai la chat.

## 11. Passaggio nel grafo, Riassunto e preferenze (decisioni 5, 6, 7) [Utente]

### 11.1 Grafo

Nessuna modifica: il prompt segue `riassunto → router → modello ⇄ strumenti → revisore`. Limite di passaggi e formula invariati. Il Router classifica il testo compilato: se l'argomento di `spiega` è fuori da `AMBITO_AGENTE`, il rifiuto è il comportamento voluto.

### 11.2 `riassumi_conversazione` e la cronologia compressa

Nessun meccanismo nuovo. L'agente riceve già il riassunto dei turni vecchi (cornice B.1 nel `SystemMessage` unico) e i messaggi rimasti nello stato: insieme coprono l'intera sessione corrente. Il prompt (Appendice A) chiede di basarsi su entrambi, di non aggiungere informazioni, di non usare strumenti e di dire in una frase se non c'è nulla da riassumere. «La nostra conversazione» e «di questa sessione» servono a far riconoscere al Router una richiesta sulla conversazione in corso. Il Riassunto dello Step 3 non cambia; il terminale non legge `Sessione.riassunto`.

**Alternativa scartata:** trascrizione della cronologia passata come argomento dal terminale (argomento non dell'utente, messaggio lungo, duplicazione del Riassunto).

**Rischio del Router:** può rifiutare per errore `riassumi_conversazione`. Regola pragmatica: al massimo **2 tentativi** di correzione modificando **solo il testo del prompt sul server**; le istruzioni del Router (Appendice A dello Step 1) non si toccano senza decisione esplicita dell'utente; poi si documenta il limite.

### 11.3 Preferenze

Il messaggio del prompt è un `HumanMessage`: le preferenze in cima al `SystemMessage` si applicano da sole. `preferenze.py`, il grafo e il `SystemMessage` non cambiano. In caso di conflitto tra lo stile delle preferenze e l'argomento del prompt (`livello`, `stile`) prevale l'argomento per quel turno; la lingua resta quella delle preferenze. Lo dice il testo del prompt (Appendice A). L'host non usa le preferenze come predefiniti degli argomenti.

## 12. Test automatici (senza modello né rete esterna)

Proporzionati al rischio (decisione 8) [Utente].

### 12.1 `server_mcp` (Client FastMCP in memoria)
- `list_prompts` restituisce `spiega` e `riassumi_conversazione` con le descrizioni di §5 e gli argomenti con `required` corretto (`argomento` True, `livello` False, `stile` False).
- `get_prompt("spiega", ...)` per i tre livelli e senza livello: un solo messaggio `user` con il testo esatto dell'Appendice A.
- `get_prompt("spiega", {"argomento": "x", "livello": "esperto"})` → errore con «valori ammessi».
- `get_prompt("riassumi_conversazione", ...)` con e senza `stile`: testo esatto dell'Appendice A.
- Strumenti e resource invariati (i test esistenti lo coprono).

### 12.2 `mcp_client` (server reale su porta libera, `tests/server_reale.py`)
- `elenca_prompt` restituisce `PromptMcp` con i campi copiati dal server.
- `ottieni_prompt` restituisce le coppie `(ruolo, testo)`.
- Rifiuto del server (`livello=esperto`) → `ErroreMcp` con il messaggio del server; questo test conferma anche la classe dell'eccezione sul trasporto HTTP (§3.1).
- Porta chiusa → `ErroreMcp` per entrambe le funzioni.
- Messaggio non testuale → `ErroreMcp` (server di prova con un prompt che restituisce un'immagine, oppure client finto: scelta del costruttore).

### 12.3 `comandi` (funzioni pure)
- Scomposizione: virgolette doppie, virgolette doppie non chiuse, apostrofo senza virgolette e dentro virgolette, barre rovesciate conservate, `#` come carattere normale, `=` mancante, chiave vuota, chiave ripetuta, nome mancante, `a=b=c`, valore vuoto ammesso.
- Controllo: prompt sconosciuto, mancante, sconosciuto, vuoto (anche facoltativo), più problemi insieme nell'ordine di §8, riga d'uso, richiesta valida → elenco vuoto.
- Formato di `/prompts`: con e senza descrizioni, nessun prompt.
- Conversione: `user`/`assistant`, ultimo non `user`, elenco vuoto, ruolo sconosciuto.

### 12.4 `terminale` (grafo finto)
- `/prompts`, `/prompt` non valido, comando sconosciuto, errore di `elenca`/`ottieni`, parametri `None`: il grafo **non** viene invocato e la chat continua.
- `/prompt` valido: il grafo riceve la cronologia più i messaggi convertiti; la riga `[prompt …]` viene scritta prima della risposta; la sessione successiva contiene i messaggi del prompt.
- Turno di prompt fallito (`GraphRecursionError`): la `Sessione` è lo stesso oggetto.
- I test esistenti di `esegui_turno` ed `esegui_chat` restano invariati (da confermare con la sonda prima del piano).

### 12.5 Integrazione
Un solo test: grafo reale con modelli finti (classificatore, agente con una chiamata a uno strumento, revisore, riassuntore) in cui i messaggi di un prompt attraversano riassunto, router, agente, strumento e revisore.

## 13. Docker

Nessuna modifica: i prompt viaggiano sullo stesso server MCP già in Compose. Dopo le modifiche a `src/` serve `docker compose build`.

## 14. Prove reali (a mano, esiti in `prove_reali/PROVE.md`)

Script pilota nella scratchpad che avvia i servizi e pilota il terminale via stdin, con `NOTE_DB_PATH` e `PREFERENZE_PATH` temporanei (preferenze dell'esempio: italiano, Europe/Rome, sintetico).

| Prova | Che cosa | Esito atteso |
|---|---|---|
| R1 | `/prompts` | nome, descrizione e argomenti dei due prompt |
| R2 | `/prompt spiega argomento="Model Context Protocol" livello=base` | risposta adeguata al livello base; log con prompt, argomenti e messaggi; Router e Revisore nel log |
| R3 | 2–3 turni, poi `/prompt riassumi_conversazione` | riassunto dei turni della sessione |
| R4 | come R3 con `SOGLIA_RIASSUNTO` bassa, dopo una compressione | riassunto che comprende anche i turni compressi |
| R5 | argomento obbligatorio mancante; argomento sconosciuto | richiesta bloccata, nessuna chiamata al modello nel log |
| R6 | server MCP spento | avvio ridotto; `/prompts` → «Prompt MCP non disponibili: …» |
| R7 | Docker Compose: `/prompts` e un `/prompt spiega` | come R1–R2 nel container; `.env` ripristinato |

Una prova per ogni modifica di testo dei prompt; al massimo 2 tentativi sul comportamento del modello, poi si documenta il limite.

## 15. Criteri di accettazione

- I due prompt sono esposti dal server con le descrizioni e i testi di questa specifica.
- `/prompts` e `/prompt` funzionano come in §7–§10; nome, descrizione e argomenti vengono solo dalla discovery.
- Le richieste non valide (§7.2, §8, §9, errori MCP) non invocano il grafo e lasciano la `Sessione` invariata.
- Un prompt valido passa per riassunto, router, agente, strumenti e revisore senza modifiche al grafo.
- I prompt non compaiono mai in `bind_tools`; avvio, avvio ridotto, preferenze, conferma di `elimina_nota` invariati.
- Suite completa verde; prove R1–R7 registrate in `PROVE.md` con esito; README aggiornato con la sezione «Comandi della CLI» e comandi verificati.

## 16. Limitazioni e compromessi dichiarati

- Una domanda che inizia con `/` non arriva più al modello.
- Solo le virgolette doppie delimitano un valore; un valore non può contenere virgolette doppie (non c'è escape).
- I messaggi della CLI (elenco, errori, riga `[prompt …]`) restano in italiano qualunque sia la lingua preferita; i testi dei prompt sono in italiano e la lingua della risposta dipende dal modello.
- Dopo una compressione il riassunto della sessione vale quanto il riassunto dello Step 3 (i dettagli già persi non tornano); il turno di riassunto entra nella cronologia come un turno normale.
- Il Router può rifiutare `spiega` su argomenti fuori ambito (voluto) e, per errore, `riassumi_conversazione`.
- Un `PromptError` del server lascia nel log del server la traccia d'errore di FastMCP.
- Ogni `/prompt` fa due richieste al server (`list_prompts` e `get_prompt`).

## 17. Builder check della specifica (2026-11-16)

Un revisore indipendente ha confrontato la specifica con il codice (`terminale.py`, `mcp_client.py`, `server_mcp.py`, `router.py`, `revisore.py`, `riassunto.py` e i test di `esegui_turno` ed `esegui_chat`): nessuna contraddizione grave. Rilievi:
1. `shlex.split` fallisce sugli apostrofi italiani non quotati (`argomento=dell'MCP` → «No closing quotation»). **Deciso dall'utente:** `shlex` con le sole virgolette doppie e senza escape (§7.2).
2. §7.1 si contraddiceva su `/prompts x`: corretto, il messaggio è «Uso: /prompts».

## 18. Lasciato al costruttore

- Nomi interni delle funzioni ausiliarie e organizzazione dei test.
- Come produrre il messaggio non testuale nel test di §12.2.
- Formattazione esatta dei log, nel rispetto dei contenuti di §6.3 e §8.

## Appendice A — Testi dei prompt (testo esatto)

### A.1 `spiega`

```text
Spiega l'argomento «{argomento}» a livello {livello}. {guida_livello} Per questa risposta il livello richiesto prevale sullo stile indicato nelle preferenze.
```

`guida_livello`:
- `base`: `Usa un linguaggio semplice, senza dare per scontate conoscenze precedenti, e aggiungi un esempio concreto.`
- `intermedio`: `Presenta i concetti principali e la terminologia corretta, dando per scontate le basi.`
- `avanzato`: `Entra nei dettagli tecnici, nei compromessi e nei casi limite.`

### A.2 `riassumi_conversazione`

```text
Riassumi la nostra conversazione di questa sessione fino a questo momento, in questo stile: {stile}. Basati sul riassunto della conversazione precedente, se è presente, e sui messaggi che precedono questa richiesta. Riporta solo ciò che è stato davvero detto o fatto, compresi i risultati degli strumenti, senza aggiungere informazioni nuove. Non serve usare strumenti. Se non ci sono ancora turni da riassumere, dillo in una frase. Per questa risposta lo stile richiesto prevale sullo stile indicato nelle preferenze.
```
