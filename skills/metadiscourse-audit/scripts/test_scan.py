#!/usr/bin/env python3
"""Tests for scan.py — the regressions that are silent when they happen.

Every case here is a bug that shipped or a false-positive family from a real
corpus. Run with: python3 test_scan.py
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan  # noqa: E402


def scan_text(text, name="doc.md"):
    """Write text to a temp file, scan it, return the findings."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        findings, _ = scan.scan_file(path)
        return findings


def classes_of(findings):
    return {f["class"] for f in findings}


class TestNormalisation(unittest.TestCase):
    def test_emphasis_no_longer_hides_a_changelog(self):
        # The shipped bug: `_Changed in ..._` — the underscore is a word
        # character, so \bChanged never matched and the italicised changelog
        # convention was invisible.
        found = scan_text("_Changed in `ingest/2026-04-b`: the delimiter now "
                          "sniffs the first line._\n")
        self.assertIn("0b", classes_of(found))

    def test_inline_code_is_not_prose(self):
        found = scan_text("Call `previously_seen()` to dedupe.\n")
        self.assertNotIn("0a", classes_of(found))

    def test_bold_does_not_hide_a_match(self):
        found = scan_text("**Previously** the queue was in-process.\n")
        self.assertIn("0a", classes_of(found))


class TestProseLines(unittest.TestCase):
    def test_front_matter_and_fences_and_comments_skipped(self):
        text = ("---\n"
                "description: previously this said something else\n"
                "---\n"
                "Real prose.\n"
                "```\n"
                "previously = 1  # code, not prose\n"
                "```\n"
                "<!-- previously a draft note -->\n")
        found = scan_text(text)
        self.assertEqual(found, [])

    def test_prose_after_front_matter_still_scanned(self):
        text = "---\ntitle: x\n---\nThe parser now merges wrapped headers.\n"
        found = scan_text(text)
        self.assertIn("0b", classes_of(found))


class TestClassFilter(unittest.TestCase):
    def test_family_matches_letters_only(self):
        # "0" must catch 0a-0d and must not catch 0.5; "1" must not catch 10.
        self.assertTrue(scan.class_matches("0a", "0"))
        self.assertTrue(scan.class_matches("0d", "0"))
        self.assertFalse(scan.class_matches("0.5", "0"))
        self.assertTrue(scan.class_matches("0.5", "0.5"))
        self.assertTrue(scan.class_matches("1", "1"))
        self.assertFalse(scan.class_matches("10", "1"))


class TestRecords(unittest.TestCase):
    def test_records_detected(self):
        for p in ("docs/adr/2026-03-11-queue.md", "docs/plans/big.md",
                  "notes/2026-01-02-standup.md", "CHANGELOG.md"):
            self.assertTrue(scan.is_record(p), p)

    def test_standing_docs_are_not_records(self):
        for p in ("docs/api.md", "README.md", "docs/newsletter.md"):
            self.assertFalse(scan.is_record(p), p)


class TestSuppressors(unittest.TestCase):
    def test_third_party_rename_is_biography(self):
        found = scan_text("Acme (formerly Initech, Inc.) is the "
                          "approachable planner.\n")
        self.assertNotIn("0a", classes_of(found))

    def test_conditional_perfect_is_runtime_not_changelog(self):
        found = scan_text("Once the index has been built, queries hit it "
                          "instead of the table.\n")
        self.assertNotIn("0b", classes_of(found))

    def test_bare_perfect_is_a_changelog(self):
        found = scan_text("The quote-escape branch has been added back.\n")
        self.assertIn("0b", classes_of(found))

    def test_condition_does_not_shield_a_changelog_on_the_same_line(self):
        found = scan_text("The quote-escape branch has been added back. Once "
                          "the file has been uploaded, the parser runs.\n")
        self.assertEqual(
            1, sum(1 for f in found if f["label"] == "perfect-tense changelog"))

    def test_most_recent_selects_data(self):
        found = scan_text("The most recently written snapshot wins.\n")
        self.assertNotIn("0b", classes_of(found))

    def test_lets_say_frames_an_example(self):
        found = scan_text("Let's say the file has 100 rows.\n")
        self.assertNotIn("3", classes_of(found))

    def test_lets_take_a_look_walks_the_reader(self):
        found = scan_text("Let's take a look at the config format.\n")
        self.assertIn("3", classes_of(found))

    def test_tutorials_own_their_voice(self):
        found = scan_text("Let's take a look at the config format.\n",
                          name="getting-started.md")
        self.assertNotIn("3", classes_of(found))

    def test_lets_you_is_a_different_word(self):
        found = scan_text("The flag lets you skip validation.\n")
        self.assertNotIn("3", classes_of(found))


class TestWrapAndDedupe(unittest.TestCase):
    def test_phrase_wrapped_across_lines_is_found(self):
        # "the / least defensible" straddles a soft wrap; both baseline eval
        # agents caught this surviving the per-line pass.
        found = scan_text("The backoff table is the\n"
                          "least defensible thing here.\n")
        hits = [f for f in found if f["class"] == "6"]
        self.assertEqual(1, len(hits))
        self.assertEqual(1, hits[0]["line"])

    def test_wrap_join_stops_at_block_boundaries(self):
        found = scan_text("The backoff table is the\n"
                          "- least defensible thing here\n")
        self.assertNotIn("6", classes_of(found))

    def test_one_finding_per_class_per_line(self):
        # Both class-4 patterns match this line; the report should count one.
        found = scan_text("Three things the reader must get right:\n")
        self.assertEqual(1, sum(1 for f in found if f["class"] == "4"))

    def test_wrap_pass_defers_to_per_line_findings(self):
        found = scan_text("and it should be\n"
                          "revisited once real traffic exists.\n")
        self.assertEqual(1, sum(1 for f in found if f["class"] == "0.5"))


class TestNewPatterns(unittest.TestCase):
    def test_corrected_residue(self):
        found = scan_text("The corrected yield is seven usable feeds from nine.\n")
        self.assertIn("0a", classes_of(found))

    def test_currently_is_an_undated_stamp(self):
        found = scan_text("The exporter currently supports CSV only.\n")
        self.assertIn("0c", classes_of(found))

    def test_future_promise(self):
        found = scan_text("Retries are not yet implemented.\n")
        self.assertIn("0d", classes_of(found))

    def test_generic_now_verb(self):
        # "sniffs" was missed by the old explicit verb list.
        found = scan_text("The reader now sniffs the delimiter.\n")
        self.assertIn("0b", classes_of(found))

    def test_temporal_idiom_is_not_recency(self):
        found = scan_text("For now defaults are conservative.\n")
        self.assertNotIn("0b", classes_of(found))

    def test_salience_adverb(self):
        found = scan_text("More importantly, the lock must be held.\n")
        self.assertIn("6", classes_of(found))


class TestCodeComments(unittest.TestCase):
    def test_hash_comment_is_scanned(self):
        found = scan_text("RETRIES = 3  # previously the default was five\n",
                          name="mod.py")
        self.assertIn("0a", classes_of(found))

    def test_hash_inside_a_string_is_not_a_comment(self):
        # The whitespace-before-marker rule: the "#" sits against a quote.
        found = scan_text('MARKER = "#previously a draft note"\n',
                          name="mod.py")
        self.assertEqual(found, [])

    def test_slash_comment_is_scanned(self):
        found = scan_text("const t = 10; // the timeout was previously 30s\n",
                          name="mod.ts")
        self.assertIn("0a", classes_of(found))

    def test_url_is_not_a_comment(self):
        # The "//" in a URL sits against a colon.
        found = scan_text('const u = "https://x.test/previously";\n',
                          name="mod.ts")
        self.assertEqual(found, [])

    def test_block_comment_spans_lines_with_real_linenos(self):
        found = scan_text("/*\n"
                          " * The parser now sniffs the delimiter.\n"
                          " */\n"
                          "parse();\n", name="mod.c")
        hits = [f for f in found if f["class"] == "0b"]
        self.assertEqual(1, len(hits))
        self.assertEqual(2, hits[0]["line"])

    def test_todo_is_a_tracker_item_not_a_finding(self):
        found = scan_text("# TODO: retries are not yet implemented\n",
                          name="mod.py")
        self.assertEqual(found, [])

    def test_the_same_promise_without_a_marker_is_a_finding(self):
        found = scan_text("# retries are not yet implemented\n",
                          name="mod.py")
        self.assertIn("0d", classes_of(found))

    def test_linter_directives_are_not_prose(self):
        found = scan_text("alert(1) // eslint-disable-line -- previously "
                          "required\n", name="mod.js")
        self.assertEqual(found, [])

    def test_comment_block_wraps_like_a_paragraph(self):
        found = scan_text("# The backoff table is the\n"
                          "# least defensible thing here.\n", name="mod.py")
        hits = [f for f in found if f["class"] == "6"]
        self.assertEqual(1, len(hits))
        self.assertEqual(1, hits[0]["line"])

    def test_line_count_is_comment_lines_only(self):
        # Density for a source file divides by scanned prose, not by code.
        text = ("import os\n"
                "# one comment line\n"
                "x = 1\n"
                "y = 2\n")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mod.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            _, n_lines = scan.scan_file(path)
        self.assertEqual(1, n_lines)


class TestCollectCode(unittest.TestCase):
    def test_directory_walk_takes_code_only_with_the_flag(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ("doc.md", "mod.py"):
                with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
                    fh.write("x\n")
            files, _, code_seen = scan.collect([d])
            self.assertEqual([os.path.join(d, "doc.md")], files)
            self.assertEqual(1, code_seen)
            files, _, code_seen = scan.collect([d], include_code=True)
            self.assertEqual({"doc.md", "mod.py"},
                             {os.path.basename(f) for f in files})
            self.assertEqual(0, code_seen)

    def test_a_named_code_file_needs_no_flag(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mod.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("x = 1\n")
            files, _, _ = scan.collect([path])
            self.assertEqual([path], files)

    def test_fix_never_counts_code_files(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "mod.py")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("# It is worth noting that the cache is an LRU.\n")
            self.assertEqual(scan.count_safe_fixes([path]), 0)


class TestSafeFixes(unittest.TestCase):
    def check(self, before, after):
        new, changes = scan.apply_safe_fixes(before)
        self.assertEqual(new, after)
        self.assertTrue(changes)

    def test_worth_noting_wrapper(self):
        self.check("It is worth noting that the cache is an LRU.",
                   "The cache is an LRU.")

    def test_count_survives_wrapper_removal(self):
        self.check("Two priors worth defending explicitly:", "Two priors:")

    def test_count_alone_is_never_touched(self):
        new, changes = scan.apply_safe_fixes("Two independent defences:")
        self.assertEqual(new, "Two independent defences:")
        self.assertEqual(changes, [])

    def test_then_confirmed(self):
        self.check("Then confirmed against a real file.",
                   "Confirmed against a real file.")

    def test_please_note(self):
        self.check("Please note that the API is rate limited.",
                   "The API is rate limited.")

    def test_mid_line_deletion_recapitalises_its_sentence(self):
        self.check("The cache is an LRU. Please note that the API is limited.",
                   "The cache is an LRU. The API is limited.")

    def test_mid_clause_deletion_stays_lowercase(self):
        self.check("Retries back off, and it is worth noting that the cap is 60s.",
                   "Retries back off, and the cap is 60s.")

    def test_count_safe_fixes_skips_fences_and_counts_lines(self):
        # Two fixable lines, one of them carrying two phrases (still one
        # line), and the same phrase inside a code fence, which must not
        # count — --fix would not touch it either.
        text = ("Please note that the cache is an LRU.\n"
                "\n"
                "Needless to say, it is worth noting that retries back off.\n"
                "\n"
                "```\n"
                "Please note that this is example output.\n"
                "```\n")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "doc.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.assertEqual(scan.count_safe_fixes([path]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
