"""
harvest.py — pull public product data from Shopify storefronts.

Why this works: every Shopify store exposes /products.json publicly (it powers
their own storefront JS). No scraping of HTML, no login, no API key. This is
public catalogue data, the same thing any shopper can see.

Politeness: 6 concurrent workers, delay between requests, max 4 pages per store,
10s timeout. Do not hammer this. One pass, then analyse offline.

Output:
  data/raw/<domain>.json   raw payload (audit trail — keep this)
  data/products.csv        tidy one-row-per-product table
  data/stores.csv          one-row-per-store harvest log
"""
import urllib.request, urllib.error, json, csv, os, time, random
import concurrent.futures as cf
from datetime import datetime, timezone

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "data", "raw")
PAGES = 4          # 250 products/page -> up to 1,000 products per store
LIMIT = 250


def get(url, tries=2):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA,
                                                       "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:
            if a == tries - 1:
                return {"__error__": f"{type(e).__name__}"}
            time.sleep(0.6 + random.random())


def harvest(domain):
    time.sleep(random.uniform(0, 0.35))
    products, pages_ok, note = [], 0, ""
    for page in range(1, PAGES + 1):
        d = get(f"https://{domain}/products.json?limit={LIMIT}&page={page}")
        if "__error__" in d:
            note = d["__error__"]
            break
        batch = d.get("products", [])
        if not batch:
            break
        products.extend(batch)
        pages_ok += 1
        if len(batch) < LIMIT:
            break
        time.sleep(0.25)

    # currency lives in /cart.js, not products.json
    cur = ""
    c = get(f"https://{domain}/cart.js")
    if isinstance(c, dict) and c.get("currency"):
        cur = c["currency"]

    if products:
        os.makedirs(RAW, exist_ok=True)
        with open(os.path.join(RAW, domain + ".json"), "w", encoding="utf8") as f:
            json.dump(products, f)

    return {
        "domain": domain,
        "currency": cur or "UNKNOWN",
        "n_products": len(products),
        "pages": pages_ok,
        "status": "ok" if products else "fail",
        "note": note,
        "harvested_at": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "_raw": products,
    }


def flatten(rows):
    out = []
    for s in rows:
        if s["status"] != "ok":
            continue
        for p in s["_raw"]:
            variants = p.get("variants") or []
            prices = [float(v["price"]) for v in variants
                      if v.get("price") not in (None, "")]
            comps = []
            for v in variants:
                cap = v.get("compare_at_price")
                if cap not in (None, "") and float(cap) > float(v["price"]):
                    comps.append(float(cap))
            if not prices:
                continue
            out.append({
                "domain": s["domain"],
                "currency": s["currency"],
                "handle": p.get("handle", ""),
                "title": (p.get("title") or "").replace("\n", " ").strip(),
                "product_type": (p.get("product_type") or "").strip(),
                "tags": "|".join(p.get("tags") or [])[:300],
                "n_variants": len(variants),
                "price_min": round(min(prices), 2),
                "price_max": round(max(prices), 2),
                "price_median_variant": round(sorted(prices)[len(prices) // 2], 2),
                "has_compare_at": int(len(comps) > 0),
                "compare_at_max": round(max(comps), 2) if comps else "",
                "available_variants": sum(1 for v in variants if v.get("available")),
                "published": p.get("published_at", "")[:10] if p.get("published_at") else "",
            })
    return out


if __name__ == "__main__":
    domains = [l.strip() for l in open(os.path.join(HERE, "stores.txt"), encoding="utf8")
               if l.strip() and not l.startswith("#")]
    print(f"harvesting {len(domains)} storefronts, max {PAGES*LIMIT} products each\n")

    rows = []
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        for i, s in enumerate(ex.map(harvest, domains), 1):
            rows.append(s)
            print(f"[{i:>3}/{len(domains)}] {s['status']:4} "
                  f"{s['n_products']:>5} products  {s['currency']:>4}  {s['domain']}")

    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    with open(os.path.join(HERE, "data", "stores.csv"), "w", newline="", encoding="utf8") as f:
        w = csv.DictWriter(f, fieldnames=["domain", "currency", "n_products",
                                         "pages", "status", "note", "harvested_at"])
        w.writeheader()
        for s in rows:
            w.writerow({k: s[k] for k in w.fieldnames})

    flat = flatten(rows)
    if flat:
        with open(os.path.join(HERE, "data", "products.csv"), "w", newline="", encoding="utf8") as f:
            w = csv.DictWriter(f, fieldnames=list(flat[0].keys()))
            w.writeheader()
            w.writerows(flat)

    ok = sum(1 for s in rows if s["status"] == "ok")
    print(f"\ndone: {ok}/{len(rows)} stores, {len(flat):,} products -> data/products.csv")
