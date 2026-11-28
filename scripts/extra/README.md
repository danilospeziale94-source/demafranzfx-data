# Sezioni aggiuntive DemafranzFX (28/11/2026)
Script e workflow NUOVI, separati da quelli esistenti (Sentiment, News, COT, Live, Ricifra, APK, che non sono stati modificati).
Ogni workflow scrive un solo file in data/, cifrato con scripts/dfx_crypto.py (stessa cifratura per licenza degli altri dati).

| Workflow | Script | File | Orari (UTC) | Fonte |
|---|---|---|---|---|
| extra-tecnici.yml | mercati.py tecnici | data/technicals.json | ogni ora lun-ven, 2 volte sab-dom | prezzi giornalieri (endpoint chart pubblico) |
| extra-stagionalita.yml | mercati.py stagionalita | data/seasonality.json | 04:40 ogni giorno | prezzi giornalieri, 20 anni |
| extra-cot-indice.yml | cot_indice.py | data/cot_index.json | venerdi sera + lun/mar/mer 12:07 | CFTC publicreporting (Legacy futures) |
| extra-insider.yml | insider.py | data/insiders.json | ogni ora lun-ven, ogni 4 ore sab-dom | SEC EDGAR Form 4 |
| extra-congresso.yml | congresso.py | data/congress.json | 06:50, 12:50, 18:50 | Clerk of the House + specchio PTR Senato |

Le cache (insider, PTR gia' letti) stanno in cache_extra/ tramite actions/cache, mai nel repo.
Per disattivare tutto: cancellare i 5 file .github/workflows/extra-*.yml (i dati esistenti non cambiano).
