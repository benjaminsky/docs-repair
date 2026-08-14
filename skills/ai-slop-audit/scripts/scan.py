#!/usr/bin/env python3
"""Scan markdown — and, with --code, code comments — for AI-generated residue.

Cheap mechanical pass. Produces candidates with file:line and a suggested
class; a reader still decides. Deliberately over-reports — a false positive
costs one glance, a miss leaves a chat turn masquerading as documentation
for another year.

Usage:
    scan.py <path>...                    # scan files or directories
    scan.py <path>... --json             # machine-readable
    scan.py <path>... --class 0          # generation residue only (0a-0d)
    scan.py <path>... --code             # also scan code comments
    scan.py <path>... --fix              # apply the safe rewrites only
    scan.py <path>... --fix --dry-run    # show what --fix would change
    scan.py <path>... --check            # exit 1 on any finding (CI gate)

A source file named on the command line is scanned without --code — naming
the file is the request. Directory walks pick up code only with the flag.
--fix never rewrites a source file: comment extraction is heuristic, and a
rewrite applied to a misjudged string literal edits the program.

What a regex cannot check — whether a confident claim is true of the code it
describes — is the skill body's job, not this script's. The one exception is
class 0d: a relative link either resolves on disk or it does not, so phantom
references are checked here, against the filesystem.

Exit status is 0 unless --check is passed, in which case any finding exits 1.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from urllib.parse import unquote

# ---------------------------------------------------------------------------
# Matching happens against a normalised copy of each line, not the raw text.
# Inline code is masked — `leverage` inside backticks is an identifier, not
# prose — and emphasis markers are stripped so that **Seamless** still hits a
# word boundary. Reported text is always the raw line. Two passes are the
# exception and run against rawer text: link targets keep their underscores
# (emphasis-stripping would corrupt `my_file.md`), and placeholder brackets
# live inside code spans as often as outside them.
# ---------------------------------------------------------------------------

INLINE_CODE = re.compile(r"`[^`]+`")
EMPHASIS = re.compile(r"(?:\*{1,3}|_{1,3})(?=\S)|(?<=\S)(?:\*{1,3}|_{1,3})")


def plain_text(line):
    """The line as the patterns should see it: code masked, emphasis gone."""
    return EMPHASIS.sub("", INLINE_CODE.sub("`code`", line))


# ---------------------------------------------------------------------------
# Patterns. Each entry: (class, label, compiled regex).
#
# Classes 0a-0d are generation residue — the process leaking into the
# artifact — and have objective tests. Classes 1-6 are the register: the
# voice and structure a model reaches for when nobody stops it.
# ---------------------------------------------------------------------------

PATTERNS = [
    # --- Class 0: generation residue -----------------------------------------
    ("0a", "assistant self-narration", re.compile(
        r"\bI(?:'|’)ve (?:added|updated|created|implemented|fixed|removed"
        r"|renamed|refactored|adjusted|modified|changed|bumped|gone ahead|also)\b"
        r"|\bI(?:'|’)ll (?:now )?(?:add|update|create|implement|fix|remove)\b"
        r"|\bI have (?:added|updated|created|implemented|refactored)\b"
        r"|\bI went ahead and\b")),
    # "As an AI language model" and knowledge-cutoff talk are the model
    # describing itself — decisive when they appear, however rare.
    ("0a", "model disclaimer", re.compile(
        r"\bAs an AI(?: language model| assistant)?\b"
        r"|\bas of my (?:last )?knowledge cutoff\b|\bmy training data\b", re.I)),
    ("0a", "chat pleasantry", re.compile(
        r"\b(?:Great question|You(?:'|’)re absolutely right"
        r"|(?:I )?[Hh]ope this helps|Happy \w+ing|Thanks for reading"
        r"|Happy to help|Please don(?:'|’)t hesitate"
        r"|Let me know if you|Feel free to (?:reach out|ask)"
        r"|Would you like me to|As requested"
        r"|Here(?:'|’)s (?:the|an) updated|Here(?:'|’)s a breakdown)\b"
        r"|^\s*(?:Certainly|Absolutely|Of course|Sure thing)[,!]")),
    ("0b", "handoff summary", re.compile(
        r"\b(?:The following changes were made|Changes made:|Key changes:"
        r"|Files (?:modified|changed):|In this update|What was done"
        r"|This (?:PR|pull request|commit|change) (?:adds|introduces|updates"
        r"|fixes|implements|refactors)"
        r"|Summary of [Cc]hanges"
        r"|The above (?:changes|implementation)"
        r"|This completes the"
        r"|No breaking changes\b"
        r"|with full test coverage"
        r"|(?:The )?[Ii]mplementation is (?:now )?complete)")),
    ("0b", "test-pass assertion", re.compile(
        r"\b[Aa]ll (?:\d+\s+)?tests?\s+(?:are\s+)?(?:now\s+)?pass(?:ing|ed)?\b")),
    ("0c", "unfilled placeholder", re.compile(
        r"\[(?:Insert|Add|Your|Describe|List|Explain|Provide|Fill"
        r"|TODO|TBD|PLACEHOLDER)\b[^\]]*\](?![([])"
        r"|\blorem ipsum\b"
        r"|\bTODO: (?:add|fill|write|describe|document|complete)\b", re.I)),

    # --- Classes 1-6: the register -------------------------------------------
    ("1", "importance inflation", re.compile(
        r"\b(?:comprehensive|robust|seamless(?:ly)?|effortless(?:ly)?"
        r"|blazing(?:ly)?[- ]fast|lightning-fast|cutting-edge"
        r"|state-of-the-art|best-in-class|world-class|enterprise-grade"
        r"|production-ready|battle-tested|feature-rich|full-fledged"
        r"|unparalleled|industry-leading|next-generation|revolutionary"
        r"|supercharge(?:s|d)?|top-notch|hassle-free"
        r"|highly (?:scalable|performant|efficient|optimized)"
        r"|simple yet powerful|powerful yet simple"
        r"|rich set of|wide (?:range|array) of|endless possibilities)\b", re.I)),
    ("2", "lexical tell", re.compile(
        r"\b(?:delve(?:s|d)?|delving|leverag(?:e|es|ed|ing)"
        r"|utiliz(?:e|es|ed|ing)|facilitat(?:e|es|ed|ing)"
        r"|streamlin(?:e|es|ed|ing)|empower(?:s|ed|ing)?"
        r"|unlock(?:s|ed|ing)?|harness(?:es|ed|ing)?|foster(?:s|ed|ing)?"
        r"|elevate(?:s|d)?|myriad|plethora|a testament to|game-?changer"
        r"|boasts?|pivotal|invaluable|meticulously|holistic|synerg\w+"
        r"|encompass(?:es|ing)?|underscor(?:e|es|ing)|showcas(?:e|es|ing)"
        r"|cornerstone|(?:rich )?tapestry of|paradigm shift"
        r"|in today(?:'|’)s|fast-paced|ever-evolving|deep(?:er)? dive"
        r"|dive deep(?:er)?)\b", re.I)),
    ("2", "role inflation", re.compile(
        r"\bplays? a (?:crucial|key|vital|pivotal|critical) role\b"
        r"|\bit is (?:crucial|essential|vital) to\b"
        r"|\b(?:serves as|acts as|forms) the (?:backbone|cornerstone"
        r"|bedrock|foundation) of\b"
        r"|\bof paramount importance\b", re.I)),
    ("3", "essay scaffold", re.compile(
        r"\bIn this (?:document|guide|section|article|README|post|page)"
        r"(?:,| we| you)"
        r"|\bIn conclusion\b|\bIn summary\b|\bTo summarize\b|\bTo sum up\b"
        r"|\bBy the end of this (?:guide|tutorial|article|document)\b"
        r"|\bThis (?:guide|document|page) (?:will walk|walks|will take"
        r"|takes) you through\b"
        r"|\bWhether you(?:'|’)re a\b|\bLook no further\b"
        r"|\bhas you covered\b|\bLet(?:'|’)s (?:dive in|get started)\b", re.I)),
    ("4", "symmetric filler", re.compile(
        r"\bnot only\b.{0,60}\bbut also\b"
        r"|\bisn(?:'|’)t just (?:about )?\w+"
        r"|\bis (?:more|about more) than just\b"
        r"|\bnot just an? \w+(?:.{0,40}\bbut\b)?"
        r"|\bstrikes? a balance between\b|\bthe perfect blend of\b"
        r"|\bthe best of both worlds\b|\bto the next level\b", re.I)),
]

# Heading-only checks. A "Conclusion" over a reference section is an essay's
# skeleton on a document that is not an essay — standing docs are consulted,
# not read through, so nothing concludes.
HEADING_PATTERNS = [
    ("3", "narrative heading", re.compile(
        r"^#{1,6}\s*[^\w]*(?:Conclusion|Final Thoughts|Final Notes"
        r"|Key Takeaways|Wrapping Up|Closing Thoughts|In Summary)\s*$", re.I)),
]

# Emoji for class 5. Deliberately not the full Unicode emoji property: the
# ranges below cover the decoration models reach for (🚀 ✨ ✅ ⚡ 📝 ⭐) while
# leaving out technical symbols like ⌘ and ▶ that keyboard and UI docs use as
# content. FE0F/200D are sequence glue, matched only when stripping.
EMOJI = re.compile("[☀-➿⬀-⭟\U0001F300-\U0001FAFF]")
EMOJI_STRIP = re.compile(
    "[☀-➿⬀-⭟\U0001F300-\U0001FAFF️‍]")
BULLET_LEAD = re.compile(r"^\s*(?:[-*+]\s+)?" + EMOJI.pattern)

# Per-label suppressors: senses the pattern can't tell apart on its own.
# Each one is a deliberate blind spot — keep the list short and justified.
SUPPRESS = {
    # "robust standard errors" is statistics; "comprehensive income" is
    # accounting; "next-generation sequencing" is a lab technique. The
    # domain owns these words; the register merely borrows them.
    "importance inflation": re.compile(
        r"\brobust (?:standard errors?|regression|statistics|estimat)"
        r"|\bcomprehensive income\b"
        r"|\bnext-generation sequencing\b", re.I),
    # A test harness is a thing, not a gesture; leverage is a quantity in
    # finance; unlocking a bootloader is a procedure; elevated privileges
    # are a security state; a programming paradigm is a category, not a
    # shift being marketed.
    "lexical tell": re.compile(
        r"\b(?:test|wiring|cable) harness(?:es)?\b"
        r"|\b(?:leverage|debt|operating) ratio\b"
        r"|\b(?:operating|financial) leverage\b"
        r"|\bunlock(?:s|ed|ing)? (?:the )?(?:device|phone|screen|bootloader"
        r"|account|mutex|lock)\b"
        r"|\belevated privileg|\bprivilege elevation\b"
        r"|\bprogramming paradigm\b", re.I),
    # "make sure all tests pass before pushing" is an instruction to the
    # reader, not a completion report by the writer.
    "test-pass assertion": re.compile(
        r"\b(?:ensure|make sure|makes sure|verify|confirm|check that|until"
        r"|so that|once|when|before|after|require[sd]?( that)?)\b", re.I),
}

# Path-level suppressors: a quickstart is allowed to say "let's get started" —
# that is the genre's contract with the reader, not slop.
PATH_SUPPRESS = {
    "essay scaffold": re.compile(
        r"tutorial|getting[-_ ]?started|walkthrough|onboarding|quickstart",
        re.I),
}

# ---------------------------------------------------------------------------
# --fix: only rewrites whose removal cannot lose a fact.
#
# A pleasantry line carries no proposition; an emoji in a heading decorates a
# name that survives without it; "In conclusion," announces the sentence that
# follows it. Everything else needs a human to decide what the surviving fact
# is, and keeping --fix this narrow is what makes it safe to run unattended.
# ---------------------------------------------------------------------------

# A line may chain them — "Hope this helps! Let me know if you have any
# questions." — and a chain of pleasantries is still propositionally empty.
PLEASANTRY_LINE = re.compile(
    r"^\W*(?:(?:I hope this helps|Hope this helps|Happy \w+ing"
    r"|Thanks for reading"
    r"|Let me know if you have any questions"
    r"|Let me know if you need anything else"
    r"|Let(?:'|’)s dive in|Feel free to reach out)(?:\s*[!.])*\s*)+\W*$", re.I)

OPENER_FIXES = [
    re.compile(r"\bIn conclusion,\s+"),
    re.compile(r"\bIn summary,\s+"),
    re.compile(r"\bTo summarize,\s+"),
]

HEADING = re.compile(r"^#{1,6}\s")


def _strip_phrase(pat, line):
    """Delete every match, re-capitalising a word that now opens its
    sentence — "runs cold. In summary, the cache helps" must come back as
    "runs cold. The cache helps"."""
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


def fix_line(line):
    """Return (new_line_or_None, [descriptions]). None means delete the line."""
    if PLEASANTRY_LINE.match(line) and line.strip():
        return None, ["deleted a pleasantry line — no proposition to lose"]
    changes = []
    new = line
    if HEADING.match(new) and EMOJI.search(new):
        stripped = EMOJI_STRIP.sub("", new)
        stripped = re.sub(r"(#{1,6})\s+", r"\1 ", stripped).rstrip()
        stripped = re.sub(r"  +", " ", stripped)
        if stripped != new:
            changes.append("stripped emoji from a heading")
            new = stripped
    for pat in OPENER_FIXES:
        new, did = _strip_phrase(pat, new)
        if did:
            changes.append(f"removed {pat.pattern!r}")
    return new, changes


def count_safe_fixes(files):
    """How many lines across *files* --fix would change. Reported at the end
    of a plain scan so the mechanical subset is discoverable from the output
    itself, not just from --help. Source files count zero: --fix refuses
    them, so advertising their phrases as fixable would be a lie."""
    n = 0
    for path in files:
        if comment_syntax(path):
            continue
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        for _, line in prose_lines(lines):
            new, changes = fix_line(line)
            if new is None or changes:
                n += 1
    return n


# ---------------------------------------------------------------------------

FENCE = re.compile(r"^\s*(```|~~~)")


def prose_lines(lines):
    """Yield (lineno, line) for prose only.

    Skips fenced code, YAML front-matter and HTML comments — the three places
    where prose-shaped text isn't prose. A fenced example saying "All tests
    pass" is output being quoted, not a claim being made.
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


# ---------------------------------------------------------------------------
# Code comments. The same residue accumulates next to code — "# I've bumped
# this to handle the new load", "// leverages a robust worker pool" — and
# the same patterns apply. Extraction machinery mirrors the sibling
# metadiscourse scanner, for the same reasons.
#
# Per extension: (line markers, block open, block close). Docstrings are out
# of scope: a triple-quoted string is data as often as documentation, and a
# guess that misjudges one reads string literals as prose. A comment marker
# is unambiguous; a string never is.
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


# Machine-directed comments are not prose: linter and formatter pragmas,
# editor modelines, encoding declarations.
DIRECTIVE = re.compile(
    r"^(?:-\*-|noqa|type:|pylint|mypy:|ruff:|flake8:|isort:|fmt:|yapf:"
    r"|eslint|prettier|biome-|@ts-|tslint:|jshint|istanbul|nolint|nosec"
    r"|NOSONAR|pragma|coverage:|cspell:|spell-?checker:|vim:|vi:"
    r"|region\b|endregion\b)", re.I)

# TODO and its relatives are tracker items living in code — greppable by
# convention, their "not yet" is their content. Flagging every TODO would
# bury the findings under a backlog nobody asked to audit.
WORK_MARKER = re.compile(r"^(?:TODO|FIXME|XXX|HACK|BUG|todo|fixme)\b")


def _find_marker(line, marker):
    """Index of marker where it can start a comment: at column 0 or after
    whitespace. One rule covers the two big false extractions — "#" inside a
    string sits against a quote ('x = "#tag"'), and the "//" in a URL sits
    against a colon — at the cost of missing the rare unspaced trailer."""
    i = 0
    while True:
        i = line.find(marker, i)
        if i <= 0:
            return i
        if line[i - 1] in " \t":
            return i
        i += 1


def comment_lines(lines, syntax):
    """Yield (lineno, text) for the comment prose in a source file.

    Skips shebangs, machine directives, work markers and pure-decoration
    banners; strips the "*" gutter of block comments and stacked markers
    ("##", "///"). Extraction is heuristic — a "#" after a space inside a
    string will be read as a comment — which is why --fix refuses source
    files and these lines are report-only.
    """
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
# Structural checks: shapes a per-line regex can't see. Markdown only.
# ---------------------------------------------------------------------------

# Markdown inline links and images. Reference-style links and autolinks are
# left alone — their targets resolve elsewhere.
LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)>\s]+)>?\s*(?:\"[^\"]*\")?\)")
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)

# Bulleted or numbered: "1. **Term**: …" walls read the same as "- **Term**:
# …" walls, and models produce both.
BOLD_BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\*\*[^*]+\*\*")
BOLD_RUN_MIN = 5

# A thematic break: ---, *** or ___ on its own line. The preceding line must
# be blank, or the dashes are a setext heading underline, not a rule.
THEMATIC_BREAK = re.compile(r"^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$")
BREAK_CONFETTI_MIN = 3


def phantom_links(prose, path):
    """Class 0d: a relative link whose target does not exist on disk.

    The one fabrication tell with a fully objective test. Site-absolute
    paths, anchors, schemes and templated targets are skipped — they resolve
    somewhere this scan can't see.
    """
    base = os.path.dirname(path)
    out = []
    for n, line in prose:
        for m in LINK.finditer(INLINE_CODE.sub("`code`", line)):
            target = m.group(1)
            if (SCHEME.match(target) or target.startswith(("#", "/", "{", "<"))
                    or "$" in target):
                continue
            rel = unquote(target.split("#")[0].split("?")[0])
            if not rel:
                continue
            if not os.path.exists(os.path.normpath(os.path.join(base, rel))):
                out.append((n, target, line.strip()))
    return out


def empty_sections(lines):
    """Class 0c: a heading whose section has no body before the next heading
    at the same or shallower depth. Scaffolding generated and never filled.

    A deeper heading counts as body — a parent section may be pure container.
    Fences count as body — a section holding only a code block is not empty.
    """
    entries = []
    in_fence = False
    for n, line in enumerate(lines, 1):
        if FENCE.match(line):
            in_fence = not in_fence
            entries.append((n, 0, True))
            continue
        if in_fence:
            entries.append((n, 0, True))
            continue
        m = re.match(r"^(#{1,6})\s+\S", line)
        entries.append((n, len(m.group(1)) if m else 0, bool(line.strip())))
    out = []
    for i, (n, depth, _) in enumerate(entries):
        if not depth:
            continue
        body = False
        for _n2, depth2, nonblank in entries[i + 1:]:
            if depth2 and depth2 <= depth:
                break
            if nonblank:
                body = True
                break
        if not body:
            out.append((n, lines[n - 1].strip()))
    return out


def bold_bullet_runs(lines):
    """Class 6: long runs of `- **Term**: description` bullets — the shape a
    model reaches for instead of a paragraph or a table. Short runs are fine;
    the finding is the wall."""
    out = []
    run_start, run_len = None, 0
    for n, line in enumerate(lines + [""], 1):
        if BOLD_BULLET.match(line):
            if run_start is None:
                run_start = n
            run_len += 1
        else:
            if run_len >= BOLD_RUN_MIN:
                out.append((run_start, run_len))
            run_start, run_len = None, 0
    return out


def separator_confetti(lines):
    """Class 6: a horizontal rule between every section. One or two thematic
    breaks structure a page; a rule per section is the generated tic.
    Returns (first_line, count) or None."""
    fm_end = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, min(len(lines), 60)):
            if lines[i].strip() in ("---", "..."):
                fm_end = i + 1
                break
    breaks = []
    in_fence = False
    for n, line in enumerate(lines, 1):
        if n <= fm_end:
            continue
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence or not THEMATIC_BREAK.match(line):
            continue
        # A run of dashes directly under text is a setext underline.
        if n >= 2 and lines[n - 2].strip():
            continue
        breaks.append(n)
    if len(breaks) >= BREAK_CONFETTI_MIN:
        return breaks[0], len(breaks)
    return None


# A line that opens a new block — the soft-wrap join below must not glue a
# paragraph's last line onto the heading, bullet or table row that follows it.
BLOCK_START = re.compile(r"^\s*(#{1,6}\s|\||[-*+]\s|\d+[.)]\s|>)")


def _suppressed(label, text, path):
    sup = SUPPRESS.get(label)
    if sup and sup.search(text):
        return True
    psup = PATH_SUPPRESS.get(label)
    return bool(psup and psup.search(path))


def _scan_prose(prose, path, markdown):
    """Run the patterns over (lineno, line) pairs. markdown gates the checks
    that only mean anything in markdown — headings, emoji, placeholders."""
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

    for n, line in prose:
        plain = plain_text(line)
        table_row = markdown and line.lstrip().startswith("|")
        heading = markdown and HEADING.match(line.lstrip())

        checks = HEADING_PATTERNS + PATTERNS if heading else PATTERNS
        for cls, label, pat in checks:
            # Placeholders live inside code spans as often as outside them,
            # so that one pattern reads the raw line — but only in markdown,
            # where a bracket is prose; in a comment it is usually code.
            if label == "unfilled placeholder":
                if not markdown:
                    continue
                hay = line
            else:
                hay = plain
            m = pat.search(hay)
            if not m:
                continue
            if _suppressed(label, hay, path):
                continue
            add(n, cls, label, m.group(0).strip(), line.strip())

        # Class 5: emoji as decoration — headings and bullet leads only.
        # A ✅ in a support-matrix table cell is content, so table rows pass.
        if markdown and not table_row and (
                (heading and EMOJI.search(line)) or BULLET_LEAD.match(line)):
            add(n, "5", "emoji decoration",
                EMOJI.search(line).group(0), line.strip())

    # Soft wraps split phrases across lines — "not only a queue / but also a
    # platform" hides the symmetry from every per-line pattern. Join each
    # adjacent pair inside a paragraph and keep only the matches that span
    # the boundary: anything else the per-line pass already saw.
    for (na, a), (nb, b) in zip(prose, prose[1:]):
        if nb != na + 1:
            continue
        if (markdown and a.lstrip().startswith(("#", "|"))) \
                or BLOCK_START.match(b):
            continue
        pa = plain_text(a)
        cut = len(pa)
        joined = pa + " " + plain_text(b)
        for cls, label, pat in PATTERNS:
            if label == "unfilled placeholder":
                continue
            if (na, cls) in seen or (nb, cls) in seen:
                continue
            m = next((mm for mm in pat.finditer(joined)
                      if mm.start() < cut < mm.end()), None)
            if m is None or _suppressed(label, m.group(0), path):
                continue
            add(na, cls, label, m.group(0).strip(),
                a.strip() + " " + b.strip())
    return findings


def scan_file(path):
    """Return (findings, line_count) for one file.

    For a source file the findings come from its comments, and line_count is
    the number of comment lines scanned — so density stays "candidates per
    100 lines of prose" rather than being flattened by the code around it.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"skipped {path}: {exc}", file=sys.stderr)
        return [], 0

    syntax = comment_syntax(path)
    if syntax:
        prose = list(comment_lines(lines, syntax))
        return _scan_prose(prose, path, markdown=False), len(prose)

    prose = list(prose_lines(lines))
    findings = _scan_prose(prose, path, markdown=True)
    seen = {(f["line"], f["class"]) for f in findings}

    def add(n, cls, label, match_text, shown_text):
        if (n, cls) in seen:
            return
        seen.add((n, cls))
        findings.append({"file": path, "line": n, "class": cls,
                         "label": label, "match": match_text,
                         "text": shown_text})

    for n, target, text in phantom_links(prose, path):
        add(n, "0d", "phantom relative link", target, text)
    for n, text in empty_sections(lines):
        add(n, "0c", "empty section", text, text)
    for start, length in bold_bullet_runs(lines):
        add(start, "6", "bold-term bullet run",
            f"{length} consecutive bullets",
            f"{length} consecutive '**Term**: …' bullets starting here")
    confetti = separator_confetti(lines)
    if confetti:
        first, count = confetti
        add(first, "6", "separator confetti",
            f"{count} horizontal rules",
            f"{count} horizontal rules in one document, first one here")
    return findings, len(lines)


def class_matches(cls, want):
    """--class filter. Exact, or a family: "0" means 0a-0d."""
    return cls == want or (cls.startswith(want) and cls[len(want):].isalpha())


# ---------------------------------------------------------------------------
# Echoes: the same explanation in more than one file. Sessions don't read
# sibling documents, so the shared explanation gets regenerated wherever it
# seems locally useful. Two granularities, both deterministic:
#
#   - a sentence repeated verbatim (after normalisation) across files.
#     Sentences are split after paragraphs are joined, so a sentence that
#     soft-wraps differently in each file still matches.
#   - a paragraph that is near-verbatim across files, by 5-word shingle
#     overlap — regeneration rarely reproduces a paragraph exactly, but the
#     shingles survive the paraphrase.
#
# Deliberately not embeddings: this scanner's contract is stdlib-only, and
# byte-identical output for identical input — a model dependency breaks
# both. "Same idea in different words" is the triage's job; the reader has
# the files open anyway.
# ---------------------------------------------------------------------------

ECHO_MIN_SENT_WORDS = 8    # a repeated sentence shorter than this is idiom
ECHO_MIN_PARA_WORDS = 25   # paragraphs below this are headings in disguise
ECHO_SHINGLE = 5
ECHO_JACCARD = 0.5

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _normalise(text):
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", "", text.lower())).strip()


def _paragraphs(prose, markdown):
    """Consecutive prose lines joined into (start_line, joined_text),
    headings, bullets and table rows excluded — those repeat legitimately.
    In markdown a block opener flushes; comment prose has no blocks."""
    paras, start, buf = [], None, []

    def flush():
        if buf:
            paras.append((start, " ".join(buf)))

    prev_n = None
    for n, line in prose:
        block = markdown and BLOCK_START.match(line)
        if block or (prev_n is not None and n != prev_n + 1):
            flush()
            start, buf = None, []
        if not block:
            if start is None:
                start = n
            buf.append(plain_text(line).strip())
        prev_n = n
    flush()
    return paras


def echoes(file_prose, markdown_flags=None):
    """Repeated sentences and near-duplicate paragraphs across files."""
    out, seen_pairs = [], set()

    all_paras = []
    for path, prose in file_prose.items():
        md = True if markdown_flags is None else markdown_flags.get(path, True)
        all_paras += [(path, start, text)
                      for start, text in _paragraphs(prose, md)]

    # Pass 1: verbatim sentences, matched after paragraph join so soft wraps
    # don't hide them. Sites point at the paragraph's first line.
    buckets = defaultdict(list)
    for path, start, text in all_paras:
        for sent in SENT_SPLIT.split(text):
            key = _normalise(sent)
            if len(key.split()) < ECHO_MIN_SENT_WORDS:
                continue
            buckets[key].append((path, start))
    for key, sites in sorted(buckets.items()):
        if len({p for p, _ in sites}) > 1:
            out.append({"text": key[:100], "count": len(sites),
                        "sites": [f"{p}:{n}" for p, n in sites]})
            for pa, _ in sites:
                for pb, _ in sites:
                    seen_pairs.add((pa, pb))

    # Pass 2: near-duplicate paragraphs. Quadratic in paragraph count, which
    # a docs corpus keeps small; the shingle-set sizes do the real filtering.
    shingled = []
    for path, start, text in all_paras:
        words = _normalise(text).split()
        if len(words) < ECHO_MIN_PARA_WORDS:
            continue
        shingles = {tuple(words[i:i + ECHO_SHINGLE])
                    for i in range(len(words) - ECHO_SHINGLE + 1)}
        shingled.append((path, start, words, shingles))
    for i, (pa, na, wa, sa) in enumerate(shingled):
        for pb, nb, _wb, sb in shingled[i + 1:]:
            if pa == pb or (pa, pb) in seen_pairs:
                continue
            union = len(sa | sb)
            if not union:
                continue
            j = len(sa & sb) / union
            if j >= ECHO_JACCARD:
                out.append({"text": " ".join(wa[:12]) + " …",
                            "count": 2, "similarity": round(j, 2),
                            "sites": [f"{pa}:{na}", f"{pb}:{nb}"]})
                seen_pairs.add((pa, pb))
                seen_pairs.add((pb, pa))
    return out


# A dated plan, spec, ADR or changelog is a record: read as of its date, its
# residue is its content. Same exclusion, same reasons, as the sibling
# metadiscourse scanner.
RECORD_DIRS = ("/plans/", "/specs/", "/adr/", "/adrs/", "/rfc/", "/rfcs/",
               "/decisions/", "/proposals/", "/journal/", "/changelog/",
               "/meeting-notes/", "/minutes/", "/retros/", "/postmortems/",
               "/superpowers/")
RECORD_FILE = re.compile(r"(^|/)(\d{4}-\d{2}-\d{2}[-_]|CHANGELOG|HISTORY"
                         r"|RELEASES|NEWS\.md)", re.I)


def is_record(path):
    norm = "/" + path.replace(os.sep, "/").lstrip("./")
    return any(d in norm for d in RECORD_DIRS) or bool(RECORD_FILE.search(norm))


def is_self(path, self_excludes):
    """True when path is the skill's own prose, compared by resolved path."""
    ap = os.path.abspath(path)
    for x in self_excludes:
        if x.endswith(os.sep):
            if ap.startswith(x):
                return True
        elif ap == x:
            return True
    return False


def collect(paths, excludes=(), self_excludes=(), include_records=False,
            include_code=False):
    """Gather markdown, minus --exclude substrings and (by default) records.

    Code files join a directory walk only with include_code; named on the
    command line they are always taken, because naming the file is the
    request. Minified files carry no prose either way.

    Returns (files, skipped_records, code_seen) so the caller can report what
    it dropped — a silent exclusion reads as "nothing there".
    """
    files, code_seen = [], 0
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in
                                 {"node_modules", ".git", "dist", "build",
                                  ".next", "vendor", ".venv", "target"})
                for name in sorted(names):
                    if name.endswith((".md", ".markdown")):
                        files.append(os.path.join(root, name))
                    elif comment_syntax(name) and ".min." not in name:
                        if include_code:
                            files.append(os.path.join(root, name))
                        else:
                            code_seen += 1
        elif p.endswith((".md", ".markdown")) or comment_syntax(p):
            files.append(p)
    files = [f for f in files
             if not any(x in f for x in excludes)
             and not is_self(f, self_excludes)]
    if include_records:
        return files, [], code_seen
    records = [f for f in files if is_record(f)]
    return [f for f in files if f not in set(records)], records, code_seen


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--class", dest="cls", help="filter, e.g. 0 or 0a or 2")
    ap.add_argument("--fix", action="store_true", help="apply the safe rewrites")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="exit 1 if anything found")
    ap.add_argument("--exclude", action="append", default=[],
                    metavar="SUBSTR", help="skip paths containing SUBSTR (repeatable)")
    ap.add_argument("--include-records", action="store_true",
                    help="also scan dated plans/specs/ADRs (excluded by default)")
    ap.add_argument("--code", action="store_true",
                    help="also scan code comments when walking directories")
    args = ap.parse_args()

    # Exclude this skill's own prose, by resolved path rather than by name:
    # a document about slop quotes slop on nearly every line, and scanning it
    # in place buries real findings under its own vocabulary.
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    self_excludes = [
        os.path.join(here, "SKILL.md"),
        os.path.join(here, "README.md"),
        os.path.join(here, "references") + os.sep,
        # The scanner's own source: its comments quote the patterns they
        # match, so a --code run over this directory reports the detector
        # as the disease.
        os.path.join(here, "scripts") + os.sep,
    ]
    if os.path.basename(os.path.dirname(here)) == "skills":
        self_excludes.append(os.path.join(os.path.dirname(os.path.dirname(here)),
                                          "README.md"))
    files, records, code_seen = collect(args.paths, args.exclude, self_excludes,
                                        args.include_records, args.code)
    if not files:
        note = ""
        if records:
            note += f" ({len(records)} record docs skipped)"
        if code_seen:
            note += (f" ({code_seen} code file(s) present — "
                     "--code scans their comments)")
        print("no standing markdown found" + note, file=sys.stderr)
        return 2

    if args.fix:
        total = 0
        code_files = 0
        for path in files:
            # Never rewrite a source file. Comment extraction is heuristic,
            # and a rewrite applied to a misjudged string literal edits the
            # program — the one failure --fix's contract cannot absorb.
            if comment_syntax(path):
                code_files += 1
                continue
            with open(path, encoding="utf-8") as fh:
                src = fh.read().splitlines(keepends=True)
            prose = dict(prose_lines([r.rstrip("\n") for r in src]))
            out, edits = [], []
            for n, raw in enumerate(src, 1):
                if n not in prose:
                    out.append(raw)
                    continue
                line = raw.rstrip("\n")
                new, changes = fix_line(line)
                if new is None:
                    edits.append((n, line, "<deleted>", changes))
                elif changes:
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
              + (f"; skipped {len(records)} record doc(s)" if records else "")
              + (f"; left {code_files} source file(s) untouched — comment "
                 "findings are report-only" if code_files else "") + ".")
        print("Everything else needs a decision about what the surviving fact "
              "is — run without --fix to see it.")
        return 0

    findings, file_stats = [], []
    file_prose, markdown_flags = {}, {}
    for path in files:
        found, n_lines = scan_file(path)
        findings += found
        file_stats.append({"file": path, "lines": n_lines,
                           "findings": len(found)})
        syntax = comment_syntax(path)
        markdown_flags[path] = not syntax
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        file_prose[path] = list(comment_lines(lines, syntax)) if syntax \
            else list(prose_lines(lines))
    if args.cls:
        findings = [f for f in findings if class_matches(f["class"], args.cls)]
        counts = defaultdict(int)
        for f in findings:
            counts[f["file"]] += 1
        for s in file_stats:
            s["findings"] = counts[s["file"]]

    for s in file_stats:
        s["per_100_lines"] = round(100 * s["findings"] / s["lines"], 1) \
            if s["lines"] else 0.0
    dense = sorted((s for s in file_stats if s["findings"]),
                   key=lambda s: -s["per_100_lines"])
    clean = [s["file"] for s in file_stats if not s["findings"]]

    echo = echoes(file_prose, markdown_flags)
    fixable = count_safe_fixes(files)

    if args.json:
        json.dump({"findings": findings, "echoes": echo,
                   "files": file_stats, "clean_files": clean,
                   "safe_fixes": fixable,
                   "skipped_records": records,
                   "skipped_code_files": code_seen}, sys.stdout, indent=2)
        print()
    else:
        by_class = defaultdict(list)
        for f in findings:
            by_class[f["class"]].append(f)
        order = ["0a", "0b", "0c", "0d", "1", "2", "3", "4", "5", "6"]
        for cls in order:
            group = by_class.get(cls)
            if not group:
                continue
            print(f"\n=== class {cls} — {len(group)} candidate(s) ===")
            for f in group:
                print(f"{f['file']}:{f['line']}  [{f['label']}]")
                print(f"    {f['text'][:160]}")
        if echo:
            print(f"\n=== echoes — {len(echo)} repeated across files ===")
            for e in echo:
                sim = f" (~{int(e['similarity'] * 100)}% similar)" \
                    if "similarity" in e else ""
                print(f"  {e['text']!r} ×{e['count']}{sim}: "
                      f"{', '.join(e['sites'])}")
        else:
            print("\nechoes: none — nothing repeats across files")
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
        if code_seen:
            print(f"Skipped {code_seen} code file(s) — pass --code to scan "
                  "their comments.")
        print("Candidates, not verdicts — class 0 first, it has the objective "
              "tests; and check the load-bearing claims against the code, "
              "which no scan can do.")

    return 1 if (args.check and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
