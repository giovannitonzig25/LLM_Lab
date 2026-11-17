// Pagina di chat (Step 8). Parla solo con il back-end, tramite l'inoltro /api del servizio del front-end.
// Percorsi e JSON dal contratto OpenAPI: docs/superpowers/specs/2026-11-17-openapi-backend.json.
// Nessun timeout: un turno dell'agente può durare minuti. I testi entrano sempre con textContent.
"use strict";

const $ = (id) => document.getElementById(id);
const el = {
  nuovaChat: $("nuova-chat"),
  elenco: $("elenco-chat"),
  elencoVuoto: $("elenco-vuoto"),
  titolo: $("titolo-chat"),
  messaggi: $("messaggi"),
  benvenuto: $("benvenuto"),
  attesa: $("attesa"),
  errore: $("errore"),
  testoErrore: $("testo-errore"),
  chiudiErrore: $("chiudi-errore"),
  modulo: $("modulo"),
  domanda: $("domanda"),
  invia: $("invia"),
  conferma: $("conferma"),
  elencoConferme: $("elenco-conferme"),
};

let chatAttiva = null; // id della chat aperta, null se nessuna
let occupato = false; // true durante l'attesa della risposta

// --- Chiamate al back-end -------------------------------------------------

async function chiama(metodo, percorso, corpo) {
  const opzioni = { method: metodo, headers: {} };
  if (corpo !== undefined) {
    opzioni.headers["Content-Type"] = "application/json";
    opzioni.body = JSON.stringify(corpo);
  }
  let risposta;
  try {
    risposta = await fetch("/api" + percorso, opzioni);
  } catch {
    throw new Error("Il servizio dell'interfaccia non risponde. Controlla che sia avviato e ricarica la pagina.");
  }
  if (risposta.status === 204) return null;
  let dati = null;
  try {
    dati = await risposta.json();
  } catch {
    // corpo non JSON: si usa il testo generico qui sotto
  }
  if (!risposta.ok) {
    if (dati && typeof dati.errore === "string") throw new Error(dati.errore);
    if (risposta.status === 422) throw new Error("Richiesta non valida (HTTP 422).");
    throw new Error(`Errore inatteso (HTTP ${risposta.status}).`);
  }
  return dati;
}

const elencaChat = () => chiama("GET", "/chat");
const creaChat = () => chiama("POST", "/chat");
const leggiChat = (id) => chiama("GET", `/chat/${id}`);
const eliminaChat = (id) => chiama("DELETE", `/chat/${id}`);
const inviaMessaggio = (id, testo, conferme) => chiama("POST", `/chat/${id}/messaggi`, { testo, conferme });

// --- Visualizzazione -------------------------------------------------------

function formattaData(iso) {
  return iso ? new Date(iso).toLocaleString("it-IT", { dateStyle: "short", timeStyle: "short" }) : "";
}

function mostraErrore(testo) {
  el.testoErrore.textContent = testo;
  el.errore.hidden = false;
}

function nascondiErrore() {
  el.errore.hidden = true;
}

function impostaAttesa(attivo) {
  occupato = attivo;
  el.attesa.hidden = !attivo;
  el.domanda.disabled = attivo;
  el.invia.disabled = attivo;
  el.nuovaChat.disabled = attivo;
  el.elenco.querySelectorAll("button").forEach((b) => (b.disabled = attivo));
}

function aggiungiMessaggio(ruolo, testo, creatoIl) {
  el.benvenuto.hidden = true;
  const bolla = document.createElement("div");
  bolla.className = `messaggio ${ruolo}`;
  bolla.textContent = testo;
  if (creatoIl) {
    const ora = document.createElement("span");
    ora.className = "ora";
    ora.textContent = formattaData(creatoIl);
    bolla.append(ora);
  }
  el.messaggi.append(bolla);
  el.messaggi.scrollTop = el.messaggi.scrollHeight;
  return bolla;
}

function mostraChat(chat) {
  el.titolo.textContent = chat.titolo;
  el.messaggi.querySelectorAll(".messaggio").forEach((m) => m.remove());
  el.benvenuto.hidden = chat.messaggi.length > 0;
  chat.messaggi.forEach((m) => aggiungiMessaggio(m.ruolo, m.testo, m.creato_il));
}

function svuotaVista() {
  chatAttiva = null;
  el.titolo.textContent = "Nuova conversazione";
  el.messaggi.querySelectorAll(".messaggio").forEach((m) => m.remove());
  el.benvenuto.hidden = false;
}

function mostraElenco(chat) {
  el.elenco.replaceChildren();
  el.elencoVuoto.hidden = chat.length > 0;
  for (const c of chat) {
    const voce = document.createElement("li");
    voce.classList.toggle("attiva", c.id === chatAttiva);
    voce.title = c.titolo;

    const testo = document.createElement("span");
    testo.className = "voce";
    const titolo = document.createElement("span");
    titolo.className = "titolo";
    titolo.textContent = c.titolo;
    const data = document.createElement("span");
    data.className = "data";
    data.textContent = c.ultimo_messaggio_il ? formattaData(c.ultimo_messaggio_il) : "nessun messaggio";
    testo.append(titolo, data);

    const elimina = document.createElement("button");
    elimina.type = "button";
    elimina.className = "elimina";
    elimina.textContent = "🗑";
    elimina.title = "Elimina la chat";
    elimina.setAttribute("aria-label", `Elimina la chat «${c.titolo}»`);
    elimina.disabled = occupato;
    elimina.addEventListener("click", (evento) => {
      evento.stopPropagation();
      eliminaDaElenco(c);
    });

    voce.append(testo, elimina);
    voce.addEventListener("click", () => apri(c.id));
    el.elenco.append(voce);
  }
}

// --- Azioni ----------------------------------------------------------------

async function aggiornaElenco() {
  try {
    mostraElenco(await elencaChat());
  } catch (errore) {
    mostraErrore(`Impossibile caricare l'elenco delle chat: ${errore.message}`);
  }
}

async function apri(id) {
  if (occupato) return;
  nascondiErrore();
  try {
    const chat = await leggiChat(id);
    chatAttiva = chat.id;
    mostraChat(chat);
    el.domanda.focus();
  } catch (errore) {
    mostraErrore(`Impossibile aprire la chat: ${errore.message}`);
  }
  await aggiornaElenco();
}

async function nuova() {
  if (occupato) return;
  nascondiErrore();
  try {
    const chat = await creaChat();
    chatAttiva = chat.id;
    mostraChat({ ...chat, messaggi: [] });
    el.domanda.focus();
  } catch (errore) {
    mostraErrore(`Impossibile creare la chat: ${errore.message}`);
  }
  await aggiornaElenco();
}

async function eliminaDaElenco(chat) {
  if (occupato) return;
  if (!confirm(`Eliminare la chat «${chat.titolo}» e tutti i suoi messaggi?`)) return;
  nascondiErrore();
  try {
    await eliminaChat(chat.id);
    if (chat.id === chatAttiva) svuotaVista();
  } catch (errore) {
    mostraErrore(`Impossibile eliminare la chat: ${errore.message}`);
  }
  await aggiornaElenco();
}

// Mostra la finestra con gli strumenti da confermare; true solo se l'utente sceglie «Conferma».
function chiediConferma(conferme) {
  el.elencoConferme.replaceChildren();
  for (const c of conferme) {
    const voce = document.createElement("li");
    const nome = document.createElement("strong");
    nome.textContent = c.strumento;
    const argomenti = document.createElement("code");
    argomenti.textContent = JSON.stringify(c.argomenti);
    voce.append(nome, " ", argomenti);
    el.elencoConferme.append(voce);
  }
  el.conferma.returnValue = "";
  return new Promise((risolvi) => {
    el.conferma.addEventListener("close", () => risolvi(el.conferma.returnValue === "conferma"), { once: true });
    el.conferma.showModal();
  });
}

async function invia(testo) {
  nascondiErrore();
  impostaAttesa(true);
  const bolla = aggiungiMessaggio("utente", testo);
  let id = chatAttiva;
  try {
    if (id === null) {
      id = (await creaChat()).id;
      chatAttiva = id;
    }
    let esito = await inviaMessaggio(id, testo, []);
    if (esito.conferme_richieste.length > 0) {
      // Il back-end non ha salvato nulla: decide l'utente, mai il modello.
      if (!(await chiediConferma(esito.conferme_richieste))) {
        bolla.remove();
        mostraErrore("Operazione annullata: non è stato eseguito né salvato nulla.");
        return;
      }
      esito = await inviaMessaggio(id, testo, esito.conferme_richieste);
    }
    mostraChat(await leggiChat(id));
    const ultima = [...el.messaggi.querySelectorAll(".messaggio.assistente")].pop();
    if (ultima && esito.strumenti_usati.length > 0) {
      const strumenti = document.createElement("span");
      strumenti.className = "strumenti";
      strumenti.textContent = "Strumenti usati: " + esito.strumenti_usati.map((s) => s.nome).join(", ");
      ultima.append(strumenti);
    }
  } catch (errore) {
    bolla.remove();
    el.domanda.value = testo;
    mostraErrore(errore.message);
  } finally {
    impostaAttesa(false);
    el.domanda.focus();
    await aggiornaElenco();
  }
}

// --- Eventi ----------------------------------------------------------------

el.nuovaChat.addEventListener("click", nuova);
el.chiudiErrore.addEventListener("click", nascondiErrore);
el.modulo.addEventListener("submit", (evento) => {
  evento.preventDefault();
  const testo = el.domanda.value.trim();
  if (!testo || occupato) return;
  el.domanda.value = "";
  invia(testo);
});
el.domanda.addEventListener("keydown", (evento) => {
  if (evento.key === "Enter" && !evento.shiftKey) {
    evento.preventDefault();
    el.modulo.requestSubmit();
  }
});

aggiornaElenco();
