# Nodo ATM di un sistema bancario distribuito con mutua esclusione Token Ring.
#
# Ogni ATM e' un processo separato con la propria memoria privata. Il saldo del conto
# condiviso NON sta in una variabile comune: viaggia dentro il token, che passa da un
# nodo al successivo tramite messaggi TCP su localhost. Solo chi ha il token puo'
# leggere e modificare il saldo, quindi le transazioni non possono mai sovrapporsi.
#
# Uso:   python atm.py <id> [operazione importo ...]
# Esempi:
#        python atm.py 1
#        python atm.py 2 prelievo 200
#        python atm.py 3 deposito 100

import json
import os
import queue
import socket
import sys
import threading
import time
from datetime import datetime

import config

USO = ("Uso: python atm.py <id 1-%d> [deposito|prelievo importo ...]\n"
       "Esempio: python atm.py 2 prelievo 200" % config.NUM_NODI)


def interpreta_richieste(parole):
    """Trasforma ['prelievo', '200', 'deposito', '50'] in [('prelievo', 200), ('deposito', 50)].
    Restituisce None se il formato non e' valido."""
    if len(parole) == 0 or len(parole) % 2 != 0:
        return None
    richieste = []
    for i in range(0, len(parole), 2):
        operazione = parole[i].lower()
        if operazione not in ("deposito", "prelievo"):
            return None
        try:
            importo = int(parole[i + 1])
        except ValueError:
            return None
        if importo <= 0:
            return None
        richieste.append((operazione, importo))
    return richieste


class NodoATM:

    def __init__(self, id_nodo, richieste_iniziali):
        self.id = id_nodo
        self.nome = "ATM%d" % id_nodo
        self.porta = config.PORTA_BASE + id_nodo

        # Ogni nodo conosce solo il proprio successore nell'anello logico
        # (ATM1 -> ATM2 -> ATM3 -> ATM4 -> ATM1)
        id_successore = id_nodo % config.NUM_NODI + 1
        self.nome_successore = "ATM%d" % id_successore
        self.porta_successore = config.PORTA_BASE + id_successore

        # Token in arrivo dal predecessore (li mette qui il thread di rete)
        self.coda_token = queue.Queue()

        # Richieste di transazione che aspettano il token
        self.richieste = queue.Queue()
        for r in richieste_iniziali:
            self.richieste.put(r)

        os.makedirs(config.CARTELLA_LOG, exist_ok=True)
        percorso_log = os.path.join(config.CARTELLA_LOG, self.nome + ".log")
        self.file_log = open(percorso_log, "w", encoding="utf-8")
        self.lock_log = threading.Lock()

    # ------------------------------------------------------------------ log

    def log(self, testo):
        # Ogni riga ha ora (con millisecondi) e nome del nodo, cosi' i log dei 4 terminali
        # si possono confrontare e unire in ordine di tempo (vedi verifica_log.py)
        ora = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        riga = "%s [%s] %s" % (ora, self.nome, testo)
        with self.lock_log:
            print(riga, flush=True)
            self.file_log.write(riga + "\n")
            self.file_log.flush()

    # ------------------------------------------------- scambio di messaggi

    def avvia_server(self):
        # Socket TCP in ascolto sulla porta del nodo: qui arriva il token dal predecessore
        try:
            server = socket.create_server((config.HOST, self.porta))
        except OSError:
            print("Porta %d gia' in uso: %s e' gia' avviato?" % (self.porta, self.nome))
            sys.exit(1)
        t = threading.Thread(target=self.ricevi_messaggi, args=(server,), daemon=True)
        t.start()

    def ricevi_messaggi(self, server):
        # Ogni messaggio arriva su una connessione propria: una riga di testo in formato JSON
        while True:
            conn, _ = server.accept()
            with conn:
                riga = conn.makefile("r", encoding="utf-8").readline()
            if not riga:
                continue
            messaggio = json.loads(riga)
            if messaggio.get("tipo") == "TOKEN":
                self.coda_token.put(messaggio)

    def invia_al_successore(self, messaggio):
        # Il token non deve andare perso: se il successore non e' (ancora) attivo
        # si riprova finche' la connessione non riesce
        dati = (json.dumps(messaggio) + "\n").encode("utf-8")
        avvisato = False
        while True:
            try:
                with socket.create_connection((config.HOST, self.porta_successore), timeout=5) as s:
                    s.sendall(dati)
                return
            except OSError:
                if not avvisato:
                    self.log("%s non raggiungibile, riprovo ogni %.0f s" %
                             (self.nome_successore, config.ATTESA_RIPROVA))
                    avvisato = True
                time.sleep(config.ATTESA_RIPROVA)

    # ---------------------------------------------------- gestione del token

    def gestisci_token(self, token, appena_creato=False):
        if appena_creato:
            self.log("Possiedo il token iniziale (saldo %d)" % token["saldo"])
        else:
            self.log("Token ricevuto (passaggio n. %d, saldo %d)" % (token["passaggio"], token["saldo"]))

        if self.richieste.empty():
            # Nessun bisogno della sezione critica: il token passa subito al successore
            self.log("Nessuna richiesta in attesa")
        else:
            # Una sola transazione per ogni giro del token, cosi' nessun nodo
            # puo' tenere il token troppo a lungo
            operazione, importo = self.richieste.get()
            self.sezione_critica(token, operazione, importo)

        time.sleep(config.PAUSA_TOKEN)  # solo per leggibilita' dei log
        token["passaggio"] += 1
        self.log("Token inoltrato a %s" % self.nome_successore)
        self.invia_al_successore(token)

    # ------------------------------------------------------- sezione critica

    def sezione_critica(self, token, operazione, importo):
        # Qui arriva solo il nodo che possiede il token, e il token viene inoltrato
        # solo DOPO la fine della transazione: per questo la transazione e' atomica
        # e nessun altro ATM puo' modificare il saldo nello stesso momento.

        # 1. lettura del saldo corrente (dal token)
        saldo = token["saldo"]
        self.log(">>> INIZIO transazione: %s %d (saldo letto: %d)" % (operazione, importo, saldo))

        # 2. validazione dell'operazione
        if operazione == "prelievo" and importo > saldo:
            self.log("    Operazione rifiutata: saldo insufficiente")
            self.log("<<< FINE transazione: %s %d RIFIUTATO" % (operazione, importo))
            self.log("Saldo invariato: %d" % saldo)
            return

        time.sleep(config.DURATA_TRANSAZIONE)  # tempo di elaborazione simulato

        # 3. aggiornamento del saldo
        if operazione == "deposito":
            nuovo_saldo = saldo + importo
        else:
            nuovo_saldo = saldo - importo

        # 4. scrittura del nuovo valore (nel token, che lo porta agli altri nodi)
        token["saldo"] = nuovo_saldo

        # 5. registrazione (log) dell'operazione
        self.log("<<< FINE transazione: %s %d eseguito" % (operazione, importo))
        self.log("Saldo aggiornato: %d -> %d" % (saldo, nuovo_saldo))

    # ------------------------------------------------------- input tastiera

    def leggi_tastiera(self):
        # Permette di inserire nuove richieste mentre il nodo e' in esecuzione,
        # ad esempio scrivendo "prelievo 300" e premendo Invio
        while True:
            try:
                riga = input()
            except (EOFError, KeyboardInterrupt):
                # nessuna tastiera (es. avvio in background) oppure Ctrl+C:
                # la chiusura del nodo la gestisce il thread principale
                return
            if not riga.strip():
                continue
            richieste = interpreta_richieste(riga.split())
            if richieste is None:
                print("Comando non valido. Scrivi ad esempio: deposito 100  oppure  prelievo 50")
                continue
            for operazione, importo in richieste:
                self.richieste.put((operazione, importo))
                self.log("Nuova richiesta: %s %d (in attesa del token)" % (operazione, importo))

    # ----------------------------------------------------------- avvio nodo

    def esegui(self):
        self.avvia_server()
        self.log("Avviato su %s:%d, successore %s (porta %d)" %
                 (config.HOST, self.porta, self.nome_successore, self.porta_successore))
        for operazione, importo in list(self.richieste.queue):
            self.log("Richiesta da eseguire: %s %d" % (operazione, importo))

        threading.Thread(target=self.leggi_tastiera, daemon=True).start()

        # Solo il nodo iniziale crea il token: nel sistema ne esiste esattamente uno
        if self.id == config.NODO_CON_TOKEN_INIZIALE:
            token = {"tipo": "TOKEN", "saldo": config.SALDO_INIZIALE, "passaggio": 0}
            self.gestisci_token(token, appena_creato=True)

        while True:
            try:
                # il timeout serve solo a far funzionare Ctrl+C anche su Windows
                token = self.coda_token.get(timeout=0.5)
            except queue.Empty:
                continue
            self.gestisci_token(token)


def main():
    if len(sys.argv) < 2 or not sys.argv[1].isdigit():
        print(USO)
        sys.exit(1)
    id_nodo = int(sys.argv[1])
    if id_nodo < 1 or id_nodo > config.NUM_NODI:
        print(USO)
        sys.exit(1)

    richieste = []
    if len(sys.argv) > 2:
        richieste = interpreta_richieste(sys.argv[2:])
        if richieste is None:
            print(USO)
            sys.exit(1)

    nodo = NodoATM(id_nodo, richieste)

    # Il titolo della finestra del terminale diventa il nome del nodo
    if os.name == "nt":
        os.system("title " + nodo.nome)
    else:
        print("\033]0;%s\007" % nodo.nome, end="", flush=True)

    try:
        nodo.esegui()
    except KeyboardInterrupt:
        nodo.log("Nodo terminato (Ctrl+C)")
        # chiusura immediata, senza aspettare i thread di rete e tastiera
        os._exit(0)


if __name__ == "__main__":
    main()
