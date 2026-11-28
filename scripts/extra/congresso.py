"""Operazioni dei membri del Congresso USA -> data/congress.json
Camera: indice annuale e PDF ufficiali dei Periodic Transaction Report (Clerk of the House), letti con pdftotext.
Senato: specchio pubblico GitHub dei PTR ufficiali (efdsearch.senate.gov blocca le richieste automatiche).
Cache dei PDF gia' letti in cache_extra/congress_cache.json (actions/cache)."""
import io, re, subprocess, tempfile, time, zipfile, json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from comune import http_get, write, now_iso, cache_read, cache_write

SENATE = ["https://raw.githubusercontent.com/KasperSK-DK/senate-ptr-data/main/data/filings.json",
          "https://cdn.jsdelivr.net/gh/KasperSK-DK/senate-ptr-data@main/data/filings.json"]
LOOKBACK, MAX_DOCS = 45, 60
TYPE_IT = {"P": "Acquisto", "S": "Vendita", "S (partial)": "Vendita parziale", "E": "Scambio"}
TYPE_SEN = {"Purchase": ("Acquisto", "P"), "Sale (Full)": ("Vendita", "S"), "Sale (Partial)": ("Vendita parziale", "S"), "Exchange": ("Scambio", "E")}
OWN = {"SP": "Coniuge", "JT": "Cointestato", "DC": "Figlio a carico", "Self": "Titolare", "Joint": "Cointestato", "Spouse": "Coniuge", "Child": "Figlio a carico"}
ROW = re.compile(r"\s(P|S \(partial\)|S|E)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s+(\$[\d,]+(?:\s*-\s*(?:\$[\d,]+)?)?|Over \$[\d,]+|Spouse/DC Over \$[\d,]+)")


def iso(mdy):
    try: return datetime.strptime(mdy, "%m/%d/%Y").strftime("%Y-%m-%d")
    except Exception: return mdy


def pdf_text(b):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
        f.write(b); f.flush()
        return subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True, timeout=60).stdout


def parse_ptr(text):
    L, out = text.splitlines(), []
    for i, ln in enumerate(L):
        m = ROW.search(ln)
        if not m: continue
        typ, td, nd, amt = m.groups()
        amt = re.sub(r"\s+", " ", amt).strip()
        if amt.endswith("-") and i + 1 < len(L):
            m2 = re.search(r"(\$[\d,]+)\s*$", L[i + 1])
            if m2: amt += " " + m2.group(1)
        left, owner = ln[: m.start()].strip(), ""
        mo = re.match(r"^(SP|JT|DC)\s+(.*)$", left)
        if mo: owner, left = mo.group(1), mo.group(2)
        asset, j = left, i + 1
        while "[" not in asset and j < len(L) and j <= i + 3:
            nx = L[j][:70].strip()
            if nx.startswith("F ") or not nx: break
            asset += " " + nx; j += 1
        asset = re.sub(r"\s+", " ", asset).strip()
        tk, at = re.search(r"\(([A-Z][A-Z0-9.\-]{0,6})\)", asset), re.search(r"\[([A-Z]{2})\]", asset)
        name = re.sub(r"\s*\[[A-Z]{2}\]\s*$", "", asset)
        out.append({"o": OWN.get(owner, "Titolare"), "a": name[:90], "t": tk.group(1) if tk else None,
                    "at": at.group(1) if at else None, "ty": TYPE_IT.get(typ, typ), "c": typ.split()[0],
                    "d": iso(td), "amt": amt})
    return out


def house(cut, err):
    cache, files, y = cache_read("congress_cache.json", {}) or {}, [], datetime.now().year
    for yy in ((y, y - 1) if datetime.now().month == 1 else (y,)):
        try:
            z = zipfile.ZipFile(io.BytesIO(http_get(f"https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{yy}FD.zip")))
            for m in ET.fromstring(z.read(f"{yy}FD.xml")):
                if m.findtext("FilingType") != "P": continue
                fd = datetime.strptime(m.findtext("FilingDate"), "%m/%d/%Y").strftime("%Y-%m-%d")
                files.append({"doc": m.findtext("DocID"), "y": yy, "f": fd, "m": " ".join(x for x in [m.findtext("First"), m.findtext("Last")] if x),
                              "st": m.findtext("StateDst") or ""})
        except Exception as e:
            err.append(f"indice Camera {yy}: {e}")
    files = sorted([f for f in files if f["f"] >= cut], key=lambda f: f["f"], reverse=True)[:MAX_DOCS]
    trades, paper = [], 0
    for f in files:
        rec = cache.get(f["doc"])
        if rec is None:
            try:
                time.sleep(0.8)
                rows = parse_ptr(pdf_text(http_get(f"https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{f['y']}/{f['doc']}.pdf")))
                rec = {"rows": rows}; cache[f["doc"]] = rec
            except Exception as e:
                err.append(f"PTR {f['doc']}: {e}"); continue
        if not rec["rows"]: paper += 1
        for r in rec["rows"]:
            trades.append({**r, "ch": "Camera", "m": f["m"], "st": f["st"], "f": f["f"]})
    keep = {f["doc"] for f in files}
    cache_write("congress_cache.json", {k: v for k, v in cache.items() if k in keep})
    return trades, len(files), paper


def senate(cut, err):
    raw = None
    for u in SENATE:
        try: raw = json.loads(http_get(u).decode("utf-8")); cache_write("senate.json", raw); break
        except Exception as e: err.append(f"Senato {u.split('/')[2]}: {e}")
    if raw is None: raw = cache_read("senate.json")
    if not raw or not raw.get("filings"): return [], 0, 0, None
    trades, docs, paper = [], 0, 0
    for f in raw["filings"]:
        fd = (f.get("filed") or "")[:10]
        if fd < cut: continue
        docs += 1
        if f.get("paper"): paper += 1; continue
        m = " ".join(x for x in [f.get("first"), f.get("last")] if x)
        for t in f.get("transactions") or []:
            ty, c = TYPE_SEN.get(t.get("type") or "", (t.get("type") or "n/d", "?"))
            at = t.get("asset_type")
            trades.append({"o": OWN.get(t.get("owner") or "", t.get("owner") or ""), "a": re.sub(r"\s+", " ", t.get("asset") or "")[:90],
                           "t": t.get("ticker") if t.get("ticker") not in (None, "", "--") else None,
                           "at": "ST" if at in ("Stock", "Stock Option") else at, "ty": ty, "c": c, "d": (t.get("date") or "")[:10],
                           "amt": t.get("amount") or "", "ch": "Senato", "m": m, "st": "", "f": fd})
    return trades, docs, paper, raw.get("generated_at")


def run():
    err = []
    cut = (datetime.now() - timedelta(days=LOOKBACK)).strftime("%Y-%m-%d")
    h, hd, hp = house(cut, err)
    s, sd, sp, sgen = senate(cut, err)
    if not h and not s: raise SystemExit("congresso: nessuna fonte disponibile " + "; ".join(err))
    tr = sorted(h + s, key=lambda x: (x["f"], x["d"]), reverse=True)
    write("congress", {"updated": now_iso(), "from": cut,
                       "fonte": "Camera USA: Clerk of the House (PTR ufficiali). Senato USA: archivio pubblico dei PTR ufficiali di efdsearch.senate.gov",
                       "house": {"docs": hd, "paper": hp, "n": len(h)}, "senate": {"docs": sd, "paper": sp, "n": len(s), "generated": sgen},
                       "trades": tr,
                       "nota": "Operazioni dichiarate dai membri del Congresso secondo lo STOCK Act (entro 45 giorni dall'operazione). "
                               "Gli importi sono dichiarati per fasce. I moduli compilati a mano o scansionati non sono leggibili automaticamente e non compaiono nell'elenco.",
                       "errors": err[:10]})
    print("congresso: Camera", len(h), "Senato", len(s), "errori", err[:5])


if __name__ == "__main__":
    run()
