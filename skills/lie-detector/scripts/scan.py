#!/usr/bin/env python3
"""Draw a verifiable random sample of factual claims from documentation.

This script does not decide whether anything is true. It does two jobs a
person should not do by hand, because a person doing them by hand will
reach for the claims they already suspect:

  1. Extract the *checkable* claims from a corpus — sentences asserting
     something a reader could act on, and that code, config or a test can
     contradict. Over-extraction is deliberate; the skill discards.
  2. Draw n of them by a lottery anyone can recompute. Each claim gets a
     ticket, sha256(seed || claim id); the n lowest tickets are the sample.
     Publish the seed and the corpus digest and a sceptic can rerun this
     command and get your sample back, byte for byte.

That is what "provably random" can mean for a repository. Two properties,
and they are separate:

  * **Verifiable** — anyone can recompute the draw. Always true here.
  * **Unbiasable** — the drawer could not have shopped for a seed that
    draws the easy claims. Only true if the seed was fixed by someone
    other than the drawer, or by a public value nobody controlled at the
    time the corpus digest was published (a drand round, a NIST beacon
    pulse, a closing index). Pass it with --seed.

The default seed is the corpus's own git HEAD, which is verifiable but only
weakly unbiasable — it is a value the drawer could re-roll by committing
again. The output says which of the two you got.

Usage:
    scan.py <path>... -n 20                # draw 20 claims
    scan.py <path>... --seed drand:4210000 # externally fixed seed
    scan.py <path>... --pool               # the whole population, no draw
    scan.py <path>... --class A            # stratify: draw within one class
    scan.py <path>... --code               # also mine code comments
    scan.py <path>... --json > audit.json  # the manifest
    scan.py <path>... --verify audit.json  # recompute a published draw
    scan.py --interval 2 20                # what 2 lies in 20 implies

Exit status: 0 normally, 2 when there is nothing to sample, and 1 when
--verify finds the draw does not reproduce.
"""

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
# Reading prose. Same block/fence/front-matter rules as the sibling audits:
# a sentence inside a fence is output being quoted, not a claim being made.
# ---------------------------------------------------------------------------

FENCE = re.compile(r"^\s*(```|~~~)")
HEADING = re.compile(r"^\s*#{1,6}\s")
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TABLE_SEP = re.compile(r"^\s*\|?[\s:|-]*-{2,}[\s:|-]*\|?\s*$")
LINK_ONLY = re.compile(r"^\s*!?\[[^\]]*\]\([^)]*\)\s*$")
INLINE_CODE = re.compile(r"`[^`]+`")
EMPHASIS = re.compile(r"(?:\*{1,3}|_{1,3})(?=\S)|(?<=\S)(?:\*{1,3}|_{1,3})")


def prose_lines(lines):
    """Yield (lineno, line) for prose only: no fences, front-matter or HTML."""
    fm_end = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, min(len(lines), 60)):
            if lines[i].strip() in ("---", "..."):
                fm_end = i + 1
                break

    in_fence = in_comment = False
    for n, line in enumerate(lines, 1):
        if n <= fm_end:
            continue
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        s = line.strip()
        if in_comment:
            if "-->" in s:
                in_comment = False
            continue
        if s.startswith("<!--"):
            if "-->" not in s:
                in_comment = True
            continue
        if not s:
            continue
        yield n, line


def _clean(line):
    """A prose line as a sentence-joiner should see it."""
    s = line.strip()
    if s.startswith(">"):
        s = s.lstrip(">").strip()
    s = BULLET.sub("", s)
    return s


def blocks(prose):
    """Group (lineno, line) into blocks that a sentence may span.

    Yields (kind, block), where kind is "row" for a table row and "prose"
    otherwise. A block breaks at a blank line (a gap in the line numbers),
    at a heading, at a new list item and at a table row — the four places
    where joining two lines would invent a sentence nobody wrote.
    """
    block, prev = [], None
    for n, line in prose:
        starts_new = (
            prev is not None and n != prev + 1
            or HEADING.match(line)
            or BULLET.match(line)
            or line.lstrip().startswith("|")
        )
        if starts_new and block:
            yield "prose", block
            block = []
        prev = n
        if HEADING.match(line):
            continue                      # a heading names, it does not claim
        if TABLE_SEP.match(line) or LINK_ONLY.match(line):
            continue
        if line.lstrip().startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            cells = [c for c in cells if c]
            if len(cells) >= 2:
                yield "row", [(n, " — ".join(cells))]
            continue
        block.append((n, _clean(line)))
    if block:
        yield "prose", block


ABBREV = re.compile(r"\b(?:e\.g|i\.e|etc|vs|cf|approx|Fig|Eq|al|Inc|Ltd"
                    r"|Mr|Ms|Dr|St)\.$", re.I)
SPLIT = re.compile(r"(?<=[.!?])\s+(?=[\"'`(\[*_A-Z0-9])")


def sentences(block):
    """Yield (lineno, sentence) for one block, soft wraps rejoined.

    The line number is where the sentence *starts*, which is the line a
    reader opens the file to.
    """
    parts, marks, pos = [], [], 0
    for n, text in block:
        if parts:
            parts.append(" ")
            pos += 1
        marks.append((pos, n))
        parts.append(text)
        pos += len(text)
    joined = "".join(parts)

    def line_at(offset):
        best = marks[0][1]
        for start, n in marks:
            if start <= offset:
                best = n
            else:
                break
        return best

    start = 0
    for m in SPLIT.finditer(joined):
        candidate = joined[start:m.start()]
        if ABBREV.search(candidate.rstrip()):
            continue                       # "e.g. " is not a sentence end
        yield line_at(start), candidate.strip()
        start = m.end()
    tail = joined[start:].strip()
    if tail:
        yield line_at(start), tail


# ---------------------------------------------------------------------------
# What counts as a claim. Ordered by how cheaply it can be disproved: a
# number is checked against a constant, a guarantee against a test suite, a
# vendor's behaviour against nothing you own. The class a sentence gets is
# the first one that matches, so the sample skews toward the checkable — the
# point is falsification, not coverage of every sentence in the corpus.
# ---------------------------------------------------------------------------

UNIT = (r"ms|s|sec|secs|seconds?|min|mins|minutes?|hours?|days?|weeks?"
        r"|[kmgt]i?b|bytes?|bits?|rows?|records?|files?|lines?|items?"
        r"|requests?|connections?|threads?|workers?|processes|retries"
        r"|attempts?|times|%|percent|chars?|characters?")

_IDENT = (r"(?:`(?:--?[A-Za-z0-9][\w.-]*|[A-Z][A-Z0-9_]{2,}"
          r"|[\w./-]+\.[A-Za-z]{1,5}|\w+\(\)|[\w.-]+/[\w./-]+)`"
          r"|(?<![\w-])--[a-z][\w-]+|\$[A-Z][A-Z0-9_]{2,})")

_ASSERTS = (r"\b(?:is|are|was|sets?|returns?|accepts?|takes?|reads?|writes?"
            r"|creates?|runs?|uses?|supports?|controls?|enables?|disables?"
            r"|expects?|lives?|contains?|holds?|maps?|points?|defaults?"
            r"|exits?|skips?|applies|scans?|prints?|adds?|removes?"
            r"|requires?|written|stored|logged|passed)\b")

CLAIM_CLASSES = [
    ("A", "numeric or default", re.compile(
        r"\b(?:defaults?\s+to|by\s+default|is\s+the\s+default"
        r"|set\s+to\s+\d)\b"
        r"|\b\d+(?:\.\d+)?\s*(?:" + UNIT + r")\b"
        r"|\b(?:limit(?:ed|s)?|maximum|minimum|max|min|timeout|port|size"
        r"|interval|threshold|quota|ttl|batch|depth|width|precision)\b"
        r"[^.]{0,40}?\b\d+", re.I)),

    ("B", "interface", re.compile(
        # Either order: the identifier can be the subject ("`--retries` sets
        # the count") or the object ("the count is read from `RELAY_HOME`").
        r"(?:" + _IDENT + r"[\s\S]{0,80}?" + _ASSERTS + r"|"
        + _ASSERTS + r"[\s\S]{0,80}?" + _IDENT + r")", re.I)),

    # "all" and "any" are determiners far more often than they are
    # absolutes ("all three routes", "any of the above"), and a population
    # they dominate is a sample of ordinary prose. The words kept here are
    # the ones a reader would call a promise if the code broke it.
    ("C", "guarantee or absolute", re.compile(
        r"\b(?:never|always|every|none|only|cannot|can't"
        r"|rarely|seldom|usually|typically|generally|mostly|almost\s+always"
        r"|no\s+\w+\s+(?:is|are|can)|guarantees?|guaranteed|ensures?"
        r"|idempotent|atomic|thread-safe|lossless|immutable|deterministic"
        r"|in\s+every\s+case)\b", re.I)),

    ("D", "dependency or platform", re.compile(
        r"\b(?:requires?|required|depends?\s+on|compatible\s+with"
        r"|supported\s+(?:on|by)|works?\s+(?:on|with)|tested\s+(?:on|with)"
        r"|needs?|runs?\s+on)\b"
        r"|\b(?:python|node|npm|ruby|go|java|rust|php|postgres|postgresql"
        r"|mysql|sqlite|redis|linux|macos|windows|docker|kubernetes|bash)\b"
        r"[^.]{0,20}\bv?\d+(?:\.\d+)*\+?", re.I)),

    ("E", "behaviour on error", re.compile(
        r"\b(?:returns?|raises?|throws?|falls?\s+back|retr(?:y|ies|ied)"
        r"|logs?|ignores?|skips?|validates?|rejects?|aborts?|rolls?\s+back"
        r"|fails?|exits?\s+(?:with|non-zero|\d)|on\s+(?:error|failure)"
        r"|if\s+(?:it|the|this)\s+\w+\s+fails)\b", re.I)),

    ("F", "external or cited", re.compile(
        r"https?://|\bRFC\s?\d+\b|\blicen[cs]ed\s+under\b"
        r"|\b(?:MIT|Apache-2\.0|GPL(?:v[23])?|BSD-[23]-Clause)\b"
        r"|\baccording\s+to\b|\bper\s+the\b", re.I)),
]

# Not claims, whatever else they contain: the document talking about itself,
# an invitation, a question, a heading fragment. These are the audit's own
# false-positive families made mechanical, so the population stays worth
# sampling from.
NOT_A_CLAIM = re.compile(
    r"^(?:see|note|for\s+(?:example|instance)|e\.g\.|i\.e\.)\b[\s\S]{0,30}$"
    r"|^(?:usage|example|options?|arguments?|synopsis)\s*:"
    r"|\b(?:this\s+(?:guide|document|page|section|README)|we(?:'ll|\s+will))\b"
    r"|^\s*[\w -]+\s*:\s*$",
    re.I)

MIN_WORDS = 5
# A table row is already stripped to its content — "`--timeout` — 30
# seconds" is a complete claim in four words, where four words of prose is a
# fragment.
MIN_ROW_WORDS = 3


def classify(sentence, min_words=MIN_WORDS):
    """The claim class of a sentence, or None when it asserts nothing."""
    text = sentence.strip()
    if text.endswith("?") or len(text.split()) < min_words:
        return None
    if NOT_A_CLAIM.search(text):
        return None
    masked = EMPHASIS.sub("", INLINE_CODE.sub(" ⟦code⟧ ", text))
    for cls, label, pattern in CLAIM_CLASSES:
        probe = text if cls == "B" else masked
        if pattern.search(probe):
            return cls, label
    return None


def normalise(text):
    """The form a claim's identity is computed from.

    Whitespace and emphasis are noise: rewrapping a paragraph must not
    reshuffle the lottery, or every commit invalidates the last audit.
    """
    return re.sub(r"\s+", " ", EMPHASIS.sub("", text)).strip()


def claims_in(path, rel=None):
    """Every claim candidate in one file, in document order."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"skipped {path}: {exc}", file=sys.stderr)
        return [], 0

    syntax = comment_syntax(path)
    if syntax:
        prose = list(comment_lines(lines, syntax))
        counted = len(prose)
    else:
        prose = list(prose_lines(lines))
        counted = len(lines)

    out, seen = [], defaultdict(int)
    for kind, block in blocks(prose):
        floor = MIN_ROW_WORDS if kind == "row" else MIN_WORDS
        for lineno, sentence in sentences(block):
            verdict = classify(sentence, floor)
            if not verdict:
                continue
            cls, label = verdict
            norm = normalise(sentence)
            occurrence = seen[norm]
            seen[norm] += 1
            key = "\n".join([rel or path, norm, str(occurrence)])
            out.append({
                "id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:12],
                "file": rel or path,
                "line": lineno,
                "class": cls,
                "label": label,
                "text": sentence,
            })
    return out, counted


# ---------------------------------------------------------------------------
# Code comments. A comment claims as freely as a paragraph does — "# the
# upstream limit is 500" beside a constant of 1000 — and it is checked
# against the code it sits in, which makes it the cheapest claim in the
# corpus to disprove. Extraction machinery mirrors the sibling audits.
# ---------------------------------------------------------------------------

COMMENT_SYNTAX = {}
for _ext in (".py .sh .bash .zsh .rb .pl .r .jl .yaml .yml .toml .tf .nix "
             ".cmake .mk .ex .exs").split():
    COMMENT_SYNTAX[_ext] = (("#",), None, None)
for _ext in (".js .jsx .mjs .cjs .ts .tsx .c .h .cc .hh .cpp .hpp .java .go "
             ".rs .swift .kt .kts .scala .cs .dart .m .mm .proto").split():
    COMMENT_SYNTAX[_ext] = (("//",), "/*", "*/")
for _ext in ".sql .lua .hs".split():
    COMMENT_SYNTAX[_ext] = (("--",), None, None)
COMMENT_SYNTAX[".php"] = (("//", "#"), "/*", "*/")

CODE_BASENAMES = {"Makefile", "makefile", "GNUmakefile", "Dockerfile",
                  "Justfile", "justfile"}


def comment_syntax(path):
    """The comment spec for path, or None for a non-code file."""
    base = os.path.basename(path)
    if base in CODE_BASENAMES:
        return (("#",), None, None)
    return COMMENT_SYNTAX.get(os.path.splitext(base)[1].lower())


DIRECTIVE = re.compile(
    r"^(?:-\*-|noqa|type:|pylint|mypy:|ruff:|flake8:|isort:|fmt:|yapf:"
    r"|eslint|prettier|biome-|@ts-|tslint:|jshint|istanbul|nolint|nosec"
    r"|NOSONAR|pragma|coverage:|cspell:|spell-?checker:|vim:|vi:"
    r"|region\b|endregion\b)", re.I)

# A TODO is a tracker item, and its claim is about the future — there is
# nothing in the tree for it to contradict.
WORK_MARKER = re.compile(r"^(?:TODO|FIXME|XXX|HACK|BUG|todo|fixme)\b")


def _find_marker(line, marker):
    """Index of marker where it can start a comment: column 0, or after
    whitespace. Keeps '#' inside a string and the '//' in a URL out."""
    i = 0
    while True:
        i = line.find(marker, i)
        if i <= 0:
            return i
        if line[i - 1] in " \t":
            return i
        i += 1


def comment_lines(lines, syntax):
    """Yield (lineno, text) for the comment prose in a source file."""
    markers, bopen, bclose = syntax
    in_block = False
    for n, line in enumerate(lines, 1):
        if n == 1 and line.startswith("#!"):
            continue
        if in_block:
            end = line.find(bclose)
            text = line if end == -1 else line[:end]
            in_block = end == -1
        else:
            best = None
            for mk in markers:
                p = _find_marker(line, mk)
                if p != -1 and (best is None or p < best[0]):
                    best = (p, mk, False)
            if bopen:
                p = _find_marker(line, bopen)
                if p != -1 and (best is None or p < best[0]):
                    best = (p, bopen, True)
            if best is None:
                continue
            pos, mk, is_block = best
            text = line[pos + len(mk):]
            if is_block:
                end = text.find(bclose)
                if end == -1:
                    in_block = True
                else:
                    text = text[:end]
        s = text.strip().lstrip("#*/!").strip()
        if not s or not re.search(r"[A-Za-z]", s):
            continue
        if DIRECTIVE.match(s) or WORK_MARKER.match(s):
            continue
        yield n, s


# ---------------------------------------------------------------------------
# Corpus selection. Records are excluded for the same reason as in the
# sibling audits, and for one more: a dated plan's claims were true of a
# proposal, and disproving them proves only that the plan changed.
# ---------------------------------------------------------------------------

RECORD_DIRS = ("/plans/", "/specs/", "/adr/", "/adrs/", "/rfc/", "/rfcs/",
               "/decisions/", "/proposals/", "/journal/", "/changelog/",
               "/meeting-notes/", "/minutes/", "/retros/", "/postmortems/",
               "/superpowers/")
RECORD_FILE = re.compile(r"(^|/)(\d{4}-\d{2}-\d{2}[-_]|CHANGELOG|HISTORY"
                         r"|RELEASES|NEWS\.md)", re.I)

SKIP_DIRS = {"node_modules", ".git", "dist", "build", ".next", "vendor",
             ".venv", "target"}


def is_record(path):
    norm = "/" + path.replace(os.sep, "/").lstrip("./")
    return any(d in norm for d in RECORD_DIRS) or bool(RECORD_FILE.search(norm))


def collect(paths, excludes=(), include_records=False, include_code=False):
    """Gather the corpus. Sorted, so the draw does not depend on the
    filesystem's traversal order. Returns (files, skipped_records)."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
                for name in sorted(names):
                    if name.endswith((".md", ".markdown")):
                        files.append(os.path.join(root, name))
                    elif (include_code and comment_syntax(name)
                          and ".min." not in name):
                        files.append(os.path.join(root, name))
        elif p.endswith((".md", ".markdown")) or comment_syntax(p):
            files.append(p)
    files = sorted(set(f for f in files
                       if not any(x in f for x in excludes)))
    if include_records:
        return files, []
    records = [f for f in files if is_record(f)]
    return [f for f in files if f not in set(records)], records


# ---------------------------------------------------------------------------
# The lottery. Ticket = sha256(seed || id); lowest n tickets win. Sorting a
# hash is not a shuffle anyone can steer: to move a claim out of the sample
# you have to change the claim, which changes the corpus digest, which is
# printed beside the seed.
# ---------------------------------------------------------------------------


def ticket(seed, claim_id):
    return hashlib.sha256(
        (seed + "\x00" + claim_id).encode("utf-8")).hexdigest()


def corpus_digest(files):
    """A digest over the corpus's content, so a later verifier can tell
    "the draw was different" from "the documents were"."""
    h = hashlib.sha256()
    for path in sorted(files):
        try:
            with open(path, "rb") as fh:
                content = fh.read()
        except OSError:
            content = b""
        h.update(path.replace(os.sep, "/").encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(content).hexdigest().encode("ascii"))
        h.update(b"\n")
    return h.hexdigest()[:16]


def draw(claims, seed, n):
    """(sample, queue) — the n winning claims, then the rest in draw order.

    The queue matters: when a drawn claim turns out not to be checkable,
    the replacement is the next ticket, not one the auditor liked better.
    """
    ordered = sorted(claims, key=lambda c: (ticket(seed, c["id"]), c["id"]))
    for rank, claim in enumerate(ordered, 1):
        claim["ticket"] = ticket(seed, claim["id"])[:16]
        claim["rank"] = rank
    return ordered[:n], ordered[n:]


def git_head():
    """The corpus repo's HEAD, or None outside a checkout."""
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    sha = out.stdout.decode("ascii", "ignore").strip()
    return sha or None


def wilson(k, n, z=1.96):
    """95% Wilson interval for k lies found in n draws.

    A sample of twenty with nothing false does not mean the docs are true;
    it means the false rate is probably under about one in six. The report
    should say which of those it is claiming.
    """
    if n <= 0:
        return 0.0, 1.0
    p = k / float(n)
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, centre - margin), min(1.0, centre + margin)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

QUEUE_SHOWN = 5


def _render(claim):
    return ("{file}:{line}  [{cls} {label}]  id {id}\n    {text}"
            .format(cls=claim["class"], **claim))


def report(sample, queue, claims, stats, manifest, records, args):
    if args.pool:
        print("=== population — every claim candidate, in document order ===")
        for c in sorted(claims, key=lambda c: (c["file"], c["line"])):
            print(_render(c))
        print()
    else:
        print("=== sample — {} of {} claim(s) ===".format(len(sample),
                                                          len(claims)))
        for c in sample:
            print(_render(c))
        if queue:
            print("\n=== queue — the next draws, in order, for any claim "
                  "that turns out unfalsifiable ===")
            for c in queue[:QUEUE_SHOWN]:
                print(_render(c))

    by_class = defaultdict(int)
    for c in claims:
        by_class[(c["class"], c["label"])] += 1
    print("\n=== population by class ===")
    for (cls, label), count in sorted(by_class.items()):
        print("    {}  {:<24} {}".format(cls, label, count))

    dense = sorted((s for s in stats if s["claims"]),
                   key=lambda s: -s["per_100_lines"])
    if dense:
        print("\n=== claims per 100 lines ===")
        for s in dense:
            print("    {:5.1f}  {}  ({} in {} lines)".format(
                s["per_100_lines"], s["file"], s["claims"], s["lines"]))
    silent = [s["file"] for s in stats if not s["claims"]]
    if silent:
        print("\nno claims extracted: " + ", ".join(silent))

    print("\nseed: {} ({})".format(manifest["seed"], manifest["seed_source"]))
    print("corpus: sha256:{}  population: {}  drawn: {}".format(
        manifest["corpus"], manifest["population"], len(sample)))
    print(manifest["unbiasable"])
    if records:
        print("Skipped {} record(s) — dated plans, specs, ADRs, changelogs. "
              "Their claims were true of a proposal.".format(len(records)))
    print("\nAnyone can recompute this draw:")
    print("    {} {} --seed {} -n {}".format(
        os.path.basename(sys.argv[0]), " ".join(args.paths),
        manifest["seed"], manifest["n"]))
    print("Candidates, not lies — each drawn claim needs the code open, and "
          "'no evidence' is Unsupported, not False.")


def do_verify(path, claims, manifest):
    """Recompute someone else's draw. Exit 1 when it does not reproduce."""
    try:
        with open(path, encoding="utf-8") as fh:
            old = json.load(fh)
    except (OSError, ValueError) as exc:
        print("cannot read manifest {}: {}".format(path, exc), file=sys.stderr)
        return 1

    problems = []
    for key, label in (("seed", "seed"), ("corpus", "corpus digest"),
                       ("population", "population size"), ("n", "n")):
        if old.get(key) != manifest.get(key):
            problems.append("{}: manifest {!r}, recomputed {!r}".format(
                label, old.get(key), manifest.get(key)))

    old_ids = [c["id"] for c in old.get("sample", [])]
    new_ids = [c["id"] for c in manifest["sample"]]
    if old_ids != new_ids:
        problems.append("sample: {} of {} drawn claims differ".format(
            len(set(old_ids) ^ set(new_ids)), max(len(old_ids), len(new_ids))))

    if problems:
        print("DRAW DOES NOT REPRODUCE")
        for p in problems:
            print("  - " + p)
        if old.get("corpus") != manifest.get("corpus"):
            print("\nThe corpus digest moved, so the documents changed since "
                  "the draw. That is expected after edits — rerun the draw "
                  "against this revision rather than reading it as a lie.")
        return 1

    print("DRAW REPRODUCES")
    print("  seed {} over {} claim(s); the same {} were drawn.".format(
        manifest["seed"], manifest["population"], len(new_ids)))
    return 0


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*")
    ap.add_argument("-n", type=int, default=20,
                    help="how many claims to draw (default 20)")
    ap.add_argument("--seed", help="lottery seed; use an externally fixed "
                                   "value when someone has to trust the draw")
    ap.add_argument("--pool", action="store_true",
                    help="print the whole population instead of a draw")
    ap.add_argument("--class", dest="cls",
                    help="draw within one class only (A-F): a stratified "
                         "sample, not a sample of the corpus")
    ap.add_argument("--json", action="store_true", help="the manifest")
    ap.add_argument("--verify", metavar="MANIFEST",
                    help="recompute the draw in MANIFEST — its seed and n are "
                         "taken from the file; exit 1 if it does not reproduce")
    ap.add_argument("--code", action="store_true",
                    help="also mine code comments when walking directories")
    ap.add_argument("--exclude", action="append", default=[], metavar="SUBSTR",
                    help="skip paths containing SUBSTR (repeatable)")
    ap.add_argument("--include-records", action="store_true",
                    help="also sample dated plans/specs/ADRs")
    ap.add_argument("--interval", nargs=2, type=int, metavar=("K", "N"),
                    help="what K lies in N draws implies for the corpus")
    args = ap.parse_args()

    if args.interval:
        k, n = args.interval
        if n <= 0 or k < 0 or k > n:
            print("--interval needs 0 <= K <= N and N > 0", file=sys.stderr)
            return 2
        lo, hi = wilson(k, n)
        print("{} false in {} drawn.".format(k, n))
        print("Corpus false-claim rate: {:.0%} observed, 95% interval "
              "{:.0%}-{:.0%}.".format(k / float(n), lo, hi))
        if k == 0:
            print("Nothing was disproved, which bounds the rate rather than "
                  "clearing the corpus: up to {:.0%} of claims could still "
                  "be false.".format(hi))
        return 0

    if not args.paths:
        print("nothing to sample: name a file or directory", file=sys.stderr)
        return 2

    files, records = collect(args.paths, args.exclude, args.include_records,
                             args.code)
    if not files:
        note = " ({} record(s) skipped)".format(len(records)) if records else ""
        print("no standing documents found" + note, file=sys.stderr)
        return 2

    claims, stats = [], []
    for path in files:
        found, counted = claims_in(path)
        claims += found
        stats.append({"file": path, "lines": counted, "claims": len(found),
                      "per_100_lines": round(100 * len(found) / counted, 1)
                      if counted else 0.0})
    if args.cls:
        want = args.cls.upper()
        claims = [c for c in claims if c["class"] == want]
        counts = defaultdict(int)
        for c in claims:
            counts[c["file"]] += 1
        for s in stats:
            s["claims"] = counts[s["file"]]
            s["per_100_lines"] = round(100 * s["claims"] / s["lines"], 1) \
                if s["lines"] else 0.0

    if not claims:
        print("no checkable claims found in {} file(s)".format(len(files)),
              file=sys.stderr)
        return 2

    # Verifying reproduces someone else's draw, so its parameters come from
    # their manifest unless the caller deliberately overrides them.
    if args.verify and not args.seed:
        try:
            with open(args.verify, encoding="utf-8") as fh:
                prior = json.load(fh)
            args.seed = prior.get("seed") or args.seed
            if prior.get("n"):
                args.n = prior["n"]
        except (OSError, ValueError):
            pass                      # do_verify reports the unreadable file

    head = git_head()
    if args.seed:
        seed, source = args.seed, "given on the command line"
    elif head:
        seed, source = "git:" + head[:12], "the corpus repo's HEAD"
    else:
        seed, source = "corpus:" + corpus_digest(files), "the corpus itself"

    unbiasable = (
        "This draw is verifiable and unbiasable: the seed came from outside "
        "the corpus, so it could not be shopped for."
        if args.seed else
        "This draw is verifiable but only weakly unbiasable: the seed comes "
        "from the corpus, which the drawer controls. Pass --seed with a value "
        "fixed by someone else — a drand round, a beacon pulse, the "
        "requester's own string — when the draw has to be trusted.")

    sample, queue = draw(claims, seed, max(0, args.n))
    manifest = {
        "seed": seed,
        "seed_source": source,
        "unbiasable": unbiasable,
        "corpus": corpus_digest(files),
        "files": [s["file"] for s in stats],
        "population": len(claims),
        "n": max(0, args.n),
        "class_filter": args.cls.upper() if args.cls else None,
        "sample": sample,
        "queue": queue[:QUEUE_SHOWN],
        "stats": stats,
        "skipped_records": records,
    }

    if args.verify:
        return do_verify(args.verify, claims, manifest)
    if args.json:
        json.dump(manifest, sys.stdout, indent=2)
        print()
        return 0
    report(sample, queue, claims, stats, manifest, records, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
