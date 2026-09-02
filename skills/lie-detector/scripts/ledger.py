#!/usr/bin/env python3
"""The claim ledger: every factual claim in a doc set, and what settled it.

`scan.py` extracts claims and can draw a sample of them. This manages the
other mode — a ledger checked into the audited repository, holding one entry
per claim with its verdict and the evidence cited for it.

    ledger.py init docs README.md      # enrol every claim, unverified
    ledger.py check                    # the gate: new, stale or refuted
    ledger.py check --backlog          # what to verify next, batched
    ledger.py record verdicts.json     # write verdicts back, with evidence
    ledger.py show docs/relay.md:16    # provenance for one claim

Four commands, because a person does four things: enrol once, ask what needs
attention, write down what they found, and look up one sentence. Everything
else is a view of the same comparison, so it is a flag on `check`.

The division of labour: everything here is mechanical — extraction, identity,
hashing, staleness, ordering, the gate. Deciding what evidence settles a
claim, and reading it, is the skill's job. This file will not record a
verdict nobody established, which is why `record` rejects a supported or
refuted verdict that quotes no evidence.

Exit status: 0 clean, 1 the gate found something blocking, 2 nothing to do.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import OrderedDict, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan  # noqa: E402  — extraction is shared with the sampling mode

SCHEMA = 1
DEFAULT_LEDGER = "*.claims.toml"

VERDICTS = ("unverified", "supported", "refuted", "unsupported", "unverifiable")
NEEDS_EVIDENCE = ("supported", "refuted")


# ---------------------------------------------------------------------------
# TOML. Reading uses the standard library where it exists; below 3.11 there is
# no tomllib, and this repository ships no dependencies, so the fallback parses
# the subset this file writes. Hand-edits stay inside that subset — strings,
# integers, booleans, arrays of strings, [[claim]] and [[claim.evidence]] —
# and anything outside it raises rather than being silently dropped.
# ---------------------------------------------------------------------------

try:
    import tomllib as _tomllib
except ImportError:
    _tomllib = None


def _unescape(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            nxt = s[i + 1]
            out.append({"n": "\n", "t": "\t", '"': '"', "\\": "\\"}.get(nxt, nxt))
            i += 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _split_top(s):
    """Split an array body on commas that are not inside a string."""
    parts, buf, in_str, esc = [], [], False, False
    for c in s:
        if in_str:
            buf.append(c)
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
            buf.append(c)
        elif c == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(c)
    if "".join(buf).strip():
        parts.append("".join(buf))
    return parts


def _value(raw):
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) >= 2:
        return _unescape(raw[1:-1])
    if raw in ("true", "false"):
        return raw == "true"
    if raw.startswith("[") and raw.endswith("]"):
        return [_value(p) for p in _split_top(raw[1:-1]) if p.strip()]
    try:
        return int(raw)
    except ValueError:
        raise ValueError("unsupported TOML value: %r" % raw)


def _loads_fallback(text):
    doc = {}
    table = doc
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[["):
            if not line.endswith("]]"):
                raise ValueError("line %d: unterminated table header" % lineno)
            path = line[2:-2].strip().split(".")
            if len(path) == 1:
                table = {}
                doc.setdefault(path[0], []).append(table)
            else:
                parent = doc.get(path[0])
                if not parent:
                    raise ValueError("line %d: %s before any [[%s]]"
                                     % (lineno, line, path[0]))
                child = {}
                parent[-1].setdefault(".".join(path[1:]), []).append(child)
                table = child
            continue
        if line.startswith("["):
            raise ValueError("line %d: single-bracket tables are not supported"
                             % lineno)
        if "=" not in line:
            raise ValueError("line %d: expected key = value" % lineno)
        key, _, val = line.partition("=")
        try:
            table[key.strip()] = _value(val)
        except ValueError as exc:
            raise ValueError("line %d: %s" % (lineno, exc))
    return doc


def loads(text):
    """Parse the ledger. tomllib where available, the subset parser below it.

    tomllib nests [[claim.evidence]] under the claim's "evidence" key; the
    fallback stores it under the same name, so callers see one shape.
    """
    if _tomllib is not None:
        return _tomllib.loads(text)
    return _loads_fallback(text)


def _dump_value(v):
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, (list, tuple)):
        return "[" + ", ".join(_dump_value(x) for x in v) + "]"
    s = str(v).replace("\\", "\\\\").replace('"', '\\"')
    s = s.replace("\n", "\\n").replace("\t", "\\t")
    return '"' + s + '"'


CLAIM_KEY_ORDER = ("id", "line", "text", "anchored",
                   "skeleton_hash", "class", "verdict", "exempt", "severity",
                   "correction", "note", "searched", "guarded_by",
                   "supersedes", "verified_at", "verified_by", "revision")
EVIDENCE_KEY_ORDER = ("file", "symbol", "lines", "hash", "quote", "why", "note")


def _dump_table(d, order):
    lines = []
    for key in order:
        if key in d and d[key] not in (None, ""):
            lines.append("%s = %s" % (key, _dump_value(d[key])))
    for key in sorted(k for k in d if k not in order):
        if key in ("evidence", "evidence_candidate"):
            continue
        if d[key] not in (None, ""):
            lines.append("%s = %s" % (key, _dump_value(d[key])))
    return lines


def dumps(ledger):
    """Serialise, sorted by claim id.

    Sorted because two branches that each add claims should conflict only
    where they genuinely disagree; append order would conflict every time.
    """
    out = ["# Written by lie-detector. One entry per factual claim, with the",
           "# evidence that settled it. Re-check with: ledger.py check",
           "schema = %d" % ledger.get("schema", SCHEMA),
           "doc = %s" % _dump_value(ledger.get("doc", "")),
           "generated_at = %s" % _dump_value(ledger.get("generated_at", ""))]
    for key in ("revision", "code", "include_records", "exclude"):
        if ledger.get(key):
            out.append("%s = %s" % (key, _dump_value(ledger[key])))
    out.append("")
    for claim in sorted(ledger.get("claim", []), key=lambda c: c["id"]):
        out.append("[[claim]]")
        out += _dump_table(claim, CLAIM_KEY_ORDER)
        for kind in ("evidence", "evidence_candidate"):
            for ev in claim.get(kind, []):
                out.append("")
                out.append("  [[claim.%s]]" % kind)
                out += ["  " + line for line in
                        _dump_table(ev, EVIDENCE_KEY_ORDER)]
        out.append("")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Identity and staleness are two different hashes, and keeping them apart is
# what lets a verdict have a history.
#
#   identity  — which claim this is: the file plus the identifiers it is
#               about (a flag, a constant, a path). Editing 500 to 100 leaves
#               identity alone, so the entry keeps its audit trail instead of
#               arriving as a stranger.
#   skeleton  — what it asserts: those identifiers plus the numbers, units,
#               quantifiers and modals. Rewording prose does not move it;
#               changing a value, a unit or a "never" does.
#
# The pairing is the answer to the obvious objection to hashing prose — that
# a typo fix would invalidate a verdict somebody spent real attention on.
# ---------------------------------------------------------------------------

# A claim may carry its own id in the document, as a markdown footnote
# reference at the end of the sentence: "…defaults to 500 events.[^c4e23315]"
# An anchored claim can be reworded freely and keep its verdict, which the
# derived key cannot promise — a third of the claims in a real corpus name no
# identifier at all, and those are keyed on their opening words.
ANCHOR = re.compile(r"\[\^c([0-9a-f]{8})\]")
ANCHOR_DEF = re.compile(r"^\[\^c([0-9a-f]{8})\]:\s*(.*)$")

_UNIT = scan.UNIT

IDENT = re.compile(
    r"`([^`]+)`"
    r"|(?<![\w-])(--[a-z][\w-]*)"
    r"|\$([A-Z][A-Z0-9_]*)"
    r"|\b([A-Z][A-Z0-9_]{2,})\b"
    r"|\b([\w./-]+\.[A-Za-z]{1,5})\b"
    r"|\b(\w+\(\))")

NUMBER = re.compile(r"\b(\d+(?:\.\d+)?)\s*(" + _UNIT + r")?\b", re.I)

# Words that change what a sentence promises. "never" to "rarely" has to move
# the skeleton, or the ledger would keep a verdict for a claim that softened.
QUANT = re.compile(
    r"\b(never|always|every|none|only|all|any|cannot|can't|must|must not"
    r"|no|not|rarely|sometimes|usually|often|idempotent|atomic|thread-safe"
    r"|lossless|immutable|deterministic|guarantees?|guaranteed|ensures?"
    r"|before|after|nightly|daily|hourly)\b", re.I)

STOPWORDS = frozenset(
    "a an the and or but if then than that this these those is are was were "
    "be been being it its of to in on at by for with from as so up out".split())


def _tokens(text, pattern, lower=False):
    for m in pattern.finditer(text):
        value = next((g for g in m.groups() if g), None)
        if value:
            yield m.start(), (value.lower() if lower else value)


def identifiers(text):
    """The names a claim is about, in document order."""
    return [v for _, v in sorted(_tokens(text, IDENT))]


def skeleton(text):
    """Identifiers, values and promise-words: what the sentence asserts."""
    marks = list(_tokens(text, IDENT))
    marks += [(pos, v.lower()) for pos, v in _tokens(text, QUANT)]
    for m in NUMBER.finditer(text):
        marks.append((m.start(1), m.group(1)))
        if m.group(2):
            marks.append((m.start(2), m.group(2).lower()))
    return [v for _, v in sorted(marks)]


def identity_key(text):
    """What makes this claim *this* claim.

    Identifiers when the sentence has any. Otherwise the first content words,
    which is coarse — but a claim with no identifier ("no event is ever
    delivered twice") has nothing more stable to be keyed on, and a rewrite
    of it is a new claim in every sense that matters.
    """
    idents = identifiers(text)
    if idents:
        return "|".join(idents)
    words = [w.lower() for w in re.findall(r"[A-Za-z][\w'-]*", text)
             if w.lower() not in STOPWORDS]
    return " ".join(words[:6])


def _hash(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def claim_id(relpath, key, occurrence):
    # Eight hex digits, because the id is also the footnote marker a reader
    # sees in the prose: [^c4e233156]. Long enough that two claims in a
    # corpus will not collide, short enough not to shout.
    return _hash(relpath, key, occurrence)[:8]


def display_text(text):
    """The sentence as the ledger stores it: verbatim, rewrapped.

    Emphasis markers are *not* stripped here, though the matching passes
    strip them. An underscore inside a code span is part of an identifier,
    and a ledger recording `identitykey()` where the document says
    `identity_key()` is one nobody can check against the document.
    """
    return re.sub(r"\s+", " ", text).strip()


def normalise_lines(lines):
    return "\n".join(re.sub(r"\s+", " ", ln).strip() for ln in lines)


def parse_range(spec):
    """"12" or "12-18" to a (start, end) pair, 1-indexed and inclusive."""
    spec = str(spec)
    if "-" in spec:
        a, _, b = spec.partition("-")
        return int(a), int(b)
    return int(spec), int(spec)


def evidence_hash(path, line_spec, root="."):
    """Hash of the cited lines. None when the file or range is gone — which
    is itself a move: evidence that no longer exists cannot still support."""
    full = os.path.join(root, path)
    try:
        with open(full, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    start, end = parse_range(line_spec)
    if start < 1 or end > len(lines) or start > end:
        return None
    return _hash(normalise_lines(lines[start - 1:end]))[:8]


# ---------------------------------------------------------------------------
# Extraction to entries, and the comparison that makes the ledger derived
# state rather than a registry anyone maintains.
# ---------------------------------------------------------------------------


def extract(paths, excludes=(), include_records=False, include_code=False,
            root="."):
    """Every claim in the corpus, as ledger entries keyed by id."""
    files, records = scan.collect(paths, excludes, include_records,
                                  include_code)
    entries, seen = OrderedDict(), defaultdict(int)
    for path in files:
        rel = os.path.relpath(path, root) if root != "." else path
        rel = rel.replace(os.sep, "/")
        if rel.startswith("./"):
            # A sidecar names its document as "CLAUDE.md"; a walk from "."
            # hands back "./CLAUDE.md", and the two must be the same key.
            rel = rel[2:]
        found, _ = scan.claims_in(path, rel=rel,
                                  include=ANCHOR.search)
        for claim in found:
            raw = claim["text"]
            # An anchor inside a code span is an example of one — this
            # repository's own docs show `[^c4e233156]` while explaining the
            # scheme — and reading it as an id would hand two sentences the
            # same claim.
            outside = scan.INLINE_CODE.sub(lambda m: " " * len(m.group(0)), raw)
            spans = [m.span() for m in ANCHOR.finditer(outside)]
            anchored = ANCHOR.search(outside)
            # Remove only the real markers. A quoted one is part of the
            # sentence — the docs explaining the scheme contain both.
            text = raw
            for a, b in reversed(spans):
                text = text[:a] + text[b:]
            text = text.strip()
            if anchored:
                # The document names its own claim. Reword the sentence
                # however you like; the verdict follows the anchor.
                cid = anchored.group(1)
            else:
                key = identity_key(text)
                occurrence = seen[(rel, key)]
                seen[(rel, key)] += 1
                cid = claim_id(rel, key, occurrence)
            claim = dict(claim, text=text)
            entries[cid] = {
                "id": cid,
                "file": rel,
                "line": claim["line"],
                "text": display_text(claim["text"]),
                "anchored": bool(anchored),
                "skeleton_hash": _hash("|".join(skeleton(claim["text"])))[:8],
                "class": claim["class"],
            }
    return entries, files, records


SIDECAR_SUFFIX = ".claims.toml"


def sidecar_for(doc):
    """README.md -> README.claims.toml, beside the document making the claims."""
    base, _ = os.path.splitext(doc)
    return base + SIDECAR_SUFFIX


def find_sidecars(root="."):
    """Every sidecar under root, in a stable order.

    Sidecars are self-describing — each names the document it covers — so
    `check` needs no corpus argument and no central index to find its work.
    """
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in scan.SKIP_DIRS)
        for name in sorted(names):
            if name.endswith(SIDECAR_SUFFIX):
                out.append(os.path.relpath(os.path.join(base, name), root))
    return out


def load_ledger(path):
    with open(path, encoding="utf-8") as fh:
        return loads(fh.read())


def claims_by_id(ledger):
    return {c["id"]: c for c in ledger.get("claim", [])}


def evidence_moved(claim, root="."):
    """The cited evidence whose hash no longer matches, if any."""
    moved = []
    for ev in claim.get("evidence", []):
        if not ev.get("hash"):
            continue
        now = evidence_hash(ev["file"], ev.get("lines", "1"), root)
        if now != ev["hash"]:
            moved.append((ev, now))
    return moved


def relocate_evidence(ev, root="."):
    """Where the cited quote lives now, or None if it is really gone.

    Editing a file above a citation moves every line number below it while
    changing nothing about the evidence. That is bookkeeping, not a stale
    verdict — but only when the quote is still there verbatim. If it is not,
    the evidence changed and a person has to look again.
    """
    path = os.path.join(root, ev["file"])
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    want = re.sub(r"\s+", " ", ev.get("quote", "")).strip()
    if not want:
        return None
    span = 1
    if "-" in str(ev.get("lines", "")):
        a, b = str(ev["lines"]).split("-")
        span = max(1, int(b) - int(a) + 1)
    for i in range(0, max(0, len(lines) - span + 1)):
        window = normalise_lines(lines[i:i + span]).replace("\n", " ")
        if want in re.sub(r"\s+", " ", window):
            return str(i + 1) if span == 1 else "%d-%d" % (i + 1, i + span)
    return None


def compare(entries, ledger, root="."):
    """The four outcomes: new, stale, orphan, live.

    Nobody adds entries by hand. Each run re-derives the claim set from the
    documents and diffs it against the ledger, so a doc edit cannot escape
    unnoticed — only be ignored, which is what the gate is for.
    """
    recorded = claims_by_id(ledger)
    new, stale, live = [], [], []
    for cid, entry in entries.items():
        prior = recorded.get(cid)
        if prior is None:
            new.append(entry)
            continue
        reasons = []
        if prior.get("skeleton_hash") != entry["skeleton_hash"]:
            reasons.append("claim edited")
        for ev, now in evidence_moved(prior, root):
            where = relocate_evidence(ev, root)
            if where:
                reasons.append("evidence at %s moved to :%s (quote unchanged)"
                               % (ev["file"], where))
            else:
                reasons.append("evidence changed: %s:%s" % (ev["file"],
                                                            ev.get("lines", "?")))
        if reasons and prior.get("verdict") != "unverified":
            stale.append((entry, prior, reasons))
        elif reasons:
            stale.append((entry, prior, reasons))
        else:
            live.append((entry, prior))
    orphan = [c for cid, c in recorded.items() if cid not in entries]
    return {"new": new, "stale": stale, "live": live, "orphan": orphan}


# ---------------------------------------------------------------------------
# Candidate evidence. The expensive half of verifying a claim is finding the
# code that could settle it; that half is mechanical, so init does it and
# leaves the judgement. A candidate is explicitly not evidence: nobody has
# looked at it yet, and `record` will not accept one as a citation.
# ---------------------------------------------------------------------------

CONFIG_NAMES = {"pyproject.toml", "setup.cfg", "setup.py", "package.json",
                "Cargo.toml", "go.mod", "pom.xml", "build.gradle",
                "requirements.txt", "tox.ini", ".env.example"}

# What a definition looks like. ":" is deliberately absent: every line of
# YAML has one, which made CI config look like the definition of everything
# it mentions.
DEFINITION = re.compile(
    r"=[^=]|\bdef\b|\bclass\b|\bconst\b|\blet\b|\bvar\b|\bfn\b"
    r"|add_argument|addoption|\bexport\b|^\s*[\w.]+\s*:\s*\S")

# Data and config formats name things without defining them. A workflow that
# runs `scan.py` is not where `scan.py`'s behaviour is settled.
DATA_EXT = (".yml", ".yaml", ".json", ".toml", ".cfg", ".ini", ".lock")

MAX_TOKENS = 600
MAX_HITS_PER_TOKEN = 4


def searchable_files(root=".", limit=4000):
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in scan.SKIP_DIRS)
        for name in sorted(names):
            if name in CONFIG_NAMES or (scan.comment_syntax(name)
                                        and ".min." not in name):
                out.append(os.path.relpath(os.path.join(base, name), root))
                if len(out) >= limit:
                    return out
    return out


PROSE_EXT = (".md", ".markdown", ".rst", ".txt")


def _token_forms(ident):
    """A backticked `src/relay.py` and a bare MAX_RETRIES search differently."""
    ident = ident.strip("`")
    if ident.lower().endswith(PROSE_EXT):
        # A claim about a document is settled by the document, or by whether
        # it exists — never by CI config happening to name it.
        return set()
    forms = {ident}
    if ident.endswith("()"):
        forms.add(ident[:-2])
    if ident.startswith("--"):
        forms.add(ident[2:].replace("-", "_"))
    return {f for f in forms if len(f) >= 3}


def find_candidates(entries, root=".", files=None):
    """One pass over the code for every claim's identifiers at once.

    Per-claim searching would re-read the tree hundreds of times; the cost
    here is dominated by reading files, so they get read once.
    """
    token_to_claims = defaultdict(set)
    for cid, entry in entries.items():
        for ident in identifiers(entry["text"]):
            for form in _token_forms(ident):
                token_to_claims[form.lower()].add(cid)
    tokens = sorted(token_to_claims, key=lambda t: (-len(t), t))[:MAX_TOKENS]
    if not tokens:
        return {}
    # Case-insensitive: docs say `--timeout`, code says TIMEOUT_SECONDS,
    # and a candidate search that misses that link is worth little.
    probe = re.compile("|".join(re.escape(t) for t in tokens), re.I)

    hits = defaultdict(list)
    for rel in (files if files is not None else searchable_files(root)):
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as fh:
                content = fh.read()
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(content.splitlines(), 1):
            if len(line) > 400:
                continue
            is_data = rel.lower().endswith(DATA_EXT)
            for m in set(x.lower() for x in probe.findall(line)):
                if len(hits[m]) < MAX_HITS_PER_TOKEN * 4:
                    hits[m].append((rel, n, line.strip(),
                                    bool(DEFINITION.search(line))
                                    and not is_data))

    # A file matching many different identifiers is an index — CI config, a
    # manifest, a table of contents. Its mentions are not evidence, and left
    # in they become the first candidate for half the corpus, collapsing the
    # batching into one meaningless group.
    breadth = defaultdict(set)
    for token, found in hits.items():
        for rel, _, _, is_def in found:
            if not is_def:
                breadth[rel].add(token)
    indexes = {rel for rel, toks in breadth.items() if len(toks) >= 6}

    out = defaultdict(list)
    for token, found in hits.items():
        found = [h for h in found if h[3] or h[0] not in indexes]
        found.sort(key=lambda h: (not h[3], h[0], h[1]))   # definitions first
        for cid in token_to_claims[token]:
            for rel, n, text, is_def in found[:MAX_HITS_PER_TOKEN]:
                if len(out[cid]) >= MAX_HITS_PER_TOKEN:
                    break
                if any(c["file"] == rel and c["lines"] == str(n)
                       for c in out[cid]):
                    continue
                out[cid].append({
                    "file": rel, "lines": str(n), "quote": text[:200],
                    "why": ("defines or assigns `%s`" if is_def
                            else "mentions `%s`") % token,
                })
    return out


# ---------------------------------------------------------------------------
# Wiring the repository's agent instructions. The gate catches an unverified
# claim at merge, which is late: the session that wrote it is gone, and
# somebody reloads the code cold to answer what its author could have
# answered for free. A line in the instructions closes that gap — so init
# looks for one, and prints a block when it finds none.
#
# It prints. Editing the file that governs how every agent behaves in a
# repository is not a side effect anyone should discover afterwards.
# ---------------------------------------------------------------------------

AGENT_FILES = ("AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md",
               ".github/copilot-instructions.md", ".cursorrules")

BLOCK = """## Documentation claims

Every factual claim in {corpus} is recorded in a sidecar beside the document
that makes it (`{ledger}`), with the evidence that settled each one.

After editing those docs, or changing a default, flag, path or guarantee they
describe, run `lie-detector check`. Verify whatever it reports as new or
stale in the same session — you already have the code open, and nobody
downstream will.

Never record a verdict without quoting the `file:line` that settles it. If
nothing settles it, `unsupported` is the honest answer.
"""

HOOK = """{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 skills/lie-detector/scripts/ledger.py check --quiet || true"
          }
        ]
      }
    ]
  }
}"""


def agent_files_present(root="."):
    present = [f for f in AGENT_FILES if os.path.isfile(os.path.join(root, f))]
    rules = os.path.join(root, ".cursor", "rules")
    if os.path.isdir(rules):
        present += [os.path.join(".cursor", "rules", n)
                    for n in sorted(os.listdir(rules)) if n.endswith(".mdc")]
    return present


def wiring_reference(root=".", ledger_path=SIDECAR_SUFFIX):
    """Where the ledger is already mentioned, as (file, lineno), or None.

    Deliberately coarse: any mention of the tool or the ledger's own filename
    counts. A repository that names either has made a decision, and asking
    again on every init is how a tool teaches people to ignore it.
    """
    needles = ("lie-detector", SIDECAR_SUFFIX)
    for rel in agent_files_present(root):
        try:
            with open(os.path.join(root, rel), encoding="utf-8") as fh:
                for n, line in enumerate(fh.read().splitlines(), 1):
                    if any(needle in line for needle in needles):
                        return rel, n
        except (OSError, UnicodeDecodeError):
            continue
    return None


def wiring_target(root="."):
    """AGENTS.md when both exist — more tools read it — else whichever does."""
    for name in ("AGENTS.md", "CLAUDE.md"):
        if os.path.isfile(os.path.join(root, name)):
            return name
    return None


def block_for(ledger_path, corpus):
    return BLOCK.format(ledger=ledger_path,
                        corpus=" and ".join("`%s`" % c for c in corpus)
                        or "the documentation")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


ANCHOR_HEADER = "<!-- claim anchors: written by lie-detector -->"

# Files an agent loads into every session it starts. A footnote block in one
# of these is paid for on every session, forever — in this repository it was
# 23% of CLAUDE.md and roughly 500 tokens a session, against 72 tokens for
# the markers that actually carry identity. So they are anchored without
# footnotes: the marker keeps the claim's name in the document, and the
# provenance lives in the sidecar, one `show` away.
CONTEXT_DOCS = ("CLAUDE.md", "AGENTS.md", ".cursorrules",
                "copilot-instructions.md", "GEMINI.md", ".windsurfrules")


def wants_footnotes(doc_path):
    return os.path.basename(doc_path) not in CONTEXT_DOCS


def anchor_id(cid):
    return "c" + cid


def _definition(claim):
    """The footnote a reader sees: what settled this sentence, and when."""
    verdict = claim.get("verdict", "unverified")
    if verdict == "unverified":
        return "not yet verified"
    where = ", ".join("%s:%s" % (e["file"], e["lines"])
                      for e in claim.get("evidence", [])[:2])
    when = (claim.get("verified_at") or "")[:10]
    parts = [verdict]
    if when:
        parts.append(when)
    if where:
        parts.append(where)
    return " · ".join(parts)


def sync_anchors(doc_path, claims, root=".", footnotes=None):
    """Put each claim's marker on its sentence, and refresh the footnotes.

    Markers are appended to the sentence the claim was extracted from, and
    the definitions are collected in one block at the end of the document,
    where markdown renders them as footnotes. Idempotent: a sentence that
    already carries its marker is left alone.
    """
    full = os.path.join(root, doc_path)
    with open(full, encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    by_line = {}
    for claim in claims:
        by_line.setdefault(int(claim["line"]), []).append(claim)

    # Trim any previous block first, so definitions are rewritten rather than
    # accumulated — an append-only footnote list is its own kind of rot.
    end = len(lines)
    for n, line in enumerate(lines):
        if line.strip() == ANCHOR_HEADER:
            end = n
            break
    body = lines[:end]

    added = 0
    joined = "\n".join(body)
    for n, claims_here in sorted(by_line.items()):
        for claim in claims_here:
            marker = "[^%s]" % anchor_id(claim["id"])
            if marker in joined:
                continue
            # Anchor on the claim's own sentence, not the next one: match the
            # tail of its text in the document, allowing for the soft wraps
            # the extractor joined over, and insert after the match.
            tail = claim["text"].strip()[-40:]
            probe = re.compile(r"\s+".join(re.escape(w) for w in tail.split()))
            placed = False
            for j in range(max(0, n - 1), min(len(body), n + 8)):
                window = "\n".join(body[j:j + 3])
                m = probe.search(window)
                if not m:
                    continue
                upto = window[:m.end()]
                line_off = upto.count("\n")
                col = len(upto) - (upto.rfind("\n") + 1)
                body[j + line_off] = (body[j + line_off][:col] + marker
                                      + body[j + line_off][col:])
                joined = "\n".join(body)
                added += 1
                placed = True
                break
            if not placed and n - 1 < len(body) \
                    and body[n - 1].lstrip().startswith("|"):
                row = body[n - 1].rstrip()
                if row.endswith("|"):
                    body[n - 1] = row[:-1].rstrip() + marker + " |"
                else:
                    body[n - 1] = row + marker
                joined = "\n".join(body)
                added += 1
                placed = True
            if not placed:
                print("  could not anchor %s (%s:%s) — sentence not found "
                      "where the ledger says it is"
                      % (anchor_id(claim["id"]), doc_path, n), file=sys.stderr)

    if footnotes is None:
        footnotes = wants_footnotes(doc_path)
    while body and not body[-1].strip():
        body.pop()
    if footnotes:
        defs = [ANCHOR_HEADER, ""]
        for claim in sorted(claims, key=lambda c: int(c["line"])):
            defs.append("[^%s]: %s" % (anchor_id(claim["id"]),
                                       _definition(claim)))
        out = body + [""] + defs + [""]
    else:
        # No block at all — not even the header, which would be one more line
        # in every session's context for no reader's benefit.
        out = body + [""]
    with open(full, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    return added


def _now():
    # utcnow() is deprecated from 3.12; this form works from 3.8 up.
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _revision(root="."):
    try:
        out = subprocess.run(["git", "-C", root, "rev-parse", "--short", "HEAD"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return out.stdout.decode("ascii", "ignore").strip() if out.returncode == 0 else ""


def cmd_init(args):
    """Enrol every claim, writing one sidecar per document.

    A sidecar sits beside the document it covers — README.claims.toml next to
    README.md — so the metadata lives with the prose making the claims, each
    file stays reviewable, and a docs PR touches only the sidecars for the
    documents it changed.
    """
    root = args.root
    if args.print_hook:
        print(HOOK)
        return 0
    if args.wire and not args.paths:
        return cmd_wire_only(args)

    entries, files, records = extract(args.paths, args.exclude,
                                      args.include_records, args.code, root)
    if not entries:
        print("no claims found in %d file(s)" % len(files), file=sys.stderr)
        return 2

    existing = [f for f in files
                if os.path.exists(os.path.join(root, sidecar_for(
                    os.path.relpath(f, root) if root != "." else f)))]
    if existing and not args.force:
        print("sidecars already exist for %d document(s) — use `check` to see "
              "what moved, `init --wire` for the agent block, or --force to "
              "re-enrol." % len(existing), file=sys.stderr)
        return 2

    candidates = {} if args.no_candidates else find_candidates(entries, root)
    stamp, revision = _now(), _revision(root)
    by_doc = defaultdict(list)
    for cid, entry in entries.items():
        entry.update({"verdict": "unverified", "exempt": True,
                      "note": "grandfathered by init on %s" % stamp[:10]})
        if candidates.get(cid):
            entry["evidence_candidate"] = candidates[cid]
        by_doc[entry["file"]].append(entry)

    written = []
    for doc, claims in sorted(by_doc.items()):
        for claim in claims:
            claim.pop("file", None)
        led = {"schema": SCHEMA, "doc": doc, "generated_at": stamp,
               "claim": claims}
        if revision:
            led["revision"] = revision
        if args.code:
            led["code"] = True
        if args.include_records:
            led["include_records"] = True
        if args.exclude:
            led["exclude"] = list(args.exclude)
        path = os.path.join(root, sidecar_for(doc))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(dumps(led))
        written.append((sidecar_for(doc), len(claims)))

    with_candidates = sum(1 for cid in entries if candidates.get(cid))
    print("Extracting claims from %d file(s)...\n" % len(files))
    print("  %4d claims extracted" % len(entries))
    print("  %4d with evidence candidates found mechanically" % with_candidates)
    print("  %4d with no candidate — these need a human to say what would "
          "settle them" % (len(entries) - with_candidates))
    print("")
    for path, n in written:
        print("  wrote %-40s %3d claims" % (path, n))
    if records:
        print("\nSkipped %d record(s) — dated plans, specs, ADRs, changelogs."
              % len(records))

    if args.anchor:
        total = 0
        for doc, claims in sorted(by_doc.items()):
            total += sync_anchors(doc, claims, root)
        print("\nAnchored %d sentence(s): each carries its claim id as a "
              "markdown footnote, so a reworded sentence keeps its verdict."
              % total)
        print("Re-run `check` — anchoring edits the documents, which moves "
              "the claims it just wrote.")

    by_class = defaultdict(int)
    for entry in entries.values():
        by_class[entry["class"]] += 1
    print("\nBacklog by class:")
    for cls, label, _ in scan.CLAIM_CLASSES:
        if by_class.get(cls):
            print("    %s  %-24s %4d" % (cls, label, by_class[cls]))

    print("\nNothing is marked supported. An unverified entry is a claim the")
    print("ledger knows about, not one anybody has an opinion on.")
    print("\nNext:  ledger.py check --backlog")
    print("Gate:  ledger.py check   (passes today: every claim is exempt)")

    _report_wiring(args, root, written[0][0] if written else "*.claims.toml")
    return 0


def _report_wiring(args, root, ledger_path):
    found = wiring_reference(root)
    if found:
        print("\nAgent instructions already reference the ledger — %s:%d."
              % found)
        return
    present = agent_files_present(root)
    target = wiring_target(root)
    block = block_for(ledger_path, args.paths)
    print("")
    if present:
        if len(present) == 1:
            print("! %s exists and does not mention the claim ledger."
                  % present[0])
        else:
            print("! %s exist; none of them mentions the claim ledger."
                  % ", ".join(present))
    else:
        print("! No agent instruction file found (AGENTS.md, CLAUDE.md, …).")
    print("  Without a reference there, a session writing docs will not know")
    print("  to verify its own claims, and the first thing that tells it is a")
    print("  red build.\n")
    print("  Suggested addition to %s:\n" % (target or "AGENTS.md (new file)"))
    for line in block.rstrip("\n").splitlines():
        print("  | " + line)
    print("")
    if args.wire:
        rc = apply_wiring(root, target, block, create=args.create)
        return rc
    print("  Apply it:   ledger.py init --wire" +
          ("" if target else "  (add --create to make AGENTS.md)"))
    print("  Or copy it yourself. Nothing was written.")
    if os.path.isfile(os.path.join(root, ".claude", "settings.json")):
        print("\n  Optional: a PostToolUse hook can run `check` after every doc")
        print("  edit — see `ledger.py init --print-hook`. Opt-in: a hook that")
        print("  fires on every edit is a preference, not a default.")


def apply_wiring(root, target, block, create=False):
    if target is None:
        if not create:
            print("  Not written: no AGENTS.md or CLAUDE.md exists, and a repo")
            print("  with no agent instructions may not want its first one to")
            print("  be ours. Pass --create to write AGENTS.md anyway.")
            return 0
        target = "AGENTS.md"
    path = os.path.join(root, target)
    existing = ""
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as fh:
            existing = fh.read()
    if "lie-detector" in existing or ".claims.toml" in existing:
        print("  Already referenced in %s — nothing to do." % target)
        return 0
    sep = "" if not existing or existing.endswith("\n\n") else (
        "\n" if existing.endswith("\n") else "\n\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(existing + sep + block)
    print("  Appended %d lines to %s." % (len(block.strip().splitlines()),
                                          target))
    return 0


def load_all(root="."):
    """Every sidecar under root as (path, ledger, doc, claims-by-id)."""
    out = []
    for rel in find_sidecars(root):
        try:
            led = load_ledger(os.path.join(root, rel))
        except (OSError, ValueError) as exc:
            print("skipped %s: %s" % (rel, exc), file=sys.stderr)
            continue
        doc = led.get("doc")
        if not doc:
            continue
        claims = {}
        for c in led.get("claim", []):
            c.setdefault("file", doc)
            claims[c["id"]] = c
        out.append((rel, led, doc, claims))
    return out


def merged(sidecars):
    """One ledger-shaped view over every sidecar, for compare()."""
    claims = []
    for _, _, _, by_id in sidecars:
        claims += list(by_id.values())
    return {"claim": claims}


def corpus_from(ledger, args):
    """The corpus and walk options: the ledger's, unless overridden."""
    paths = getattr(args, "paths", None) or ledger.get("corpus") or []
    return {
        "paths": paths,
        "excludes": getattr(args, "exclude", None) or ledger.get("exclude", []),
        "include_records": getattr(args, "include_records", False)
        or bool(ledger.get("include_records")),
        "include_code": getattr(args, "code", False) or bool(ledger.get("code")),
    }


def cmd_check(args):
    root = args.root
    sidecars = load_all(root)
    if not sidecars:
        print("no sidecars found — run `ledger.py init <paths>` first",
              file=sys.stderr)
        return 2

    docs = [doc for _, _, doc, _ in sidecars]
    opts = corpus_from(sidecars[0][1], args)
    targets = args.paths or [os.path.join(root, d) for d in docs]
    entries, files, _ = extract(targets, opts["excludes"],
                                opts["include_records"], opts["include_code"],
                                root)
    ledger = merged(sidecars)
    state = compare(entries, ledger, root)
    recorded = claims_by_id(ledger)

    if args.backlog:
        return _print_backlog(entries, state, recorded, args)
    if args.prune:
        return _prune_sidecars(sidecars, entries, root, args)
    if args.relocate:
        return _relocate(sidecars, root, args)

    blocking, advisory, rows = 0, 0, []
    for entry in state["new"]:
        blocking += 1
        rows.append(("FAIL", entry, "new claim, no verdict"))
    for entry, prior, reasons in state["stale"]:
        if prior.get("verdict") == "unverified" and prior.get("exempt"):
            if "claim edited" in reasons:
                blocking += 1
                rows.append(("FAIL", entry,
                             "claim edited since exemption — verify or re-exempt"))
            continue
        blocking += 1
        rows.append(("FAIL", entry, "stale — " + "; ".join(reasons)))
    exempt = live = unsupported = unverifiable = 0
    for entry, prior in state["live"]:
        verdict = prior.get("verdict", "unverified")
        if verdict == "refuted":
            blocking += 1
            rows.append(("FAIL", entry, "refuted — " +
                         (prior.get("correction") or "no correction recorded")))
        elif verdict == "unsupported":
            unsupported += 1
            if args.strict:
                blocking += 1
                rows.append(("FAIL", entry, "unsupported (--strict)"))
            else:
                advisory += 1
                rows.append(("WARN", entry, "unsupported — " +
                             (prior.get("note") or "nothing settles it")))
        elif verdict == "unverified":
            exempt += 1
        elif verdict == "unverifiable":
            unverifiable += 1
        else:
            live += 1
    for orphan in state["orphan"]:
        if orphan.get("verdict", "unverified") == "unverified":
            rows.append(("prune", orphan, "no longer in the docs"))
            continue
        advisory += 1
        rows.append(("NOTE", orphan,
                     "was %s, and the claim is gone — deleted, or reworded "
                     "past recognition. Prune it, or record the rewrite with "
                     "supersedes." % orphan["verdict"]))

    if not args.quiet or blocking:
        for level, entry, why in rows:
            if level == "prune":
                continue
            print("%-5s %s:%s  %s" % (level, entry.get("file", "?"),
                                      entry.get("line", "?"), why))
        if exempt:
            print("ok    %d exempt (grandfathered, unverified)" % exempt)
        if live:
            print("ok    %d supported" % live)
        if unverifiable:
            print("ok    %d unverifiable (advisory; a writing finding)"
                  % unverifiable)
        total = len(entries)
        verified = total - exempt - len(state["new"])
        print("\n%d blocking, %d advisory. Coverage %d%% (%d/%d verified) "
              "across %d document(s)."
              % (blocking, advisory,
                 (100 * verified // total) if total else 100, verified, total,
                 len(sidecars)))
        if exempt:
            print("Exemption backlog: %d." % exempt)
        if state["orphan"]:
            print("%d orphan entr%s — run `ledger.py check --prune`."
                  % (len(state["orphan"]),
                     "y" if len(state["orphan"]) == 1 else "ies"))
    return 1 if blocking else 0


def _relocate(sidecars, root, args):
    """Re-address citations whose quote is intact but whose line has moved."""
    moved, stuck = 0, []
    for rel, led, doc, by_id in sidecars:
        touched = False
        for claim in led.get("claim", []):
            for ev in claim.get("evidence", []):
                now = evidence_hash(ev["file"], ev.get("lines", "1"), root)
                if now == ev.get("hash"):
                    continue
                where = relocate_evidence(ev, root)
                if where is None:
                    stuck.append((claim["id"], ev["file"]))
                    continue
                ev["lines"] = where
                ev["hash"] = evidence_hash(ev["file"], where, root)
                moved += 1
                touched = True
        if touched and not args.dry_run:
            for c in led.get("claim", []):
                c.pop("file", None)
            with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
                fh.write(dumps(led))
    verb = "would re-address" if args.dry_run else "Re-addressed"
    print("%s %d citation(s) whose quote had not changed." % (verb, moved))
    for cid, f in stuck:
        print("  %s: quote is gone from %s — the evidence changed, so this "
              "one needs a person." % (cid, f))
    return 1 if stuck else 0


def _prune_sidecars(sidecars, entries, root, args):
    dropped = 0
    for rel, led, doc, by_id in sidecars:
        keep = [c for c in led.get("claim", []) if c["id"] in entries]
        gone = len(led.get("claim", [])) - len(keep)
        if not gone:
            continue
        dropped += gone
        if args.dry_run:
            continue
        led["claim"] = keep
        for c in keep:
            c.pop("file", None)
        with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
            fh.write(dumps(led))
    if not dropped:
        print("no orphans.")
    elif args.dry_run:
        print("would prune %d orphan entr%s"
              % (dropped, "y" if dropped == 1 else "ies"))
    else:
        print("Pruned %d orphan entr%s."
              % (dropped, "y" if dropped == 1 else "ies"))
    return 0


def _print_backlog(entries, state, recorded, args):
    """The unverified backlog: what to verify next, and in what order."""
    todo = [(e, recorded.get(e["id"])) for e in state["new"]]
    todo += [(e, p) for e, p, _ in state["stale"]]
    todo += [(e, p) for e, p in state["live"]
             if p.get("verdict") == "unverified"]
    if not todo:
        print("nothing to verify — every claim has a live verdict.")
        return 0

    # Batched by the evidence they need, because the cost of verifying a claim
    # is dominated by loading the code that settles it: ten claims about one
    # file cost roughly one file's reading, where ten in id order cost ten.
    # Ordered by class, because a wrong default outranks a wrong adjective.
    order = {cls: i for i, (cls, _, _) in enumerate(scan.CLAIM_CLASSES)}
    grouped = defaultdict(list)
    for entry, prior in todo:
        where = "(no candidate — decide what would settle it)"
        if prior:
            for kind in ("evidence", "evidence_candidate"):
                if prior.get(kind):
                    where = prior[kind][0]["file"]
                    break
        grouped[where].append(entry)

    limit = args.limit
    shown, groups = 0, []
    # Claims with candidate evidence come first: they are the ones a session
    # can settle by opening one file. The no-candidate bucket needs somebody
    # to decide what would settle them at all, which is different work.
    def group_order(where):
        return (where.startswith("("), -len(grouped[where]), where)

    for where in sorted(grouped, key=group_order):
        batch = sorted(grouped[where],
                       key=lambda e: (order.get(e["class"], 9), e["file"],
                                      e.get("line", 0)))
        if shown >= limit:
            break
        batch = batch[:max(0, limit - shown)]
        shown += len(batch)
        groups.append((where, batch))

    print("%d claim(s), %d file(s) to open — batched by the evidence they need."
          % (shown, len(groups)))
    for where, batch in groups:
        print("\n%s  (%d claim%s)" % (where, len(batch),
                                      "" if len(batch) == 1 else "s"))
        for entry in batch:
            print("    %s  %s:%s  %s" % (entry["id"], entry["file"],
                                         entry.get("line", "?"),
                                         entry["text"][:96]))
    print("\nRecord verdicts with: ledger.py record verdicts.json")
    print("Every supported or refuted verdict must quote the file:line that")
    print("settles it — `record` rejects the ones that do not.")
    return 0


def _prune(ledger, entries, ledger_path, args):
    keep = [c for c in ledger.get("claim", []) if c["id"] in entries]
    dropped = len(ledger.get("claim", [])) - len(keep)
    if not dropped:
        print("no orphans.")
        return 0
    if args.dry_run:
        print("would prune %d orphan entr%s"
              % (dropped, "y" if dropped == 1 else "ies"))
        return 0
    ledger["claim"] = keep
    with open(ledger_path, "w", encoding="utf-8") as fh:
        fh.write(dumps(ledger))
    print("Pruned %d orphan entr%s." % (dropped, "y" if dropped == 1 else "ies"))
    return 0


class RecordError(Exception):
    pass


def validate_verdict(item, root="."):
    """The honesty rule, enforced rather than requested.

    A ledger of rubber-stamped verdicts is worse than no ledger: it launders
    assumption as evidence. So a supported or refuted verdict must cite
    evidence, and the quote must actually appear at the lines it cites —
    which a verdict nobody checked cannot satisfy by accident.
    """
    verdict = item.get("verdict")
    if verdict not in VERDICTS:
        raise RecordError("verdict must be one of %s, got %r"
                          % (", ".join(VERDICTS), verdict))
    evidence = item.get("evidence") or []
    if verdict in NEEDS_EVIDENCE and not evidence:
        raise RecordError("a %s verdict must cite evidence; if nothing settles "
                          "the claim, the verdict is `unsupported`" % verdict)
    if verdict == "refuted" and not item.get("correction"):
        raise RecordError("a refuted verdict must carry the correction — "
                          "whoever trusted the claim needs the true statement")
    if verdict == "unsupported" and not item.get("searched"):
        raise RecordError("an unsupported verdict must record what was "
                          "searched, so a reader can falsify the search")

    out = []
    for ev in evidence:
        for key in ("file", "lines", "quote"):
            if not ev.get(key):
                raise RecordError("evidence needs file, lines and quote")
        full = os.path.join(root, ev["file"])
        if not os.path.isfile(full):
            raise RecordError("evidence file does not exist: %s" % ev["file"])
        with open(full, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        start, end = parse_range(ev["lines"])
        if start < 1 or end > len(lines) or start > end:
            raise RecordError("evidence range %s is outside %s (%d lines)"
                              % (ev["lines"], ev["file"], len(lines)))
        cited = normalise_lines(lines[start - 1:end])
        if re.sub(r"\s+", " ", ev["quote"]).strip() not in cited:
            raise RecordError("quoted text is not at %s:%s — the citation does "
                              "not say what the verdict claims it says"
                              % (ev["file"], ev["lines"]))
        out.append({"file": ev["file"], "lines": str(ev["lines"]),
                    "quote": ev["quote"], "symbol": ev.get("symbol", ""),
                    "note": ev.get("note", ""),
                    "hash": evidence_hash(ev["file"], ev["lines"], root)})
    return out


def cmd_record(args):
    root = args.root
    sidecars = load_all(root)
    if not sidecars:
        print("no sidecars found — run `ledger.py init <paths>` first",
              file=sys.stderr)
        return 2
    owner = {}
    for rel, led, doc, by_id in sidecars:
        for cid in by_id:
            owner[cid] = (rel, led, doc, by_id)

    with open(args.verdicts, encoding="utf-8") as fh:
        payload = json.load(fh)
    items = payload if isinstance(payload, list) else payload.get("verdicts", [])
    if not items:
        print("no verdicts in %s" % args.verdicts, file=sys.stderr)
        return 2

    opts = corpus_from(sidecars[0][1], args)
    docs = [doc for _, _, doc, _ in sidecars]
    enrolled, _, _ = extract([os.path.join(root, d) for d in docs],
                             opts["excludes"], opts["include_records"],
                             opts["include_code"], root)

    stamp, revision = _now(), _revision(root)
    applied, failed, added, touched = 0, [], 0, {}
    for item in items:
        cid = item.get("id")
        entry = owner.get(cid)
        fresh = enrolled.get(cid)
        if entry is None:
            # A claim can be verified before any sidecar has heard of it:
            # fixing a false sentence writes a new one, and verifying it in
            # the same session is the point.
            if fresh is None:
                failed.append((cid, "no such claim: in no sidecar, and no "
                                    "sentence in the corpus has that id"))
                continue
            target = None
            for rel, led, doc, by_id in sidecars:
                if doc == fresh["file"]:
                    target = (rel, led, doc, by_id)
                    break
            if target is None:
                failed.append((cid, "no sidecar covers %s" % fresh["file"]))
                continue
            claim = dict(fresh)
            target[1].setdefault("claim", []).append(claim)
            target[3][cid] = claim
            owner[cid] = target
            entry = target
            added += 1
        rel, led, doc, by_id = entry
        claim = by_id[cid]
        try:
            evidence = validate_verdict(item, root)
        except RecordError as exc:
            failed.append((cid, str(exc)))
            continue
        # A verdict is reached against the sentence as it reads now.
        if fresh:
            for key in ("line", "text", "anchored", "skeleton_hash", "class"):
                claim[key] = fresh[key]
        claim["verdict"] = item["verdict"]
        claim["verified_at"] = stamp
        claim["verified_by"] = item.get("verified_by") or args.by
        if revision:
            claim["revision"] = revision
        claim.pop("exempt", None)
        if str(claim.get("note", "")).startswith("grandfathered by init"):
            claim.pop("note")
        for key in ("correction", "severity", "note", "searched",
                    "guarded_by", "supersedes"):
            if item.get(key):
                claim[key] = item[key]
        if item["verdict"] != "unverified":
            claim.pop("evidence_candidate", None)
        if evidence:
            claim["evidence"] = evidence
        applied += 1
        touched[rel] = entry

    for cid, why in failed:
        print("REJECTED %s: %s" % (cid, why), file=sys.stderr)
    if failed and not args.partial:
        print("\nNothing written — %d verdict(s) rejected. Fix them, or pass "
              "--partial to record the rest." % len(failed), file=sys.stderr)
        return 1

    for rel, (_, led, doc, by_id) in touched.items():
        led["generated_at"] = stamp
        for c in led.get("claim", []):
            c.pop("file", None)
        with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
            fh.write(dumps(led))
        # Keep the footnotes current, but only where the document already
        # carries anchors — record never introduces them.
        claims = [dict(c, file=doc) for c in led.get("claim", [])]
        if any(c.get("anchored") for c in claims):
            sync_anchors(doc, claims, root)

    print("Recorded %d verdict(s) across %d sidecar(s)%s."
          % (applied, len(touched),
             "; %d claim(s) enrolled on the way" % added if added else ""))
    if failed:
        print("Rejected %d." % len(failed))
    return 1 if failed else 0


def cmd_show(args):
    root, target, matches = args.root, args.target, []
    for _, _, doc, by_id in load_all(root):
        for claim in by_id.values():
            if claim["id"] == target or anchor_id(claim["id"]) == target \
                    or "%s:%s" % (doc, claim.get("line")) == target \
                    or doc == target:
                matches.append((doc, claim))
    if not matches:
        print("no claim matching %r" % target, file=sys.stderr)
        return 2
    for doc, claim in matches:
        print("%s:%s  [%s]  %s" % (doc, claim.get("line", "?"),
                                   claim.get("class", "-"), claim["id"]))
        print("    %s" % claim["text"])
        line = "    %s" % claim.get("verdict", "unverified")
        if claim.get("exempt"):
            line += " · exempt (grandfathered)"
        if claim.get("verified_at"):
            line += " · verified %s by %s" % (claim["verified_at"][:10],
                                              claim.get("verified_by", "?"))
        if claim.get("revision"):
            line += " @ %s" % claim["revision"]
        if claim.get("anchored"):
            line += " · anchored [^%s]" % anchor_id(claim["id"])
        print(line)
        for ev in claim.get("evidence", []):
            now = evidence_hash(ev["file"], ev["lines"], root)
            state = "unchanged since" if now == ev.get("hash") else "MOVED"
            print("    evidence: %s:%s  %s  (%s)"
                  % (ev["file"], ev["lines"], ev["quote"][:80], state))
        for ev in claim.get("evidence_candidate", []):
            print("    candidate: %s:%s  %s" % (ev["file"], ev["lines"],
                                                ev.get("why", "")))
        if claim.get("correction"):
            print("    correction: %s" % claim["correction"])
        if claim.get("note"):
            print("    note: %s" % claim["note"])
    return 0


def cmd_wire_only(args):
    """`init --wire` on a repository that is already enrolled.

    Enrolling happens once; wiring the agent instructions is a decision that
    often comes later, so it must not require re-enrolling to reach.
    """
    root = args.root
    docs = [doc for _, _, doc, _ in load_all(root)]
    corpus = args.paths or docs or ["docs"]
    found = wiring_reference(root)
    if found:
        print("Already referenced — %s:%d." % found)
        return 0
    block = block_for("<doc>" + SIDECAR_SUFFIX, corpus)
    print(block)
    return apply_wiring(root, wiring_target(root), block, create=args.create)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".", help="repository root (default: .)")
    sub = ap.add_subparsers(dest="command")

    # The same two options are accepted after the subcommand as well, because
    # `ledger.py init docs --ledger x` is what people type. SUPPRESS keeps the
    # subparser from clobbering a value given before the subcommand.
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=argparse.SUPPRESS)

    # Four commands, because there are four things a person does: enrol once,
    # ask what needs attention, write down what they found, and look up one
    # sentence. Views of the same computation are flags on `check`, not
    # commands of their own.
    p_init = sub.add_parser("init", parents=[common],
                            help="enrol every claim, unverified (once per repo)")
    p_init.add_argument("paths", nargs="*")
    p_init.add_argument("--exclude", action="append", default=[],
                        metavar="SUBSTR")
    p_init.add_argument("--include-records", action="store_true")
    p_init.add_argument("--code", action="store_true",
                        help="also enrol claims in code comments")
    p_init.add_argument("--force", action="store_true",
                        help="re-enrol from scratch, discarding verdicts")
    p_init.add_argument("--no-candidates", action="store_true")
    p_init.add_argument("--wire", action="store_true",
                        help="append the block to the agent instructions; "
                             "works on an already-enrolled repo")
    p_init.add_argument("--create", action="store_true",
                        help="with --wire, create AGENTS.md if none exists")
    p_init.add_argument("--anchor", action="store_true",
                        help="write each claim's id into the document as a "
                             "markdown footnote, so a reworded sentence keeps "
                             "its verdict")
    p_init.add_argument("--print-hook", action="store_true",
                        help="print the PostToolUse hook and exit")
    p_init.set_defaults(func=cmd_init)

    p_check = sub.add_parser("check", parents=[common],
                             help="what is new, stale or refuted (the gate)")
    # No corpus options here on purpose: the ledger records what init was
    # told, and a gate that must be re-told how to walk the corpus is one
    # that eventually gets mis-invoked in CI, silently checking less.
    p_check.add_argument("paths", nargs="*",
                         help="default: the corpus the ledger records")
    p_check.add_argument("--strict", action="store_true",
                         help="treat unsupported as blocking")
    p_check.add_argument("--quiet", action="store_true",
                         help="print nothing unless the gate blocks")
    p_check.add_argument("--backlog", action="store_true",
                         help="list what to verify next, batched by evidence")
    p_check.add_argument("--limit", type=int, default=10,
                         help="with --backlog, how many to list")
    p_check.add_argument("--relocate", action="store_true",
                         help="re-address citations whose quote is unchanged "
                              "but whose line moved; verdicts are untouched")
    p_check.add_argument("--prune", action="store_true",
                         help="drop entries whose claim is gone")
    p_check.add_argument("--dry-run", action="store_true",
                         help="with --prune, show what would go")
    p_check.set_defaults(func=cmd_check)

    p_record = sub.add_parser("record", parents=[common],
                              help="write verdicts back, with their evidence")
    p_record.add_argument("verdicts", help="JSON file of verdicts")
    p_record.add_argument("--by", default="unknown",
                          help="who or what verified these")
    p_record.add_argument("paths", nargs="*",
                          help="corpus, if the ledger does not record one")
    p_record.add_argument("--partial", action="store_true",
                          help="record the valid ones even if some are rejected")
    p_record.set_defaults(func=cmd_record)

    p_show = sub.add_parser("show", parents=[common],
                            help="provenance for one claim")
    p_show.add_argument("target", help="claim id, file:line, or a file")
    p_show.set_defaults(func=cmd_show)

    args = ap.parse_args()
    if not args.command:
        ap.print_help()
        return 2
    return args.func(args)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except BrokenPipeError:
        # `ledger.py show … | head` is how a person reads this, and a
        # traceback is not what they asked for.
        try:
            sys.stdout.close()
        finally:
            os._exit(0)
