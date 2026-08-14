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


class TestNewPatterns(unittest.TestCase):
    def test_model_disclaimer(self):
        found = scan_text("As an AI language model, note that limits apply.\n")
        self.assertIn("0a", classes_of(found))

    def test_no_breaking_changes_is_pr_speak(self):
        found = scan_text("No breaking changes were introduced.\n")
        self.assertIn("0b", classes_of(found))

    def test_boasts_and_paradigm_shift(self):
        found = scan_text("The engine boasts a paradigm shift in dispatch.\n")
        self.assertIn("2", classes_of(found))

    def test_programming_paradigm_is_a_category(self):
        found = scan_text("Rust supports more than one programming paradigm.\n")
        hits = [f for f in found if f["label"] == "lexical tell"]
        self.assertEqual([], hits)

    def test_backbone_role_inflation(self):
        found = scan_text("The broker serves as the backbone of the system.\n")
        self.assertIn("2", classes_of(found))

    def test_strikes_a_balance(self):
        found = scan_text("It strikes a balance between speed and safety.\n")
        self.assertIn("4", classes_of(found))

    def test_next_generation_sequencing_is_biology(self):
        found = scan_text("Reads come from next-generation sequencing runs.\n")
        self.assertNotIn("1", classes_of(found))


class TestWrapJoin(unittest.TestCase):
    def test_phrase_wrapped_across_lines_is_found(self):
        found = scan_text("Relay is not only a queue\n"
                          "but also a complete platform.\n")
        hits = [f for f in found if f["class"] == "4"]
        self.assertEqual(1, len(hits))
        self.assertEqual(1, hits[0]["line"])

    def test_wrap_join_stops_at_block_boundaries(self):
        found = scan_text("Relay is not only a queue\n"
                          "- but also a complete platform\n")
        self.assertNotIn("4", classes_of(found))

    def test_wrap_pass_defers_to_per_line_findings(self):
        found = scan_text("It should seamlessly\n"
                          "streamline the deploy.\n")
        self.assertEqual(1, sum(1 for f in found if f["class"] == "2"))


class TestCodeComments(unittest.TestCase):
    def test_hash_comment_is_scanned(self):
        found = scan_text("POOL = 8  # I've bumped this to handle the load\n",
                          name="mod.py")
        self.assertIn("0a", classes_of(found))

    def test_slash_comment_is_scanned(self):
        found = scan_text("// leverages a robust worker pool\nrun();\n",
                          name="mod.ts")
        self.assertEqual({"1", "2"}, classes_of(found))

    def test_hash_inside_a_string_is_not_a_comment(self):
        found = scan_text('MARKER = "#leverage the pool"\n', name="mod.py")
        self.assertEqual(found, [])

    def test_url_is_not_a_comment(self):
        found = scan_text('const u = "https://x.test/delve";\n', name="mod.ts")
        self.assertEqual(found, [])

    def test_todo_is_a_tracker_item_not_a_finding(self):
        found = scan_text("# TODO: add retries\n", name="mod.py")
        self.assertEqual(found, [])

    def test_block_comment_spans_lines_with_real_linenos(self):
        found = scan_text("/*\n"
                          " * This delves into the scheduler internals.\n"
                          " */\n"
                          "run();\n", name="mod.c")
        hits = [f for f in found if f["class"] == "2"]
        self.assertEqual(1, len(hits))
        self.assertEqual(2, hits[0]["line"])

    def test_brackets_in_comments_are_code_not_placeholders(self):
        found = scan_text("# maps [Your, Mine] tags to owners\n",
                          name="mod.py")
        self.assertNotIn("0c", classes_of(found))

    def test_line_count_is_comment_lines_only(self):
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
                fh.write("# Hope this helps!\n")
            self.assertEqual(scan.count_safe_fixes([path]), 0)


class TestStructureAdditions(unittest.TestCase):
    def test_numbered_bold_run_is_flagged(self):
        text = "".join(f"1. **Item {i}**: description\n" for i in range(5))
        found = scan_text(text)
        hits = [f for f in found if f["label"] == "bold-term bullet run"]
        self.assertEqual(1, len(hits))

    def test_separator_confetti(self):
        text = ("Intro.\n\n---\n\nMore.\n\n---\n\nEven more.\n\n---\n\nEnd.\n")
        found = scan_text(text)
        hits = [f for f in found if f["label"] == "separator confetti"]
        self.assertEqual(1, len(hits))

    def test_two_rules_are_structure_not_confetti(self):
        text = "Intro.\n\n---\n\nMore.\n\n---\n\nEnd.\n"
        found = scan_text(text)
        self.assertEqual([], [f for f in found
                              if f["label"] == "separator confetti"])

    def test_setext_underline_is_not_a_rule(self):
        text = ("Title\n---\n\nBody.\n\n---\n\nMore.\n\n---\n\nEnd.\n")
        found = scan_text(text)
        self.assertEqual([], [f for f in found
                              if f["label"] == "separator confetti"])


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

    def test_soft_wrap_does_not_hide_a_sentence_echo(self):
        # The same sentence, wrapped differently in each file — sentences are
        # split after the paragraph join, so both keys normalise identically.
        prose = {
            "a.md": [(1, "Relay leverages a robust caching layer for"),
                     (2, "lightning-fast responses.")],
            "b.md": [(1, "Relay leverages a robust caching"),
                     (2, "layer for lightning-fast responses.")],
        }
        found = scan.echoes(prose)
        self.assertEqual(1, len(found))
        self.assertEqual({"a.md:1", "b.md:1"}, set(found[0]["sites"]))

    def test_near_verbatim_paragraph_is_an_echo(self):
        base = ("The compactor walks every segment older than the retention "
                "window and rewrites live entries into a fresh segment "
                "before deleting the old one from the journal directory")
        prose = {
            "a.md": [(1, base + " on each run.")],
            "b.md": [(1, base + " every five minutes.")],
        }
        found = scan.echoes(prose)
        self.assertEqual(1, len(found))
        self.assertIn("similarity", found[0])

    def test_different_paragraphs_do_not_echo(self):
        prose = {
            "a.md": [(1, "The compactor walks every segment older than the "
                         "retention window and rewrites the live entries "
                         "into a fresh segment before deleting the old.")],
            "b.md": [(1, "Producers append to the head partition while "
                         "consumers track their own offsets in a side file "
                         "that survives restarts of the whole broker.")],
        }
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
