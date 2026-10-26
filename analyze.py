"""
analyze.py — pricing-architecture metrics from harvested Shopify catalogues.

Every metric here is computed from public product data only. No revenue, no
traffic, no conversion data exists in /products.json - so this measures
STRUCTURE, not performance. The report says so explicitly.

Output: data/metrics.json (per-store), data/summary.json (cohort level),
        data/charts.json (series for the report graphics)
"""
import csv, json, os, re, statistics as st
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

BUNDLE_RE = re.compile(
    r"\b(pack|bundle|set|kit|trio|duo|multipack|refill|sampler|collection|"
    r"\d+\s*-?\s*(pk|pack|count|ct|piece|pc))\b", re.I)

CHARM_TAGS = ("brands", "shopify")


def load():
    stores = {}
    with open(os.path.join(DATA, "stores.csv"), encoding="utf8") as f:
        for r in csv.DictReader(f):
            if r["status"] == "ok":
                stores[r["domain"]] = {"currency": r["currency"],
                                       "n_harvested": int(r["n_products"])}
    rows = defaultdict(list)
    with open(os.path.join(DATA, "products.csv"), encoding="utf8") as f:
        for r in csv.DictReader(f):
            rows[r["domain"]].append(r)
    return stores, rows


def price_ending(p):
    """Classify a price by its human-readable ending."""
    cents = round(p * 100)
    dollars = cents // 100
    if p != int(p):
        frac = round(p - int(p), 2)
        if frac in (0.99,):
            return "x.99"
        if frac in (0.95, 0.97, 0.5, 0.49, 0.29, 0.79):
            return "fraction"
        return "odd_fraction"
    if p >= 10 and dollars % 10 == 9:
        return "9-ending"
    if p >= 10 and dollars % 5 == 0:
        return "round-5"
    if p >= 10:
        return "round-even"
    return "under-10"


def pct(values, q):
    if not values:
        return 0.0
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def main():
    stores, rows = load()
    metrics = {}

    for domain, prods in rows.items():
        if not prods:
            continue
        cur = stores.get(domain, {}).get("currency", "")
        entry_prices, all_prices, endings = [], [], Counter()
        anchors, depths, variants, bundles = 0, [], [], 0
        types, untyped = set(), 0
        avail, total_v = 0, 0
        prod_avail = 0
        disp = []

        for p in prods:
            pmin, pmax = float(p["price_min"]), float(p["price_max"])
            if pmin <= 0:
                continue
            entry_prices.append(pmin)
            all_prices.append(pmin)
            endings[price_ending(pmin)] += 1
            if p["has_compare_at"] == "1":
                anchors += 1
                cap = float(p["compare_at_max"])
                if cap > pmin:
                    depths.append((cap - pmin) / cap)
            variants.append(int(p["n_variants"]))
            if BUNDLE_RE.search(p["title"]):
                bundles += 1
            pt = p["product_type"].strip()
            if pt:
                types.add(pt.lower())
            else:
                untyped += 1
            total_v += int(p["n_variants"])
            avail += int(p["available_variants"])
            prod_avail += 1 if int(p["available_variants"]) > 0 else 0
            if pmax > pmin:
                disp.append((pmax - pmin) / pmin)

        n = len(entry_prices)
        if n < 5:
            continue
        # charm = x.99 or a whole-dollar price ending in 9 (same definition as the report headline)
        nine = endings["9-ending"] + endings["x.99"]
        charm = nine / n
        roundsh = endings["round-5"] + endings["round-even"]

        metrics[domain] = {
            "currency": cur,
            "n_products": n,
            "entry_p10": round(pct(entry_prices, 0.10), 2),
            "entry_p25": round(pct(entry_prices, 0.25), 2),
            "median_price": round(st.median(entry_prices), 2),
            "p90_price": round(pct(entry_prices, 0.90), 2),
            "max_price": round(max(entry_prices), 2),
            "spread_p90_p10": round(pct(entry_prices, 0.90) / max(pct(entry_prices, 0.10), 0.01), 2),
            "under_30_share": round(sum(1 for x in entry_prices if x < 30) / n, 3),
            "under_50_share": round(sum(1 for x in entry_prices if x < 50) / n, 3),
            "any_under_25": int(any(x < 25 for x in entry_prices)),
            "charm_share": round(charm, 3),
            "x99_share": round(nine / n, 3),
            "round_share": round(roundsh / n, 3),
            "anchor_share": round(anchors / n, 3),
            "anchor_depth_median": round(st.median(depths), 3) if depths else 0.0,
            "variant_depth_median": round(st.median(variants), 1),
            "bundle_share": round(bundles / n, 3),
            "types_count": len(types),
            "untyped_share": round(untyped / n, 3),
            # variant-level rate is confounded by size count (12 sizes vs 1); kept for reference only
            "variant_stock_rate": round(avail / total_v, 3) if total_v else 0.0,
            # headline stock metric: share of products with at least one variant buyable
            "stock_rate": round(prod_avail / n, 3),
            "variant_dispersion_median": round(st.median(disp), 3) if disp else 0.0,
            "endings": dict(endings),
        }

    usd = {d: m for d, m in metrics.items() if m["currency"] in ("USD", "UNKNOWN")}
    n_unknown = sum(1 for m in usd.values() if m["currency"] == "UNKNOWN")
    n_excl = len(metrics) - len(usd)
    CURRENCY_NOTE = (f"{len(metrics)} stores harvested; {n_excl} non-USD excluded from price aggregates; "
                     f"{len(usd)} analysed ({len(usd)-n_unknown} confirmed USD, {n_unknown} currency unconfirmed)")
    X = list(usd.values())

    def med(k):
        return round(st.median([m[k] for m in X]), 2)

    def mean(k):
        return round(st.mean([m[k] for m in X]), 3)

    def share(pred):
        return round(sum(1 for m in X if pred(m)) / len(X), 3)

    tiers = {"Accessible (median < $50)": [m for m in X if m["median_price"] < 50],
             "Mid ($50-$120)": [m for m in X if 50 <= m["median_price"] < 120],
             "Premium ($120+)": [m for m in X if m["median_price"] >= 120]}

    tier_stats = {}
    for t, group in tiers.items():
        if not group:
            continue
        tier_stats[t] = {
            "n": len(group),
            "anchor_share": round(st.median([m["anchor_share"] for m in group]), 3),
            "bundle_share": round(st.median([m["bundle_share"] for m in group]), 3),
            "variant_depth": round(st.median([m["variant_depth_median"] for m in group]), 1),
            "spread": round(st.median([m["spread_p90_p10"] for m in group]), 2),
            "any_under_25": round(sum(m["any_under_25"] for m in group) / len(group), 3),
        }

    # ---- the 7 structural moves ----
    moves = {
        "Has a sub-$25 entry product": lambda m: m["any_under_25"] == 1,
        "Price ladder spread >= 3x (p90/p10)": lambda m: m["spread_p90_p10"] >= 3,
        "Majority charm-priced (x.99 / 9-ending)": lambda m: m["charm_share"] >= 0.5,
        "Sells bundles or multi-packs (>=10% of catalogue)": lambda m: m["bundle_share"] >= 0.10,
        "Offers a variant choice on most products (>=5)": lambda m: m["variant_depth_median"] >= 5,
        "Clean catalogue taxonomy (<=10% untyped)": lambda m: m["untyped_share"] <= 0.10,
        "Products in stock >= 90%": lambda m: m["stock_rate"] >= 0.90,
    }
    move_stats = {}
    for name, fn in moves.items():
        hit = [d for d, m in usd.items() if fn(m)]
        move_stats[name] = {"count": len(hit), "share": round(len(hit) / len(X), 3)}

    score = {d: sum(1 for fn in moves.values() if fn(m)) for d, m in usd.items()}
    dist = Counter(score.values())

    summary = {
        "stores_usd": len(X),
        "products": sum(m["n_products"] for m in X),
        "currency_note": CURRENCY_NOTE,
        "median_entry_price": med("entry_p10"),
        "median_price": med("median_price"),
        "median_p90": med("p90_price"),
        "median_spread": med("spread_p90_p10"),
        "mean_anchor_share": mean("anchor_share"),
        "median_anchor_depth": med("anchor_depth_median"),
        "median_charm_share": med("charm_share"),
        "median_variant_depth": med("variant_depth_median"),
        "median_bundle_share": med("bundle_share"),
        "median_untyped_share": med("untyped_share"),
        "median_stock_rate": med("stock_rate"),
        "share_any_under_25": share(lambda m: m["any_under_25"] == 1),
        "share_anchor_majority": share(lambda m: m["anchor_share"] >= 0.5),
        "share_anchor_heavy": share(lambda m: m["anchor_share"] >= 0.8),
        "share_charm_majority": share(lambda m: m["charm_share"] >= 0.5),
        "share_round_majority": share(lambda m: m["round_share"] >= 0.5),
        "share_bundle_none": share(lambda m: m["bundle_share"] < 0.02),
        "share_untyped_heavy": share(lambda m: m["untyped_share"] >= 0.30),
        "share_spread_under_2x": share(lambda m: m["spread_p90_p10"] < 2),
        "share_variant_thin": share(lambda m: m["variant_depth_median"] <= 2),
        "tiers": tier_stats,
        "moves": move_stats,
        "score_distribution": {str(k): v for k, v in sorted(dist.items())},
        "score_ge6": sum(1 for v in score.values() if v >= 6),
        "score_median": st.median(list(score.values())),
    }

    os.makedirs(DATA, exist_ok=True)
    json.dump(metrics, open(os.path.join(DATA, "metrics.json"), "w", encoding="utf8"), indent=1)
    json.dump(summary, open(os.path.join(DATA, "summary.json"), "w", encoding="utf8"), indent=1)

    print(json.dumps(summary, indent=1))
    print("\n--- weakest links (lowest score first) ---")
    for d, s in sorted(score.items(), key=lambda x: x[1])[:8]:
        m = usd[d]
        print(f"{s}/7  {d:28} entry ${m['entry_p10']:>6}  med ${m['median_price']:>7}  "
              f"spread {m['spread_p90_p10']:>4}x  anchor {m['anchor_share']:.0%}")


if __name__ == "__main__":
    main()
