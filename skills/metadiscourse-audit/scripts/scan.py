#!/usr/bin/env python3
"""Scan markdown for metadiscourse candidates.

Cheap mechanical pass. Produces candidates with file:line and a suggested
class; a reader still decides. Deliberately over-reports — a false positive
costs one glance, a miss costs a class-0 artifact surviving another year.

Usage:
    scan.py <path>...                    # scan files or directories
    scan.py <path>... --json             # machine-readable
    scan.py <path>... --class 0          # iteration artifacts only (0a-0d)
    scan.py <path>... --fix              # apply the safe rewrites only
    scan.py <path>... --fix --dry-run    # show what --fix would change
    scan.py <path>... --check            # exit 1 on any finding (CI gate)

Exit status is 0 unless --check is passed, in which case any finding exits 1.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict

# ---------------------------------------------------------------------------
# Matching happens against a normalised copy of each line, not the raw text.
#
# Markdown emphasis defeats word boundaries: in `_Changed in ..._` the
# underscore is a word character, so \bChanged never matches and an entire
# class-0b changelog hides behind its own italics. Inline code is the opposite
# problem — `previously` inside backticks is an identifier, not prose, and
# should not fire at all. So: mask inline code first, then strip emphasis
# markers. Reported text is always the raw line.
# ---------------------------------------------------------------------------

INLINE_CODE = re.compile(r"`[^`]+`")
EMPHASIS = re.compile(r"(?:\*{1,3}|_{1,3})(?=\S)|(?<=\S)(?:\*{1,3}|_{1,3})")


def plain_text(line):
    """The line as the patterns should see it: code masked, emphasis gone."""
    return EMPHASIS.sub("", INLINE_CODE.sub("`code`", line))


# ---------------------------------------------------------------------------
# Patterns. Each entry: (class, label, compiled regex).
#
# Classes 0 and 0.5 come from revising a document; 1-10 can be in a first
# draft. That ordering is why 0 and 0.5 are scanned and reported first.
# ---------------------------------------------------------------------------

PATTERNS = [
    # --- Class 0: iteration artifacts ---------------------------------------
    ("0a", "prior-state reference", re.compile(
        r"\b(previously|formerly|used to (?:be|require|assume|say|live|return"
        r"|default|mean|work|take|have)\b|an earlier (?:version|note|draft|section)"
        r"|the (?:previous|old) (?:version|revision|draft|behaviou?r|implementation)"
        r"|the original (?:table|version|note|plan)|first version|initial version"
        r"|we (?:had|thought|concluded|assumed)|no longer|has since|since then"
        r"|what we had)\b", re.I)),
    ("0a", "self-correction", re.compile(
        r"\b(was wrong|were wrong|got wrong|measured wrong|misread|mistakenly"
        r"|wrongly|superseded|revised|half right|overturn(?:ed|s)?"
        r"|turned out (?:to be )?wrong|corrected (?:above|below|this|that)"
        r"|the corrected \w+)\b", re.I)),
    ("0a", "pass/round marker", re.compile(
        r"\b((?:first|second|third|initial|original|search-only|earlier) pass"
        r"|both passes|rounds? (?:one|two|1|2))\b", re.I)),
    ("0b", "version changelog", re.compile(
        r"\b(Changed|Corrected|Added|Updated|Fixed|Removed|Introduced) in\s+[`_'\"]?\S+",
    )),
    ("0b", "recency marker on behaviour", re.compile(
        # "now" + a third-person verb: "now sniffs", "now merges wrapped
        # headers". Generic on purpose — an explicit verb list missed "sniffs"
        # on a real corpus, and the handful of non-verbs that end in -s are
        # cheaper to stoplist than the verbs are to enumerate. The lookbehinds
        # drop the temporal idioms ("for now", "until now", "by now").
        r"(?<!for )(?<!until )(?<!by )(?<!right )\bnow\s+"
        r"(?!is\b|was\b|its\b|this\b|thus\b|as\b|less\b|plus\b)"
        r"\w+(?:s|es)\b", re.I)),
    ("0b", "perfect-tense changelog", re.compile(
        r"\b(?:has|have) (?:now |since |also )?been (?:added|removed|renamed"
        r"|rewritten|refactored|dropped|updated|replaced|moved|fixed|reworked"
        r"|simplified|split|merged|deprecated|deleted|restored|reverted)\b", re.I)),
    ("0b", "recency marker", re.compile(
        r"\b(?:was|were|have|has|got|only)\s+recently\b"
        r"|\brecently\s+(?:added|changed|updated|fixed|moved|renamed|rewritten"
        r"|introduced|landed|merged|switched|migrated|gained)\b", re.I)),
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
    ("0c", "implicit 'as of now'", re.compile(
        # "currently" is a date stamp without the date: it promises the same
        # future edit and gives the reader no way to see the promise is stale.
        r"\b(currently|at present|at the time of writing"
        r"|as of (?:this )?writing|as of (?:today|right now))\b", re.I)),
    # A bare `(issue #22)` is a cheap, durable pointer — keep it. What rots is a
    # claim about the issue's *state*, so only flag a reference that carries one.
    ("0d", "status claim on a tracker item", re.compile(
        r"(?:issue|ticket|PR)\s*#\d+.{0,80}\b(has not been|hasn't been|still open"
        r"|not yet|should be (?:rewritten|updated|closed)|is blocked|remains open)\b"
        r"|\b(?:has not been|hasn't been|still open|not yet done|should be"
        r" (?:rewritten|updated|closed)).{0,80}(?:issue|ticket|PR)\s*#\d+", re.I)),
    ("0d", "future promise", re.compile(
        # Backlog leakage pointing forwards: a promise in a standing doc that
        # only the tracker can keep. "Not yet implemented" rots the day the
        # implementation lands, and nothing marks the paragraph as stale.
        r"\b(will (?:eventually )?be (?:added|fixed|implemented|addressed"
        r"|removed|replaced|supported|documented|expanded)"
        r"|not yet (?:implemented|supported|built|wired|documented|handled)"
        r"|in a (?:future|later) (?:release|version|iteration|pass|PR|change)"
        r"|coming soon|on the roadmap|future work)\b", re.I)),

    # --- Class 0.5: caveats in the main line ---------------------------------
    ("0.5", "explicit caveat", re.compile(
        r"\b(caveat|the one limit|the only limit|limitation|not verified"
        r"|unverified|should be checked|revisit(?:ed|ing)?\b|bear in mind"
        r"|keep in mind|be aware|it should be noted|to be fair|admittedly"
        r"|with the exception)", re.I)),
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
    ("3", "walking the reader", re.compile(
        # The writer narrating the reading experience instead of stating the
        # next fact. "Let's say / assume / define" survives: that is the
        # standard framing for a worked example, not a tour-guide gesture.
        r"(\blet[’']s (?!say\b|call\b|assume\b|suppose\b|denote\b|define\b"
        r"|imagine\b)\w+|\blet us (?!say\b|call\b|assume\b|suppose\b|denote\b"
        r"|define\b|imagine\b)\w+"
        r"|\bwe(?:[’']ll| will) (?:now |then |first )?(?:look|turn|dive"
        r"|cover|discuss|walk|explore|examine|return)\b"
        r"|\bbefore we (?:dive|begin|start|get started|go any further|continue)\b"
        r"|\bbefore diving in|\bin what follows\b"
        r"|\bnow that (?:we|you)(?:[’']ve| have)\b"
        r"|\bwith that out of the way\b|\bwithout further ado\b"
        r"|\bas (?:you|we) (?:can see|have seen|saw|will see)\b"
        r"|\byou m(?:ight|ay) (?:be wondering|wonder|ask)\b"
        r"|\bmoving on\b)", re.I)),
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
        # "(?!recent)" because "the most recent snapshot" selects among live
        # data — it ranks the data, not the writer's own argument.
        r"\b(the (?:single )?most (?!recent)\w+|the least \w+|the (?:weakest|strongest|best"
        r"|worst) (?:thing|part|area|link)|literally the|is the finding"
        r"|the important (?:thing|one)|the key (?:thing|point|takeaway))\b", re.I)),
    ("6", "salience adverb", re.compile(
        # The adverb form of the same move: rating the next clause's importance
        # instead of letting it earn it. "Significantly" is excluded — in
        # technical prose it usually modifies a measurement, not the reader.
        r"\b(?:(?:more|most) )?(?:importantly|crucially|critically|notably)\b", re.I)),
    ("7", "intent disclosure", re.compile(
        r"\b(deliberately|on purpose|explicitly|intentionally|by design)\b", re.I)),
    ("8", "contrastive framing", re.compile(
        r"(\bnot (?:a|an|the) [\w-]+[;,] (?:it|that|this) is\b"
        r"|\b(?:is|are) \w+, not \w+\b)", re.I)),
    ("9", "meta-commentary on the record", re.compile(
        r"\b(the diff is the record|worth recording|being wrong in a recorded way"
        r"|flagging (?:it|this) as|the point of (?:writing|documenting))\b", re.I)),
]

# NOTE: an earlier version also flagged every "What …" and "How …" heading.
# That fired on "How it works" and "What is in here" in nearly every README —
# headings that name their subject, which is exactly what class 10 asks for.
# "Why …" stays: a Why heading opens an argument by construction.
HEADING_ASSERTS = [
    ("10", "heading argues rather than names", re.compile(
        r", and why\s*$"          # "The distinction, and why"
        r"|^#{1,6}\s+Why\b"       # "Why the cache is an LRU"
        r"|—[^—]*\bnot\b[^—]*$"  # "Format stability — measured, not assumed"
        r"|:\s[^:]{0,40}\bnot\b"  # "Trailblazer: a confident but not correct answer"
        r"|\bmatters\s*$",        # "Why density matters" / "Density matters"
        re.I)),
]

# Per-label suppressors: if the (normalised) line matches, the hit is dropped.
#
# These encode senses the pattern can't tell apart from position alone. A
# "round" is a revision of a document *or* a wave of a survey; "formerly" marks
# a doc's own prior state *or* a third party's rename; "has been built" narrates
# a change *or* names the moment a condition becomes true. Suppressing the
# non-artifact senses here is better than making a reader discard the same
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
        r"\b(inc|llc|ltd|corp|company|brands?|portfolio|founded|co-founder"
        r"|CEO|CTO|president)\b\.?", re.I),
    # "Once the index has been built, queries hit it" is runtime sequencing,
    # not a changelog: the conditional marker before the perfect tense is what
    # separates "when this becomes true" from "this changed".
    "perfect-tense changelog": re.compile(
        r"\b(once|after|when|whenever|until|unless|if|before|as soon as"
        r"|assuming|provided)\b[^.;]{0,60}\b(?:has|have)\b", re.I),
    # "the most recent snapshot wins" selects among live data; it does not
    # date the prose.
    "recency marker": re.compile(r"\bmost recent(?:ly)?\b", re.I),
}

# Labels whose suppressor must overlap the finding itself, not merely appear
# somewhere on the line. "X has been added back. Once Y has been uploaded, ..."
# holds a real changelog and a runtime condition in one line; suppressing by
# line would let the condition shield the changelog.
POSITIONAL_SUPPRESS = {"perfect-tense changelog"}

# Path-level suppressors: some classes are genre, not cruft. A tutorial walks
# the reader by contract — flagging every "let's" in a quickstart would report
# the genre's voice as a finding.
PATH_SUPPRESS = {
    "walking the reader": re.compile(
        r"tutorial|getting[-_ ]?started|walkthrough|onboarding|quickstart",
        re.I),
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
    (re.compile(r"\b[Ii]t(?:[’']s| is) worth (?:noting|mentioning|pointing out) that\s+"), ""),
    # the same announcement in its other uniforms
    (re.compile(r"\b[Ii]t(?:[’']s| is) important to (?:note|remember|understand) that\s+"), ""),
    (re.compile(r"\b[Ii]t should be noted that\s+"), ""),
    (re.compile(r"\b[Pp]lease note that\s+"), ""),
    # "Worth noting: X" / "Worth knowing: X" -> "X"
    (re.compile(r"^\**Worth (?:noting|knowing|mentioning)\**:\s*"), ""),
    # discourse filler with no propositional content
    (re.compile(r"\b[Nn]eedless to say,\s*"), ""),
    (re.compile(r"^Of course,\s+"), ""),
    (re.compile(r"\b[Ii]t goes without saying that\s+"), ""),
    (re.compile(r"\b[Aa]s you can see,\s*"), ""),
    (re.compile(r"\b[Ww]ithout further ado,\s*"), ""),
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


def _strip_phrase(pat, line):
    """Delete every match, re-capitalising the word after a deletion that
    opened its sentence — "LRU. Please note that the API" must come back as
    "LRU. The API", not "LRU. the API"."""
    changed = False
    while True:
        m = pat.search(line)
        if not m:
            return line, changed
        before, after = line[:m.start()], line[m.end():]
        opens = not before.strip() or before.rstrip().endswith((".", "!", "?"))
        if opens and after and after[0].islower():
            after = after[0].upper() + after[1:]
        line = before + after
        changed = True


def count_safe_fixes(files):
    """How many lines across *files* --fix would rewrite. Reported at the end
    of a plain scan so the mechanical subset is discoverable from the output
    itself, not just from --help."""
    n = 0
    for path in files:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        for _, line in prose_lines(lines):
            _, changes = apply_safe_fixes(line)
            if changes:
                n += 1
    return n


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
        if repl == "":
            new, did = _strip_phrase(pat, new)
            if did:
                changes.append(f"removed {pat.pattern!r}")
        else:
            candidate = pat.sub(repl, new)
            if candidate != new:
                changes.append(f"removed {pat.pattern!r}")
                new = candidate

    return new, changes


# ---------------------------------------------------------------------------

FENCE = re.compile(r"^\s*(```|~~~)")


def prose_lines(lines):
    """Yield (lineno, line) for prose only.

    Skips fenced code, YAML front-matter and HTML comments — the three places
    where prose-shaped text isn't prose. Front-matter matters more than it
    looks: a skill or site description saying "previously X" is config, and
    editing it with --fix would corrupt the YAML.
    """
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


# A line that opens a new block — the soft-wrap join below must not glue a
# paragraph's last line onto the heading, bullet or table row that follows it.
BLOCK_START = re.compile(r"^\s*(#{1,6}\s|\||[-*+]\s|\d+[.)]\s|>)")


def _suppressed(label, m, text, path):
    sup = SUPPRESS.get(label)
    if sup:
        if label in POSITIONAL_SUPPRESS:
            if any(s.start() < m.end() and m.start() < s.end()
                   for s in sup.finditer(text)):
                return True
        elif sup.search(text):
            return True
    psup = PATH_SUPPRESS.get(label)
    return bool(psup and psup.search(path))


def scan_file(path):
    """Return (findings, line_count) for one markdown file."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"skipped {path}: {exc}", file=sys.stderr)
        return [], 0

    findings = []
    # One finding per class per line: a line hit by two sibling patterns is
    # still one line to read, and double-counting inflates the totals the
    # report is built on.
    seen = set()

    def add(n, cls, label, match_text, shown_text):
        if (n, cls) in seen:
            return
        seen.add((n, cls))
        findings.append({"file": path, "line": n, "class": cls,
                         "label": label, "match": match_text,
                         "text": shown_text})

    prose = list(prose_lines(lines))
    for n, line in prose:
        plain = plain_text(line)
        table_row = line.lstrip().startswith("|")
        heading = line.lstrip().startswith("#")
        checks = HEADING_ASSERTS + PATTERNS if heading else PATTERNS

        for cls, label, pat in checks:
            m = pat.search(plain)
            if not m:
                continue
            if _suppressed(label, m, plain, path):
                continue
            # A caveat inside a table cell is usually a tag, not a clause.
            if table_row and cls == "0.5" and len(line) > 200:
                continue
            add(n, cls, label, m.group(0).strip(), line.strip())

    # Soft wraps split phrases across lines — "the backoff table is the /
    # least defensible thing here" hides "the least defensible" from every
    # per-line pattern. Join each adjacent pair inside a paragraph and keep
    # only the matches that span the boundary: anything else the per-line
    # pass already saw.
    for (na, a), (nb, b) in zip(prose, prose[1:]):
        if nb != na + 1:
            continue
        if a.lstrip().startswith(("#", "|")) or BLOCK_START.match(b):
            continue
        pa = plain_text(a)
        cut = len(pa)
        joined = pa + " " + plain_text(b)
        for cls, label, pat in PATTERNS:
            if (na, cls) in seen or (nb, cls) in seen:
                continue
            m = next((mm for mm in pat.finditer(joined)
                      if mm.start() < cut < mm.end()), None)
            if m is None or _suppressed(label, m, joined, path):
                continue
            add(na, cls, label, m.group(0).strip(),
                a.strip() + " " + b.strip())
    return findings, len(lines)


def class_matches(cls, want):
    """--class filter. Exact, or a family: "0" means 0a-0d and not 0.5,
    "1" means 1 and not 10. A bare startswith gets both of those wrong."""
    return cls == want or (cls.startswith(want) and cls[len(want):].isalpha())


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
               "/meeting-notes/", "/minutes/", "/retros/", "/postmortems/",
               "/superpowers/")
RECORD_FILE = re.compile(r"(^|/)(\d{4}-\d{2}-\d{2}[-_]|CHANGELOG|HISTORY"
                         r"|RELEASES|NEWS\.md)", re.I)


def is_record(path):
    """True for point-in-time records, as opposed to standing documents."""
    norm = "/" + path.replace(os.sep, "/").lstrip("./")
    return any(d in norm for d in RECORD_DIRS) or bool(RECORD_FILE.search(norm))


def is_self(path, self_excludes):
    """True when path is the skill's own prose, compared by resolved path.

    Resolved rather than substring: the caller may pass `docs` or `./docs` or
    an absolute path, and a substring test against an absolute exclude silently
    fails on the relative forms — which is exactly the case where the scanner
    ends up reporting its own SKILL.md as 100 findings.
    """
    ap = os.path.abspath(path)
    for x in self_excludes:
        if x.endswith(os.sep):
            if ap.startswith(x):
                return True
        elif ap == x:
            return True
    return False


def collect(paths, excludes=(), self_excludes=(), include_records=False):
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
                dirs[:] = sorted(d for d in dirs if d not in
                                 {"node_modules", ".git", "dist", "build",
                                  ".next", "vendor", ".venv", "target"})
                files += [os.path.join(root, n) for n in sorted(names)
                          if n.endswith((".md", ".markdown"))]
        elif p.endswith((".md", ".markdown")):
            files.append(p)
    files = [f for f in files
             if not any(x in f for x in excludes)
             and not is_self(f, self_excludes)]
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
    self_excludes = [
        os.path.join(here, "SKILL.md"),
        os.path.join(here, "README.md"),
        os.path.join(here, "references") + os.sep,
    ]
    # Packaged as <repo>/skills/<name>/, the repo's own README documents this
    # same skill and quotes the patterns on nearly every line.
    if os.path.basename(os.path.dirname(here)) == "skills":
        self_excludes.append(os.path.join(os.path.dirname(os.path.dirname(here)),
                                          "README.md"))
    files, records = collect(args.paths, args.exclude, self_excludes,
                             args.include_records)
    if not files:
        print("no standing markdown found"
              + (f" ({len(records)} record docs skipped)" if records else ""),
              file=sys.stderr)
        return 2

    if args.fix:
        total = 0
        for path in files:
            with open(path, encoding="utf-8") as fh:
                src = fh.read().splitlines(keepends=True)
            prose = dict(prose_lines([r.rstrip("\n") for r in src]))
            out, edits = [], []
            for n, raw in enumerate(src, 1):
                if n not in prose:
                    out.append(raw)
                    continue
                line = raw.rstrip("\n")
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

    findings, file_stats = [], []
    for path in files:
        found, n_lines = scan_file(path)
        findings += found
        file_stats.append({"file": path, "lines": n_lines,
                           "findings": len(found)})
    if args.cls:
        findings = [f for f in findings if class_matches(f["class"], args.cls)]
        counts = defaultdict(int)
        for f in findings:
            counts[f["file"]] += 1
        for s in file_stats:
            s["findings"] = counts[s["file"]]

    # Density is the report's "where has revision concentrated" number: the
    # files worth editing first, and the clean files worth naming so a later
    # rewrite doesn't regress them.
    for s in file_stats:
        s["per_100_lines"] = round(100 * s["findings"] / s["lines"], 1) \
            if s["lines"] else 0.0
    dense = sorted((s for s in file_stats if s["findings"]),
                   key=lambda s: -s["per_100_lines"])
    clean = [s["file"] for s in file_stats if not s["findings"]]

    coll = collisions(findings)
    fixable = count_safe_fixes(files)

    if args.json:
        json.dump({"findings": findings, "collisions": coll,
                   "files": file_stats, "clean_files": clean,
                   "safe_fixes": fixable,
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
        else:
            print("\ncollisions: none — no superlative or aphorism repeats "
                  "across files")
        if dense:
            print("\n=== density — candidates per 100 lines ===")
            for s in dense:
                print(f"  {s['per_100_lines']:6.1f}  {s['file']}  "
                      f"({s['findings']} in {s['lines']} lines)")
        if clean:
            print(f"\nclean: {', '.join(clean)}")
        else:
            print("\nclean: none — every scanned file has candidates")
        print(f"\n{len(findings)} candidate(s) across {len(files)} file(s).")
        if fixable:
            print(f"{fixable} of these are mechanical — --fix applies them, "
                  "--fix --dry-run shows the rewrites first.")
        if records:
            print(f"Skipped {len(records)} point-in-time record(s) — dated plans, "
                  "specs, ADRs, changelogs. Their history IS their content; pass "
                  "--include-records to scan them anyway.")
        print("Candidates, not verdicts — classes 0 and 0.5 first, they are the "
              "ones that come from iterating.")

    return 1 if (args.check and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
