# Unisce i log dei 4 ATM in un'unica sequenza ordinata per tempo e controlla che:
#  - il token sia sempre in mano ad al massimo un nodo
#  - non ci siano mai due transazioni in corso nello stesso momento
#  - ogni transazione parta dal saldo lasciato dalla transazione precedente
#
# Uso (dopo aver fermato i nodi):  python verifica_log.py          solo transazioni
#                                  python verifica_log.py --tutto  anche i passaggi del token

import glob
import os
import re
import sys

import config

RIGA = re.compile(r"^(\d\d:\d\d:\d\d\.\d{3}) \[(ATM\d+)\] (.*)$")
SALDO = re.compile(r"Saldo aggiornato: (\d+) -> (\d+)")
SALDO_LETTO = re.compile(r"saldo letto: (\d+)")


def leggi_eventi():
    eventi = []
    for nome_file in sorted(glob.glob(os.path.join(config.CARTELLA_LOG, "ATM*.log"))):
        with open(nome_file, encoding="utf-8") as f:
            for riga in f:
                m = RIGA.match(riga.strip())
                if m:
                    eventi.append(m.groups())

    # Ordine per tempo. Se due righe hanno lo stesso millisecondo, l'inoltro del token
    # viene prima della ricezione (il mittente scrive il log prima di inviare)
    def chiave(indice_evento):
        indice, (ora, nodo, testo) = indice_evento
        return (ora, 0 if testo.startswith("Token inoltrato") else 1, indice)

    ordinati = sorted(enumerate(eventi), key=chiave)
    return [e for _, e in ordinati]


def main():
    mostra_tutto = "--tutto" in sys.argv
    eventi = leggi_eventi()
    if not eventi:
        print("Nessun log trovato nella cartella '%s'" % config.CARTELLA_LOG)
        return

    possessore = None      # nodo che ha il token in questo momento
    in_transazione = None  # nodo che e' in sezione critica
    ultimo_saldo = config.SALDO_INIZIALE
    eseguite = 0
    rifiutate = 0
    errori = []

    print("=== Sequenza globale ===")
    for ora, nodo, testo in eventi:
        if testo.startswith("Possiedo il token") or testo.startswith("Token ricevuto"):
            if possessore is not None:
                errori.append("%s %s riceve il token mentre lo ha ancora %s" % (ora, nodo, possessore))
            possessore = nodo
        elif testo.startswith("Token inoltrato"):
            possessore = None
        elif "INIZIO transazione" in testo:
            if in_transazione is not None:
                errori.append("%s %s inizia una transazione mentre %s e' in sezione critica"
                              % (ora, nodo, in_transazione))
            if nodo != possessore:
                errori.append("%s %s esegue una transazione senza avere il token" % (ora, nodo))
            letto = int(SALDO_LETTO.search(testo).group(1))
            if letto != ultimo_saldo:
                errori.append("%s %s legge saldo %d, atteso %d" % (ora, nodo, letto, ultimo_saldo))
            in_transazione = nodo
        elif "FINE transazione" in testo:
            in_transazione = None
            if "RIFIUTATO" in testo:
                rifiutate += 1
            else:
                eseguite += 1
        m = SALDO.search(testo)
        if m:
            ultimo_saldo = int(m.group(2))

        if mostra_tutto or "transazione" in testo or "Saldo" in testo or "rifiutata" in testo:
            print("%s [%s] %s" % (ora, nodo, testo))

    print()
    print("=== Risultato ===")
    print("Transazioni eseguite: %d, rifiutate: %d" % (eseguite, rifiutate))
    print("Saldo finale: %d" % ultimo_saldo)
    if errori:
        print("ERRORI TROVATI:")
        for e in errori:
            print("  " + e)
    else:
        print("Un solo possessore del token alla volta: OK")
        print("Nessuna transazione concorrente: OK")
        print("Saldo sempre coerente tra una transazione e l'altra: OK")


if __name__ == "__main__":
    main()
