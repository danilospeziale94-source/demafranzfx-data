"""Gestione abbonamenti (da eseguire in locale, MAI committare i codici in chiaro).
  python scripts/licenze.py nuovo   --scadenza 2027-10-29 [--nota "Mario"]
  python scripts/licenze.py rinnova --codice DFX-XXXX-XXXX --scadenza 2027-12-31
  python scripts/licenze.py blocca  --codice DFX-XXXX-XXXX   (oppure --id <hash>)
  python scripts/licenze.py sblocca --codice ...
Modifica licenses.json; poi va committato (connettore GitHub) -> le Actions ricifrano i dati."""
import argparse, json, os, secrets, sys, datetime
sys.path.insert(0, os.path.dirname(__file__))
from dfx_crypto import code_id, code_pub, norm, ROOT
P = os.path.join(ROOT, "licenses.json")
ALPH = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
def load():
    return json.load(open(P)) if os.path.exists(P) else {"v": 1, "licenses": []}
def save(d):
    d["updated"] = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    json.dump(d, open(P, "w"), indent=1)
def find(d, a):
    i = a.id or code_id(a.codice)
    for l in d["licenses"]:
        if l["id"] == i: return l
    sys.exit("licenza non trovata")
ap = argparse.ArgumentParser(); ap.add_argument("azione"); ap.add_argument("--codice"); ap.add_argument("--id")
ap.add_argument("--scadenza"); ap.add_argument("--nota", default="")
a = ap.parse_args(); d = load()
if a.azione == "nuovo":
    code = a.codice and norm(a.codice) or "DFX-" + "".join(secrets.choice(ALPH) for _ in range(4)) + "-" + "".join(secrets.choice(ALPH) for _ in range(4))
    datetime.date.fromisoformat(a.scadenza)
    d["licenses"].append({"id": code_id(code), "pub": code_pub(code), "expires": a.scadenza, "status": "active",
                          "note": a.nota, "created": datetime.date.today().isoformat()})
    save(d); print("CODICE:", code, "scadenza", a.scadenza)
elif a.azione == "rinnova":
    l = find(d, a); datetime.date.fromisoformat(a.scadenza); l["expires"] = a.scadenza; l["status"] = "active"; save(d); print("ok", l["id"][:12], a.scadenza)
elif a.azione in ("blocca", "sblocca"):
    l = find(d, a); l["status"] = "blocked" if a.azione == "blocca" else "active"; save(d); print("ok", l["id"][:12], l["status"])
else: sys.exit(__doc__)
