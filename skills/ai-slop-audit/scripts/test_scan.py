#!/usr/bin/env python3
"""Tests for scan.py — the regressions that are silent when they happen.

Run with: python3 test_scan.py
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan  # noqa: E402


def scan_text(text, name="doc.md", siblings=()):
    """Write text to a temp dir, scan it, return the findings.

    siblings: extra (name, content) files created beside it, so relative
    links have something to resolve against.
    """
    with tempfile.TemporaryDirectory() as d:
        for other, content in siblings:
            with open(os.path.join(d, other), "w", encoding="utf-8") as fh:
                fh.write(content)
        path = os.path.join(d, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        findings, _ = scan.scan_file(path)
        return findings


def classes_of(findings):
    return {f["class"] for f in findings}


class TestGenerationResidue(unittest.TestCase):
    def test_assistant_self_narration(self):
        found = scan_text("I've updated the install script to handle spaces.\n")
        self.assertIn("0a", classes_of(found))

    def test_chat_pleasantry(self):
        found = scan_text("Hope this helps! Let me know if you have any "
                          "questions.\n")
        self.assertIn("0a", classes_of(found))

    def test_first_person_design_rationale_is_not_narration(self):
        # An author explaining a choice is voice, not residue. Only the
        # edit-verbs fire.
        found = scan_text("I built this because nothing handled soft wraps.\n")
        self.assertNotIn("0a", classes_of(found))

    def test_handoff_summary(self):
        found = scan_text("The following changes were made in this update:\n")
        self.assertIn("0b", classes_of(found))

    def test_test_pass_assertion(self):
        found = scan_text("All 47 tests pass.\n")
        self.assertIn("0b", classes_of(found))

    def test_instruction_to_run_tests_is_not_an_assertion(self):
        found = scan_text("Make sure all tests pass before pushing.\n")
        self.assertNotIn("0b", classes_of(found))

    def test_unfilled_placeholder(self):
        found = scan_text("This project does [describe purpose here].\n")
        self.assertIn("0c", classes_of(found))

    def test_link_text_is_not_a_placeholder(self):
        # "[Your first pipeline](guide.md)" is a link, not a stub.
        found = scan_text("See [Your first pipeline](guide.md).\n",
                          siblings=[("guide.md", "x\n")])
        self.assertNotIn("0c", classes_of(found))


class TestPhantomLinks(unittest.TestCase):
    def test_missing_relative_target_is_flagged(self):
        found = scan_text("See [the config reference](./configuration.md).\n")
        self.assertIn("0d", classes_of(found))

    def test_existing_relative_target_is_fine(self):
        found = scan_text("See [the config reference](./configuration.md).\n",
                          siblings=[("configuration.md", "x\n")])
        self.assertNotIn("0d", classes_of(found))

    def test_anchor_survives_resolution(self):
        found = scan_text("See [setup](./configuration.md#setup).\n",
                          siblings=[("configuration.md", "x\n")])
        self.assertNotIn("0d", classes_of(found))

    def test_urls_anchors_and_absolute_paths_are_skipped(self):
        found = scan_text("See [docs](https://x.test/missing.md), "
                          "[above](#setup) and [root](/etc/none.md).\n")
        self.assertNotIn("0d", classes_of(found))

    def test_link_inside_inline_code_is_an_example(self):
        found = scan_text("Write links as `[text](./target.md)` in markdown.\n")
        self.assertNotIn("0d", classes_of(found))

    def test_underscores_in_targets_survive_normalisation(self):
        # Emphasis-stripping must not corrupt my_file.md into myfile.md.
        found = scan_text("See [notes](./my_file.md).\n",
                          siblings=[("my_file.md", "x\n")])
        self.assertNotIn("0d", classes_of(found))


class TestEmptySections(unittest.TestCase):
    def test_heading_with_no_body_is_flagged(self):
        found = scan_text("# Guide\n\nIntro.\n\n## Prerequisites\n\n"
                          "## Installation\n\nRun the installer.\n")
        hits = [f for f in found if f["label"] == "empty section"]
        self.assertEqual(1, len(hits))
        self.assertEqual(5, hits[0]["line"])

    def test_code_block_counts_as_body(self):
        found = scan_text("## Usage\n\n```\nrun it\n```\n\n## Next\n\nText.\n")
        self.assertEqual([], [f for f in found
                              if f["label"] == "empty section"])

    def test_deeper_heading_counts_as_body(self):
        # A parent section may be a pure container.
        found = scan_text("## API\n\n### get\n\nReturns a row.\n")
        self.assertEqual([], [f for f in found
                              if f["label"] == "empty section"])

    def test_trailing_empty_section_is_flagged(self):
        found = scan_text("Intro.\n\n## Troubleshooting\n")
        hits = [f for f in found if f["label"] == "empty section"]
        self.assertEqual(1, len(hits))


class TestRegister(unittest.TestCase):
    def test_importance_inflation(self):
        found = scan_text("A comprehensive, battle-tested caching layer.\n")
        self.assertIn("1", classes_of(found))

    def test_robust_statistics_is_domain_vocabulary(self):
        found = scan_text("Fit with robust standard errors.\n")
        self.assertNotIn("1", classes_of(found))

    def test_lexical_tell(self):
        found = scan_text("This lets you leverage the scheduler to "
                          "streamline dispatch.\n")
        self.assertIn("2", classes_of(found))

    def test_test_harness_is_a_thing(self):
        found = scan_text("The test harness spawns one worker per case.\n")
        self.assertNotIn("2", classes_of(found))

    def test_leverage_ratio_is_finance(self):
        found = scan_text("The fund's leverage ratio is capped at 2x.\n")
        self.assertNotIn("2", classes_of(found))

    def test_identifier_in_backticks_is_not_prose(self):
        found = scan_text("Call `unlock()` before writing.\n")
        self.assertNotIn("2", classes_of(found))

    def test_role_inflation(self):
        found = scan_text("The scheduler plays a crucial role in delivery.\n")
        self.assertIn("2", classes_of(found))

    def test_essay_scaffold(self):
        found = scan_text("In this guide, we'll walk through the setup.\n")
        self.assertIn("3", classes_of(found))

    def test_quickstarts_own_their_voice(self):
        found = scan_text("Let's get started with the config format.\n",
                          name="quickstart.md")
        self.assertNotIn("3", classes_of(found))

    def test_narrative_heading(self):
        found = scan_text("Intro.\n\n## Conclusion\n\nRelay is a queue.\n")
        self.assertIn("3", classes_of(found))

    def test_conclusion_in_body_prose_is_a_word(self):
        found = scan_text("The benchmark supports no firm conclusion yet.\n")
        self.assertNotIn("3", classes_of(found))

    def test_symmetric_filler(self):
        found = scan_text("Relay is not only a queue but also a platform.\n")
        self.assertIn("4", classes_of(found))


class TestEmoji(unittest.TestCase):
    def test_emoji_heading(self):
        found = scan_text("## 🚀 Getting Started\n\nRun the installer.\n")
        self.assertIn("5", classes_of(found))

    def test_emoji_bullet_lead(self):
        found = scan_text("- ✨ Fast startup\n")
        self.assertIn("5", classes_of(found))

    def test_emoji_in_table_cell_is_content(self):
        # A support matrix's ✅ carries the answer.
        found = scan_text("| Feature | Linux |\n| --- | --- |\n"
                          "| Streams | ✅ |\n")
        self.assertNotIn("5", classes_of(found))

    def test_emoji_mid_prose_is_not_flagged(self):
        found = scan_text("The release shipped and the team celebrated 🎉 "
                          "over lunch.\n")
        self.assertNotIn("5", classes_of(found))

    def test_keyboard_symbols_are_content(self):
        found = scan_text("## Shortcuts ⌘\n\nPress ⌘K to search.\n")
        self.assertNotIn("5", classes_of(found))


class TestBoldBulletRuns(unittest.TestCase):
    def test_run_of_five_is_flagged(self):
        text = "".join(f"- **Item {i}**: description\n" for i in range(5))
        found = scan_text(text)
        hits = [f for f in found if f["label"] == "bold-term bullet run"]
        self.assertEqual(1, len(hits))
        self.assertEqual(1, hits[0]["line"])

    def test_run_of_three_is_fine(self):
        text = "".join(f"- **Item {i}**: description\n" for i in range(3))
        found = scan_text(text)
        self.assertEqual([], [f for f in found
                              if f["label"] == "bold-term bullet run"])


class TestEchoes(unittest.TestCase):
    def test_same_sentence_in_two_files(self):
        line = ("Relay leverages a robust caching layer for "
                "lightning-fast responses.\n")
        with tempfile.TemporaryDirectory() as d:
            prose = {}
            for name in ("a.md", "b.md"):
                path = os.path.join(d, name)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(line)
                prose[path] = [(1, line.rstrip("\n"))]
            found = scan.echoes(prose)
        self.assertEqual(1, len(found))
        self.assertEqual(2, found[0]["count"])

    def test_short_lines_do_not_echo(self):
        with tempfile.TemporaryDirectory() as d:
            prose = {os.path.join(d, n): [(1, "Run the installer.")]
                     for n in ("a.md", "b.md")}
            found = scan.echoes(prose)
        self.assertEqual([], found)


class TestProseLines(unittest.TestCase):
    def test_front_matter_fences_and_comments_skipped(self):
        text = ("---\n"
                "description: a comprehensive guide\n"
                "---\n"
                "Real prose.\n"
                "```\n"
                "All tests pass.\n"
                "```\n"
                "<!-- leverage the scheduler -->\n")
        found = scan_text(text)
        self.assertEqual(found, [])


class TestRecordsAndFilter(unittest.TestCase):
    def test_records_detected(self):
        for p in ("docs/adr/2026-03-11-queue.md", "CHANGELOG.md"):
            self.assertTrue(scan.is_record(p), p)
        self.assertFalse(scan.is_record("docs/api.md"))

    def test_family_matches_letters_only(self):
        self.assertTrue(scan.class_matches("0a", "0"))
        self.assertTrue(scan.class_matches("0d", "0"))
        self.assertFalse(scan.class_matches("1", "0"))
        self.assertTrue(scan.class_matches("2", "2"))


class TestSafeFixes(unittest.TestCase):
    def test_pleasantry_line_is_deleted(self):
        new, changes = scan.fix_line("Hope this helps! 🎉")
        self.assertIsNone(new)
        self.assertTrue(changes)

    def test_pleasantry_mid_paragraph_is_not_touched(self):
        line = "Hope this helps you decide between the two backends."
        new, changes = scan.fix_line(line)
        self.assertEqual(new, line)
        self.assertEqual(changes, [])

    def test_heading_emoji_stripped(self):
        new, changes = scan.fix_line("## 🚀 Getting Started")
        self.assertEqual(new, "## Getting Started")
        self.assertTrue(changes)

    def test_variation_selector_goes_with_its_emoji(self):
        new, _ = scan.fix_line("## ⚠️ Warning")
        self.assertEqual(new, "## Warning")

    def test_opener_stripped_and_recapitalised(self):
        new, changes = scan.fix_line("In summary, the cache is an LRU.")
        self.assertEqual(new, "The cache is an LRU.")
        self.assertTrue(changes)

    def test_mid_clause_opener_stays_lowercase(self):
        new, _ = scan.fix_line("It runs cold, and in summary form only.")
        self.assertEqual(new, "It runs cold, and in summary form only.")

    def test_count_safe_fixes_skips_fences(self):
        text = ("Hope this helps!\n"
                "\n"
                "```\n"
                "## 🚀 example heading\n"
                "```\n"
                "## ✨ Features\n")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "doc.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            self.assertEqual(scan.count_safe_fixes([path]), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
