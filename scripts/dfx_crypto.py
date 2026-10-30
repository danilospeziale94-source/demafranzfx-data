"""Cifratura dati DemafranzFX.
Ogni codice abbonamento C genera (in modo deterministico) una coppia X25519:
  seed = PBKDF2-HMAC-SHA256(C, b"DFX-v1-seed", 120000, 32)  -> chiave privata
  pub  = X25519(seed).public                                -> pubblicata in licenses.json
  id   = SHA-256(C) hex                                     -> identificativo pubblico
Ogni file dati usa una chiave casuale K (AES-256-GCM). K viene "incartata" solo per le
licenze ATTIVE e non scadute: ECDH(effimera, pub) -> HKDF -> AES-GCM(K).
Chi non ha un codice valido non puo' decifrare nulla, anche leggendo il repo pubblico."""
import base64, hashlib, json, os, datetime
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
b64 = lambda b: base64.b64encode(b).decode()

def norm(code): return code.strip().upper()
def code_id(code): return hashlib.sha256(norm(code).encode()).hexdigest()
def code_pub(code):
    seed = hashlib.pbkdf2_hmac("sha256", norm(code).encode(), b"DFX-v1-seed", 120000, 32)
    pk = X25519PrivateKey.from_private_bytes(seed).public_key()
    return b64(pk.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))

def active_licenses():
    with open(os.path.join(ROOT, "licenses.json")) as f: lic = json.load(f)
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    return [l for l in lic.get("licenses", []) if l.get("status") == "active" and l.get("expires", "") >= today]

def seal(obj):
    K = AESGCM.generate_key(256); n = os.urandom(12)
    c = AESGCM(K).encrypt(n, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode(), b"dfx")
    keys = {}
    for l in active_licenses():
        eph = X25519PrivateKey.generate()
        shared = eph.exchange(X25519PublicKey.from_public_bytes(base64.b64decode(l["pub"])))
        wk = HKDF(hashes.SHA256(), 32, b"DFX-v1-wrap", b"dfx-wrap").derive(shared)
        wn = os.urandom(12)
        keys[l["id"]] = {"e": b64(eph.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)),
                         "n": b64(wn), "c": b64(AESGCM(wk).encrypt(wn, K, b"dfx-key"))}
    return {"v": 1, "keys": keys, "n": b64(n), "c": b64(c)}

def write(name, obj):
    lic = open(os.path.join(ROOT, "licenses.json"), "rb").read()
    h = hashlib.sha256(json.dumps(obj, sort_keys=True).encode() + lic + datetime.date.today().isoformat().encode()).hexdigest()[:16]
    path = os.path.join(ROOT, "data", name + ".json")
    try:
        if json.load(open(path)).get("h") == h:
            print("invariato", name); return
    except Exception: pass
    obj["generated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    sealed = seal(obj); sealed["h"] = h
    with open(path, "w") as f: json.dump(sealed, f, separators=(",", ":"))
    print("scritto", path, "licenze attive:", len(active_licenses()))
