#!/usr/bin/env python3
"""Scan markdown for the residue of AI-generated documentation.

Cheap mechanical pass. Produces candidates with file:line and a suggested
class; a reader still decides. Deliberately over-reports — a false positive
costs one glance, a miss leaves a chat turn masquerading as documentation
for another year.

Usage:
    scan.py <path>...                    # scan files or directories
    scan.py <path>... --json             # machine-readable
    scan.py <path>... --class 0          # generation residue only (0a-0d)
    scan.py <path>... --fix              # apply the safe rewrites only
    scan.py <path>... --fix --dry-run    # show what --fix would change
    scan.py <path>... --check            # exit 1 on any finding (CI gate)

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
        r"|renamed|refactored|adjusted|modified|changed|also)\b"
        r"|\bI(?:'|’)ll (?:now )?(?:add|update|create|implement|fix|remove)\b"
        r"|\bI have (?:added|updated|created|implemented|refactored)\b")),
    ("0a", "chat pleasantry", re.compile(
        r"\b(?:Great question|You(?:'|’)re absolutely right"
        r"|(?:I )?[Hh]ope this helps|Happy coding"
        r"|Let me know if you|Feel free to (?:reach out|ask)"
        r"|Would you like me to|As requested"
        r"|Here(?:'|’)s (?:the|an) updated)\b"
        r"|^\s*(?:Certainly|Absolutely|Of course)[,!]")),
    ("0b", "handoff summary", re.compile(
        r"\b(?:The following changes were made|Changes made:"
        r"|In this update|What was done"
        r"|This (?:PR|pull request|commit|change) (?:adds|introduces|updates"
        r"|fixes|implements|refactors)"
        r"|Summary of [Cc]hanges"
        r"|(?:The )?[Ii]mplementation is (?:now )?complete)\b")),
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
        r"|rich set of|wide (?:range|array) of|endless possibilities)\b", re.I)),
    ("2", "lexical tell", re.compile(
        r"\b(?:delve(?:s|d)?|delving|leverag(?:e|es|ed|ing)"
        r"|utiliz(?:e|es|ed|ing)|facilitat(?:e|es|ed|ing)"
        r"|streamlin(?:e|es|ed|ing)|empower(?:s|ed|ing)?"
        r"|unlock(?:s|ed|ing)?|harness(?:es|ed|ing)?|foster(?:s|ed|ing)?"
        r"|elevate(?:s|d)?|myriad|plethora|a testament to|game-?changer"
        r"|in today(?:'|’)s|fast-paced|ever-evolving|deep(?:er)? dive"
        r"|dive deep(?:er)?)\b", re.I)),
    ("2", "role inflation", re.compile(
        r"\bplays? a (?:crucial|key|vital|pivotal|critical) role\b"
        r"|\bit is (?:crucial|essential|vital) to\b"
        r"|\bof paramount importance\b", re.I)),
    ("3", "essay scaffold", re.compile(
        r"\bIn this (?:document|guide|section|article|README|post|page)"
        r"(?:,| we| you)"
        r"|\bIn conclusion\b|\bIn summary\b|\bTo summarize\b|\bTo sum up\b"
        r"|\bWhether you(?:'|’)re a\b|\bLook no further\b"
        r"|\bhas you covered\b|\bLet(?:'|’)s (?:dive in|get started)\b", re.I)),
    ("4", "symmetric filler", re.compile(
        r"\bnot only\b.{0,60}\bbut also\b"
        r"|\bisn(?:'|’)t just (?:about )?\w+"
        r"|\bis (?:more|about more) than just\b"
        r"|\bnot just an? \w+(?:.{0,40}\bbut\b)?"
        r"|\bthe best of both worlds\b|\bto the next level\b", re.I)),
]

# Heading-only checks. A "Conclusion" over a reference section is an essay's
# skeleton on a document that is not an essay — standing docs are consulted,
# not read through, so nothing concludes.
HEADING_PATTERNS = [
    ("3", "narrative heading", re.compile(
        r"^#{1,6}\s*[^\w]*(?:Conclusion|Final Thoughts|Key Takeaways"
        r"|Wrapping Up|Closing Thoughts|In Summary)\s*$", re.I)),
]

# Emoji for class 5. Deliberately not the full Unicode emoji property: the
# ranges below cover the decoration models reach for (🚀 ✨ ✅ ⚡ 📝 ⭐) while
# leaving out technical symbols like ⌘ and ▶ that keyboard and UI docs use as
# content. FE0F/200D are sequence glue, matched only when stripping.
EMOJI = re.compile("[\u2600-\u27bf\u2b00-\u2b5f\U0001F300-\U0001FAFF]")
EMOJI_STRIP = re.compile(
    "[\u2600-\u27bf\u2b00-\u2b5f\U0001F300-\U0001FAFF\ufe0f\u200d]")
BULLET_LEAD = re.compile(r"^\s*(?:[-*+]\s+)?" + EMOJI.pattern)

# Per-label suppressors: senses the pattern can't tell apart on its own.
# Each one is a deliberate blind spot — keep the list short and justified.
SUPPRESS = {
    # "robust standard errors" is statistics; "comprehensive income" is
    # accounting. The domain owns these words; the register merely borrows.
    "importance inflation": re.compile(
        r"\brobust (?:standard errors?|regression|statistics|estimat)"
        r"|\bcomprehensive income\b", re.I),
    # A test harness is a thing, not a gesture; leverage is a quantity in
    # finance; unlocking a bootloader is a procedure; elevated privileges
    # are a security state.
    "lexical tell": re.compile(
        r"\b(?:test|wiring|cable) harness(?:es)?\b"
        r"|\b(?:leverage|debt|operating|financial) ratio\b"
        r"|\b(?:operating|financial) leverage\b"
        r"|\bunlock(?:s|ed|ing)? (?:the )?(?:device|phone|screen|bootloader"
        r"|account|mutex|lock)\b"
        r"|\belevated privileg|\bprivilege elevation\b", re.I),
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
    r"^\W*(?:(?:I hope this helps|Hope this helps|Happy coding"
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
    itself, not just from --help."""
    n = 0
    for path in files:
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
# Structural checks: shapes a per-line regex can't see.
# ---------------------------------------------------------------------------

# Markdown inline links and images. Reference-style links and autolinks are
# left alone — their targets resolve elsewhere.
LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)>\s]+)>?\s*(?:\"[^\"]*\")?\)")
SCHEME = re.compile(r"^[a-z][a-z0-9+.-]*:", re.I)

BOLD_BULLET = re.compile(r"^\s*[-*+]\s+\*\*[^*]+\*\*")
BOLD_RUN_MIN = 5


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


# ---------------------------------------------------------------------------

def _suppressed(label, text, path):
    sup = SUPPRESS.get(label)
    if sup and sup.search(text):
        return True
    psup = PATH_SUPPRESS.get(label)
    return bool(psup and psup.search(path))


def scan_file(path):
    """Return (findings, line_count) for one file."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        print(f"skipped {path}: {exc}", file=sys.stderr)
        return [], 0

    prose = list(prose_lines(lines))
    findings = []
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
        table_row = line.lstrip().startswith("|")
        heading = HEADING.match(line.lstrip())

        checks = HEADING_PATTERNS + PATTERNS if heading else PATTERNS
        for cls, label, pat in checks:
            # Placeholders live inside code spans as often as outside them,
            # so that one pattern reads the raw line.
            hay = line if label == "unfilled placeholder" else plain
            m = pat.search(hay)
            if not m:
                continue
            if _suppressed(label, hay, path):
                continue
            add(n, cls, label, m.group(0).strip(), line.strip())

        # Class 5: emoji as decoration — headings and bullet leads only.
        # A ✅ in a support-matrix table cell is content, so table rows pass.
        if not table_row and (
                (heading and EMOJI.search(line)) or BULLET_LEAD.match(line)):
            add(n, "5", "emoji decoration",
                EMOJI.search(line).group(0), line.strip())

    for n, target, text in phantom_links(prose, path):
        add(n, "0d", "phantom relative link", target, text)
    for n, text in empty_sections(lines):
        add(n, "0c", "empty section", text, text)
    for start, length in bold_bullet_runs(lines):
        add(start, "6", "bold-term bullet run",
            f"{length} consecutive bullets",
            f"{length} consecutive '**Term**: …' bullets starting here")

    return findings, len(lines)


def class_matches(cls, want):
    """--class filter. Exact, or a family: "0" means 0a-0d."""
    return cls == want or (cls.startswith(want) and cls[len(want):].isalpha())


def echoes(file_prose):
    """The same sentence in more than one file.

    Sessions don't read sibling documents, so the same explanation gets
    regenerated wherever it seems locally useful — near-verbatim. Only
    meaningful corpus-wide; no single file shows the problem.
    """
    buckets = defaultdict(list)
    for path, prose in file_prose.items():
        for n, line in prose:
            key = re.sub(r"\s+", " ",
                         re.sub(r"[^a-z0-9 ]", "", line.lower())).strip()
            if len(key) < 60:
                continue
            buckets[key].append((path, n))
    out = []
    for key, sites in sorted(buckets.items()):
        if len({p for p, _ in sites}) > 1:
            out.append({"text": key[:100], "count": len(sites),
                        "sites": [f"{p}:{n}" for p, n in sites]})
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


def collect(paths, excludes=(), self_excludes=(), include_records=False):
    """Gather markdown, minus --exclude substrings and (by default) records."""
    files = []
    for p in paths:
        if os.path.isdir(p):
            for root, dirs, names in os.walk(p):
                dirs[:] = sorted(d for d in dirs if d not in
                                 {"node_modules", ".git", "dist", "build",
                                  ".next", "vendor", ".venv", "target"})
                for name in sorted(names):
                    if name.endswith((".md", ".markdown")):
                        files.append(os.path.join(root, name))
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
    ap.add_argument("--class", dest="cls", help="filter, e.g. 0 or 0a or 2")
    ap.add_argument("--fix", action="store_true", help="apply the safe rewrites")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true", help="exit 1 if anything found")
    ap.add_argument("--exclude", action="append", default=[],
                    metavar="SUBSTR", help="skip paths containing SUBSTR (repeatable)")
    ap.add_argument("--include-records", action="store_true",
                    help="also scan dated plans/specs/ADRs (excluded by default)")
    args = ap.parse_args()

    # Exclude this skill's own prose, by resolved path rather than by name:
    # a document about slop quotes slop on nearly every line, and scanning it
    # in place buries real findings under its own vocabulary.
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    self_excludes = [
        os.path.join(here, "SKILL.md"),
        os.path.join(here, "README.md"),
        os.path.join(here, "references") + os.sep,
        os.path.join(here, "scripts") + os.sep,
    ]
    if os.path.basename(os.path.dirname(here)) == "skills":
        self_excludes.append(os.path.join(os.path.dirname(os.path.dirname(here)),
                                          "README.md"))
    files, records = collect(args.paths, args.exclude, self_excludes,
                             args.include_records)
    if not files:
        note = f" ({len(records)} record docs skipped)" if records else ""
        print("no standing markdown found" + note, file=sys.stderr)
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
              + ".")
        print("Everything else needs a decision about what the surviving fact "
              "is — run without --fix to see it.")
        return 0

    findings, file_stats, file_prose = [], [], {}
    for path in files:
        found, n_lines = scan_file(path)
        findings += found
        file_stats.append({"file": path, "lines": n_lines,
                           "findings": len(found)})
        with open(path, encoding="utf-8") as fh:
            file_prose[path] = list(prose_lines(fh.read().splitlines()))
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

    echo = echoes(file_prose)
    fixable = count_safe_fixes(files)

    if args.json:
        json.dump({"findings": findings, "echoes": echo,
                   "files": file_stats, "clean_files": clean,
                   "safe_fixes": fixable,
                   "skipped_records": records}, sys.stdout, indent=2)
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
            print(f"\n=== echoes — {len(echo)} sentence(s) in more than one file ===")
            for e in echo:
                print(f"  {e['text']!r} ×{e['count']}: {', '.join(e['sites'])}")
        else:
            print("\nechoes: none — no sentence repeats across files")
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
        print("Candidates, not verdicts — class 0 first, it has the objective "
              "tests; and check the load-bearing claims against the code, "
              "which no scan can do.")

    return 1 if (args.check and findings) else 0


if __name__ == "__main__":
    sys.exit(main())
