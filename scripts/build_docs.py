#!/usr/bin/env python3
"""Build the two deliverable documents from the harvested PubMed records.

Input : data/articles.json   (pmid -> raw PubMed article object, from extract.py)
        data/roles.json      (optional; name -> {role, source} from web research)
Output: docs/clevers_publications.md    full bibliography incl. abstracts
        docs/clevers_group_members.md   people / co-authorship analysis
        data/coauthors.csv              machine-readable people table
"""
import csv
import html
import json
import os
import re
import sys
import unicodedata
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DOCS = os.path.join(ROOT, "docs")

CLEVERS_KEY = "clevers, h"

# --- affiliations that identify a Clevers-lab posting ----------------------
# The lab's homes over 30 years: the Dept of Immunology at the University
# Hospital / UMC Utrecht (1991-2002), the Hubrecht Laboratory / Netherlands
# Institute for Developmental Biology (NIOB), renamed the Hubrecht Institute
# in 2007, and the Princess Máxima Center for Pediatric Oncology (2015-).
HUBRECHT = re.compile(r"hubrecht", re.I)
MAXIMA = re.compile(r"m[aá]xima", re.I)
NIOB = re.compile(
    r"netherlands institute (for|of) developmental biology|nederlands?"
    r"\w* institute? (for|of) developmental biology|\bNIOB\b",
    re.I,
)
UTRECHT_IMMUNO = re.compile(
    r"(immunolog\w*)[^.;]{0,120}(utrecht)|(utrecht)[^.;]{0,120}(immunolog\w*)", re.I
)
GROUP_RES = (HUBRECHT, MAXIMA, NIOB, UTRECHT_IMMUNO)

EMAIL = re.compile(r"\s*(Electronic address:\s*)?[\w.+-]+@[\w.-]+\.\w+\.?\s*$", re.I)


def clean(s):
    if not s:
        return ""
    s = html.unescape(s)
    s = s.replace(" ", " ").replace("​", "")
    return re.sub(r"[ \t]+", " ", s).strip()


def clean_aff(a):
    """Normalise an affiliation string: unescape, drop trailing contact email."""
    a = clean(a)
    prev = None
    while prev != a:  # some records repeat the address per sub-affiliation
        prev = a
        a = EMAIL.sub("", a).strip()
    return a.rstrip(";, ").strip() or ""


def strip_accents(s):
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def author_name(a):
    last = clean(a.get("last_name") or a.get("collective_name") or "")
    fore = clean(a.get("fore_name") or "")
    if not fore:
        fore = clean(a.get("initials") or "")
    return f"{last}, {fore}".rstrip(", ") if last else fore


def author_key(name):
    """Collapse 'Clevers, Hans' and 'Clevers, H' onto one key.

    Key = normalised surname + first given-name initial. PubMed switched from
    initials-only to full forenames during the 1990s, so without this merge the
    same person appears twice. The cost is that two genuinely different people
    sharing a surname and first initial collapse into one entry; the report
    lists the name variants behind each row so those can be audited.
    """
    last, _, fore = name.partition(",")
    last = re.sub(r"\s+", " ", strip_accents(last).strip().lower())
    fore = strip_accents(fore).strip()
    return f"{last}, {fore[:1].lower()}" if fore else last


def display_name(variants):
    """Prefer the variant that spells the given name out."""
    return sorted(variants, key=lambda n: (-len(n.partition(",")[2].strip()), n))[0]


def is_group_aff(a):
    return any(r.search(a) for r in GROUP_RES)


def load():
    """Read raw PubMed records and reshape into a compact internal form."""
    with open(os.path.join(DATA, "articles.json"), encoding="utf-8") as fh:
        raw = json.load(fh)

    pubs = {}
    for pmid, a in raw.items():
        ids = a.get("identifiers", {}) or {}
        pd = a.get("publication_date", {}) or {}
        cit = a.get("citation", {}) or {}
        jr = a.get("journal", {}) or {}

        affs, authors = [], []
        for au in a.get("authors", []) or []:
            name = author_name(au)
            if not name:
                continue
            idxs = []
            for aff in au.get("affiliations", []) or []:
                aff = clean_aff(aff)
                if not aff:
                    continue
                if aff not in affs:
                    affs.append(aff)
                idxs.append(affs.index(aff))
            authors.append((name, idxs))

        year = pd.get("year") or ""
        pubs[pmid] = {
            "pmid": pmid,
            "doi": ids.get("doi") or a.get("doi") or "",
            "pmc": ids.get("pmc") or "",
            "title": clean(a.get("title") or "").rstrip("."),
            "journal": clean(jr.get("iso_abbreviation") or jr.get("title") or ""),
            "journal_full": clean(jr.get("title") or ""),
            "year": int(year) if str(year).isdigit() else None,
            "year_raw": year,
            "month": pd.get("month") or "",
            "vol": cit.get("volume") or "",
            "issue": cit.get("issue") or "",
            "pages": cit.get("pages") or "",
            "types": a.get("article_types") or [],
            "affs": affs,
            "authors": authors,
            "abstract": clean(a.get("abstract") or ""),
        }
    return pubs


def vancouver(p):
    short = []
    for name, _ in p["authors"]:
        last, _, fore = name.partition(",")
        inits = "".join(w[0] for w in fore.split() if w[:1].isalpha())
        short.append(f"{last.strip()} {inits}".strip())
    bits = [", ".join(short) + ".", p["title"] + ".", p["journal"] + "."]
    loc = str(p["year_raw"] or "")
    if p["vol"]:
        loc += f";{p['vol']}"
    if p["issue"]:
        loc += f"({p['issue']})"
    if p["pages"]:
        loc += f":{p['pages']}"
    bits.append(loc + ".")
    return " ".join(b for b in bits if b.strip(". "))


# --------------------------------------------------------------------------
def build_publications(pubs):
    recs = sorted(
        pubs.values(),
        key=lambda p: (-(p["year"] or 0), p["journal"], p["title"]),
    )
    by_year = defaultdict(int)
    for p in recs:
        by_year[p["year"]] += 1
    n_abs = sum(1 for p in recs if p["abstract"])
    n_aff = sum(1 for p in recs if p["affs"])

    o = []
    o.append("# Hans Clevers — complete publication list with full bibliography\n")
    o.append(
        "Compiled from **PubMed** (NCBI), author query `Clevers H[Author]`, retrieved "
        "through the PubMed MCP server. Each entry carries its PubMed ID, DOI and PMC "
        "ID where deposited, the journal reference, the complete author list with each "
        "author's affiliation as indexed by PubMed, and the abstract.\n"
    )
    o.append("## Scope and coverage\n")
    o.append(
        f"| | |\n| --- | ---: |\n"
        f"| Records returned by the PubMed query | 877 |\n"
        f"| Records retrieved in full | {len(recs)} |\n"
        f"| Records carrying an abstract | {n_abs} |\n"
        f"| Records carrying at least one affiliation | {n_aff} |\n"
        f"| Earliest publication year | {min(p['year'] for p in recs if p['year'])} |\n"
        f"| Latest publication year | {max(p['year'] for p in recs if p['year'])} |\n"
    )
    o.append(
        "\n**Caveats you should read before using this list.**\n\n"
        "1. *Author disambiguation.* The query `Clevers H[Author]` matches the "
        "surname-plus-initial string, not a person. It is dominated by Hans "
        "(Johannes C.) Clevers, but a small number of records by unrelated authors "
        "publishing as \"Clevers H\" cannot be excluded without manual inspection of "
        "every record. PubMed also does not index every item Clevers has authored "
        "(book chapters, some commentary, non-indexed journals), so this is his "
        "PubMed-indexed output rather than a certified complete bibliography.\n"
        "2. *Affiliation completeness.* PubMed stored **only the first author's** "
        "affiliation for records entered before roughly 2014, and frequently no "
        "affiliation at all before the mid-1990s. Where an author below carries no "
        "superscript, PubMed holds no affiliation for them on that paper. This is a "
        "limitation of the source, not an omission here.\n"
        "3. *Text fidelity.* Abstracts are reproduced verbatim from PubMed. PubMed "
        "strips italicised species and gene names from some abstracts, which is why a "
        "few read with words missing (e.g. \"which causes Johne's disease\"). "
        "Trailing contact e-mail addresses have been removed from affiliation strings; "
        "everything else is as indexed.\n"
        "4. *One unretrievable record.* PMID 25905254 is returned by the search index "
        "but has no retrievable record (withdrawn/deleted citation), so 876 of the 877 "
        "hits are documented in full.\n"
    )

    o.append("\n## Publications per year\n")
    o.append("| Year | Papers |")
    o.append("| --- | ---: |")
    for y in sorted((k for k in by_year if k), reverse=True):
        o.append(f"| {y} | {by_year[y]} |")
    o.append("")
    o.append("---")

    n = 0
    cur = object()
    for p in recs:
        if p["year"] != cur:
            cur = p["year"]
            o.append(f"\n## {cur}\n")
        n += 1
        o.append(f"### {n}. {p['title']}\n")
        o.append(f"**Citation.** {vancouver(p)}\n")

        ids = [f"PMID [{p['pmid']}](https://pubmed.ncbi.nlm.nih.gov/{p['pmid']}/)"]
        if p["doi"]:
            ids.append(f"DOI [{p['doi']}](https://doi.org/{p['doi']})")
        if p["pmc"]:
            ids.append(
                f"PMC [{p['pmc']}](https://www.ncbi.nlm.nih.gov/pmc/articles/{p['pmc']}/)"
            )
        o.append("**Identifiers.** " + " · ".join(ids) + "\n")

        j = f"**Journal.** {p['journal_full'] or p['journal']}"
        if p["vol"]:
            j += f", vol. {p['vol']}"
        if p["issue"]:
            j += f", issue {p['issue']}"
        if p["pages"]:
            j += f", pp. {p['pages']}"
        j += f" ({p['year_raw']}"
        if p["month"]:
            j += f"-{p['month']}"
        j += ")"
        if p["types"]:
            j += f" — _{', '.join(p['types'])}_"
        o.append(j + "\n")

        o.append("**Authors.**\n")
        for name, idxs in p["authors"]:
            marks = "".join(f"<sup>{i + 1}</sup>" for i in idxs)
            o.append(f"- {name}{marks}")
        o.append("")
        if p["affs"]:
            o.append("**Affiliations.**\n")
            for i, aff in enumerate(p["affs"], 1):
                o.append(f"{i}. {aff}")
            o.append("")
        else:
            o.append("**Affiliations.** _None indexed in PubMed for this record._\n")

        o.append(f"**Abstract.** {p['abstract'] or '_No abstract in the PubMed record._'}\n")
        o.append("---")

    return "\n".join(o) + "\n"


# --------------------------------------------------------------------------
def analyse(pubs):
    people = defaultdict(
        lambda: {
            "variants": set(),
            "pmids": set(),
            "years": [],
            "affs": set(),
            "group_affs": set(),
            "group_years": [],
        }
    )
    for p in pubs.values():
        y = p["year"]
        for name, idxs in p["authors"]:
            rec = people[author_key(name)]
            rec["variants"].add(name)
            rec["pmids"].add(p["pmid"])
            if y:
                rec["years"].append(y)
            mine = [p["affs"][i] for i in idxs if i < len(p["affs"])]
            rec["affs"].update(mine)
            g = [a for a in mine if is_group_aff(a)]
            if g:
                rec["group_affs"].update(g)
                if y:
                    rec["group_years"].append(y)
    return people


def rows_from(people):
    rows = []
    for k, r in people.items():
        if k == CLEVERS_KEY:
            continue
        ys = sorted(r["years"])
        gy = sorted(r["group_years"])
        rows.append(
            {
                "key": k,
                "name": display_name(r["variants"]),
                "variants": sorted(r["variants"]),
                "papers": len(r["pmids"]),
                "first": ys[0] if ys else "",
                "last": ys[-1] if ys else "",
                "gfirst": gy[0] if gy else "",
                "glast": gy[-1] if gy else "",
                "group_affs": sorted(r["group_affs"]),
                "affs": sorted(r["affs"]),
            }
        )
    rows.sort(key=lambda r: (-r["papers"], str(r["first"]), r["name"]))
    return rows


def which_site(affs):
    s = " ".join(affs)
    out = []
    if HUBRECHT.search(s) or NIOB.search(s):
        out.append("Hubrecht/NIOB")
    if MAXIMA.search(s):
        out.append("Princess Máxima")
    if UTRECHT_IMMUNO.search(s) and not out:
        out.append("UMC Utrecht Immunology")
    elif UTRECHT_IMMUNO.search(s):
        out.append("UMC Utrecht Immunology")
    return " + ".join(out) or "—"


def build_people(pubs, rows, roles):
    members = [r for r in rows if r["gfirst"] != ""]
    others = [r for r in rows if r["gfirst"] == ""]

    o = []
    o.append("# The Hans Clevers group — people, 1985–2026\n")
    o.append(
        "Who worked in Hans Clevers' laboratory over the last thirty years, how many "
        "papers each person co-authored with him, and when their first joint paper "
        "appeared. Derived from the complete PubMed record set in "
        "`clevers_publications.md`, cross-checked against the current Hubrecht "
        "Institute and Princess Máxima Center group pages, with roles established by "
        "targeted web research per person.\n"
    )

    o.append("## The lab's three homes\n")
    o.append(
        "Clevers' group has occupied three institutional addresses, which is what makes "
        "affiliation strings usable as a membership signal:\n\n"
        "| Period | Institution as it appears in PubMed |\n"
        "| --- | --- |\n"
        "| 1991–2002 | Department of Immunology, University Hospital / University "
        "Medical Center Utrecht |\n"
        "| 2002–2012 | Hubrecht Laboratory, Netherlands Institute for Developmental "
        "Biology (NIOB); renamed **Hubrecht Institute** (KNAW & UMC Utrecht) in 2007 |\n"
        "| 2015–present | **Princess Máxima Center for Pediatric Oncology**, held "
        "jointly with the Hubrecht; Oncode Institute from 2018; from 2022 also Roche "
        "pRED / Institute of Human Biology, Basel |\n\n"
        "Clevers was President of the KNAW (2012–2015) and Head of Pharma Research and "
        "Early Development at Roche (from March 2022), running the Utrecht group "
        "throughout.\n"
    )

    o.append("## How to read the tables\n")
    o.append(
        "- **Papers with Clevers** — distinct PubMed records co-authored with him.\n"
        "- **First / last co-publication** — years of the earliest and latest shared paper.\n"
        "- **Group-affiliation window** — the first and last year in which *that person's "
        "own affiliation line* on a shared paper names the Hubrecht, the NIOB, the "
        "Princess Máxima Center, or the Utrecht immunology department. It is a lower "
        "bound on their time in the lab, not a contract length.\n"
        "- **Evidence tier A** (Table A) — group affiliation documented in PubMed. "
        "**Tier C** (Table B) — co-author on a shared paper for whom PubMed holds no "
        "affiliation at all. Tier C is *absence of data, not evidence of non-membership*: "
        "PubMed indexed only the first author's address before ~2014, so most people who "
        "passed through the lab in its first two decades land in Table B. Several of the "
        "lab's best-known alumni are there for that reason and are annotated individually.\n"
    )
    o.append(
        f"**Totals.** {len(rows)} distinct co-authors across {len(pubs)} publications. "
        f"{len(members)} have a Hubrecht / NIOB / Máxima / Utrecht-immunology affiliation "
        f"documented on at least one shared paper.\n"
    )

    o.append("\n## Table A — people with a documented Clevers-group affiliation\n")
    o.append(
        "| # | Name | Papers with Clevers | First co-pub | Last co-pub | Group affiliation window | Site | Role in the group | Role source |"
    )
    o.append("| ---: | --- | ---: | ---: | ---: | --- | --- | --- | --- |")
    for i, r in enumerate(members, 1):
        role = roles.get(r["key"], {})
        win = f"{r['gfirst']}–{r['glast']}"
        o.append(
            f"| {i} | {r['name']} | {r['papers']} | {r['first']} | {r['last']} | {win} | "
            f"{which_site(r['group_affs'])} | {role.get('role', '—')} | "
            f"{role.get('source', '—')} |"
        )

    o.append("\n## Table B — co-authors with no affiliation indexed on any shared paper\n")
    o.append(
        "Ordered by number of shared papers. Anyone with a substantial count and an "
        "early first co-publication is, in practice, almost always a lab member from "
        "the pre-2014 era; annotated where established.\n"
    )
    o.append(
        "| # | Name | Papers with Clevers | First co-pub | Last co-pub | Role in the group | Role source |"
    )
    o.append("| ---: | --- | ---: | ---: | --- | --- | --- |")
    for i, r in enumerate(others, 1):
        role = roles.get(r["key"], {})
        o.append(
            f"| {i} | {r['name']} | {r['papers']} | {r['first']} | {r['last']} | "
            f"{role.get('role', '—')} | {role.get('source', '—')} |"
        )

    return "\n".join(o) + "\n"


def write_csv(rows, roles):
    path = os.path.join(DATA, "coauthors.csv")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "name",
                "name_variants",
                "papers_with_clevers",
                "first_copublication",
                "last_copublication",
                "group_affiliation_first_year",
                "group_affiliation_last_year",
                "evidence_tier",
                "site",
                "role_assigned",
                "role_source",
            ]
        )
        for r in rows:
            role = roles.get(r["key"], {})
            w.writerow(
                [
                    r["name"],
                    " | ".join(r["variants"]),
                    r["papers"],
                    r["first"],
                    r["last"],
                    r["gfirst"],
                    r["glast"],
                    "A" if r["gfirst"] != "" else "C",
                    which_site(r["group_affs"]) if r["gfirst"] != "" else "",
                    role.get("role", ""),
                    role.get("source", ""),
                ]
            )


def main():
    pubs = load()
    roles = {}
    rp = os.path.join(DATA, "roles.json")
    if os.path.exists(rp):
        with open(rp, encoding="utf-8") as fh:
            roles = {author_key(k): v for k, v in json.load(fh).items()}

    os.makedirs(DOCS, exist_ok=True)
    with open(os.path.join(DOCS, "clevers_publications.md"), "w", encoding="utf-8") as fh:
        fh.write(build_publications(pubs))

    rows = rows_from(analyse(pubs))
    with open(os.path.join(DOCS, "clevers_group_members.md"), "w", encoding="utf-8") as fh:
        fh.write(build_people(pubs, rows, roles))
    write_csv(rows, roles)

    print(f"publications      : {len(pubs)}")
    print(f"distinct coauthors: {len(rows)}")
    print(f"tier A (group aff): {sum(1 for r in rows if r['gfirst'] != '')}")
    print(f"roles assigned    : {sum(1 for r in rows if r['key'] in roles)}")


if __name__ == "__main__":
    main()
