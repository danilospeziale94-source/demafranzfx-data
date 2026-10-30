"""Uso: python scripts/fetch.py sentiment|news|cot|all"""
import json, sys, time, datetime, urllib.request, urllib.parse
from zoneinfo import ZoneInfo
sys.path.insert(0, __import__("os").path.dirname(__file__))
from dfx_crypto import write

UA = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/124 Mobile Safari/537.36"
ROME = ZoneInfo("Europe/Rome")
# id fonte -> nome mostrato (la fonte stessa e' esclusa)
BROKERS = {"amarkets": "AMarkets", "dukscopy": "Dukascopy", "ftroanda": "Oanda", "fxblue": "FXBlue", "instfor": "InstaForex",
           "myfxbook": "Myfxbook", "xm": "XM", "fxcm": "IG", "fiboforx": "FiboGroup"}

def get(url, headers=None, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json", **(headers or {})})
            with urllib.request.urlopen(req, timeout=30) as r: return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            print("errore", url[:60], e); time.sleep(3 + i * 4)
    return None

def sentiment():
    d = get("https://fxssi.com/api/current-ratios?user_id=0&rand=%d" % int(time.time()),
            {"Referer": "https://fxssi.com/tools/current-ratio", "X-Requested-With": "XMLHttpRequest"})
    if not d or not d.get("pairs"): raise SystemExit("sentiment non disponibile")
    pairs, brokers = {}, {}
    for sym, v in d["pairs"].items():
        try: avg = float(v.get("average"))
        except Exception:
            vals = [float(x) for k, x in v.items() if k != "average" and x not in (None, "")]
            if not vals: continue
            avg = sum(vals) / len(vals)
        pairs[sym] = round(avg, 1)
        bl = []
        for k, x in v.items():
            if k in ("average", "fxssi") or k not in BROKERS or x in (None, ""): continue
            try: bl.append([BROKERS[k], round(float(x), 1)])
            except Exception: pass
        if bl: brokers[sym] = sorted(bl, key=lambda b: -b[1])
    write("sentiment", {"pairs": pairs, "brokers": brokers})

def cot():
    where = urllib.parse.quote("market_and_exchange_names='GOLD - COMMODITY EXCHANGE INC.'")
    rows = get("https://publicreporting.cftc.gov/resource/jun7-fc8e.json?$where=%s&$order=%s&$limit=8"
               % (where, urllib.parse.quote("report_date_as_yyyy_mm_dd DESC")))
    if not rows: raise SystemExit("cot non disponibile")
    n = lambda r, k: float(r.get(k) or 0)
    out, seen = [], set()
    for r in rows:
        dt = str(r.get("report_date_as_yyyy_mm_dd", ""))[:10]
        if not dt or dt in seen: continue
        seen.add(dt)
        out.append({"date": dt,
                    "ist": int(n(r, "noncomm_positions_long_all") - n(r, "noncomm_positions_short_all")),
                    "com": int(n(r, "comm_positions_long_all") - n(r, "comm_positions_short_all")),
                    "ret": int(n(r, "nonrept_positions_long_all") - n(r, "nonrept_positions_short_all"))})
    write("cot", {"market": "XAUUSD", "reports": out[:4]})

def news():
    items = []
    ff = get("https://nfs.faireconomy.media/ff_calendar_thisweek.json")
    for x in ff or []:
        if str(x.get("country", "")).upper() != "USD": continue
        imp = str(x.get("impact", "")).lower()
        if imp not in ("high", "medium"): continue
        items.append({"title": x.get("title", ""), "date": datetime.datetime.fromisoformat(x["date"]).astimezone(datetime.timezone.utc).isoformat(),
                      "impact": "high" if imp == "high" else "medium", "forecast": x.get("forecast", ""),
                      "previous": x.get("previous", ""), "actual": x.get("actual", "") or ""})
    # FXEmpire: valori "actual" piu' rapidi (best effort)
    now = datetime.datetime.now(ROME); mon = (now - datetime.timedelta(days=now.weekday())).date()
    fx = get("https://www.fxempire.com/api/v1/en/economic-calendar?dateFrom=%s&dateTo=%s&country=united-states"
             % (mon.isoformat(), (mon + datetime.timedelta(days=6)).isoformat()), {"Referer": "https://www.fxempire.com/economic-calendar"}, tries=1)
    idx = {(i["date"][:16], i["title"].lower()): i for i in items}
    for day in (fx or {}).get("calendar", []) if isinstance(fx, dict) else []:
        for e in day.get("events", []):
            imp = int(e.get("impact") or 0)
            if imp < 2 or not e.get("name"): continue
            try: dt = datetime.datetime.fromisoformat(str(e["date"]).replace("Z", "+00:00")).astimezone(datetime.timezone.utc)
            except Exception: continue
            act = "" if e.get("actual") in (None, "None", "null") else str(e.get("actual"))
            words = {w for w in e["name"].lower().replace("/", " ").split() if len(w) > 3}
            hit = next((i for (d, t), i in idx.items() if d == dt.isoformat()[:16] and words & {w for w in t.replace("/", " ").split() if len(w) > 3}), None)
            if hit:
                if act and not hit["actual"]: hit["actual"] = act
            elif ff is None:
                items.append({"title": e["name"], "date": dt.isoformat(), "impact": "high" if imp >= 3 else "medium",
                              "forecast": str(e.get("forecast") or ""), "previous": str(e.get("previous") or ""), "actual": act})
    if ff is None and not items: raise SystemExit("news non disponibili")
    items.sort(key=lambda i: i["date"])
    write("news", {"week_start": mon.isoformat(), "items": items})

if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what != "all": globals()[what]()
    else:
        for f in (sentiment, news, cot):
            try: f()
            except SystemExit as e: print("ERRORE", f.__name__, e)
