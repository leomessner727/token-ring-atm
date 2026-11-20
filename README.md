# Transazioni bancarie distribuite con mutua esclusione Token Ring

Progetto per l'esame di Intelligenza Artificiale Distribuita (Progetto 1).
Studente: Leo Messner, matricola 0322600155.

Quattro ATM (processi separati, ognuno nel proprio terminale) lavorano sullo stesso conto
bancario. Non c'e' memoria condivisa: il saldo viaggia dentro il token, che gira
nell'anello logico `ATM1 -> ATM2 -> ATM3 -> ATM4 -> ATM1` tramite messaggi TCP su localhost.
Solo il nodo che possiede il token puo' eseguire una transazione (deposito o prelievo).

## Requisiti

- Python 3.8 o superiore (testato con Python 3.14 su Windows 11)
- Solo librerie standard (`socket`, `threading`, `queue`, `json`, ...): non serve installare nulla
- Nessuna compilazione

## Avvio (esempio della traccia)

Aprire 4 terminali nella cartella del progetto e avviare un nodo per terminale
(su Linux/macOS usare `python3` al posto di `python`):

| Terminale | Comando | Porta |
|---|---|---|
| 1 | `python atm.py 1` | 5001 |
| 2 | `python atm.py 2 prelievo 200` | 5002 |
| 3 | `python atm.py 3 deposito 100` | 5003 |
| 4 | `python atm.py 4 prelievo 500` | 5004 |

Funziona in qualsiasi ordine di avvio. Consigliato: prima ATM2, ATM3 e ATM4, per ultimo ATM1,
che crea l'unico token con saldo 1000. Se il successore non e' ancora attivo, il nodo riprova
ogni 2 secondi. Risultato atteso:
1000 -> 800 (ATM2) -> 900 (ATM3) -> 400 (ATM4).

Mentre i nodi sono in esecuzione si possono aggiungere richieste scrivendo nel terminale
di un nodo, ad esempio `prelievo 300` oppure `deposito 50`, e premendo Invio.
La richiesta viene eseguita al prossimo arrivo del token. I nodi si fermano con Ctrl+C.

## Log e verifica

Ogni riga di log ha ora, nome del nodo e evento (token ricevuto, token inoltrato, inizio e
fine transazione, saldo aggiornato). Ogni nodo scrive anche il file `log/ATMx.log`.

Dopo aver fermato i nodi:

```
python verifica_log.py          # sequenza delle transazioni + controlli
python verifica_log.py --tutto  # anche tutti i passaggi del token
```

Lo script unisce i 4 log in ordine di tempo e controlla che il token sia sempre in un solo
nodo, che non ci siano transazioni concorrenti e che ogni transazione parta dal saldo
lasciato dalla precedente. Nella cartella `log_esempio/` ci sono i log di un'esecuzione
dell'esempio della traccia.

## File

| File | Contenuto |
|---|---|
| `atm.py` | il nodo ATM: rete, gestione del token, sezione critica, input da tastiera |
| `config.py` | porte, saldo iniziale, tempi (pausa del token, durata della transazione) |
| `verifica_log.py` | unione e controllo dei log |
| `log_esempio/` | log di esempio |
| `video/` | video dimostrativo |

## Video dimostrativo

Il video si trova in `video/demo_token_ring.mp4` (1:55, senza tagli) e mostra i 4 nodi in terminali
separati (in alto a sinistra ATM1, in alto a destra ATM2, in basso a sinistra ATM3, in basso a destra ATM4),
la circolazione del token e l'esecuzione delle transazioni. Tempi indicativi:

| Tempo | Cosa si vede |
|---|---|
| 0:04 a 0:23 | avvio di ATM2, ATM3, ATM4 e per ultimo ATM1, che crea il token |
| 0:24 a 0:31 | esempio della traccia: 1000 -> 800 (ATM2) -> 900 (ATM3) -> 400 (ATM4) |
| 0:31 a 0:50 | il token continua a girare senza richieste |
| 0:50 | ATM3 `prelievo 300` scritto da tastiera: 400 -> 100 |
| 0:59 | ATM1 `prelievo 5000`: rifiutato, saldo insufficiente |
| 1:07 a 1:18 | ATM2 `deposito 50` (100 -> 150), poi ATM4 `deposito 70` (150 -> 220) |
| 1:31 a 1:36 | arresto dei 4 nodi con Ctrl+C |
| 1:40 | `python verifica_log.py`: 6 transazioni eseguite, 1 rifiutata, saldo finale 220, tutti i controlli OK |
