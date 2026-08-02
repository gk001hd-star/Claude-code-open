#!/usr/bin/env python3
"""Recover every PubMed article record from this session.

Two sources, both on disk:
  1. tool-results/*.txt  -- results the harness spilled because they were large
  2. the session transcript JSONL -- holds the text of every tool result,
     including the smaller ones that were returned inline

Both are scanned; records are keyed by PMID so duplicates collapse.
Output: data/articles.json  (pmid -> raw PubMed article object)
"""
import glob
import json
import os
import re
import sys

TOOL_RESULTS = "/root/.claude/projects/-home-user-Claude-code-open/52f27286-28f7-57b5-9dfe-b25217b65d1b/tool-results"
TRANSCRIPT = "/root/.claude/projects/-home-user-Claude-code-open/52f27286-28f7-57b5-9dfe-b25217b65d1b.jsonl"
OUT = "data/articles.json"


def harvest(blob, sink):
    """Pull the {"articles":[...]} payload out of an arbitrary text blob."""
    i = blob.find('{"articles":')
    if i < 0:
        return 0
    dec = json.JSONDecoder()
    try:
        obj, _ = dec.raw_decode(blob[i:])
    except ValueError:
        return 0
    n = 0
    for a in obj.get("articles", []):
        pmid = a.get("identifiers", {}).get("pmid")
        if pmid:
            sink[pmid] = a
            n += 1
    return n


def walk(node, out):
    """Collect every string in a nested JSON structure."""
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            walk(v, out)
    elif isinstance(node, list):
        for v in node:
            walk(v, out)


def main():
    sink = {}
    if os.path.exists(OUT):
        sink.update(json.load(open(OUT, encoding="utf-8")))
    before = len(sink)

    for f in sorted(glob.glob(os.path.join(TOOL_RESULTS, "*.txt"))):
        harvest(open(f, encoding="utf-8", errors="replace").read(), sink)

    if os.path.exists(TRANSCRIPT):
        with open(TRANSCRIPT, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '{\\"articles\\":' not in line and '{"articles":' not in line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                strings = []
                walk(rec, strings)
                for s in strings:
                    if '{"articles":' in s:
                        harvest(s, sink)

    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(sink, fh, ensure_ascii=False)

    wanted = [l.strip() for l in open("raw/all_pmids.txt") if l.strip()]
    missing = [p for p in wanted if p not in sink]
    with open("raw/missing.txt", "w") as fh:
        fh.write("\n".join(missing))
    print(f"recovered {len(sink)} articles (+{len(sink)-before} new)")
    print(f"missing {len(missing)} of {len(wanted)}")


if __name__ == "__main__":
    main()
