# What 71 Shopify stores do with price

A study of price structure across the public product catalogues of 71 Shopify stores (22,956 products), pulled on one day in October 2026.

- Read the study: https://olowu-pricing-study.netlify.app/
- The study measures how stores structure prices, not how much they sell.

## Results

- 60% of products end in a round number. 20% end in .99 or a 9.
- 63 of 71 stores use compare-at prices. The median store carries one on 19% of its products.
- The median store has 93% of its products in stock. Ten stores are below 75%.
- Median price: $42.

## Limits

- I picked the 71 stores, so the sample is not random and it includes some large brands.
- Stock is a one-day snapshot.
- 73 stores were harvested. Two are not priced in USD and were excluded, leaving 71. Three of the 71 listed no currency and are treated as USD.
- Bundles are detected from title keywords, so some are missed and some are false positives.

## What is in this repo

Per-store scores, the full product table and the raw payloads are not published: the study promises that store-level scores stay private. This repo has the code and the cohort-level numbers.

- `stores.txt`: the 73 candidate domains.
- `harvest.py`: reads each store's public `/products.json`. It uses 6 workers, a delay between requests and at most 4 pages per store. Run it once, then work offline.
- `analyze.py`: computes the per-store metrics and the cohort summary.
- `build_report.py`: builds the report page.
- `data/summary.json`: the cohort-level numbers behind the study.
- `report/`: the published study and its sample dashboard (fictional data).

## Reproduce it

Python 3, standard library only.

```
python harvest.py        # writes data/raw, data/products.csv, data/stores.csv
python analyze.py        # writes data/metrics.json, data/summary.json, data/charts.json
python build_report.py   # writes case-study.html
```

Catalogues change daily, so a new harvest will not match the published numbers. Run on the original harvest, `analyze.py` gives the `summary.json` committed here exactly.
