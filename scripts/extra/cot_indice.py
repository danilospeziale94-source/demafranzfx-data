"""Indice COT con prezzo sovrapposto -> data/cot_index.json
Stessi mercati e stesso dataset CFTC (Legacy, solo futures) del COT esistente, ma con ~5 anni di storico.
Indice COT = (netto - minimo) / (massimo - minimo) * 100 sulle ultime 156 settimane (3 anni) e 52 settimane.
Il file COT esistente (data/cot.json) non viene toccato."""
import bisect, time, urllib.parse
from comune import http_json, prezzi, write, now_iso

# codice CFTC, chiave (uguale al COT dell'app), nome, tipo, simbolo prezzo (futures, stessa direzione del COT)
MKT = [("098662", "USD", "Indice Dollaro (DXY)", "usd", "DX-Y.NYB"), ("099741", "EUR", "Euro", "fx", "6E=F"),
       ("096742", "GBP", "Sterlina", "fx", "6B=F"), ("097741", "JPY", "Yen giapponese", "fx", "6J=F"),
       ("092741", "CHF", "Franco svizzero", "fx", "6S=F"), ("090741", "CAD", "Dollaro canadese", "fx", "6C=F"),
       ("232741", "AUD", "Dollaro australiano", "fx", "6A=F"), ("112741", "NZD", "Dollaro neozelandese", "fx", "6N=F"),
       ("088691", "XAU", "Oro", "comm", "GC=F"), ("084691", "XAG", "Argento", "comm", "SI=F"),
       ("067651", "OIL", "Petrolio WTI", "comm", "CL=F"), ("13874A", "SPX", "S&P 500", "index", "ES=F"),
       ("209742", "NDX", "Nasdaq 100", "index", "NQ=F"), ("124603", "DJI", "Dow Jones", "index", "YM=F")]
WEEKS = 156 + 104  # 3 anni per la finestra + 2 anni di serie da mostrare
SHOW = 104
COLS = ["report_date_as_yyyy_mm_dd", "cftc_contract_market_code", "open_interest_all",
        "noncomm_positions_long_all", "noncomm_positions_short_all", "comm_positions_long_all",
        "comm_positions_short_all", "nonrept_positions_long_all", "nonrept_positions_short_all"]


def idx(vals, i, n):
    w = [v for v in vals[max(0, i - n + 1): i + 1] if v is not None]
    if len(w) < min(n, 26): return None
    lo, hi = min(w), max(w)
    return 50.0 if hi == lo else round((vals[i] - lo) / (hi - lo) * 100, 1)


def run():
    codes = ",".join("'%s'" % m[0] for m in MKT)
    q = {"$select": ",".join(COLS), "$where": "cftc_contract_market_code in(%s)" % codes,
         "$order": "report_date_as_yyyy_mm_dd DESC", "$limit": str(len(MKT) * (WEEKS + 10))}
    rows = http_json("https://publicreporting.cftc.gov/resource/jun7-fc8e.json?" + urllib.parse.urlencode(q))
    if not rows: raise SystemExit("cot_index: CFTC non disponibile")
    by = {}
    for r in rows:
        dt = str(r.get("report_date_as_yyyy_mm_dd", ""))[:10]
        by.setdefault(r["cftc_contract_market_code"], {})[dt] = r
    n = lambda r, k: float(r.get(k) or 0)
    out, err = [], []
    for code, key, name, kind, sym in MKT:
        d = by.get(code)
        if not d: err.append(key + ": nessun dato"); continue
        dates = sorted(d)[-WEEKS:]
        ist = [int(n(d[x], "noncomm_positions_long_all") - n(d[x], "noncomm_positions_short_all")) for x in dates]
        com = [int(n(d[x], "comm_positions_long_all") - n(d[x], "comm_positions_short_all")) for x in dates]
        ret = [int(n(d[x], "nonrept_positions_long_all") - n(d[x], "nonrept_positions_short_all")) for x in dates]
        oi = [int(n(d[x], "open_interest_all")) for x in dates]
        L = len(dates); s0 = max(0, L - SHOW)
        ser = {k: [idx(v, i, 156) for i in range(s0, L)] for k, v in (("ist", ist), ("com", com), ("ret", ret))}
        px = None
        try:
            pr = prezzi(sym, "5y"); pd_ = [p[0] for p in pr]
            px = []
            for x in dates[s0:]:
                i = bisect.bisect_right(pd_, x) - 1
                px.append((round(pr[i][4], 2 if pr[i][4] > 50 else 5)) if i >= 0 else None)
        except Exception as e:
            err.append(f"{key} prezzo: {e}")
        time.sleep(0.5)
        last = L - 1
        out.append({"key": key, "name": name, "kind": kind, "dates": dates[s0:], "price": px,
                    "ist": ist[s0:], "com": com[s0:], "ret": ret[s0:], "oi": oi[s0:], "idx": ser,
                    "now": {"date": dates[last], "ist": ist[last], "com": com[last], "ret": ret[last], "oi": oi[last],
                            "i156": {"ist": idx(ist, last, 156), "com": idx(com, last, 156), "ret": idx(ret, last, 156)},
                            "i52": {"ist": idx(ist, last, 52), "com": idx(com, last, 52), "ret": idx(ret, last, 52)},
                            "i156_prev": {"ist": idx(ist, last - 1, 156), "com": idx(com, last - 1, 156)},
                            "pct_oi": round(ist[last] / oi[last] * 100, 1) if oi[last] else None,
                            "max156": max(ist[-156:]), "min156": min(ist[-156:])}})
    if not out: raise SystemExit("cot_index: nessun mercato")
    write("cot_index", {"updated": now_iso(), "fonte": "CFTC, Commitments of Traders (Legacy, solo futures)",
                        "markets": out, "errors": err,
                        "nota": "Indice COT: dove si trova oggi la posizione netta rispetto al suo minimo (0) e massimo (100) delle ultime 156 settimane. "
                                "Sopra 80 = posizionamento vicino ai massimi di 3 anni, sotto 20 = vicino ai minimi. Prezzo: chiusura del futures al martedì del report."})
    print("cot_index:", len(out), "errori:", err)


if __name__ == "__main__":
    run()
