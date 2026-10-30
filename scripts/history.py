"""Storico sentiment: un campione ogni 10 min, ultimi 7 giorni.
Lo stato grezzo e' cifrato con la chiave segreta DFX_HIST_KEY (secret del repo) in state/hist.enc;
la versione per l'app e' data/sentiment_history.json, cifrata per licenza come gli altri file."""
import base64, json, os, time
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dfx_crypto import ROOT, write
PATH = os.path.join(ROOT, "state", "hist.enc"); STEP = 600; KEEP = 7 * 86400 + STEP

def _key():
    k = os.environ.get("DFX_HIST_KEY")
    if not k: raise SystemExit("DFX_HIST_KEY mancante")
    return base64.b64decode(k)

def load():
    try:
        raw = open(PATH, "rb").read()
        return json.loads(AESGCM(_key()).decrypt(raw[:12], raw[12:], b"dfx-hist"))
    except FileNotFoundError: return {"t": [], "p": {}}

def save(h):
    os.makedirs(os.path.dirname(PATH), exist_ok=True); n = os.urandom(12)
    open(PATH, "wb").write(n + AESGCM(_key()).encrypt(n, json.dumps(h, separators=(",", ":")).encode(), b"dfx-hist"))

def add(h, ts, pairs):
    ts = int(ts) // STEP * STEP
    if h["t"] and ts <= h["t"][-1]: return False
    n = len(h["t"]); h["t"].append(ts)
    for p in set(h["p"]) | set(pairs):
        h["p"].setdefault(p, [None] * n).append(pairs.get(p))
    cut = ts - KEEP; i = 0
    while i < len(h["t"]) and h["t"][i] < cut: i += 1
    if i:
        h["t"] = h["t"][i:]
        for p in list(h["p"]):
            h["p"][p] = h["p"][p][i:]
            if all(v is None for v in h["p"][p]): del h["p"][p]
    return True

def publish(h): write("sentiment_history", {"step": STEP, "t": h["t"], "p": h["p"]})

def update(pairs, ts=None):
    h = load()
    if add(h, ts or time.time(), pairs): save(h)
    publish(h)  # write() salta se invariato; ricifra se cambiano le licenze
