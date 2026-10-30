"""Spiegazioni brevi in italiano per news e COT (mostrate nell'app)."""
import re
CUR = {"USD": "il dollaro USA", "EUR": "l'euro", "GBP": "la sterlina", "JPY": "lo yen", "CHF": "il franco svizzero",
       "CAD": "il dollaro canadese", "AUD": "il dollaro australiano", "NZD": "il dollaro neozelandese", "CNY": "lo yuan"}
PAESE = {"USD": "USA", "EUR": "Eurozona", "GBP": "Regno Unito", "JPY": "Giappone", "CHF": "Svizzera", "CAD": "Canada",
         "AUD": "Australia", "NZD": "Nuova Zelanda", "CNY": "Cina"}
BANCA = {"USD": "Fed", "EUR": "BCE", "GBP": "Bank of England", "JPY": "Bank of Japan", "CHF": "BNS", "CAD": "Bank of Canada",
         "AUD": "RBA", "NZD": "RBNZ", "CNY": "PBoC"}
SU = "se il dato esce sopra le attese {c} tende a rafforzarsi, se sotto tende a indebolirsi."
GIU = "se il dato esce sopra le attese {c} tende a indebolirsi (dato negativo per l'economia), se sotto tende a rafforzarsi."
# (regex, descrizione, regola)  -- l'ordine conta: il primo che combacia vince
RULES = [
 (r"non-?farm (employment change|payrolls)", "NFP: nuovi posti di lavoro fuori dal settore agricolo, il dato sul lavoro più seguito al mondo", SU),
 (r"adp", "ADP: stima privata dei nuovi posti di lavoro, anticipa l'NFP", SU),
 (r"unemployment claims|jobless claims", "Richieste settimanali di sussidi di disoccupazione", GIU),
 (r"unemployment rate", "Tasso di disoccupazione", GIU),
 (r"claimant count", "Nuove richieste di sussidio di disoccupazione", GIU),
 (r"employment change|employment", "Variazione del numero di occupati", SU),
 (r"average (hourly )?earnings|wage|employment cost", "Crescita dei salari: spinge l'inflazione e quindi i tassi", SU),
 (r"jolts|job openings", "Posti di lavoro vacanti: misura la forza della domanda di lavoro", SU),
 (r"core pce|pce price", "PCE: l'indicatore di inflazione preferito dalla Fed", SU),
 (r"trimmed mean|core cpi|cpi|consumer price|hicp", "Inflazione al consumo: se sale la banca centrale tende a tenere i tassi alti", SU),
 (r"ppi|producer price", "Prezzi alla produzione: anticipano l'inflazione al consumo", SU),
 (r"gdp price index|deflator", "Inflazione implicita nel PIL", SU),
 (r"gdp", "PIL: misura la crescita dell'economia", SU),
 (r"retail sales", "Vendite al dettaglio: misurano i consumi delle famiglie", SU),
 (r"ism manufacturing|manufacturing pmi", "PMI manifatturiero: sopra 50 il settore cresce, sotto 50 si contrae", SU),
 (r"ism services|services pmi|non-manufacturing", "PMI servizi: sopra 50 il settore cresce, sotto 50 si contrae", SU),
 (r"pmi", "Indice PMI: sopra 50 l'economia cresce, sotto 50 si contrae", SU),
 (r"consumer (confidence|sentiment)|uom", "Fiducia dei consumatori: anticipa la spesa delle famiglie", SU),
 (r"ifo|zew|business (climate|confidence)|tankan", "Fiducia delle imprese", SU),
 (r"durable goods", "Ordini di beni durevoli: misurano gli investimenti", SU),
 (r"industrial production|manufacturing production", "Produzione industriale", SU),
 (r"housing starts|building permits|home sales|pending home", "Mercato immobiliare", SU),
 (r"trade balance|current account", "Bilancia commerciale: differenza tra esportazioni e importazioni", SU),
 (r"crude oil inventories", "Scorte settimanali di petrolio USA: se salgono più del previsto il petrolio tende a scendere e viceversa", None),
 (r"budget|fiscal|forecast statement", "Comunicazione del governo su conti pubblici e previsioni economiche", "più crescita e conti in ordine sostengono {c}, sorprese negative {lo} indeboliscono."),
 (r"federal funds rate|cash rate|policy rate|bank rate|overnight rate|refinancing rate|interest rate|rate decision|deposit facility", "Decisione sui tassi: {b}", "tassi più alti o toni aggressivi rafforzano {c}, tagli o toni morbidi {lo} indeboliscono."),
 (r"statement|minutes|monetary policy|outlook report|policy report", "Comunicazione ufficiale sulla politica monetaria: {b}", "toni aggressivi (tassi alti più a lungo) rafforzano {c}, toni morbidi {lo} indeboliscono."),
 (r"press conference|speaks|testifies|testimony", "Intervento pubblico della banca centrale: {b}", "puo' muovere molto {c}: toni aggressivi {lo} rafforzano, toni morbidi {lo} indeboliscono."),
 (r"election|vote|referendum", "Evento politico", "l'incertezza tende a far muovere molto {c}."),
]
def news(title, cur):
    t = title.lower(); c = CUR.get(cur, cur); b = BANCA.get(cur, "banca centrale")
    for rx, d, r in RULES:
        if re.search(rx, t):
            s = d.format(b=b) + " (" + PAESE.get(cur, cur) + ")."
            return s + (" " + r.format(c=c, lo=('la' if cur in ('EUR','GBP') else 'lo'))[0].upper() + r.format(c=c, lo=('la' if cur in ('EUR','GBP') else 'lo'))[1:] if r else "")
    return "Dato macroeconomico (" + PAESE.get(cur, cur) + "). Un dato migliore delle attese di solito rafforza " + c + ", uno peggiore lo indebolisce."

COT_BASE = "Il COT (CFTC) mostra ogni settimana le posizioni sui futures di grandi speculatori (istituzionali), commercial (aziende che si coprono dal rischio) e piccoli trader. "
def cot(name, kind):
    if kind == "fx": what = "Posizione netta sui futures di " + name + " a Chicago (CME). Istituzionali netti long = scommettono sul rafforzamento di questa valuta contro il dollaro; se aumentano settimana dopo settimana il trend rialzista è sostenuto."
    elif kind == "usd": what = "Posizione netta sull'indice del dollaro (DXY). Istituzionali netti long = scommettono sul dollaro forte contro le principali valute."
    elif kind == "index": what = "Posizione netta sui futures dell'indice " + name + ". Istituzionali netti long = aspettative rialziste sulla borsa USA."
    else: what = "Posizione netta sui futures di " + name + ". Istituzionali netti long = aspettative rialziste sul prezzo; i commercial (produttori) di solito stanno dalla parte opposta."
    return COT_BASE + what + " Il report fotografa il martedì e viene pubblicato il venerdì."
