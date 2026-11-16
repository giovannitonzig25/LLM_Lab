"""Comandi della CLI per i prompt MCP (Step 5): `/prompts` e `/prompt nome argomento=valore`.

MCP non prevede un comando standard: i comandi li definisce la CLI. Nome, descrizione e argomenti dei prompt
vengono solo dalla discovery (`elenca_prompt`); qui non c'è nessun nome di prompt scritto a mano.
"""
import logging
import shlex
from collections.abc import Callable, Mapping, Sequence

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from assistente.mcp_client import ErroreMcp, PromptMcp

LOG = logging.getLogger("assistente.comandi")

COMANDO_SCONOSCIUTO = "Comando sconosciuto. Comandi disponibili: /prompts, /prompt nome argomento=valore"
USO_PROMPTS = "Uso: /prompts"
USO_PROMPT = "Uso: /prompt nome argomento=valore … (valori con spazi tra virgolette doppie). Usa /prompts per l'elenco."
CLIENT_NON_CONFIGURATO = "Prompt MCP non disponibili: client non configurato."
NON_DISPONIBILI = "Prompt MCP non disponibili: "
NON_ESEGUITO = "Prompt non eseguito: "
NON_UTILIZZABILE = "Prompt non utilizzabile: "

Elenca = Callable[[], Sequence[PromptMcp]]
Ottieni = Callable[[str, dict[str, str]], list[tuple[str, str]]]


class ErroreComando(Exception):
    """Richiesta non utilizzabile; il messaggio è il testo da mostrare all'utente."""


def scomponi_richiesta(riga: str) -> tuple[str, dict[str, str]]:
    """`/prompt nome chiave=valore ...` → (nome, argomenti). Solo le virgolette doppie delimitano un valore (§7.2)."""
    lexer = shlex.shlex(riga, posix=True)
    lexer.whitespace_split = True
    lexer.quotes = '"'
    lexer.escape = ""
    lexer.commenters = ""
    try:
        parti = list(lexer)
    except ValueError as errore:
        raise ErroreComando(f"Virgolette non chiuse. {USO_PROMPT}") from errore
    if len(parti) < 2:
        raise ErroreComando(f"Manca il nome del prompt. {USO_PROMPT}")
    nome, argomenti = parti[1], {}
    for parte in parti[2:]:
        chiave, uguale, valore = parte.partition("=")
        if not uguale:
            raise ErroreComando(f"Argomento senza '=': {parte}. {USO_PROMPT}")
        if not chiave:
            raise ErroreComando(f"Argomento senza nome: {parte}. {USO_PROMPT}")
        if chiave in argomenti:
            raise ErroreComando(f"Argomento ripetuto: {chiave}. {USO_PROMPT}")
        argomenti[chiave] = valore
    return nome, argomenti


def riga_uso(prompt: PromptMcp) -> str:
    parti = [f"{a.nome}=…" if a.obbligatorio else f"[{a.nome}=…]" for a in prompt.argomenti]
    return " ".join(["Uso: /prompt", prompt.nome, *parti])


def controlla_richiesta(prompts: Sequence[PromptMcp], nome: str, argomenti: Mapping[str, str]) -> list[str]:
    """Problemi della richiesta rispetto alla discovery (§8); lista vuota = via libera."""
    prompt = next((p for p in prompts if p.nome == nome), None)
    if prompt is None:
        return [f"Prompt sconosciuto: {nome}. Usa /prompts per l'elenco."]
    dichiarati = [a.nome for a in prompt.argomenti]
    problemi = []
    mancanti = [a.nome for a in prompt.argomenti if a.obbligatorio and a.nome not in argomenti]
    if mancanti:
        problemi.append(f"Argomenti obbligatori mancanti: {', '.join(mancanti)}.")
    sconosciuti = [chiave for chiave in argomenti if chiave not in dichiarati]
    if sconosciuti:
        accettati = ", ".join(dichiarati) or "nessuno"
        problemi.append(f"Argomenti sconosciuti: {', '.join(sconosciuti)}. Argomenti accettati: {accettati}.")
    vuoti = [chiave for chiave, valore in argomenti.items() if not valore.strip()]
    if vuoti:
        problemi.append(f"Valore vuoto per: {', '.join(vuoti)}.")
    if problemi:
        problemi.append(riga_uso(prompt))
    return problemi


def testo_elenco(prompts: Sequence[PromptMcp]) -> str:
    """Testo di `/prompts`, costruito solo dalla discovery (§7.3)."""
    if not prompts:
        return "Nessun prompt disponibile."
    righe = ["Prompt disponibili:"]
    for prompt in prompts:
        righe.append(f"/prompt {prompt.nome} — {prompt.descrizione}" if prompt.descrizione else f"/prompt {prompt.nome}")
        for argomento in prompt.argomenti:
            riga = f"    {argomento.nome} ({'obbligatorio' if argomento.obbligatorio else 'facoltativo'})"
            righe.append(f"{riga}: {argomento.descrizione}" if argomento.descrizione else riga)
    return "\n".join(righe)


def converti_messaggi(coppie: Sequence[tuple[str, str]]) -> list[BaseMessage]:
    """(ruolo, testo) → messaggi LangChain; l'ultimo dev'essere dell'utente: è la domanda del turno (§9)."""
    if not coppie:
        raise ErroreComando(f"{NON_UTILIZZABILE}nessun messaggio.")
    messaggi: list[BaseMessage] = []
    for ruolo, testo in coppie:
        if ruolo == "user":
            messaggi.append(HumanMessage(testo))
        elif ruolo == "assistant":
            messaggi.append(AIMessage(testo))
        else:
            raise ErroreComando(f"{NON_UTILIZZABILE}ruolo non riconosciuto: {ruolo}.")
    if not isinstance(messaggi[-1], HumanMessage):
        raise ErroreComando(f"{NON_UTILIZZABILE}l'ultimo messaggio non è dell'utente.")
    return messaggi


def _richiama(riga: str, elenca: Elenca, ottieni: Ottieni) -> tuple[list[str], list[BaseMessage]]:
    try:
        nome, argomenti = scomponi_richiesta(riga)
    except ErroreComando as errore:
        return [str(errore)], []
    try:
        prompts = elenca()
    except ErroreMcp as errore:
        return [f"{NON_DISPONIBILI}{errore}"], []
    problemi = controlla_richiesta(prompts, nome, argomenti)
    if problemi:
        LOG.warning("richiesta respinta: prompt=%s argomenti=%s problemi=%s", nome, argomenti, problemi)
        return problemi, []
    try:
        coppie = ottieni(nome, argomenti)
    except ErroreMcp as errore:
        return [f"{NON_ESEGUITO}{errore}"], []
    try:
        messaggi = converti_messaggi(coppie)
    except ErroreComando as errore:
        return [str(errore)], []
    righe = [
        f"[prompt {nome}] {testo}" if ruolo == "user" else f"[prompt {nome}, assistente] {testo}"
        for ruolo, testo in coppie
    ]
    return righe, messaggi


def esegui_comando(riga: str, elenca: Elenca | None, ottieni: Ottieni | None) -> tuple[list[str], list[BaseMessage]]:
    """Esegue una riga che inizia con `/`: righe da stampare e messaggi per il turno (vuoti se non parte un turno).

    Non solleva per errori MCP o d'uso: ogni problema diventa una riga da stampare.
    """
    parti = riga.split()
    nome_comando = parti[0] if parti else riga
    if nome_comando == "/prompts" and len(parti) > 1:
        return [USO_PROMPTS], []
    if nome_comando not in ("/prompts", "/prompt"):
        return [COMANDO_SCONOSCIUTO], []
    if elenca is None or ottieni is None:
        return [CLIENT_NON_CONFIGURATO], []
    if nome_comando == "/prompts":
        try:
            return [testo_elenco(elenca())], []
        except ErroreMcp as errore:
            return [f"{NON_DISPONIBILI}{errore}"], []
    return _richiama(riga, elenca, ottieni)
