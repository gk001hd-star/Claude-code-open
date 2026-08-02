#!/usr/bin/env python3
"""Audit data/pi_status.json for internal consistency and weak evidence.

Checks that do not need the network:
  1. keys that match no candidate in the corpus (typo / wrong person)
  2. two different names collapsing onto the same author_key
  3. pi=true with no group page, or lead_type disagreeing with pi
  4. group pages that are bare institutional homepages rather than a group page
  5. entries whose source string signals thin evidence
  6. paper counts and years cross-checked against coauthors.csv
"""
import csv, json, os, re, sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_docs import author_key  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")

pis = json.load(open(os.path.join(D, "pi_status.json"), encoding="utf-8"))
pis = {k: v for k, v in pis.items() if not k.startswith("_")}
rows = {author_key(r["name"]): r for r in
        csv.DictReader(open(os.path.join(D, "coauthors.csv"), encoding="utf-8"))}
cands = {author_key(c["name"]): c for c in
         json.load(open(os.path.join(D, "pi_candidates.json"), encoding="utf-8"))}

issues = defaultdict(list)

# 1 + 2
seen = {}
for name in pis:
    k = author_key(name)
    if k not in rows:
        issues["not a co-author in the corpus"].append(name)
    elif k not in cands:
        issues["checked but below the 3-paper cut-off (counted separately, not an error)"].append(name)
    if k in seen:
        issues["two entries collapse onto one author key"].append(f"{seen[k]} / {name}")
    seen[k] = name

# 3
for name, v in pis.items():
    pi, lead = v.get("pi"), v.get("lead_type")
    if pi is True and not v.get("group_page"):
        issues["pi=true but no group page"].append(name)
    if pi is True and lead != "academic_pi":
        issues["pi=true but lead_type is not academic_pi"].append(f"{name} ({lead})")
    if lead == "academic_pi" and pi is not True:
        issues["lead_type=academic_pi but pi is not true"].append(f"{name} (pi={pi})")
    if lead and pi == "unknown":
        issues["marked as a leader while pi is unknown"].append(name)
    if v.get("category") == "external_collaborator" and v.get("clevers_trainee"):
        issues["external collaborator flagged as a trainee"].append(name)

# 4 — a group page should be deeper than a bare domain
BARE = re.compile(r"^https?://[^/]+/?$")
LABDOMAIN = re.compile(r"lab|laborator|group", re.I)
for name, v in pis.items():
    page = v.get("group_page") or ""
    if not (page and BARE.match(page)):
        continue
    host = page.split("//")[-1].rstrip("/")
    if LABDOMAIN.search(host):
        continue                      # e.g. bendellab.com, rooselab.ucsf.edu - that IS the group page
    if v.get("lead_type") == "industry_lead":
        continue                      # a company homepage is the right target for a CEO
    issues["group page is a generic homepage, not about this person"].append(f"{name} -> {page}")

# 7 - does the corpus actually place this person in the group?
affs = json.load(open(os.path.join(D, "pi_remaining_affs.json"), encoding="utf-8"))
for name, v in pis.items():
    if not v.get("clevers_trainee"):
        continue
    k = author_key(name)
    row = rows.get(k)
    if row and row["evidence_tier"] == "C" and row["first_copublication"] and \
       int(row["first_copublication"]) >= 2014:
        issues["flagged as a trainee but no group affiliation on any post-2014 paper"].append(name)

# 5
THIN = re.compile(r"inconclusive|provisional|not located|search result;|LinkedIn|RocketReach|ZoomInfo", re.I)
for name, v in pis.items():
    if v.get("pi") is not True:
        continue
    if THIN.search(v.get("source", "")):
        issues["pi=true resting on thin or non-institutional evidence"].append(
            f"{name} — {v.get('source','')}")

# 6
for name, v in pis.items():
    k = author_key(name)
    if k in rows and v.get("pi") is True:
        first = rows[k]["first_copublication"]
        if first and int(first) >= 2022 and "student" not in v.get("position", "").lower() \
                and not v.get("identity_verified"):
            issues["PI whose first co-publication is very recent (verify identity)"].append(
                f"{name} (first {first})")

total = sum(len(v) for v in issues.values())
out = ["# Validation report — alumni PI data\n",
       "Automated audit of `data/pi_status.json`, run by `scripts/validate.py`. "
       "Everything here is a check on internal consistency and evidence quality; "
       "it does not need the network. Re-run it after any edit to the data.\n",
       f"**{len(pis)} entries audited — {total} open item(s) across {len(issues)} categories.**\n"]
for label in sorted(issues):
    print(f"\n## {label}  [{len(issues[label])}]")
    out.append(f"\n## {label} ({len(issues[label])})\n")
    for item in sorted(issues[label]):
        print("   -", item)
        out.append(f"- {item}")
if not issues:
    out.append("\nNo open items.")
os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
with open(os.path.join(ROOT, "docs", "validation_report.md"), "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")
print(f"\n{total} issue(s) across {len(issues)} categories; {len(pis)} entries audited.")
print("wrote docs/validation_report.md")
