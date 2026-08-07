#!/usr/bin/env python3
"""Scan markdown for metadiscourse candidates.

Cheap mechanical pass. Produces candidates with file:line and a suggested
class; a reader still decides. Deliberately over-reports — a false positive
costs one glance, a miss costs a class-0 artifact surviving another year.

Usage:
    scan.py <path>...                    # scan files or directories
    scan.py <path>... --json             # machine-readable
    scan.py <path>... --class 0          # only iteration artifacts
    scan.py <path>... --fix              # apply the safe rewrites only
    scan.py <path>... --fix --dry-run    # show what --fix would change

Exit status is 0 unless --check is passed, in which case any finding exits 1.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
# Patterns. Each entry: (class, label, compiled regex).
#
# Classes 0 and 0.5 come from revising a document; 1-10 can be in a first
# draft. That ordering is why 0 and 0.5 are scanned and reported first.
# ---------------------------------------------------------------------------

PATTERNS = [
    # --- Class 0: iteration artifacts ---------------------------------------
    ("0a", "prior-state reference", re.compile(
        r"\b(previously|formerly|used to be|an earlier (?:version|note|draft|section)"
        r"|the original (?:table|version|note|plan)|first version|initial version"
        r"|we (?:had|thought|concluded|assumed)|no longer|has since|since then"
        r"|what we had)\b", re.I)),
    ("0a", "self-correction", re.compile(
        r"\b(was wrong|were wrong|got wrong|measured wrong|misread|mistakenly"
        r"|wrongly|superseded|revised|half right|overturn(?:ed|s)?"
        r"|turned out (?:to be )?wrong|corrected (?:above|below|this|that))\b", re.I)),
    ("0a", "pass/round marker", re.compile(
        r"\b((?:first|second|third|initial|original|search-only|earlier) pass"
        r"|both passes|rounds? (?:one|two|1|2))\b", re.I)),
    ("0b", "version changelog", re.compile(
        r"\b(Changed|Corrected|Added|Updated|Fixed|Removed|Introduced) in\s+[`_'\"]?\S+",
    )),
    ("0b", "recency marker on behaviour", re.compile(
        r"\bnow\s+(parses|uses|prints|carries|reads|returns|handles|supports"
        r"|requires|merges|includes|emits|writes|treats|scores|flags|drops)\b")),
    # NOTE: a "does X rather than Y" pattern was tried here and removed. Across
    # four repos it fired ~25 times and was wrong every time: "X rather than Y"
    # is how design docs state a *choice*, not how they narrate a *change*.
    # A changelog says what the code used to do; a design contrast says what it
    # does instead of a plausible alternative. Only the first is an artifact.
    ("0b", "pre-change narrative", re.compile(
        r"\b(before this (?:branch|change|fix) existed|until (?:recently|this)"
        r"|the first version of (?:this|the) \w+)\b", re.I)),
    ("0c", "dated status stamp", re.compile(
        r"(_?Status[:\s]+\d{4}-\d{2}-\d{2}|\bas of \d{4}|\bnow settled\b"
        r"|\bstill (?:TODO|TBD|open)\b|\bhas not been made\b)", re.I)),
    # A bare `(issue #22)` is a cheap, durable pointer — keep it. What rots is a
    # claim about the issue's *state*, so only flag a reference that carries one.
    ("0d", "status claim on a tracker item", re.compile(
        r"(?:issue|ticket|PR)\s*#\d+.{0,80}\b(has not been|hasn't been|still open"
        r"|not yet|should be (?:rewritten|updated|closed)|is blocked|remains open)\b"
        r"|\b(?:has not been|hasn't been|still open|not yet done|should be"
        r" (?:rewritten|updated|closed)).{0,80}(?:issue|ticket|PR)\s*#\d+", re.I)),

    # --- Class 0.5: caveats in the main line ---------------------------------
    ("0.5", "explicit caveat", re.compile(
        r"\b(caveat|the one limit|the only limit|limitation|not verified"
        r"|unverified|should be checked|bear in mind|keep in mind|be aware"
        r"|it should be noted|to be fair|admittedly|with the exception)\b", re.I)),
    ("0.5", "mid-sentence concession", re.compile(
        r"\b(however|although|though|that said|then again|on the other hand"
        r"|but note|note that)\b", re.I)),
    ("0.5", "risk note", re.compile(
        r"\b(risk|hazard|danger|pitfall|gotcha)\b", re.I)),

    # --- Classes 1-10: staging ------------------------------------------------
    ("1", "document self-reference", re.compile(
        r"\b(this (?:document|doc|section|note|guide|file|page|README|plan|table)\b"
        r"|how to read this|the point of writing|for the record"
        r"|a note on\b|notes on\b)", re.I)),
    ("2", "navigation", re.compile(
        r"\b(see (?:§|section|above|below)|as (?:noted|mentioned|discussed|described)"
        r" (?:above|below|earlier)|the (?:table|section|list|point) (?:above|below)"
        r"|stop reading|read .{0,20}first)\b", re.I)),
    ("4", "enumerative pre-announcement", re.compile(
        r"^\**(Two|Three|Four|Five|Six|Seven|Eight|Nine|Ten|Both|Several)\b"
        r"[^.!?]{0,60}:\s*$")),
    ("4", "inline count preamble", re.compile(
        r"\b(Two|Three|Four|Five|Six|Seven) (things|further|more|hard|key|reasons"
        r"|consequences|caveats|rules|priors|gaps|ways|independent|separate)\b")),
    ("5", "'worth X' attitude marker", re.compile(
        r"\bworth (a\b|the\b|it\b|\d|noting|knowing|remembering|mentioning"
        r"|recording|carrying|defending|deciding|re-?checking|a glance)", re.I)),
    ("6", "salience superlative", re.compile(
        r"\b(the (?:single )?most \w+|the least \w+|the (?:weakest|strongest|best"
        r"|worst) (?:thing|part|area|link)|literally the|is the finding"
        r"|the important (?:thing|one)|the key (?:thing|point|takeaway))\b", re.I)),
    ("7", "intent disclosure", re.compile(
        r"\b(deliberately|on purpose|explicitly|intentionally|by design)\b", re.I)),
    ("8", "contrastive framing", re.compile(
        r"(\bnot (?:a|an|the) [\w-]+[;,] (?:it|that|this) is\b"
        r"|\b(?:is|are) \w+, not \w+\b)", re.I)),
    ("9", "meta-commentary on the record", re.compile(
        r"\b(the diff is the record|worth recording|being wrong in a recorded way"
        r"|flagging (?:it|this) as|the point of (?:writing|documenting))\b", re.I)),
]

HEADING_ASSERTS = [
    ("10", "heading argues rather than names", re.compile(
        r"^#{1,6}\s+.*(, and why\s*$|^#{1,6}\s+(?:Why|What|How) .{0,60}$"
        r"|—.*\bnot\b.*$|:\s*.{0,40}\bnot\b)", re.I)),
]

# Per-label suppressors: if the line matches, the hit is dropped.
#
# These encode senses the pattern can't tell apart from position alone. A
# "round" is a revision of a document *or* a wave of a survey; "formerly" marks
# a doc's own prior state *or* a third party's rename. Suppressing the research
# and third-party senses here is better than making a reader discard the same
# false positives on every run — but each one is a deliberate blind spot, so
# keep the list short and justified.
SUPPRESS = {
    "pass/round marker": re.compile(
        r"\b(survey|sampling|funding|seed|series [a-e]\b|interview|review|bidding"
        r"|tournament|election|negotiation)\b", re.I),
    # "Acme (formerly Initech)" is a fact about a company, not about
    # this document. Same for a person's prior employer in a bio line.
    "prior-state reference": re.compile(
        r"\b(formerly|previously|née|rebranded|renamed|acquired by|spun out"
        r"|prior to joining|before joining)\b[^.]{0,60}"
        r"\b(inc\.|llc|ltd|corp|company|brands?|portfolio|founded|co-founder"
        r"|CEO|CTO|president)\b", re.I),
}

# ---------------------------------------------------------------------------
# --fix: only rewrites whose removal cannot lose a fact.
#
# Everything valuable in this audit needs a human to decide what the surviving
# fact is; those are reported, never applied. Keeping --fix this narrow is what
# makes it safe to run unattended.
# ---------------------------------------------------------------------------

NUM_WORDS = {"Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"}

SAFE_FIXES = [
    # "It is worth noting that X" -> "X"
    (re.compile(r"\bIt(?:'s| is) worth (?:noting|mentioning|pointing out) that\s+"), ""),
    # "Worth noting: X" / "Worth knowing: X" -> "X"
    (re.compile(r"^\**Worth (?:noting|knowing|mentioning)\**:\s*"), ""),
    # discourse filler with no propositional content
    (re.compile(r"\bNeedless to say,\s*"), ""),
    (re.compile(r"^Of course,\s+"), ""),
    (re.compile(r"\bIt goes without saying that\s+"), ""),
    # "Then confirmed against X" -> "Confirmed against X" (ordering isn't a fact)
    (re.compile(r"\bThen confirmed\b"), "Confirmed"),
]

# "Two priors worth defending explicitly:" -> "Two priors:"
#
# The *wrapper* is lossless to remove; the *count* is not. Dropping "Two" from
# "Two independent defences" loses the argument (that there are two, and that
# their independence is the point), and dropping "Three" from "Three passes"
# loses a reader's sense of how long the list is before they start it. Counts
# are reported as class 4 for a human to judge, never auto-stripped — the whole
# claim of --fix is that it cannot lose a fact.
COUNT_WORTH_PREAMBLE = re.compile(
    r"^(\**)((?:" + "|".join(NUM_WORDS) + r")\s+[a-z][\w-]*)\s+worth\s+[\w\s]+?(\**:)\s*$")


def apply_safe_fixes(line):
    """Return (new_line, [descriptions]) for the conservative rewrite set."""
    changes = []
    new = line

    m = COUNT_WORTH_PREAMBLE.match(new)
    if m:
        bold, head, close = m.groups()
        new = f"{bold}{head}{close}"
        changes.append("dropped the 'worth …' wrapper from a list preamble")
        return new, changes

    for pat, repl in SAFE_FIXES:
        candidate = pat.sub(repl, new)
        if candidate != new:
            changes.append(f"removed {pat.pattern!r}")
            new = candidate

    if changes and new and new[0].islower() and line[0].isupper():
        new = new[0].upper() + new[1:]

    return new, changes


# ---------------------------------------------------------------------------

FENCE = re.compile(r"^\s*```")


def scan_file(path):
    """Yield findings for one markdown file, skipping fenced code blocks."""
    findings = []
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"skipped {path}: {exc}", file=sys.stderr)
        return findings

    in_fence = False
    for n, line in enumerate(lines, 1):
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or not line.strip():
            continue

        table_row = line.lstrip().startswith("|")
        heading = line.lstrip().startswith("#")

        checks = HEADING_ASSERTS if heading else PATTERNS
        if heading:
            checks = HEADING_ASSERTS + PATTERNS

        for cls, label, pat in checks:
            m = pat.search(line)
            if not m:
                continue
            sup = SUPPRESS.get(label)
            if sup and sup.search(line):
                continue
            # A caveat inside a table cell is usually a tag, not a clause.
            if table_row and cls == "0.5" and len(line) > 200:
                continue
            findings.append({
                "file": path,
                "line": n,
                "class": cls,
                "label": label,
                "match": m.group(0).strip(),
                "text": line.strip(),
            })
    return findings


def collisions(findings):
    """Superlatives and aphorisms repeated across files.

    Only meaningful corpus-wide: a superlative is information exactly once.
    Two documents each calling something 'the most important' cancel out, and
    neither file shows the problem on its own.
    """
    buckets = defaultdict(list)
    for f in findings:
        if f["class"] not in ("6", "9"):
            continue
        key = re.sub(r"[^a-z ]", "", f["match"].lower()).strip()
        if len(key) < 8:
            continue
        buckets[key].append(f)
    out = []
    for key, group in sorted(buckets.items()):
        files = {g["file"] for g in group}
        if len(files) > 1 or len(group) > 2:
            out.append({"phrase": key, "count": len(group),
                        "sites": [f"{g['file']}:{g['line']}" for g in group]})
    return out


# A dated plan, spec, ADR or RFC is a record of a decision at a moment. Its
# "previously/now" language is its content, not residue — the document is
# *supposed* to be read as of its date. Scanning them buries the standing docs:
# on two real repos they were 175/234 and 117/121 of all findings.
RECORD_DIRS = ("/plans/", "/specs/", "/adr/", "/adrs/", "/rfc/", "/rfcs/",
               "/decisions/", "/proposals/", "/journal/", "/changelog/",
               "/meeting-notes/", "/retros/", "/superpowers/")
RECORD_FILE = re.compile(r"(^|/)(\d{4}-\d{2}-\d{2}[-_]|CHANGELOG|HISTORY|RELEASES)",
                         re.I)


def is_record(path):
    """True for point-in-time records, as opposed to standing documents."""
    norm = "/" + path.replace(os.sep, "/").lstrip("./")
    return any(d in norm for d in RECORD_DIRS) or bool(RECORD_FILE.search(norm))


def collect(paths, excludes=(), include_records=False):
    """Gather markdown, minus --exclude substrings and (by default) records.

    Also worth excluding: a document *about* metadiscourse quotes metadiscourse
    on every line, and so does a style guide. Left in, they dominate the output.

    Returns (files, skipped_records) so the caller can report what it dropped —
    a silent exclusion reads as "nothing there".
    """
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = [d for d in dirs if d not in
                           {"node_modules", ".git", "dist", "build", ".next",
                            "vendor", ".venv", "target"}]
                files += [os.path.join(root, n) for n in sorted(names)
                          if n.endswith((".md", ".markdown"))]
        elif p.endswith((".md", ".markdown")):
            files.append(p)
    files = [f for f in files if not any(x in f for x in excludes)]
    if include_records:
        return files, []
    records = [f for f in files if is_record(f)]
    return [f for f in files if f not in set(records)], records


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--class", dest="cls", help="filter, e.g. 0 or 0.5 or 6")
    ap.add_argument("--fix", action="store_true", help="apply the safe rewrites")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="exit 1 if anything found")
    ap.add_argument("--exclude", action="append", default=[],
                    metavar="SUBSTR", help="skip paths containing SUBSTR (repeatable)")
    ap.add_argument("--include-records", action="store_true",
                    help="also scan dated plans/specs/ADRs (excluded by default)")
    args = ap.parse_args()

    # Exclude this skill's own prose, by resolved path rather than by name.
    # A document *about* metadiscourse quotes metadiscourse on every line, so
    # scanning SKILL.md or references/ buries real findings. Matching on the
    # name instead would blind the scanner to anything under a directory called
    # metadiscourse-audit — including the install directory and its fixtures.
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    excludes = list(args.exclude) + [
        os.path.join(here, "SKILL.md"),
        os.path.join(here, "README.md"),
        os.path.join(here, "references") + os.sep,
    ]
    files, records = collect(args.paths, excludes, args.include_records)
    if not files:
        print("no standing markdown found"
              + (f" ({len(records)} record docs skipped)" if records else ""),
              file=sys.stderr)
        return 2

    if args.fix:
        total = 0
        for path in files:
            src = open(path, encoding="utf-8").read().splitlines(keepends=True)
            out, edits, in_fence = [], [], False
            for n, raw in enumerate(src, 1):
                line = raw.rstrip("\n")
                if FENCE.match(line):
                    in_fence = not in_fence
                    out.append(raw)
                    continue
                if in_fence:
                    out.append(raw)
                    continue
                new, changes = apply_safe_fixes(line)
                if changes:
                    edits.append((n, line, new, changes))
                    out.append(new + ("\n" if raw.endswith("\n") else ""))
                else:
                    out.append(raw)
            if edits:
                total += len(edits)
                print(f"\n{path}")
                for n, old, new, changes in edits:
                    print(f"  {n}: - {old}")
                    print(f"  {n}: + {new}")
                    print(f"      ({'; '.join(changes)})")
                if not args.dry_run:
                    open(path, "w", encoding="utf-8").write("".join(out))
        verb = "would apply" if args.dry_run else "applied"
        print(f"\n{verb} {total} safe rewrite(s)"
              + (f"; skipped {len(records)} record doc(s)." if records else "."))
        print("Everything else needs a decision about what the surviving fact is "
              "— run without --fix to see it.")
        return 0

    findings = []
    for path in files:
        findings += scan_file(path)
    if args.cls:
        findings = [f for f in findings if f["class"].startswith(args.cls)]

    coll = collisions(findings)

    if args.json:
        json.dump({"findings": findings, "collisions": coll,
                   "skipped_records": records}, sys.stdout, indent=2)
        print()
    else:
        by_class = defaultdict(list)
        for f in findings:
            by_class[f["class"]].append(f)
        order = ["0a", "0b", "0c", "0d", "0.5"] + [str(i) for i in range(1, 11)]
        for cls in order:
            group = by_class.get(cls)
            if not group:
                continue
            print(f"\n=== class {cls} — {len(group)} candidate(s) ===")
            for f in group:
                print(f"{f['file']}:{f['line']}  [{f['label']}]")
                print(f"    {f['text'][:160]}")
        if coll:
            print(f"\n=== collisions — {len(coll)} phrase(s) repeated across files ===")
            for c in coll:
                print(f"  {c['phrase']!r} ×{c['count']}: {', '.join(c['sites'])}")
        print(f"\n{len(findings)} candidate(s) across {len(files)} file(s).")
        if records:
            print(f"Skipped {len(records)} point-in-time record(s) — dated plans, "
                  "specs, ADRs, changelogs. Their history IS their content; pass "
                  "--include-records to scan them anyway.")
        print("Candidates, not verdicts — classes 0 and 0.5 first, they are the "
              "ones that come from iterating.")

    return 1 if (args.check and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
