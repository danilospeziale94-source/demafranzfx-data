"""Insider USA (SEC EDGAR, Form 4) -> data/insiders.json
Solo acquisti (P) e vendite (S) a mercato aperto degli ultimi 14 giorni di depositi.
Feed "Latest Filings" di EDGAR + XML originale di ogni Form 4, User-Agent dichiarato (regole SEC, max ~5 richieste/s).
Cache per numero di protocollo in cache_extra/insider_cache.json (actions/cache)."""
import json, re, time
import xml.etree.ElementTree as ET
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from comune import http_get, SEC_UA, write, now_iso, cache_read, cache_write

FEED = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcurrent&type=4&owner=include&count=100&start={start}&output=atom"
PAGES, DELAY, KEEP_DAYS, MAX_NEW = 6, 0.22, 14, 500
NS = {"a": "http://www.w3.org/2005/Atom"}


def sec(url):
    time.sleep(DELAY)
    return http_get(url, ua=SEC_UA, headers={"Accept": "*/*"})


def feed():
    seen = {}
    for p in range(PAGES):
        root = ET.fromstring(sec(FEED.format(start=p * 100)))
        ents = root.findall("a:entry", NS)
        for e in ents:
            m = re.search(r"/data/(\d+)/(\d{18})/", e.find("a:link", NS).get("href"))
            if m:
                seen.setdefault(m.group(2), {"acc": m.group(2), "cik": m.group(1), "filed": e.findtext("a:updated", namespaces=NS)})
        if len(ents) < 100: break
    return list(seen.values())


def tx(n, path):
    x = n.find(path)
    return x.text.strip() if x is not None and x.text else None


def fnum(x):
    try: return float(x)
    except Exception: return None


def form4(b):
    r = ET.fromstring(b)
    iss = {"name": tx(r, "issuer/issuerName"), "ticker": (tx(r, "issuer/issuerTradingSymbol") or "").upper()}
    owners = []
    for o in r.findall("reportingOwner"):
        rel, roles = o.find("reportingOwnerRelationship"), []
        if rel is not None:
            if tx(rel, "isDirector") in ("1", "true"): roles.append("Consigliere")
            if tx(rel, "isOfficer") in ("1", "true"): roles.append(tx(rel, "officerTitle") or "Dirigente")
            if tx(rel, "isTenPercentOwner") in ("1", "true"): roles.append("Socio >10%")
        owners.append({"n": tx(o, "reportingOwnerId/rptOwnerName"), "r": roles})
    txs = []
    for t in r.findall("nonDerivativeTable/nonDerivativeTransaction"):
        c = tx(t, "transactionCoding/transactionCode")
        if c not in ("P", "S"): continue
        sh, px = fnum(tx(t, "transactionAmounts/transactionShares/value")), fnum(tx(t, "transactionAmounts/transactionPricePerShare/value"))
        txs.append({"c": c, "d": (tx(t, "transactionDate/value") or "")[:10], "sh": sh, "px": px,
                    "after": fnum(tx(t, "postTransactionAmounts/sharesOwnedFollowingTransaction/value"))})
    return {"iss": iss, "own": owners, "plan": tx(r, "aff10b5One") in ("1", "true"), "txs": txs}


def filing(f):
    base = f"https://www.sec.gov/Archives/edgar/data/{f['cik']}/{f['acc']}/"
    items = json.loads(sec(base + "index.json"))["directory"]["item"]
    xs = [i["name"] for i in items if i["name"].lower().endswith(".xml") and not i["name"].lower().startswith("filingsummary")]
    if not xs: return {"skip": True, "filed": f["filed"]}
    d = form4(sec(base + xs[0])); d["filed"] = f["filed"]
    if not d["txs"]: return {"skip": True, "filed": f["filed"]}
    return d


def run():
    cache, err, new = cache_read("insider_cache.json", {}) or {}, [], 0
    try: ents = feed()
    except Exception as e: ents = []; err.append(f"feed EDGAR: {e}")
    for f in ents:
        if f["acc"] in cache: continue
        if new >= MAX_NEW: break
        try: cache[f["acc"]] = filing(f); new += 1
        except Exception as e: err.append(f"{f['acc']}: {e}")
    cut = datetime.now(timezone.utc) - timedelta(days=KEEP_DAYS)
    cache = {k: v for k, v in cache.items() if v.get("filed") and datetime.fromisoformat(v["filed"]) >= cut}
    cache_write("insider_cache.json", cache)
    if not cache: raise SystemExit("insider: nessun dato (feed non raggiungibile e cache vuota)")
    rows = []
    for acc, d in cache.items():
        if d.get("skip"): continue
        for code in ("P", "S"):
            t = [x for x in d["txs"] if x["c"] == code]
            if not t: continue
            val = sum((x["sh"] or 0) * (x["px"] or 0) for x in t); sh = sum(x["sh"] or 0 for x in t)
            after = max(t, key=lambda x: x["d"] or "").get("after")
            before = None if after is None else (after - sh if code == "P" else after + sh)
            rows.append({"k": acc, "c": code, "t": d["iss"]["ticker"], "co": d["iss"]["name"],
                         "ow": (d["own"][0]["n"] or "") if d["own"] else "", "on": len(d["own"]), "ro": sorted({r for o in d["own"] for r in o["r"]}),
                         "d": max(x["d"] or "" for x in t), "f": d["filed"][:10], "sh": round(sh), "v": round(val),
                         "px": round(val / sh, 2) if sh else None, "plan": d.get("plan"),
                         "dp": round(sh / before * 100 * (1 if code == "P" else -1), 1) if before else None,
                         "nw": bool(code == "P" and before is not None and before <= 0)})
    rows = [r for r in rows if r["v"] > 0]
    buys = sorted([r for r in rows if r["c"] == "P"], key=lambda r: -r["v"])
    sells = sorted([r for r in rows if r["c"] == "S"], key=lambda r: -r["v"])
    # aziende con piu' insider diversi che comprano nella finestra (cluster)
    cl = defaultdict(lambda: {"own": set(), "v": 0, "co": ""})
    for r in buys:
        c = cl[r["t"]]; c["own"].add(r["ow"]); c["v"] += r["v"]; c["co"] = r["co"]
    clusters = sorted([{"t": t, "co": c["co"], "n": len(c["own"]), "v": c["v"]} for t, c in cl.items() if t and len(c["own"]) >= 2],
                      key=lambda x: (-x["n"], -x["v"]))[:15]
    write("insiders", {"updated": now_iso(), "fonte": "SEC EDGAR, Form 4 originali",
                       "days": KEEP_DAYS, "filings": sum(1 for v in cache.values() if not v.get("skip")),
                       "buys": buys[:150], "sells": sells[:150], "clusters": clusters,
                       "tot": {"bv": sum(r["v"] for r in buys), "sv": sum(r["v"] for r in sells), "nb": len(buys), "ns": len(sells)},
                       "nota": f"Solo compravendite a mercato aperto (P = acquisto, S = vendita) dichiarate negli ultimi {KEEP_DAYS} giorni. "
                               "Esclusi premi in azioni, esercizio di opzioni e regali. Le vendite \"programmate\" (piano 10b5-1) sono segnalate.",
                       "errors": err[:10]})
    print("insider:", len(buys), "acquisti", len(sells), "vendite, nuovi", new, "errori", len(err))


if __name__ == "__main__":
    run()
