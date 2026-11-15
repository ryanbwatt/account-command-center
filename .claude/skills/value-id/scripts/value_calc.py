#!/usr/bin/env python3
"""Realized-value calculator for /value-id: metric x published benchmark rate, per lever.

Usage:
  python3 value_calc.py inputs.json      # prints levers, totals, ROI multiple + health (internal)
  python3 value_calc.py                  # self-check

inputs.json: {"metrics": {...}, "annual_spend": optional, "rates": optional overrides}
Metric keys: live_viewing_hours, vod_views, avg_vod_minutes, bandwidth_gb,
storage_gb_months, caption_minutes. A lever whose metric is missing is "needs input",
never estimated, and stays out of the total.
"""
import json
import sys

# Published list rates. Every one is cited on the deck's assumptions slide; override per run via "rates".
RATES = {
    "cost_per_learning_hour": (123.0, "ATD 2024 State of the Industry: average cost per learning hour used (2023 data)"),
    "cdn_per_gb": (0.085, "Amazon CloudFront list price, US data transfer out, first 10 TB/month"),
    "storage_per_gb_month": (0.023, "Amazon S3 Standard list price, first 50 TB/month"),
    "caption_per_minute": (2.50, "3Play Media list price, English captions, 99% accuracy, standard turnaround"),
}

# (key, label, lens, hard savings?, needed metrics, value function)
LEVERS = [
    ("live_training", "Live training and webinars delivered", "End user", False,
     ["live_viewing_hours"], lambda m, r: m["live_viewing_hours"] * r["cost_per_learning_hour"]),
    ("ondemand_training", "On-demand learning delivered", "End user", False,
     ["vod_views", "avg_vod_minutes"], lambda m, r: m["vod_views"] * m["avg_vod_minutes"] / 60 * r["cost_per_learning_hour"]),
    ("delivery", "Video delivery infrastructure", "Operations", True,
     ["bandwidth_gb"], lambda m, r: m["bandwidth_gb"] * r["cdn_per_gb"]),
    ("storage", "Video storage infrastructure", "Operations", True,
     ["storage_gb_months"], lambda m, r: m["storage_gb_months"] * r["storage_per_gb_month"]),
    ("captions", "Accessibility captioning", "Operations", True,
     ["caption_minutes"], lambda m, r: m["caption_minutes"] * r["caption_per_minute"]),
]


def health(multiple):
    # ponytail: fixed thresholds on total value / spend; tune once a few accounts have run
    return "green" if multiple >= 3 else "amber" if multiple >= 1 else "red"


def calc(inputs):
    m = {k: v for k, v in inputs.get("metrics", {}).items() if v is not None}
    rates = {k: v for k, (v, _) in RATES.items()} | inputs.get("rates", {})
    levers = []
    for key, label, lens, hard, needs, fn in LEVERS:
        missing = [n for n in needs if n not in m]
        levers.append({"key": key, "label": label, "lens": lens, "hard_savings": hard,
                       "value": None if missing else round(fn(m, rates)),
                       "needs_input": missing})
    counted = [l for l in levers if l["value"] is not None]
    out = {"levers": levers,
           "total": sum(l["value"] for l in counted),
           "hard_savings": sum(l["value"] for l in counted if l["hard_savings"]),
           "rates": {k: {"value": rates[k], "source": RATES[k][1]} for k in RATES}}
    spend = inputs.get("annual_spend")
    if spend:
        out["roi_multiple"] = round(out["total"] / spend, 1)
        out["health"] = health(out["roi_multiple"])
    return out


def _check():
    r = calc({"metrics": {"live_viewing_hours": 100, "bandwidth_gb": 1000, "vod_views": 600},
              "annual_spend": 10000})
    by = {l["key"]: l for l in r["levers"]}
    assert by["live_training"]["value"] == 12300
    assert by["delivery"]["value"] == 85
    assert by["ondemand_training"]["value"] is None and by["ondemand_training"]["needs_input"] == ["avg_vod_minutes"]
    assert r["total"] == 12385 and r["hard_savings"] == 85
    assert r["roi_multiple"] == 1.2 and r["health"] == "amber"
    assert calc({"metrics": {"caption_minutes": 10}, "rates": {"caption_per_minute": 1.0}})["total"] == 10
    assert "roi_multiple" not in calc({"metrics": {}})
    print("ok")


if __name__ == "__main__":
    if len(sys.argv) == 1:
        _check()
    else:
        with open(sys.argv[1]) as f:
            print(json.dumps(calc(json.load(f)), indent=2))
