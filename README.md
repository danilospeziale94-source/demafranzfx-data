# demafranzfx-data

Dati per l'app DemafranzFX (sentiment media broker/retail, COT CFTC XAUUSD, calendario news USD), aggiornati da GitHub Actions.

## Protezione dei dati
Il repo è pubblico (minuti Actions gratuiti illimitati) ma i file in `data/` sono cifrati:
- ogni codice abbonamento `DFX-XXXX-XXXX` genera (PBKDF2-SHA256, 120k iterazioni) una chiave X25519; in `licenses.json` ci sono solo l'id SHA-256 e la chiave pubblica, mai il codice;
- ogni file è cifrato AES-256-GCM con una chiave casuale, "incartata" (ECDH X25519 + HKDF + AES-GCM) solo per le licenze attive e non scadute;
- bloccare/far scadere un codice lo esclude dalla cifratura successiva (workflow `rekey`).

Limiti: chi ha un codice valido può comunque condividere i dati decifrati; nessun vincolo al dispositivo (servirebbe un server).
Gestione codici: `scripts/licenze.py` (vedi GESTORE_ABBONAMENTI.md).
