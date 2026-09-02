#!/usr/bin/env python3
"""Tests for ledger.py.

Three things here are load-bearing and silent when they break: the split
between identity and skeleton hashing (get it wrong and either every typo
demands re-verification, or a changed number does not), the honesty rules in
`record` (get them wrong and the ledger launders assumption as evidence), and
the TOML fallback parser (get it wrong and the tool works on 3.11 and lies on
3.8).

Run with: python3 test_ledger.py
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ledger  # noqa: E402
import scan  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

DOC = """# Relay

The `--batch-size` flag defaults to 500 events per flush.

The drain never blocks longer than the configured timeout.

Relay requires Python 3.9 or newer and runs on Linux.
"""

CODE = """BATCH_SIZE = 500
TIMEOUT_SECONDS = 10
"""


def tree(doc=DOC, code=CODE, extra=None):
    """A repo-shaped temp dir: docs/relay.md plus src/relay.py."""
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "docs"))
    os.makedirs(os.path.join(d, "src"))
    with open(os.path.join(d, "docs", "relay.md"), "w", encoding="utf-8") as fh:
        fh.write(doc)
    with open(os.path.join(d, "src", "relay.py"), "w", encoding="utf-8") as fh:
        fh.write(code)
    for rel, body in (extra or {}).items():
        path = os.path.join(d, rel)
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
    return d


def entries_of(root):
    entries, _, _ = ledger.extract([os.path.join(root, "docs")], root=root)
    return entries


def only(entries, needle):
    return next(e for e in entries.values() if needle in e["text"])


class TestToml(unittest.TestCase):
    def roundtrip(self, doc, fallback):
        text = ledger.dumps(doc)
        real = ledger._tomllib
        try:
            if fallback:
                ledger._tomllib = None
            return ledger.loads(text)
        finally:
            ledger._tomllib = real

    def sample(self):
        return {"schema": 1, "corpus": ["docs", "README.md"],
                "generated_at": "2026-09-01T00:00:00Z",
                "claim": [
                    {"id": "aaa", "file": "docs/a.md", "line": 3,
                     "text": 'He said "500" \\ maybe', "verdict": "supported",
                     "exempt": True, "searched": ["journal", "wal"],
                     "evidence": [{"file": "src/a.py", "lines": "3-4",
                                   "quote": "X = 500", "hash": "abcd1234"}]},
                    {"id": "bbb", "file": "docs/a.md", "line": 9,
                     "text": "second", "verdict": "unverified"}]}

    def test_roundtrip_with_stdlib_reader(self):
        if ledger._tomllib is None:
            self.skipTest("no tomllib on this interpreter")
        got = self.roundtrip(self.sample(), fallback=False)
        self.assertEqual(len(got["claim"]), 2)
        self.assertEqual(got["claim"][0]["text"], 'He said "500" \\ maybe')
        self.assertEqual(got["claim"][0]["evidence"][0]["lines"], "3-4")

    def test_fallback_parser_agrees_with_stdlib(self):
        doc = self.sample()
        mine = self.roundtrip(doc, fallback=True)
        self.assertEqual(len(mine["claim"]), 2)
        self.assertEqual(mine["claim"][0]["text"], 'He said "500" \\ maybe')
        self.assertEqual(mine["claim"][0]["searched"], ["journal", "wal"])
        self.assertTrue(mine["claim"][0]["exempt"])
        self.assertEqual(mine["claim"][0]["evidence"][0]["hash"], "abcd1234")
        if ledger._tomllib is not None:
            self.assertEqual(mine, self.roundtrip(doc, fallback=False))

    def test_entries_are_sorted_so_branches_conflict_less(self):
        doc = self.sample()
        doc["claim"].reverse()
        text = ledger.dumps(doc)
        self.assertLess(text.index('id = "aaa"'), text.index('id = "bbb"'))

    def test_fallback_rejects_what_it_cannot_parse(self):
        real = ledger._tomllib
        ledger._tomllib = None
        try:
            with self.assertRaises(ValueError):
                ledger.loads("[table]\nkey = 1\n")
            with self.assertRaises(ValueError):
                ledger.loads("key = 2026-01-01T00:00:00Z\n")
        finally:
            ledger._tomllib = real


class TestIdentityAndSkeleton(unittest.TestCase):
    def test_identifiers_are_the_names_a_claim_is_about(self):
        self.assertEqual(
            ledger.identifiers("The `--batch-size` flag writes var/x.json"),
            ["--batch-size", "var/x.json"])

    def test_rewording_moves_neither_hash(self):
        a = "The `--batch-size` flag defaults to 500 events per flush."
        b = "The `--batch-size` flag defaults to 500 events on each flush."
        self.assertEqual(ledger.identity_key(a), ledger.identity_key(b))
        self.assertEqual(ledger.skeleton(a), ledger.skeleton(b))

    def test_changing_a_value_moves_the_skeleton_but_not_identity(self):
        a = "The `--batch-size` flag defaults to 500 events per flush."
        b = "The `--batch-size` flag defaults to 100 events per flush."
        self.assertEqual(ledger.identity_key(a), ledger.identity_key(b))
        self.assertNotEqual(ledger.skeleton(a), ledger.skeleton(b))

    def test_changing_a_unit_moves_the_skeleton(self):
        a = "The timeout is 30 seconds."
        b = "The timeout is 30 ms."
        self.assertNotEqual(ledger.skeleton(a), ledger.skeleton(b))

    def test_softening_a_guarantee_moves_the_skeleton(self):
        a = "The drain never blocks longer than the timeout."
        b = "The drain rarely blocks longer than the timeout."
        self.assertNotEqual(ledger.skeleton(a), ledger.skeleton(b))

    def test_a_softened_guarantee_is_still_extracted(self):
        # Otherwise "never" -> "rarely" drops the claim out of the corpus and
        # its verdict becomes an orphan instead of demanding re-verification.
        root = tree(doc="# R\n\nThe drain rarely blocks longer than the "
                        "configured timeout.\n")
        self.assertEqual(len(entries_of(root)), 1)

    def test_an_id_survives_rewrapping(self):
        wrapped = tree(doc="# R\n\nThe `--batch-size` flag defaults\n"
                           "to 500 events per flush.\n")
        flowed = tree(doc="# R\n\nThe `--batch-size` flag defaults to 500 "
                          "events per flush.\n")
        self.assertEqual(list(entries_of(wrapped)), list(entries_of(flowed)))

    def test_two_claims_about_different_things_get_different_ids(self):
        entries = entries_of(tree())
        self.assertEqual(len(entries), len(set(entries)))


class TestEvidenceHash(unittest.TestCase):
    def test_hash_tracks_the_cited_lines_only(self):
        root = tree()
        before = ledger.evidence_hash("src/relay.py", "1", root)
        with open(os.path.join(root, "src", "relay.py"), "w",
                  encoding="utf-8") as fh:
            fh.write("BATCH_SIZE = 500\nTIMEOUT_SECONDS = 30\n")
        self.assertEqual(before, ledger.evidence_hash("src/relay.py", "1", root))
        self.assertNotEqual(before,
                            ledger.evidence_hash("src/relay.py", "2", root))

    def test_whitespace_only_changes_do_not_move_it(self):
        root = tree()
        before = ledger.evidence_hash("src/relay.py", "1", root)
        with open(os.path.join(root, "src", "relay.py"), "w",
                  encoding="utf-8") as fh:
            fh.write("BATCH_SIZE   =  500\nTIMEOUT_SECONDS = 10\n")
        self.assertEqual(before, ledger.evidence_hash("src/relay.py", "1", root))

    def test_missing_file_or_range_is_a_move(self):
        root = tree()
        self.assertIsNone(ledger.evidence_hash("src/gone.py", "1", root))
        self.assertIsNone(ledger.evidence_hash("src/relay.py", "99", root))


class TestCompare(unittest.TestCase):
    def ledger_for(self, root, verdict="unverified", evidence=None):
        entries = entries_of(root)
        claims = []
        for entry in entries.values():
            claim = dict(entry, verdict=verdict, exempt=(verdict == "unverified"))
            if evidence and "batch-size" in entry["text"]:
                claim["verdict"] = "supported"
                claim["exempt"] = False
                claim["evidence"] = evidence
            claims.append(claim)
        return {"schema": 1, "corpus": ["docs"], "claim": claims}, entries

    def test_a_new_claim_is_new(self):
        root = tree()
        led, _ = self.ledger_for(root)
        with open(os.path.join(root, "docs", "relay.md"), "a",
                  encoding="utf-8") as fh:
            fh.write("\nThe report is written to `var/parked.json` nightly.\n")
        state = ledger.compare(entries_of(root), led, root)
        self.assertEqual(len(state["new"]), 1)
        self.assertIn("parked.json", state["new"][0]["text"])

    def test_an_edited_claim_is_stale_and_keeps_its_id(self):
        root = tree()
        led, before = self.ledger_for(root)
        target = only(before, "batch-size")
        path = os.path.join(root, "docs", "relay.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read().replace("500", "100")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        state = ledger.compare(entries_of(root), led, root)
        self.assertEqual([e["id"] for e, _, _ in state["stale"]], [target["id"]])
        self.assertIn("claim edited", state["stale"][0][2])
        self.assertEqual(state["new"], [])

    def test_changed_evidence_is_stale(self):
        root = tree()
        ev = [{"file": "src/relay.py", "lines": "1", "quote": "BATCH_SIZE = 500",
               "hash": ledger.evidence_hash("src/relay.py", "1", root)}]
        led, _ = self.ledger_for(root, evidence=ev)
        path = os.path.join(root, "src", "relay.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("BATCH_SIZE = 100\nTIMEOUT_SECONDS = 10\n")
        state = ledger.compare(entries_of(root), led, root)
        reasons = [r for _, _, rs in state["stale"] for r in rs]
        self.assertTrue(any("evidence changed" in r for r in reasons), reasons)

    def test_evidence_that_only_moved_says_so(self):
        root = tree()
        ev = [{"file": "src/relay.py", "lines": "1", "quote": "BATCH_SIZE = 500",
               "hash": ledger.evidence_hash("src/relay.py", "1", root)}]
        led, _ = self.ledger_for(root, evidence=ev)
        path = os.path.join(root, "src", "relay.py")
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# inserted\n" + body)
        state = ledger.compare(entries_of(root), led, root)
        reasons = [r for _, _, rs in state["stale"] for r in rs]
        self.assertTrue(any("quote unchanged" in r for r in reasons), reasons)

    def test_a_deleted_claim_is_an_orphan(self):
        root = tree()
        led, _ = self.ledger_for(root)
        path = os.path.join(root, "docs", "relay.md")
        with open(path, encoding="utf-8") as fh:
            text = "".join(l for l in fh if "batch-size" not in l)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        state = ledger.compare(entries_of(root), led, root)
        self.assertEqual(len(state["orphan"]), 1)

    def test_an_untouched_claim_stays_live(self):
        root = tree()
        led, _ = self.ledger_for(root)
        state = ledger.compare(entries_of(root), led, root)
        self.assertEqual(state["new"], [])
        self.assertEqual(state["stale"], [])
        self.assertEqual(len(state["live"]), len(entries_of(root)))


class TestHonestyRules(unittest.TestCase):
    """`record` refuses verdicts nobody established. Without these the ledger
    is a place to write down assumptions and call them evidence."""

    def setUp(self):
        self.root = tree()

    def good_evidence(self):
        return [{"file": "src/relay.py", "lines": "1", "quote": "BATCH_SIZE = 500"}]

    def test_supported_needs_evidence(self):
        with self.assertRaises(ledger.RecordError) as cm:
            ledger.validate_verdict({"verdict": "supported"}, self.root)
        self.assertIn("unsupported", str(cm.exception))

    def test_refuted_needs_a_correction(self):
        with self.assertRaises(ledger.RecordError):
            ledger.validate_verdict({"verdict": "refuted",
                                     "evidence": self.good_evidence()},
                                    self.root)

    def test_unsupported_needs_the_search_recorded(self):
        with self.assertRaises(ledger.RecordError):
            ledger.validate_verdict({"verdict": "unsupported"}, self.root)

    def test_a_quote_that_is_not_there_is_rejected(self):
        bad = [{"file": "src/relay.py", "lines": "1",
                "quote": "JOURNAL_ENABLED = True"}]
        with self.assertRaises(ledger.RecordError) as cm:
            ledger.validate_verdict({"verdict": "supported", "evidence": bad},
                                    self.root)
        self.assertIn("does not say", str(cm.exception))

    def test_a_range_outside_the_file_is_rejected(self):
        bad = [{"file": "src/relay.py", "lines": "80-90", "quote": "x"}]
        with self.assertRaises(ledger.RecordError):
            ledger.validate_verdict({"verdict": "supported", "evidence": bad},
                                    self.root)

    def test_an_unknown_verdict_is_rejected(self):
        with self.assertRaises(ledger.RecordError):
            ledger.validate_verdict({"verdict": "probably-fine"}, self.root)

    def test_a_real_citation_is_accepted_and_hashed(self):
        out = ledger.validate_verdict({"verdict": "supported",
                                       "evidence": self.good_evidence()},
                                      self.root)
        self.assertEqual(out[0]["hash"],
                         ledger.evidence_hash("src/relay.py", "1", self.root))

    def test_whitespace_in_a_quote_is_forgiven(self):
        ev = [{"file": "src/relay.py", "lines": "1", "quote": "BATCH_SIZE  =  500"}]
        ledger.validate_verdict({"verdict": "supported", "evidence": ev},
                                self.root)


class TestWiring(unittest.TestCase):
    def test_agents_md_wins_when_both_exist(self):
        root = tree(extra={"AGENTS.md": "# A\n", "CLAUDE.md": "# C\n"})
        self.assertEqual(ledger.wiring_target(root), "AGENTS.md")

    def test_claude_md_is_used_when_it_is_the_only_one(self):
        root = tree(extra={"CLAUDE.md": "# C\n"})
        self.assertEqual(ledger.wiring_target(root), "CLAUDE.md")

    def test_an_existing_reference_is_found_anywhere_agents_read(self):
        root = tree(extra={"CONTRIBUTING.md": "run lie-detector check\n"})
        self.assertEqual(ledger.wiring_reference(root)[0], "CONTRIBUTING.md")

    def test_the_ledger_filename_counts_as_a_reference(self):
        root = tree(extra={"AGENTS.md": "see docs/.claims.toml\n"})
        self.assertIsNotNone(ledger.wiring_reference(root))

    def test_no_reference_when_nothing_mentions_it(self):
        root = tree(extra={"AGENTS.md": "# A\n"})
        self.assertIsNone(ledger.wiring_reference(root))

    def test_applying_twice_appends_once(self):
        root = tree(extra={"AGENTS.md": "# A\n"})
        block = ledger.block_for("docs/.claims.toml", ["docs"])
        ledger.apply_wiring(root, "AGENTS.md", block)
        ledger.apply_wiring(root, "AGENTS.md", block)
        with open(os.path.join(root, "AGENTS.md"), encoding="utf-8") as fh:
            body = fh.read()
        self.assertEqual(body.count("## Documentation claims"), 1)

    def test_nothing_is_created_without_an_explicit_ask(self):
        root = tree()
        block = ledger.block_for("docs/.claims.toml", ["docs"])
        ledger.apply_wiring(root, None, block, create=False)
        self.assertFalse(os.path.exists(os.path.join(root, "AGENTS.md")))
        ledger.apply_wiring(root, None, block, create=True)
        self.assertTrue(os.path.exists(os.path.join(root, "AGENTS.md")))


class TestSidecarsAndAnchors(unittest.TestCase):
    """The two things a claim needs: somewhere to live, and a stable name."""

    def run_cli(self, root, *args):
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "ledger.py"), "--root", root]
            + list(args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return proc.returncode, proc.stdout.decode("utf-8", "replace")

    def test_init_writes_one_sidecar_per_document(self):
        root = tree(extra={"docs/ops.md": "# Ops\n\nThe drain never blocks "
                                          "longer than the timeout.\n"})
        code, out = self.run_cli(root, "init", os.path.join(root, "docs"))
        self.assertEqual(code, 0, out)
        for name in ("relay.claims.toml", "ops.claims.toml"):
            self.assertTrue(os.path.isfile(os.path.join(root, "docs", name)),
                            name + " missing\n" + out)

    def test_a_sidecar_names_the_document_it_covers(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"))
        led = ledger.load_ledger(os.path.join(root, "docs",
                                              "relay.claims.toml"))
        self.assertEqual(led["doc"], "docs/relay.md")

    def test_check_finds_its_work_without_being_told_the_corpus(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"))
        code, out = self.run_cli(root, "check")
        self.assertEqual(code, 0, out)
        self.assertIn("across 1 document(s)", out)

    def test_the_marker_is_the_id(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"), "--anchor")
        led = ledger.load_ledger(os.path.join(root, "docs",
                                              "relay.claims.toml"))
        with open(os.path.join(root, "docs", "relay.md"),
                  encoding="utf-8") as fh:
            body = fh.read()
        for claim in led["claim"]:
            self.assertIn("[^c%s]" % claim["id"], body)

    def test_anchoring_is_idempotent(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"), "--anchor")
        with open(os.path.join(root, "docs", "relay.md"), encoding="utf-8") as fh:
            once = fh.read()
        led = ledger.load_ledger(os.path.join(root, "docs", "relay.claims.toml"))
        claims = [dict(c, file="docs/relay.md") for c in led["claim"]]
        ledger.sync_anchors("docs/relay.md", claims, root)
        with open(os.path.join(root, "docs", "relay.md"), encoding="utf-8") as fh:
            self.assertEqual(once, fh.read())

    def test_an_anchored_claim_survives_a_rewrite(self):
        # The whole point of the anchor: without it, a reworded sentence is an
        # orphan plus a new claim, and the verdict is lost.
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"), "--anchor")
        path = os.path.join(root, "docs", "relay.md")
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        body = body.replace(
            "The `--batch-size` flag defaults to 500 events per flush.",
            "Each flush carries 500 events unless `--batch-size` says otherwise.")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        entries, _, _ = ledger.extract([os.path.join(root, "docs")], root=root)
        led = ledger.load_ledger(os.path.join(root, "docs", "relay.claims.toml"))
        state = ledger.compare(entries, led, root)
        self.assertEqual(state["orphan"], [])
        self.assertEqual(state["new"], [])

    def test_a_table_row_is_anchored_in_its_last_cell(self):
        root = tree(doc="# R\n\n| Option | Default |\n| --- | --- |\n"
                        "| `--timeout` | 30 seconds |\n")
        self.run_cli(root, "init", os.path.join(root, "docs"), "--anchor")
        with open(os.path.join(root, "docs", "relay.md"),
                  encoding="utf-8") as fh:
            row = [l for l in fh if "--timeout" in l][0]
        self.assertRegex(row.strip(), r"\[\^c[0-9a-f]{8}\] \|$")

    def test_the_anchor_is_not_part_of_the_claim(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"), "--anchor")
        entries, _, _ = ledger.extract([os.path.join(root, "docs")], root=root)
        for entry in entries.values():
            self.assertNotIn("[^c", entry["text"])

    def test_an_anchor_in_a_code_span_is_an_example_not_an_id(self):
        # The docs explaining the scheme quote a marker; reading it as an id
        # hands two unrelated sentences the same claim.
        root = tree(doc="# R\n\nA claim carries its id as `[^cdeadbeef]` at "
                        "the end of the sentence, and defaults to 500 rows.\n")
        entries, _, _ = ledger.extract([os.path.join(root, "docs")], root=root)
        self.assertNotIn("deadbeef", entries)
        self.assertFalse(list(entries.values())[0]["anchored"])

    def test_a_quoted_anchor_stays_in_the_claim_text(self):
        # Stripping it would make the stored sentence differ from the one in
        # the document, and the claim would stale on every anchoring pass.
        root = tree(doc="# R\n\nA claim carries `[^cdeadbeef]` and defaults "
                        "to 500 rows per flush.\n")
        entry = list(entries_of(root).values())[0]
        self.assertIn("`[^cdeadbeef]`", entry["text"])

    def test_a_context_file_gets_markers_but_no_footnote_block(self):
        # CLAUDE.md and its siblings are loaded into every session an agent
        # starts, so a definitions block there is paid for forever. The
        # markers stay — they are what carries identity — and the provenance
        # lives in the sidecar.
        root = tree(extra={"CLAUDE.md": "# Notes\n\nThe timeout is 30 "
                                        "seconds by default here.\n"})
        self.run_cli(root, "init", os.path.join(root, "CLAUDE.md"), "--anchor")
        with open(os.path.join(root, "CLAUDE.md"), encoding="utf-8") as fh:
            body = fh.read()
        # The comment form, because a footnote reference with no definition
        # renders as literal "[^c4e23315]" — which is what made an
        # unfootnoted document look vandalised.
        self.assertRegex(body, r"<!--c[0-9a-f]{8}-->")
        self.assertNotIn("[^c", body)
        self.assertNotIn(ledger.ANCHOR_HEADER, body)

    def test_an_ordinary_document_keeps_its_footnotes(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"), "--anchor")
        with open(os.path.join(root, "docs", "relay.md"),
                  encoding="utf-8") as fh:
            body = fh.read()
        self.assertIn(ledger.ANCHOR_HEADER, body)
        self.assertIn("\n[^c", body)

    def test_a_comment_marker_still_ends_its_sentence(self):
        # "…vocabulary.<!--c4e23315-->" has to remain a sentence boundary, or
        # two claims merge into one and both go stale.
        root = tree(extra={"CLAUDE.md": "# N\n\nThe timeout is 30 seconds by "
                                        "default. The port is 9102 on every "
                                        "node here.\n"})
        self.run_cli(root, "init", os.path.join(root, "CLAUDE.md"), "--anchor")
        entries, _, _ = ledger.extract([os.path.join(root, "CLAUDE.md")],
                                       root=root)
        self.assertEqual(len(entries), 2, [e["text"] for e in entries.values()])

    def test_a_document_can_change_marker_form(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"), "--anchor")
        led = ledger.load_ledger(os.path.join(root, "docs",
                                              "relay.claims.toml"))
        claims = [dict(c, file="docs/relay.md") for c in led["claim"]]
        ledger.sync_anchors("docs/relay.md", claims, root, footnotes=False)
        with open(os.path.join(root, "docs", "relay.md"),
                  encoding="utf-8") as fh:
            body = fh.read()
        self.assertNotIn("[^c", body)          # no stale footnote markers
        self.assertRegex(body, r"<!--c[0-9a-f]{8}-->")

    def test_footnotes_are_rewritten_not_accumulated(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"), "--anchor")
        led = ledger.load_ledger(os.path.join(root, "docs", "relay.claims.toml"))
        claims = [dict(c, file="docs/relay.md") for c in led["claim"]]
        for _ in range(3):
            ledger.sync_anchors("docs/relay.md", claims, root)
        with open(os.path.join(root, "docs", "relay.md"),
                  encoding="utf-8") as fh:
            body = fh.read()
        self.assertEqual(body.count(ledger.ANCHOR_HEADER), 1)


class TestRelocate(unittest.TestCase):
    def run_cli(self, root, *args):
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "ledger.py"), "--root", root]
            + list(args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return proc.returncode, proc.stdout.decode("utf-8", "replace")

    def verified(self, root):
        self.run_cli(root, "init", os.path.join(root, "docs"))
        led = ledger.load_ledger(os.path.join(root, "docs",
                                              "relay.claims.toml"))
        cid = next(c["id"] for c in led["claim"] if "batch-size" in c["text"])
        path = os.path.join(root, "v.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([{"id": cid, "verdict": "supported",
                        "evidence": [{"file": "src/relay.py", "lines": "1",
                                      "quote": "BATCH_SIZE = 500"}]}], fh)
        self.run_cli(root, "record", path, "--by", "test")
        return cid

    def test_a_citation_that_only_moved_is_re_addressed(self):
        # Inserting a line above the evidence moves every citation below it
        # and changes nothing about the evidence itself.
        root = tree()
        self.verified(root)
        path = os.path.join(root, "src", "relay.py")
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("# a new comment\n" + body)
        self.assertEqual(self.run_cli(root, "check")[0], 1)
        code, out = self.run_cli(root, "check", "--relocate")
        self.assertEqual(code, 0, out)
        self.assertIn("Re-addressed 1", out)
        self.assertEqual(self.run_cli(root, "check")[0], 0)

    def test_evidence_that_really_changed_is_not_re_addressed(self):
        root = tree()
        self.verified(root)
        path = os.path.join(root, "src", "relay.py")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("BATCH_SIZE = 100\nTIMEOUT_SECONDS = 10\n")
        code, out = self.run_cli(root, "check", "--relocate")
        self.assertEqual(code, 1, out)
        self.assertIn("needs a person", out)


class TestCommandLine(unittest.TestCase):
    """Exit codes are what a CI gate wires itself to, both directions."""

    def run_cli(self, root, *args):
        proc = subprocess.run(
            [sys.executable, os.path.join(HERE, "ledger.py"), "--root", root]
            + list(args), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return proc.returncode, proc.stdout.decode("utf-8", "replace")

    @staticmethod
    def sidecar(root):
        return os.path.join(root, "docs", "relay.claims.toml")

    def test_init_then_check_is_green_and_re_init_refuses(self):
        root = tree()
        code, out = self.run_cli(root, "init", os.path.join(root, "docs"))
        self.assertEqual(code, 0, out)
        self.assertIn("claims extracted", out)
        self.assertEqual(self.run_cli(root, "check")[0], 0)
        self.assertEqual(self.run_cli(root, "init",
                                      os.path.join(root, "docs"))[0], 2)

    def test_a_new_claim_fails_the_gate(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"))
        with open(os.path.join(root, "docs", "relay.md"), "a",
                  encoding="utf-8") as fh:
            fh.write("\nThe `--retries` flag defaults to 5 attempts.\n")
        code, out = self.run_cli(root, "check")
        self.assertEqual(code, 1, out)
        self.assertIn("new claim", out)

    def test_check_without_a_ledger_exits_2(self):
        self.assertEqual(self.run_cli(tree(), "check")[0], 2)

    def test_init_reports_missing_wiring_and_wire_adds_it_later(self):
        root = tree(extra={"AGENTS.md": "# A\n"})
        code, out = self.run_cli(root, "init", os.path.join(root, "docs"))
        self.assertIn("does not mention the claim ledger", out)
        code, out = self.run_cli(root, "init", "--wire")
        self.assertEqual(code, 0, out)
        with open(os.path.join(root, "AGENTS.md"), encoding="utf-8") as fh:
            self.assertIn("lie-detector", fh.read())

    def test_record_enrols_a_claim_the_ledger_has_not_seen(self):
        # Fixing a false sentence writes a new one, and verifying it in the
        # same session is the point. Rejecting it because the ledger predates
        # it made the commonest flow impossible.
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"))
        with open(os.path.join(root, "docs", "relay.md"), "a",
                  encoding="utf-8") as fh:
            fh.write("\nThe `--retries` flag defaults to 5 attempts.\n")
        entries, _, _ = ledger.extract([os.path.join(root, "docs")], root=root)
        cid = next(e["id"] for e in entries.values() if "--retries" in e["text"])
        path = os.path.join(root, "v.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([{"id": cid, "verdict": "unsupported",
                        "searched": ["retries", "src/**"]}], fh)
        code, out = self.run_cli(root, "record", path, "--by", "test")
        self.assertEqual(code, 0, out)
        self.assertIn("enrolled on the way", out)
        self.assertEqual(self.run_cli(root, "check")[0], 0)

    def test_re_verifying_a_staled_claim_clears_it(self):
        # Recording against the old wording left the entry stale forever: the
        # ledger kept diffing against a sentence nobody had written since.
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"))
        led = ledger.load_ledger(self.sidecar(root))
        cid = next(c["id"] for c in led["claim"] if "batch-size" in c["text"])
        path = os.path.join(root, "docs", "relay.md")
        with open(path, encoding="utf-8") as fh:
            text = fh.read().replace("500 events", "100 events")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        self.assertEqual(self.run_cli(root, "check")[0], 1)
        verdicts = os.path.join(root, "v.json")
        with open(verdicts, "w", encoding="utf-8") as fh:
            json.dump([{"id": cid, "verdict": "unsupported",
                        "searched": ["BATCH_SIZE", "src/**"]}], fh)
        self.run_cli(root, "record", verdicts, "--by", "test")
        code, out = self.run_cli(root, "check")
        self.assertEqual(code, 0, out)

    def test_record_still_rejects_an_id_that_is_nowhere(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"))
        path = os.path.join(root, "v.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([{"id": "deadbeefcafe", "verdict": "unverifiable"}], fh)
        code, out = self.run_cli(root, "record", path)
        self.assertEqual(code, 1, out)

    def test_the_stored_text_keeps_identifiers_intact(self):
        # scan's matching passes strip emphasis markers; the ledger must not,
        # or it records `identitykey()` where the document says
        # `identity_key()` and nobody can check one against the other.
        root = tree(doc="# R\n\nThe `parse_row()` helper reads `my_file.md` "
                        "and *always* returns 3 rows.\n")
        entry = list(entries_of(root).values())[0]
        self.assertIn("`parse_row()`", entry["text"])
        self.assertIn("`my_file.md`", entry["text"])
        self.assertIn("*always*", entry["text"])

    def test_config_files_are_not_treated_as_definitions(self):
        # A workflow that runs scan.py is not where scan.py is defined, and
        # letting it count made CI config the first candidate for half a
        # corpus.
        root = tree(extra={"ci.yml": "steps:\n  - run: python3 src/relay.py\n"})
        cands = ledger.find_candidates(entries_of(root), root)
        for hits in cands.values():
            for hit in hits:
                self.assertNotEqual(hit["file"], "ci.yml",
                                    "config mention offered as evidence")

    def test_check_backlog_lists_unverified_claims(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"))
        code, out = self.run_cli(root, "check", "--backlog", "--limit", "2")
        self.assertEqual(code, 0, out)
        self.assertIn("batched by the evidence", out)

    def test_check_inherits_the_corpus_and_options_from_the_ledger(self):
        # A gate that has to be re-told how to walk the corpus is one that
        # eventually gets mis-invoked in CI.
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"), "--code")
        led = ledger.load_ledger(self.sidecar(root))
        self.assertTrue(led.get("code"))
        self.assertEqual(self.run_cli(root, "check")[0], 0)

    def test_record_rejects_and_writes_nothing(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"))
        led = ledger.load_ledger(self.sidecar(root))
        cid = led["claim"][0]["id"]
        path = os.path.join(root, "bad.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([{"id": cid, "verdict": "supported"}], fh)
        code, out = self.run_cli(root, "record", path)
        self.assertEqual(code, 1, out)
        after = ledger.load_ledger(self.sidecar(root))
        self.assertEqual(after["claim"][0]["verdict"], "unverified")

    def test_record_then_show_carries_the_provenance(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"))
        led = ledger.load_ledger(self.sidecar(root))
        cid = next(c["id"] for c in led["claim"] if "batch-size" in c["text"])
        path = os.path.join(root, "ok.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump([{"id": cid, "verdict": "supported",
                        "evidence": [{"file": "src/relay.py", "lines": "1",
                                      "quote": "BATCH_SIZE = 500"}]}], fh)
        code, out = self.run_cli(root, "record", path, "--by", "test")
        self.assertEqual(code, 0, out)
        code, out = self.run_cli(root, "show", cid)
        self.assertIn("supported", out)
        self.assertIn("unchanged since", out)
        self.assertNotIn("grandfathered", out)

    def test_check_prunes_orphans_only_when_asked(self):
        root = tree()
        self.run_cli(root, "init", os.path.join(root, "docs"))
        path = os.path.join(root, "docs", "relay.md")
        with open(path, encoding="utf-8") as fh:
            text = "".join(l for l in fh if "batch-size" not in l)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        code, out = self.run_cli(root, "check", "--prune", "--dry-run")
        self.assertIn("would prune 1", out)
        before = len(ledger.load_ledger(
            self.sidecar(root))["claim"])
        self.run_cli(root, "check", "--prune")
        after = len(ledger.load_ledger(
            self.sidecar(root))["claim"])
        self.assertEqual(after, before - 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
