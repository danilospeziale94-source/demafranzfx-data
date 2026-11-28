"""Sezioni aggiuntive DemafranzFX (stagionalita', tecnici, indice COT, insider, Congresso).
Riusa la cifratura esistente (scripts/dfx_crypto.write) senza modificarla.
Le cache grezze stanno in cache_extra/ (actions/cache, mai committate)."""
import json, os, sys, time, urllib.request, urllib.error, urllib.parse
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from dfx_crypto import write  # noqa: E402  (cifratura invariata)

ROOT = os.path.dirname(os.path.dirname(HERE))
CACHE = os.path.join(ROOT, "cache_extra")
UA = "Mozilla/5.0 (X11; Linux x86_64) DemafranzFX/1.0"
# la SEC chiede un User-Agent con nome e contatto (https://www.sec.gov/os/accessing-edgar-data)
SEC_UA = "DarkLiquidity Research darkliquidityTW@gmail.com"

# mercati seguiti dall'app: id, nome, gruppo, simbolo prezzi giornalieri
MERCATI = [
    ("XAUUSD", "Oro", "com", "GC=F"), ("XAGUSD", "Argento", "com", "SI=F"),
    ("XTIUSD", "Petrolio WTI", "com", "CL=F"),
    ("EURUSD", "EUR/USD", "fx", "EURUSD=X"), ("GBPUSD", "GBP/USD", "fx", "GBPUSD=X"),
    ("USDJPY", "USD/JPY", "fx", "JPY=X"), ("AUDUSD", "AUD/USD", "fx", "AUDUSD=X"),
    ("NZDUSD", "NZD/USD", "fx", "NZDUSD=X"), ("USDCAD", "USD/CAD", "fx", "CAD=X"),
    ("USDCHF", "USD/CHF", "fx", "CHF=X"), ("EURJPY", "EUR/JPY", "fx", "EURJPY=X"),
    ("GBPJPY", "GBP/JPY", "fx", "GBPJPY=X"),
    ("SP500", "S&P 500", "idx", "^GSPC"), ("NAS100", "Nasdaq 100", "idx", "^NDX"),
    ("US30", "Dow Jones", "idx", "^DJI"), ("GER40", "DAX 40", "idx", "^GDAXI"),
    ("USDX", "Indice Dollaro", "idx", "DX-Y.NYB"), ("BTCUSD", "Bitcoin", "cry", "BTC-USD"),
]


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def http_get(url, ua=UA, timeout=40, tries=3, headers=None):
    last = None
    for i in range(tries):
        try:
            h = {"User-Agent": ua, "Accept-Encoding": "identity"}
            h.update(headers or {})
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            last = e
            if e.code in (403, 404):
                raise
        except Exception as e:  # noqa
            last = e
        time.sleep(2 + 3 * i)
    raise last


def http_json(url, **kw):
    return json.loads(http_get(url, **kw).decode("utf-8"))


def prezzi(sym, rng="2y"):
    """Chiusure giornaliere [(YYYY-MM-DD, open, high, low, close)] dall'endpoint chart pubblico."""
    host = "query1" if hash(sym) % 2 else "query2"
    url = (f"https://{host}.finance.yahoo.com/v8/finance/chart/" + urllib.parse.quote(sym)
           + f"?range={rng}&interval=1d&includeAdjustedClose=false")
    d = http_json(url)["chart"]["result"][0]
    q, off = d["indicators"]["quote"][0], d["meta"].get("gmtoffset", 0)
    rows = {}
    for i, t in enumerate(d.get("timestamp") or []):
        c = q["close"][i]
        if c is None:
            continue
        day = datetime.fromtimestamp(t + off, timezone.utc).strftime("%Y-%m-%d")
        rows[day] = (day, q["open"][i], q["high"][i], q["low"][i], c)
    return [rows[k] for k in sorted(rows)]


def cache_read(name, default=None):
    try:
        with open(os.path.join(CACHE, name)) as f:
            return json.load(f)
    except Exception:
        return default


def cache_write(name, obj):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, name)
    with open(p + ".tmp", "w") as f:
        json.dump(obj, f, separators=(",", ":"))
    os.replace(p + ".tmp", p)


def r2(x, n=2):
    return None if x is None else round(x, n)
