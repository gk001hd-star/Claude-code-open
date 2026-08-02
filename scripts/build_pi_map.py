#!/usr/bin/env python3
"""Build docs/clevers_alumni_pi_map.md.

Joins the co-authorship table (data/coauthors.csv) with the per-person role
research (data/roles.json) and the PI check (data/pi_status.json), and reports
which alumni became principal investigators and where their current group page is.

Also lists, explicitly, the candidates that have not yet been checked — so the
coverage of this document is visible rather than implied.
"""
import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_docs import author_key  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")




def load():
    rows = list(csv.DictReader(open(os.path.join(DATA, "coauthors.csv"), encoding="utf-8")))
    for r in rows:
        r["key"] = author_key(r["name"])
        r["n"] = int(r["papers_with_clevers"])
    roles = {author_key(k): v for k, v in
             json.load(open(os.path.join(DATA, "roles.json"), encoding="utf-8")).items()
             if not k.startswith("_")}
    pis = {author_key(k): v for k, v in
           json.load(open(os.path.join(DATA, "pi_status.json"), encoding="utf-8")).items()
           if not k.startswith("_")}
    cands = json.load(open(os.path.join(DATA, "pi_candidates.json"), encoding="utf-8"))
    for c in cands:
        c["key"] = author_key(c["name"])
    return rows, roles, pis, cands


def is_collaborator(key, roles, pis):
    """True when the person led their own group independently of the Clevers lab.

    Read from an explicit `clevers_trainee` flag rather than inferred from prose,
    so borderline cases (people at the Hubrecht but in another group) are a
    deliberate call rather than an accident of wording.
    """
    return not pis.get(key, {}).get("clevers_trainee", True)


def link(p):
    page = p.get("group_page") or ""
    return f"[{page.split('//')[-1].rstrip('/')[:60]}]({page})" if page else "— none found"


def main():
    rows, roles, pis, cands = load()
    by_key = {r["key"]: r for r in rows}

    checked = [k for k in pis]
    pi_yes = [k for k in checked if pis[k]["pi"] is True]
    pi_no = [k for k in checked if pis[k]["pi"] is False]
    unknown = [k for k in checked if pis[k]["pi"] == "unknown"]

    alumni_pi = [k for k in pi_yes if not is_collaborator(k, roles, pis)]
    collab_pi = [k for k in pi_yes if is_collaborator(k, roles, pis)]

    def npapers(k):
        return by_key.get(k, {}).get("n", 0)

    alumni_pi.sort(key=lambda k: -npapers(k))
    collab_pi.sort(key=lambda k: -npapers(k))
    pi_no.sort(key=lambda k: -npapers(k))
    unknown.sort(key=lambda k: -npapers(k))

    unchecked = [c for c in cands if c["key"] not in pis]
    unchecked.sort(key=lambda c: -c["papers"])

    o = []
    o.append("# Clevers-group alumni: who became a principal investigator, and where\n")
    o.append(
        "For each person checked, whether they now head their own research group and "
        "the URL of that group's page. Built on the co-authorship data in "
        "`clevers_group_members.md`; PI status established by one targeted web search "
        "per person against institutional pages, lab sites and thesis-defence "
        "announcements.\n"
    )

    o.append("## Coverage — read this first\n")
    o.append(
        f"| | |\n| --- | ---: |\n"
        f"| Candidate alumni identified (≥3 joint papers) | {len(cands)} |\n"
        f"| **Checked so far** | **{len(checked)}** |\n"
        f"| → confirmed principal investigators | {len(pi_yes)} |\n"
        f"| &nbsp;&nbsp;&nbsp;of which trained in the Clevers group | {len(alumni_pi)} |\n"
        f"| &nbsp;&nbsp;&nbsp;of which were already independent (collaborators) | {len(collab_pi)} |\n"
        f"| → confirmed *not* running an academic group | {len(pi_no)} |\n"
        f"| → checked but unresolved | {len(unknown)} |\n"
        f"| **Not yet checked** | **{len(unchecked)}** |\n"
    )
    o.append(
        "\nThe candidate pool is everyone with **three or more** joint papers who either has a "
        "documented Hubrecht/NIOB/Máxima/Utrecht-immunology affiliation, or is a pre-2014 "
        "co-author (the era when PubMed indexed only the first author's address). The checked "
        "set was worked through in descending order of joint papers, so it covers the most "
        "prolific members first. **Section 5 lists every unchecked candidate by name** — this "
        "document is a partial pass over a named list, not a claim to have covered everyone.\n"
    )
    o.append(
        "Two caveats on the classification. A person is marked a PI only where a source shows "
        "them heading a named group, lab or department — not merely holding a senior title. "
        "And people who ran their own laboratory *before* working with Clevers are separated "
        "into Section 3, because calling them \"alumni who became PIs\" would misattribute their "
        "careers to this lab.\n"
    )

    o.append("\n## 1. Alumni who became principal investigators\n")
    o.append(
        "People who trained in or worked for the Clevers group and now head their own group. "
        "Sorted by joint papers with Clevers.\n"
    )
    o.append("| # | Name | Papers | Years with Clevers | Role then | Position now | Current group page |")
    o.append("| ---: | --- | ---: | --- | --- | --- | --- |")
    for i, k in enumerate(alumni_pi, 1):
        r = by_key.get(k, {})
        p = pis[k]
        role = roles.get(k, {}).get("role", "—")
        role = role.split(";")[0].split("→")[0].strip()
        yrs = f"{r.get('first_copublication','?')}–{r.get('last_copublication','?')}"
        o.append(
            f"| {i} | **{r.get('name', k)}** | {r.get('n','')} | {yrs} | {role} | "
            f"{p['position']}, {p['institution']} | {link(p)} |"
        )

    o.append("\n## 2. Alumni who did not take an academic PI route\n")
    o.append(
        "Checked and confirmed not to head an academic research group: industry roles, "
        "company leadership, clinical posts, core-facility and technical staff, research "
        "management, and people still in training. Several of these are senior positions — "
        "they are simply not research-group leadership.\n"
    )
    o.append("| # | Name | Papers | Years with Clevers | Where they are now | Page |")
    o.append("| ---: | --- | ---: | --- | --- | --- |")
    for i, k in enumerate(pi_no, 1):
        r = by_key.get(k, {})
        p = pis[k]
        yrs = f"{r.get('first_copublication','?')}–{r.get('last_copublication','?')}"
        inst = f", {p['institution']}" if p["institution"] else ""
        o.append(f"| {i} | {r.get('name', k)} | {r.get('n','')} | {yrs} | {p['position']}{inst} | {link(p)} |")

    o.append("\n## 3. PIs who were collaborators, not Clevers trainees\n")
    o.append(
        "These people head their own groups but did so independently of the Clevers lab — "
        "they are frequent co-authors, fellow institute group leaders or external "
        "collaborators. Listed so the alumni count in Section 1 is not inflated.\n"
    )
    o.append("| # | Name | Papers | Years co-authoring | Position | Group page |")
    o.append("| ---: | --- | ---: | --- | --- | --- |")
    for i, k in enumerate(collab_pi, 1):
        r = by_key.get(k, {})
        p = pis[k]
        yrs = f"{r.get('first_copublication','?')}–{r.get('last_copublication','?')}"
        o.append(
            f"| {i} | {r.get('name', k)} | {r.get('n','')} | {yrs} | "
            f"{p['position']}, {p['institution']} | {link(p)} |"
        )

    o.append("\n## 4. Checked but unresolved\n")
    o.append(
        "Searched, but no source found that settles whether they now lead a group. Mostly "
        "people with common names, or who left academia without a public profile.\n"
    )
    o.append("| # | Name | Papers | Years with Clevers | What is known |")
    o.append("| ---: | --- | ---: | --- | --- |")
    for i, k in enumerate(unknown, 1):
        r = by_key.get(k, {})
        p = pis[k]
        yrs = f"{r.get('first_copublication','?')}–{r.get('last_copublication','?')}"
        o.append(f"| {i} | {r.get('name', k)} | {r.get('n','')} | {yrs} | {p['position']} |")

    o.append("\n## 5. Candidates not yet checked\n")
    o.append(
        f"The remaining {len(unchecked)} people in the candidate pool, in descending order of "
        "joint papers. Each still needs one search. Tier A means a Hubrecht/NIOB/Máxima/"
        "Utrecht-immunology affiliation is documented in PubMed; tier C means they are a "
        "pre-2014 co-author whose affiliation PubMed never recorded, so the list contains "
        "both further lab members and external collaborators.\n"
    )
    o.append("| # | Name | Papers | First co-pub | Last co-pub | Tier |")
    o.append("| ---: | --- | ---: | ---: | ---: | :---: |")
    for i, c in enumerate(unchecked, 1):
        o.append(f"| {i} | {c['name']} | {c['papers']} | {c['first']} | {c['last']} | {c['tier']} |")

    o.append(
        "\n---\n\nTo extend this document: add entries to `data/pi_status.json` "
        "(`name` → `pi` / `position` / `institution` / `group_page` / `source`) and re-run "
        "`python3 scripts/build_pi_map.py`. Names are matched on surname plus first initial, "
        "so the spelling of the given name does not need to match the table exactly.\n"
    )

    os.makedirs(DOCS, exist_ok=True)
    out = os.path.join(DOCS, "clevers_alumni_pi_map.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write("\n".join(o) + "\n")

    print(f"checked {len(checked)} of {len(cands)} candidates")
    print(f"  alumni PIs      : {len(alumni_pi)}")
    print(f"  collaborator PIs: {len(collab_pi)}")
    print(f"  not a PI        : {len(pi_no)}")
    print(f"  unresolved      : {len(unknown)}")
    print(f"  unchecked       : {len(unchecked)}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
