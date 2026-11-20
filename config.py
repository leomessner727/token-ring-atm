# Parametri comuni del sistema Token Ring (4 ATM su localhost).

HOST = "127.0.0.1"

# Numero di nodi nell'anello: ATM1 -> ATM2 -> ATM3 -> ATM4 -> ATM1
NUM_NODI = 4

# Il nodo ATMi ascolta sulla porta PORTA_BASE + i (ATM1 = 5001, ..., ATM4 = 5004)
PORTA_BASE = 5000

# Stato iniziale (come nell'esempio della traccia)
SALDO_INIZIALE = 1000
NODO_CON_TOKEN_INIZIALE = 1

# Pausa prima di inoltrare il token, solo per rendere leggibili i log a video.
# Con 0 il token gira alla massima velocita'.
PAUSA_TOKEN = 1.0

# Durata simulata della sezione critica (per vedere bene inizio e fine della transazione)
DURATA_TRANSAZIONE = 1.5

# Attesa tra due tentativi se il successore non e' ancora avviato
ATTESA_RIPROVA = 2.0

# Cartella dove ogni nodo scrive il proprio file di log
CARTELLA_LOG = "log"
