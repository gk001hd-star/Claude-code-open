#!/usr/bin/env python3
"""Build web/universe_data.json — the payload behind the Clevers Universe page.

One record per person with a documented Clevers-group affiliation (tier A),
carrying their shared papers, their years, their role, and where they are now.
Papers are held once in a shared table and referenced by index, which keeps the
payload small enough to inline in the page.

Run after build_docs.py, then re-inject with:
    python3 scripts/build_universe.py --inject
"""
import argparse, csv, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_docs import author_key, load  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA, WEB = os.path.join(ROOT, "data"), os.path.join(ROOT, "web")


def era(row):
    """Which of the lab's three homes did this person arrive into?"""
    y, site = int(row["group_affiliation_first_year"]), row["site"]
    if "Immunology" in site and "Hubrecht" not in site and "Máxima" not in site:
        return 0
    return 0 if y < 2002 else (1 if y < 2015 else 2)


def build():
    pubs = load()
    rows = {author_key(r["name"]): r for r in
            csv.DictReader(open(os.path.join(DATA, "coauthors.csv"), encoding="utf-8"))}
    roles = {author_key(k): v for k, v in
             json.load(open(os.path.join(DATA, "roles.json"), encoding="utf-8")).items()
             if not k.startswith("_")}
    pis = {author_key(k): v for k, v in
           json.load(open(os.path.join(DATA, "pi_status.json"), encoding="utf-8")).items()
           if not k.startswith("_")}

    tier_a = {k: r for k, r in rows.items() if r["evidence_tier"] == "A"}

    papers, idx = [], {}
    for p in sorted(pubs.values(), key=lambda x: (x["year"] or 0, x["title"])):
        idx[p["pmid"]] = len(papers)
        papers.append([p["year"], p["title"], p["journal"], p["doi"], p["pmid"]])

    per = {}
    for p in pubs.values():
        for name, _ in p["authors"]:
            k = author_key(name)
            if k in tier_a:
                per.setdefault(k, []).append(idx[p["pmid"]])

    people = []
    for k, r in tier_a.items():
        pi = pis.get(k, {})
        people.append({
            "n": r["name"], "p": sorted(set(per.get(k, []))),
            "f": int(r["first_copublication"]), "l": int(r["last_copublication"]),
            "gf": int(r["group_affiliation_first_year"]),
            "gl": int(r["group_affiliation_last_year"]),
            "e": era(r), "s": r["site"], "r": roles.get(k, {}).get("role", ""),
            "pi": pi.get("lead_type") or "",
            "tr": bool(pi.get("clevers_trainee", True)) if pi else True,
            "ck": bool(pi), "pos": pi.get("position", ""),
            "inst": pi.get("institution", ""), "url": pi.get("group_page", ""),
        })
    # sorted by shared papers: the page places people by rank, so the core lands
    # in the inner orbits and the long tail forms the halo
    people.sort(key=lambda x: (-len(x["p"]), x["n"]))

    years = [p[0] for p in papers if p[0]]
    return {"papers": papers, "people": people,
            "meta": {"npapers": len(papers), "npeople": len(people),
                     "y0": min(years), "y1": max(years)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inject", action="store_true",
                    help="also splice the payload into web/clevers_universe.html")
    args = ap.parse_args()

    data = build()
    os.makedirs(WEB, exist_ok=True)
    out = os.path.join(WEB, "universe_data.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(data['people'])} people, {len(data['papers'])} papers "
          f"-> {out} ({os.path.getsize(out):,} bytes)")

    if args.inject:
        page = os.path.join(WEB, "clevers_universe.html")
        html = open(page, encoding="utf-8").read()
        blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        if "/*__DATA__*/" in html:
            html = html.replace("/*__DATA__*/", blob)
        else:
            import re
            html = re.sub(r"const DATA = \{.*?\};\n", "const DATA = " + blob + ";\n",
                          html, count=1, flags=re.S)
        open(page, "w", encoding="utf-8").write(html)
        print(f"injected into {page}")


if __name__ == "__main__":
    main()
