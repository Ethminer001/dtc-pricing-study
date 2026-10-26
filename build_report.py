"""build_report.py — generates case-study.html from the harvested data."""
import html as _html, json, os, statistics as st
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(HERE, "data", "metrics.json"), encoding="utf8"))
U = {d: m for d, m in M.items() if m["currency"] in ("USD", "UNKNOWN")}
S = json.load(open(os.path.join(HERE, "data", "summary.json"), encoding="utf8"))
N = len(U)
PROD = sum(m["n_products"] for m in U.values())

def pctf(x, d=1):
    return f"{x*100:.{d}f}%"

def med(k):
    return st.median([m[k] for m in U.values()])

# ---------- chart primitives ----------
def hbar(rows, w=680, label_w=290, color="#0f766e", maxv=None, fmt=lambda v: f"{v}"):
    """rows: list of (label, value, optional colour)"""
    maxv = maxv or max(v for _, v, *_ in rows)
    rh, gap = 34, 13
    h = len(rows) * (rh + gap) + 10
    barw = w - label_w - 90
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" height="auto" role="img">']
    y = 4
    for row in rows:
        lab, val = row[0], row[1]
        col = row[2] if len(row) > 2 else color
        bw = max(3, val / maxv * barw)
        out.append(f'<text x="0" y="{y+rh*0.62:.0f}" font-size="13" fill="#344054" font-family="inherit">{_html.escape(str(lab))}</text>')
        out.append(f'<rect x="{label_w}" y="{y}" width="{barw}" height="{rh}" rx="5" fill="#f1f3f9"/>')
        out.append(f'<rect x="{label_w}" y="{y}" width="{bw:.1f}" height="{rh}" rx="5" fill="{col}"/>')
        out.append(f'<text x="{label_w+barw+12}" y="{y+rh*0.66:.0f}" font-size="13" font-weight="700" '
                   f'fill="#101828">{fmt(val)}</text>')
        y += rh + gap
    out.append("</svg>")
    return "".join(out)

def vbars(rows, w=680, h=230, color="#0f766e", unit=""):
    """rows: list of (label, value)"""
    pad, top = 34, 26
    maxv = max(v for _, v in rows) * 1.12 or 1
    n = len(rows)
    slot = (w - pad * 2) / n
    bw = slot * 0.58
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" height="auto" role="img">']
    for i in range(4):
        y = h - pad - (i / 3) * (h - pad - top)
        out.append(f'<line x1="{pad}" y1="{y:.0f}" x2="{w-pad}" y2="{y:.0f}" stroke="#eef0f5"/>')
    for i, (lab, v) in enumerate(rows):
        bh = v / maxv * (h - pad - top)
        x = pad + i * slot + (slot - bw) / 2
        y = h - pad - bh
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="4" fill="{color}"/>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{y-7:.1f}" font-size="11.5" font-weight="700" '
                   f'fill="#101828" text-anchor="middle">{v}{unit}</text>')
        out.append(f'<text x="{x+bw/2:.1f}" y="{h-pad+17:.0f}" font-size="10.5" fill="#98a2b3" '
                   f'text-anchor="middle">{lab}</text>')
    out.append("</svg>")
    return "".join(out)

def hist(vals, w=680, h=230, color="#0f766e", nbin=10):
    pad, top = 34, 24
    lo, hi = 0.0, 1.0
    counts = [0] * nbin
    for v in vals:
        i = min(int(v * nbin), nbin - 1)
        counts[i] += 1
    maxc = max(counts) * 1.15 or 1
    slot = (w - pad * 2) / nbin
    bw = slot * 0.82
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" height="auto" role="img">']
    out.append(f'<line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="#e4e7ec"/>')
    for i, c in enumerate(counts):
        bh = c / maxc * (h - pad - top)
        x = pad + i * slot + (slot - bw) / 2
        y = h - pad - bh
        if c:
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3" fill="{color}" opacity="{0.45+0.55*(c/max(counts)):.2f}"/>')
            out.append(f'<text x="{x+bw/2:.1f}" y="{y-6:.1f}" font-size="11" font-weight="700" fill="#101828" text-anchor="middle">{c}</text>')
    for i in range(0, nbin + 1, 2):
        x = pad + i * slot
        out.append(f'<text x="{x:.1f}" y="{h-pad+16:.0f}" font-size="10" fill="#98a2b3" text-anchor="middle">{i*10}%</text>')
    out.append("</svg>")
    return "".join(out)

# ---------- data prep ----------
RND = None  # set below once endings is known
N_CONF = sum(1 for m in U.values() if m["currency"] == "USD")
charm_vals = [m["charm_share"] for m in U.values()]
charm_buckets = [(f"{i*10}–{i*10+10}%", sum(1 for v in charm_vals if i/10 <= v < (i+1)/10 or (i == 9 and v == 1.0)))
                 for i in range(10)]

endings = Counter()
for m in U.values():
    for k, v in m["endings"].items():
        endings[k] += v
ET = sum(endings.values())
RND = (endings["round-even"] + endings["round-5"]) / ET
end_labels = [("Round ($45, $70)", endings["round-even"] + endings["round-5"]),
              (".99 endings", endings["x.99"]),
              ("9-ending ($29, $39)", endings["9-ending"]),
              ("Other fractions", endings["fraction"] + endings["odd_fraction"])]

moves = S["moves"]
move_rows = [(k, round(v["share"] * 100)) for k, v in
             sorted(moves.items(), key=lambda x: -x[1]["share"])]

score_dist = S["score_distribution"]
score_rows = [(f"{k}/7", v) for k, v in score_dist.items()]

stock = [m["stock_rate"] for m in U.values()]
n_under75 = sum(1 for x in stock if x < 0.75)
n7 = S["score_distribution"].get("7", 0)
stock_buckets = [("≥95%", sum(1 for x in stock if x >= 0.95)),
                 ("90–95%", sum(1 for x in stock if 0.90 <= x < 0.95)),
                 ("80–90%", sum(1 for x in stock if 0.80 <= x < 0.90)),
                 ("70–80%", sum(1 for x in stock if 0.70 <= x < 0.80)),
                 ("<70%", sum(1 for x in stock if x < 0.70))]

withb = [m for m in U.values() if m["bundle_share"] >= 0.10]
nob = [m for m in U.values() if m["bundle_share"] < 0.02]
bundle_cmp = [("Sells bundles / multi-packs", st.median([m["variant_depth_median"] for m in withb])),
              ("Does not sell bundles", st.median([m["variant_depth_median"] for m in nob]))]

T = S["tiers"]
anchor_users = [m for m in U.values() if m["anchor_share"] > 0]
anchor_median = sorted(m["anchor_share"] for m in anchor_users)[len(anchor_users)//2]

tier_rows = ""
for name, t in T.items():
    name = _html.escape(name)
    tier_rows += (f"<tr><td class='strong'>{name}</td><td class='mono'>{t['n']}</td>"
                  f"<td class='mono'>{pctf(t['anchor_share'],0)}</td>"
                  f"<td class='mono'>{pctf(t['bundle_share'],0)}</td>"
                  f"<td class='mono'>{t['variant_depth']:.1f}</td>"
                  f"<td class='mono'>{t['spread']:.1f}×</td></tr>")

HTML = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>What {N} Shopify stores do with price: a public-data teardown</title>
<style>
 *{{box-sizing:border-box}}
 body{{margin:0;padding:0 0 70px;background:#f6f6f4;color:#101828;
   font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
   -webkit-font-smoothing:antialiased;line-height:1.5}}
 .wrap{{max-width:820px;margin:0 auto;padding:0 20px}}
 .hero{{background:linear-gradient(150deg,#111827 0%,#1f2937 50%,#0f766e 100%);
   color:#fff;padding:54px 20px 46px;margin-bottom:26px}}
 .hero .in{{max-width:820px;margin:0 auto;padding:0 20px}}
 .eyebrow{{font-size:11px;letter-spacing:2px;text-transform:uppercase;color:#99d5cf;font-weight:750;margin-bottom:16px}}
 .hero h1{{font-size:36px;line-height:1.15;margin:0 0 16px;letter-spacing:-1.3px;font-weight:800}}
 .hero p{{font-size:16px;line-height:1.65;color:#d1d5db;margin:0 0 8px;max-width:640px}}
 .byline{{font-size:12.5px;color:#9ca3af;margin-top:20px;padding-top:18px;border-top:1px solid rgba(255,255,255,.15)}}
 .card{{background:#fff;border:1px solid #e9eaf1;border-radius:16px;padding:26px 30px;margin-bottom:20px;
   box-shadow:0 1px 2px rgba(16,24,40,.04)}}
 h2{{font-size:21px;margin:0 0 6px;letter-spacing:-.5px}}
 h2 .num{{color:#0f766e;font-weight:800;margin-right:8px}}
 .kicker{{font-size:12px;text-transform:uppercase;letter-spacing:1.4px;color:#98a2b3;font-weight:750;margin:0 0 14px}}
 p{{font-size:15px;line-height:1.7;color:#475467;margin:0 0 14px}}
 p.lead{{font-size:16.5px;color:#344054}}
 b,strong{{color:#101828}}
 .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:22px 0 4px}}
 .stat{{background:#f8f9fd;border:1px solid #eef0f7;border-radius:12px;padding:16px}}
 .stat .v{{font-size:25px;font-weight:780;letter-spacing:-.9px;line-height:1}}
 .stat .l{{font-size:11px;color:#667085;margin-top:7px;line-height:1.4}}
 .finding{{border-left:3px solid #0f766e;padding-left:18px;margin:26px 0}}
 .finding h3{{font-size:16.5px;margin:0 0 8px;letter-spacing:-.2px}}
 .finding p{{font-size:14.5px;margin-bottom:10px}}
 .callout{{background:#f0f9f8;border:1px solid #bfe3df;border-radius:12px;padding:18px 22px;margin:18px 0}}
 .callout p{{margin:0;font-size:14.5px;color:#115e59}}
 .warn{{background:#fffbeb;border:1px solid #fde68a;border-radius:12px;padding:18px 22px;margin:18px 0}}
 .warn p,.warn li{{font-size:14px;color:#78350f;line-height:1.65}}
 .warn h3{{font-size:13px;text-transform:uppercase;letter-spacing:1px;margin:0 0 10px;color:#92400e}}
 .chart{{margin:18px 0 6px}}
 .cap{{font-size:11.5px;color:#98a2b3;margin-top:6px;line-height:1.5}}
 table{{width:100%;border-collapse:collapse;font-size:13.5px;margin:14px 0 6px}}
 th{{text-align:left;font-size:10px;text-transform:uppercase;letter-spacing:.8px;color:#98a2b3;
   font-weight:750;padding:0 8px 10px 0;border-bottom:1px solid #eef0f5}}
 td{{padding:10px 8px 10px 0;border-bottom:1px solid #f2f4f8;color:#475467}}
 tr:last-child td{{border-bottom:none}}
 .mono{{font-variant-numeric:tabular-nums}}
 .good{{color:#027a48;font-weight:700}} .bad{{color:#b42318;font-weight:700}}
 .cta{{background:linear-gradient(135deg,#111827,#1f2937);color:#fff;border-radius:16px;
   padding:30px 32px;margin:24px 0 0}}
 .cta h2{{color:#fff}}
 .cta p{{color:#d1d5db;font-size:14.5px}}
 .cta a.alt{{background:transparent;color:#fff;border:1px solid rgba(255,255,255,.4);margin-left:8px}}
 .cta a{{display:inline-block;background:#fff;color:#111827;text-decoration:none;
   padding:13px 26px;border-radius:10px;font-weight:750;font-size:14px;margin-top:8px}}
 ul.tight{{margin:0 0 14px;padding-left:20px}}
 ul.tight li{{font-size:14.5px;line-height:1.7;color:#475467;margin-bottom:8px}}
 .foot{{text-align:center;font-size:11.5px;color:#98a2b3;margin-top:30px;line-height:1.8}}
 code{{background:#f1f3f9;padding:2px 6px;border-radius:4px;font-size:12.5px;color:#115e59}}
</style></head><body>

<div class="hero"><div class="in">
  <div class="eyebrow">Public-data teardown &middot; {N} storefronts &middot; {PROD:,} products</div>
  <h1>Advice says price everything at $X.99.<br/>{sum(1 for v in charm_vals if v >= 0.5)} of the {N} stores in this study do.</h1>
  <p>I pulled the public catalogue of {N} Shopify brands and measured their price structure: entry
  points, ladder spread, compare-at discounts, bundles, variant depth and availability. Most stores
  charm-price almost nothing. Compare-at prices sit on a minority of products. Most products in most
  catalogues are in stock.</p>
  <div class="byline">Analysis date: 24 October 2026 &nbsp;&middot;&nbsp; Source: public
  <code style="background:rgba(255,255,255,.13);color:#e5e7eb">/products.json</code> endpoints
  &nbsp;&middot;&nbsp; Scripts available on request</div>
</div></div>

<div class="wrap">

<div class="card">
  <div class="kicker">Why I ran this</div>
  <p class="lead">Most operators set prices by copying the last brand they saw or a tip from TikTok.
  I measured what {N} brands do instead.</p>
  <p>This study covers price <b>structure</b>. It does not cover price <b>performance</b>. Every
  number comes from public catalogue data, and the methodology section at the bottom shows how to
  reproduce or challenge each one.</p>
  <div class="stats">
    <div class="stat"><div class="v">{N}</div><div class="l">US storefronts</div></div>
    <div class="stat"><div class="v">{PROD:,}</div><div class="l">products analysed</div></div>
    <div class="stat"><div class="v">${med('median_price'):.0f}</div><div class="l">median price point</div></div>
    <div class="stat"><div class="v">{med('spread_p90_p10'):.1f}×</div><div class="l">median price ladder spread</div></div>
    <div class="stat"><div class="v">{pctf(med('stock_rate'),0)}</div><div class="l">median share of products in stock</div></div>
  </div>
</div>

<div class="card">
  <div class="kicker">Finding 01 &middot; price endings</div>
  <h2>Round prices outnumber charm prices {RND/((endings['x.99']+endings['9-ending'])/ET):.0f} to 1.</h2>
  <p><b>{pctf(endings['x.99']/ET + endings['9-ending']/ET,0)}</b> of the {PROD:,} products
  end in <code>.99</code> or a 9. {pctf(RND,0)} end in a round number. The most common price points
  are <b>$45</b>, <b>$38</b>, <b>$35</b>, <b>$40</b> and <b>$30</b>.</p>
  <div class="chart">{hbar([(l, v, "#0f766e" if i == 0 else "#99d5cf") for i, (l, v) in enumerate(end_labels)],
                          fmt=lambda v: f"{v:,} ({v/ET*100:.0f}%)")}</div>
  <p class="cap">How each sampled product price ends. Round = whole-dollar prices not ending in 9, including round-5.
  Percentages are of all products; the {pctf(endings['under-10']/ET,0)} priced under $10 have no bar.</p>

  <p>Stores pick a style and keep it. {sum(1 for v in charm_vals if v < 0.2)} stores charm-price under
  20% of their catalogue, {sum(1 for v in charm_vals if v >= 0.5)} charm-price half or more, and few
  sit between.</p>
  <div class="chart">{hist(charm_vals)}</div>
  <p class="cap">Distribution of {N} stores by share of their catalogue priced .99 or ending in 9.</p>
  <div class="callout"><p><b>So what?</b> Within a store, price endings tend to follow one house style.
  This study cannot say which style sells better. A catalogue that mixes endings is unusual in this
  cohort.</p></div>
</div>

<div class="card">
  <div class="kicker">Finding 02 &middot; discounting</div>
  <h2>Compare-at prices are common, and most stores use them on a minority of products.</h2>
  <p>A popular claim says DTC brands run inflated compare-at prices across the whole catalogue.
  {sum(1 for m in U.values() if m['anchor_share']>0)} of {N} stores use compare-at pricing somewhere.
  Among those {len(anchor_users)}, the median store carries one on <b>{anchor_median:.0%}</b> of its
  products, and <b>{pctf(S['share_anchor_heavy'],0)}</b> of all stores carry one on 80% or more.</p>
  <p>Where a compare-at price exists, the typical discount is <b>{pctf(med('anchor_depth_median'),0)}</b>.
  Half of the stores that use them sit between 15% and 33%, and the 10th to 90th percentile runs from
  about 10% to 46%.</p>
  <div class="callout"><p><b>So what?</b> This measures whether a compare-at price is
  <i>present</i>. It cannot show whether the "was" price ever sold. Check whether your own catalogue
  applies one discount depth to a $12 item and a $200 item.</p></div>
</div>

<div class="card">
  <div class="kicker">Finding 03 &middot; availability</div>
  <h2>Most products are buyable. About one store in seven has a real gap.</h2>
  <p>I checked each product for at least one buyable variant on the snapshot day. The median store has
  <b>{pctf(med('stock_rate'),0)}</b> of its products available. <b>{stock_buckets[0][1]} of {N}</b>
  stores sit at 95% or above and <b>{n_under75}</b> sit below 75%.</p>
  <div class="chart">{vbars(stock_buckets, color="#0f766e", unit=" stores")}</div>
  <p class="cap">Distribution of stores by share of products with at least one buyable variant.</p>
  <p>My first pass counted variants. That count tracked the number of sizes a store sells: a shoe
  brand with 12 sizes shows more gaps than a one-size coffee brand (correlation with variant depth:
  &minus;0.39). I switched to products, which removes the effect.</p>
  <div class="warn"><h3>What this does not show</h3>
  <p>This is a one-day snapshot, and a sold-out product can be deliberate, such as a limited drop or a
  seasonal line. Public data cannot show whether sold-out products receive paid traffic. Answering that
  takes Shopify inventory joined to ad-platform data, and you can run that check on your own store.</p></div>
</div>

<div class="card">
  <div class="kicker">Finding 04 &middot; a structural checklist</div>
  <h2>Three checks are near-universal. Four split the stores.</h2>
  <p>I scored each store against seven structural checks. The criteria are my own, not an industry
  standard, and they describe a catalogue without grading it. A majority-charm catalogue has a style,
  which carries no merit of its own.</p>
  <div class="chart">{hbar(move_rows, label_w=340, fmt=lambda v: f"{v}%")}</div>
  <p class="cap">Share of the {N} stores passing each check.</p>
  <p>A sub-$25 entry product, a price ladder of 3&times; or more, and a clean taxonomy appear in most
  stores, so passing them says little. The other four vary much more.</p>
  <div class="chart">{vbars(score_rows, color="#115e59", unit=" stores")}</div>
  <p class="cap">Stores by number of the seven checks passed. Median score:
  {S['score_median']:.0f}/7. {n7} store passes all seven, and {S['score_ge6']} score 6 or more.</p>
</div>

<div class="card">
  <div class="kicker">Finding 05 &middot; price tiers</div>
  <h2>How behaviour changes with price tier</h2>
  <p>Splitting the cohort by median price shows these differences:</p>
  <table>
    <thead><tr><th>Price tier</th><th>Stores</th><th>Uses anchors</th><th>Bundles</th>
    <th>Variants</th><th>Ladder spread</th></tr></thead>
    <tbody>{tier_rows}</tbody>
  </table>
  <p>Variant depth rises with price tier: 1.0, 2.5, then 5.0 variants per product. The premium tier has
  the widest ladder (10.9&times;), and the middle tier has a narrower ladder than the accessible tier.
  Compare-at use peaks in the middle tier. The premium row holds only
  {T.get('Premium ($120+)',{}).get('n',0)} stores, so treat it as a hypothesis.</p>
</div>

<div class="card">
  <div class="kicker">Exploratory &middot; read with caution</div>
  <h2>Stores with bundles tend to carry fewer variants.</h2>
  <p>The {len(withb)} stores with a bundle or multi-pack programme have a median of
  <b>{bundle_cmp[0][1]:.0f}</b> variants per product. The {len(nob)} stores with almost no bundles have a
  median of <b>{bundle_cmp[1][1]:.0f}</b>.</p>
  <div class="chart">{hbar([(l, v) for l, v in bundle_cmp],
                          fmt=lambda v: f"{v:.0f} variants", maxv=8)}</div>
  <p class="cap">Median variants per product. Bundle stores: &ge;10% of products flagged as
  bundles. No-bundle stores: &lt;2%.</p>
  <p>I read no strategy into this. The bundle flag comes from product titles (pack, set, kit, refill),
  the comparison group has {len(nob)} stores, and category may explain the gap: consumables get
  bundled and apparel gets sizes. Check your own catalogue instead of treating this as evidence.</p>
</div>

<div class="card" style="border-color:#bfe3df;background:#f7fbfa">
  <div class="kicker">Read this before you quote any of it</div>
  <h2>What this study can and cannot tell you</h2>
  <p>This study has six limits:</p>
  <ul class="tight">
    <li><b>It measures structure, not outcomes.</b> Public catalogue data holds no revenue, traffic,
    conversion rate or ad spend, so nothing here shows that a pattern causes sales. The test of cause is
    an A/B test on your own store.</li>
    <li><b>Survivorship.</b> The sample holds brands still trading and still findable. Brands that closed
    may have used the same pricing.</li>
    <li><b>The sample is not random.</b> I selected {N} English-language, US-facing Shopify brands from
    well-known DTC names, including large ones (Allbirds, Everlane and Fashion Nova). Small stores may
    differ. The study covers Shopify only, with no Amazon or marketplace brands.</li>
    <li><b>Snapshots drift.</b> I pulled the data on 24 October 2026. Prices, stock and catalogues change
    weekly, so rerunning the scripts gives different numbers.</li>
    <li><b>Some definitions are mine.</b> The seven checks in Finding 04 are my criteria. Bundles come from
    title keywords, which flag some false positives and miss some real bundles.</li>
    <li><b>Three currencies are unconfirmed.</b> Three of the {N} stores did not expose a currency. I
    treat them as USD because they are US-facing brands.</li>
  </ul>
  <p>This report publishes no store-level scores or rankings.</p>
</div>

<div class="card">
  <div class="kicker">Ten minutes</div>
  <h2>Three checks for your own store</h2>
  <ol class="tight" style="padding-left:22px">
    <li><b>Price endings.</b> Export your product prices and count the distinct endings. More than two
    suggests nobody chose a house style.</li>
    <li><b>Variants and bundles.</b> Count your median variants per product and the share of your
    catalogue that is a bundle or multi-pack. If both are low, you have no tested way to raise order
    value.</li>
    <li><b>Stock and ad spend.</b> List your out-of-stock variants and check which of those products
    had active campaigns last month. Each match is ad spend sent to a sold-out product.</li>
  </ol>
  <p>Most brands cannot answer the third question, because Shopify and the ad platforms hold the data
  in separate places.</p>
  <div class="cta">
    <h2>I build this for DTC brands</h2>
    <p>I build reporting that joins Shopify, ad platforms and margin in one dashboard and writes the
    weekly summary in plain English. The sample below uses fictional data.</p>
    <a href="demo-dashboard.html">See the sample dashboard</a>
    <a class="alt" href="mailto:olowu.tayo200@gmail.com?subject=Catalogue%20check%20for%20my%20store">Email me for a catalogue check of your store</a>
  </div>
</div>

<div class="card">
  <div class="kicker">Methodology</div>
  <h2>How I built it</h2>
  <ul class="tight">
    <li><b>Data source.</b> Every Shopify storefront publishes its catalogue at
    <code>/products.json</code>, the feed that powers its own product pages. The collection used no HTML
    scraping, no login and no API key. I ran 6 concurrent requests with throttling and a 1,000-product
    cap per store.</li>
    <li><b>Sample.</b> {len(open(os.path.join(HERE,'stores.txt'), encoding="utf8").read().split())}
    candidate domains were probed, and all exposed a public catalogue. I excluded two storefronts (one
    CAD, one AUD) from price aggregates, which leaves {N} stores.</li>
    <li><b>Product count.</b> {PROD:,} products. Stores with more than 1,000 products contribute their
    first 1,000, so very large catalogues are sampled.</li>
    <li><b>Price used.</b> The lowest variant price per product, which is the entry price a shopper
    sees.</li>
    <li><b>Availability.</b> A product counts as in stock if at least one variant is available. I
    rejected a variant-level count because it tracks how many sizes a store sells.</li>
    <li><b>Charm pricing.</b> A price counts as charm if it is x.99, or a whole-dollar price ending in 9
    (for example $29), at $10 or above.</li>
    <li><b>Anchor depth.</b> <code>(compare_at − price) / compare_at</code>, taken on products where
    a compare-at price exists and exceeds the sale price.</li>
    <li><b>Currency.</b> I checked each store through <code>/cart.js</code> or its product-page markup.
    {N_CONF} of the {N} stores are confirmed USD. Three exposed no currency to automated checks, and I
    include them as USD because they are US-facing brands. That is the one assumption in the
    study.</li>
    <li><b>Dates.</b> I harvested the data on 24 October 2026. The scripts (<code>harvest.py</code>,
    <code>analyze.py</code>) are available on request.</li>
  </ul>
</div>

<p class="foot">
  <b>Olowu Aduragbemi</b>, data analyst. I build reporting systems for e-commerce brands.<br/>
  <a href="mailto:olowu.tayo200@gmail.com">olowu.tayo200@gmail.com</a> &middot;
  <a href="https://www.linkedin.com/in/eriioluwa">LinkedIn</a> &middot; Dataset and scripts available on request.
</p>

</div></body></html>"""

open(os.path.join(HERE, "case-study.html"), "w", encoding="utf8").write(HTML)
print("wrote case-study.html", len(HTML), "bytes")
