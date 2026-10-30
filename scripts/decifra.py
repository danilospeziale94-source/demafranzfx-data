"""Test: python scripts/decifra.py DFX-XXXX-XXXX data/news.json"""
import base64, hashlib, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
from dfx_crypto import code_id, norm
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
code, path = norm(sys.argv[1]), sys.argv[2]; d = json.load(open(path)); B = base64.b64decode
k = d["keys"][code_id(code)]
seed = hashlib.pbkdf2_hmac("sha256", code.encode(), b"DFX-v1-seed", 120000, 32)
sh = X25519PrivateKey.from_private_bytes(seed).exchange(X25519PublicKey.from_public_bytes(B(k["e"])))
wk = HKDF(hashes.SHA256(), 32, b"DFX-v1-wrap", b"dfx-wrap").derive(sh)
K = AESGCM(wk).decrypt(B(k["n"]), B(k["c"]), b"dfx-key")
print(json.dumps(json.loads(AESGCM(K).decrypt(B(d["n"]), B(d["c"]), b"dfx")), indent=1, ensure_ascii=False))
