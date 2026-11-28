"""Uso: python scripts/extra/mercati.py tecnici|stagionalita
tecnici      -> data/technicals.json   (RSI 14, stocastico, medie mobili, MACD, sintesi tecnica)
stagionalita -> data/seasonality.json  (percorso medio annuale e tabella mensile su 1/3/5/10/15 anni)
Indicatori calcolati da DemafranzFX su chiusure giornaliere pubbliche."""
import sys, time
from collections import defaultdict
from datetime import date
from statistics import mean, median
from comune import MERCATI, prezzi, write, now_iso, r2

MESI = ["Gen", "Feb", "Mar", "Apr", "Mag", "Giu", "Lug", "Ago", "Set", "Ott", "Nov", "Dic"]
FONTE = "Elaborazione DemafranzFX su prezzi giornalieri di chiusura"


# ---------------- tecnici ----------------
def sma(a, n):
    return mean(a[-n:]) if len(a) >= n else None


def ema_series(a, n):
    k, out, e = 2 / (n + 1), [], None
    for x in a:
        e = x if e is None else x * k + e * (1 - k)
        out.append(e)
    return out


def rsi(c, n=14):
    if len(c) < n + 1:
        return None
    g = l = 0.0
    for i in range(1, n + 1):
        d = c[i] - c[i - 1]; g += max(d, 0); l += max(-d, 0)
    ag, al = g / n, l / n
    for i in range(n + 1, len(c)):
        d = c[i] - c[i - 1]
        ag = (ag * (n - 1) + max(d, 0)) / n; al = (al * (n - 1) + max(-d, 0)) / n
    return 100.0 if al == 0 else 100 - 100 / (1 + ag / al)


def stoch(rows, n=14, ks=3, ds=3):
    k = []
    for i in range(n - 1, len(rows)):
        w = rows[i - n + 1: i + 1]
        hh = max(r[2] if r[2] is not None else r[4] for r in w)
        ll = min(r[3] if r[3] is not None else r[4] for r in w)
        k.append(50.0 if hh == ll else (rows[i][4] - ll) / (hh - ll) * 100)
    kk = [mean(k[i - ks + 1: i + 1]) for i in range(ks - 1, len(k))]
    return kk[-1], mean(kk[-ds:])


def pct(a, b):
    return round((a / b - 1) * 100, 2) if a is not None and b else None


def zona(r, k):
    if r >= 70 and k >= 80: return "Ipercomprato forte"
    if r >= 70 or k >= 80: return "Ipercomprato"
    if r <= 30 and k <= 20: return "Ipervenduto forte"
    if r <= 30 or k <= 20: return "Ipervenduto"
    return "Neutro"


SINTESI = {6: ("Rialzista", 2), 5: ("Rialzista", 2), 4: ("Lievemente rialzista", 1), 3: ("Neutrale", 0),
           2: ("Lievemente ribassista", -1), 1: ("Ribassista", -2), 0: ("Ribassista", -2)}


def tecnico(mid, nome, grp, sym):
    rows = prezzi(sym, "2y")
    rows = [r for r in rows if r[4] is not None]
    c = [r[4] for r in rows]
    if len(c) < 210:
        raise ValueError("storico insufficiente")
    last = c[-1]
    s20, s50, s200 = sma(c, 20), sma(c, 50), sma(c, 200)
    r14 = rsi(c[-300:]); k, d = stoch(rows[-60:])
    macd = [a - b for a, b in zip(ema_series(c, 12), ema_series(c, 26))]
    sig = ema_series(macd, 9); hist = macd[-1] - sig[-1]
    seg = [("Prezzo sopra la media 20", last > s20), ("Prezzo sopra la media 50", last > s50),
           ("Prezzo sopra la media 200", last > s200), ("Media 50 sopra la media 200", s50 > s200),
           ("RSI sopra 50", r14 > 50), ("MACD sopra la linea segnale", hist > 0)]
    up = sum(1 for _, v in seg if v)
    lab, sc = SINTESI[up]
    dec = 2 if last > 50 else 5 if last < 20 else 3
    return {"id": mid, "name": nome, "grp": grp, "date": rows[-1][0], "close": round(last, dec),
            "rsi": round(r14, 1), "k": round(k, 1), "d": round(d, 1),
            "sma": {"20": round(s20, dec), "50": round(s50, dec), "200": round(s200, dec)},
            "d20": pct(last, s20), "d50": pct(last, s50), "d200": pct(last, s200),
            "ch1d": pct(last, c[-2]), "ch5d": pct(last, c[-6]), "ch21d": pct(last, c[-22]), "ch63d": pct(last, c[-64]),
            "macd": round(hist / last * 10000, 2),  # istogramma in punti base del prezzo
            "spark": [round(x, dec) for x in c[-90:]],
            "zone": zona(r14, k), "trend": lab, "score": sc, "up": up,
            "signals": [{"t": t, "ok": v} for t, v in seg]}


def tecnici():
    out, err = [], []
    for m in MERCATI:
        try: out.append(tecnico(*m))
        except Exception as e: err.append(f"{m[0]}: {e}")
        time.sleep(0.6)
    if len(out) < len(MERCATI) // 2:
        raise SystemExit("tecnici: troppe fonti non disponibili " + "; ".join(err))
    cnt = defaultdict(int)
    for a in out: cnt[a["score"]] += 1
    write("technicals", {"updated": now_iso(), "fonte": FONTE + " (timeframe giornaliero)", "assets": out,
                         "summary": {"bull": cnt[2] + cnt[1], "neutral": cnt[0], "bear": cnt[-1] + cnt[-2]},
                         "nota": "RSI 14 (Wilder), stocastico 14-3-3, medie mobili semplici 20/50/200, MACD 12-26-9 sulle chiusure giornaliere. "
                                 "La sintesi conta quanti dei 6 segnali sono positivi: è una descrizione dello stato tecnico, non un'indicazione operativa.",
                         "errors": err})
    print("tecnici:", len(out), "errori:", err)


# ---------------- stagionalita ----------------
def percorsi(rows):
    by = defaultdict(list)
    for d, o, h, l, c in rows:
        y, m, dd = map(int, d.split("-"))
        by[y].append((date(y, m, dd).timetuple().tm_yday, c))
    out = {}
    for y, pts in by.items():
        prev = by.get(y - 1)
        base = prev[-1][1] if prev else pts[0][1]
        arr = [None] * 367; arr[0] = 0.0
        for doy, c in pts: arr[doy] = (c / base - 1) * 100
        lastv = 0.0
        for i in range(1, 367):
            if arr[i] is None: arr[i] = lastv
            else: lastv = arr[i]
        out[y] = {"arr": arr, "last": pts[-1][0], "n": len(pts), "has_prev": prev is not None}
    return out


def mensili(rows):
    last = {}
    for d, o, h, l, c in rows: last[d[:7]] = c
    ks = sorted(last)
    return {ks[i]: (last[ks[i]] / last[ks[i - 1]] - 1) * 100 for i in range(1, len(ks))}


STEP = 2  # un punto ogni 2 giorni dell'anno: curva leggera per il telefono


def stag(mid, nome, grp, sym):
    rows = prezzi(sym, "20y")
    cy = int(rows[-1][0][:4])
    P = percorsi(rows)
    full = sorted(y for y in P if y < cy and P[y]["n"] > 150 and P[y]["has_prev"])
    idx = list(range(0, 367, STEP))
    if idx[-1] != 366: idx.append(366)
    avg, tab = {}, {}
    mr = mensili(rows)
    for w in (1, 3, 5, 10, 15):
        ys = full[-w:]
        if len(ys) < w: continue
        avg[str(w)] = {"y": [ys[0], ys[-1]], "p": [round(mean(P[y]["arr"][i] for y in ys), 2) for i in idx]}
        rr = []
        for mi in range(1, 13):
            v = [mr[f"{y}-{mi:02d}"] for y in ys if f"{y}-{mi:02d}" in mr]
            rr.append(None if not v else {"avg": r2(mean(v)), "med": r2(median(v)), "win": round(sum(x > 0 for x in v) / len(v) * 100),
                                          "n": len(v), "best": r2(max(v)), "worst": r2(min(v))})
        tab[str(w)] = rr
    cur = P.get(cy)
    curp = [round(cur["arr"][i], 2) for i in idx if i <= cur["last"]] if cur else []
    return {"id": mid, "name": nome, "grp": grp, "year": cy, "last": rows[-1][0], "from": rows[0][0],
            "avg": avg, "cur": curp, "months": tab,
            "cur_months": [r2(mr.get(f"{cy}-{m:02d}")) for m in range(1, 13)]}


def stagionalita():
    out, err = [], []
    for m in MERCATI:
        try: out.append(stag(*m))
        except Exception as e: err.append(f"{m[0]}: {e}")
        time.sleep(0.8)
    if len(out) < len(MERCATI) // 2:
        raise SystemExit("stagionalita: troppe fonti non disponibili " + "; ".join(err))
    write("seasonality", {"updated": now_iso(), "fonte": FONTE + " (fino a 20 anni di storico)", "step": STEP,
                          "months_labels": MESI, "assets": out,
                          "nota": "Percorso = variazione % cumulata dall'ultima chiusura dell'anno precedente. Media sugli anni solari completi, anno in corso escluso. "
                                  "La stagionalità descrive il comportamento medio passato: non garantisce i movimenti futuri.",
                          "errors": err})
    print("stagionalita:", len(out), "errori:", err)


if __name__ == "__main__":
    {"tecnici": tecnici, "stagionalita": stagionalita}[sys.argv[1]]()
