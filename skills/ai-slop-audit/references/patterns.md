# The taxonomy

Classes 0a-0d are generation residue: the process leaking into the artifact,
each with an objective test. Classes 1-6 are the register: what generated
prose sounds and looks like when nobody pushes back. Echoes are the
corpus-level pattern with no per-file test at all, and redundancy with code
has no scanner test at all — it needs the implementation open.

Load this file when a finding is ambiguous or you want the rewrite patterns;
`SKILL.md`'s summaries are enough for clear cases.

## Class 0a — conversation residue

A chat turn committed as documentation. The author is present in the text,
performing the edit or addressing the requester.

```diff
- I've updated the install script to handle Windows paths as well.
+ The install script handles Windows paths.
```

```diff
- Hope this helps! Let me know if you have any questions.
```

**Test:** a standing document has no author performing edits inside it, and
no addressee. If the sentence only makes sense as one side of a
conversation, it is residue.

**Rewrite:** convert the performed action to the present-tense fact
("I've added X" → the doc simply describes X, where X is described), delete
the pleasantry outright. Pure pleasantry lines are in `--fix`'s safe set.

## Class 0b — handoff residue

The completion report pasted where a description belongs: "Summary of
changes", "The following changes were made", "All 47 tests pass",
"Implementation is now complete". True of a session on a Tuesday; committed
as if it described the system.

```diff
- ## Summary of Changes
-
- The following changes were made in this update: the scheduler was
- refactored to use a worker pool.
+ The scheduler dispatches through a worker pool.
```

**Test:** does the paragraph describe the system, or a work session on the
system? Sessions are events; if the note is worth keeping, it is a record
(a dated file under `plans/`), not a section of a standing doc.

**Rewrite:** extract the one live fact ("worker pool"), state it where the
component is described, delete the report. "All N tests pass" is a claim
about a moment — CI knows; the doc should not.

## Class 0c — template residue

Scaffolding generated and never filled: `[Describe the clustering setup
here.]`, a "## Troubleshooting" heading over nothing, lorem ipsum.

**Test:** would the reader mistake it for content? A bracketed stub and an
empty section both promise something that does not exist.

**Rewrite:** delete the stub; delete the empty section *and list it in the
report as a possible gap* — someone thought the section should exist, and
the author may want the content rather than the removal.

## Class 0d — phantom references

A relative link whose target does not exist on disk. The one fabrication
tell with a fully objective test, so the scanner checks the filesystem and
these arrive as facts, not candidates.

**Rewrite:** if the target should exist, that is a gap to report. If the
link was hallucinated, delete it and check the surrounding claims — a
sentence confident enough to cite a nonexistent file is confident enough to
be wrong about other things. Treat a 0d hit as a flag on its whole
paragraph for step-4 verification.

## Class 1 — importance inflation

Unearned adjectives: comprehensive, robust, seamless, effortless,
blazing-fast, production-ready, battle-tested, enterprise-grade,
state-of-the-art. Generated prose rates everything it describes, and rates
it high.

```diff
- Relay leverages a robust caching layer for lightning-fast responses.
+ Relay caches hot partitions; p99 read latency is 3 ms.
```

**Rewrite:** deflate to the measurable fact, or to nothing. There is no
rewrite in which the adjective survives. If nobody has the number, the
honest sentence is the one without the claim — and "the docs claim
performance nobody measured" belongs in the report.

## Class 2 — lexical tells

The vocabulary: delve, leverage, utilize, facilitate, streamline, empower,
unlock, harness, foster, myriad, plethora, "a testament to", "in today's
fast-paced", "deep dive", "plays a crucial role". Each has a plain word
underneath ("use", "help", "let") or nothing underneath at all.

**Rewrite:** substitute the plain word; delete the ones with nothing
underneath. This class is Fold almost every time — the sentence usually
carries a real claim.

## Class 3 — essay scaffolding

The five-paragraph essay's skeleton on a document that is not an essay:
"In this guide, we'll walk through…", "Whether you're a beginner or an
expert…", "In conclusion…", a "## Conclusion" or "## Key Takeaways" heading
on a reference page. Standing docs are consulted, not read through; nothing
concludes.

**Rewrite:** delete openers and closers; a Conclusion section's one live
fact, if any, moves to where its subject is described. "In conclusion,"-
family sentence openers are in `--fix`'s safe set.

## Class 4 — symmetric filler

"Not only X but also Y", "isn't just X, it's Y", "the best of both worlds",
"takes X to the next level". Symmetry standing in for content.

**Rewrite:** state X and Y as two plain claims, or pick the one that is
true. If neither survives alone, neither survived the symmetry either.

## Class 5 — decoration

Emoji on headings and bullet leads: 🚀 ✨ 🎯 ⚡. Chosen by no one, meaning
nothing, and — because every generated doc gets them — signalling nothing.
Heading emoji are in `--fix`'s safe set.

## Class 6 — structure as filler

The wall of `**Term**: description` bullets where a table or a paragraph
belongs. The scanner flags runs of five or more. Parallel rows → table;
an argument → paragraph; the report should say which.

## Echoes

The same sentence in more than one file. Sessions don't read sibling docs,
so each one regenerates the shared explanation — near-verbatim, because
they share a register. **Rewrite:** one home (the file that owns the
topic), links everywhere else.

## Redundancy with code — no scanner class

No pattern catches this one: whether a sentence restates the code is
answerable only with the code open, which is why it is a step (5) rather
than a class. It is included here because it produces more Cuts on a
generated corpus than any register class.

```diff
- The `parse_row` function takes a row and returns a dict. It loops over the
- configured columns and coerces each value to the column's declared type.
+ Row values are coerced to the column's declared type; a column absent from
+ the header is an error, because a silently missing column looked identical
+ to a null in the 2026-02 incident.
```

```diff
- # increment the retry counter
  retries += 1
```

```diff
- # sleep 400ms
+ # 400ms: the upstream rate limiter's window is 350ms and its clock drifts
  time.sleep(0.4)
```

**Test:** if someone edited the implementation and left this line alone,
would the line become wrong? Then the implementation owns it — Cut, citing
the symbol. A line that survives that edit is explaining a constraint, a
rejected alternative, a cross-file invariant or an external reason, and it
is the part of the document worth having.

**Rewrite:** delete the narration; where a *why* is buried in it, keep only
that clause. A whole file narrating one module is a report finding, not a
line-by-line edit — delete it and link the source.

**Records:** a merged plan is the same redundancy at file scale, and it
misleads on top of it — a plan reads as intent, so a finished one gets taken
for outstanding work. Delete merged plans; keep specs, which state what the
system must do and outlive the implementation. Move any *why* that exists
only in the plan into the standing docs first.

# The false-positive families

Most discards come from a handful of collisions. Check these before
spending a glance per candidate.

1. **The domain owns the word.** Robust standard errors (statistics),
   comprehensive income (accounting), leverage ratio (finance), test
   harness, unlocking a mutex or a bootloader, elevated privileges. The
   scanner suppresses the ones it can recognise; expect more in any
   specialised corpus, and treat a term the codebase itself uses as the
   domain talking.

2. **Chosen decoration.** Gitmoji, emoji section markers by declared
   convention, a ✅/❌ support matrix. Convention beats class 5 — that is
   what step 1 exists to establish.

3. **The genre's contract.** A quickstart saying "let's get started" is the
   genre's voice. The scanner path-suppresses obvious tutorial filenames;
   apply the same judgement to files it can't recognise by name.

4. **Authorial first person.** "I built this because nothing handled soft
   wraps" is a person explaining a choice — voice, not residue. Class 0a is
   only the *performed edit* and the *addressed reader*.

5. **An earned adjective.** "Comprehensive" next to the coverage number,
   "fast" next to the benchmark. If the measurable fact is already present,
   the adjective is summary, not inflation — Keep, or Fold the two into one
   sentence.

6. **Documentation for readers without the source.** A published API
   reference, an SDK's parameter table, a CLI's flag list: restating the
   code is what these are for. Step 5 applies to prose shadowing code its
   own readers can open.

7. **Verification provenance.** A claim anchor (`[^c4e23315]`), its footnote
   definition, an evidence citation. Its subject is whether a sentence is
   true, which is content; `metadiscourse-audit` protects it explicitly and
   so does this audit. The scanner skips anchors and their definitions.

8. **Human-written flourish.** People write "not only… but also" too, and
   people wrote "delve" for centuries before models did. A class 2-4 hit in
   a file that is otherwise clean, with git history showing a human author,
   is probably just their style — the audit removes slop, it does not
   enforce plainness on a writer who chose otherwise.
