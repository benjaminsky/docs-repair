#!/usr/bin/env python3
"""Tests for scan.py — the regressions that are silent when they happen.

The sampling tests carry the weight here. A claim scanner that misses a
sentence costs one finding; a lottery that is not reproducible, or that
depends on the order the filesystem handed the files over, invalidates
every audit that cited it.

Run with: python3 test_scan.py
"""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan  # noqa: E402


def claims_of(text, name="doc.md"):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        found, _ = scan.claims_in(path, rel=name)
        return found


def texts(claims):
    return [c["text"] for c in claims]


class TestExtraction(unittest.TestCase):
    def test_a_default_is_a_claim(self):
        found = claims_of("The batch size defaults to 500 events.\n")
        self.assertEqual([c["class"] for c in found], ["A"])

    def test_a_guarantee_is_a_claim(self):
        found = claims_of("No event is ever delivered twice by the writer.\n")
        self.assertEqual([c["class"] for c in found], ["C"])

    def test_an_interface_claim_reads_either_word_order(self):
        subject = claims_of("The `--retries` flag sets how many attempts "
                            "run.\n")
        obj = claims_of("The parked report is written to `var/parked.json` "
                        "by the job.\n")
        self.assertEqual([c["class"] for c in subject], ["B"])
        self.assertEqual([c["class"] for c in obj], ["B"])

    def test_a_question_is_not_a_claim(self):
        self.assertEqual(claims_of("Is the default timeout 30 seconds?\n"), [])

    def test_a_heading_is_not_a_claim(self):
        self.assertEqual(claims_of("## The timeout is 30 seconds\n"), [])

    def test_a_fenced_example_is_not_a_claim(self):
        text = ("```\n"
                "The timeout defaults to 30 seconds.\n"
                "```\n")
        self.assertEqual(claims_of(text), [])

    def test_front_matter_is_not_prose(self):
        text = ("---\n"
                "summary: the timeout defaults to 30 seconds\n"
                "---\n"
                "\n"
                "Nothing here.\n")
        self.assertEqual(claims_of(text), [])

    def test_prose_with_no_assertion_is_not_a_claim(self):
        self.assertEqual(
            claims_of("Relay forwards events to the downstream sinks.\n"), [])

    def test_a_table_row_is_one_claim(self):
        text = ("| Option | Default |\n"
                "| --- | --- |\n"
                "| `--timeout` | 30 seconds |\n")
        found = claims_of(text)
        self.assertEqual(texts(found), ["`--timeout` — 30 seconds"])

    def test_a_soft_wrapped_sentence_is_one_claim_at_its_first_line(self):
        text = ("Relay retries a failed flush 5 times before parking\n"
                "the batch, which the operator then replays.\n")
        found = claims_of(text)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["line"], 1)
        self.assertIn("parking the batch", found[0]["text"])

    def test_two_sentences_on_one_line_are_two_claims(self):
        found = claims_of("The timeout is 30 seconds. The metrics port "
                          "is 9102 on every node.\n")
        self.assertEqual(len(found), 2)

    def test_an_abbreviation_does_not_end_a_sentence(self):
        found = claims_of("The sinks (e.g. S3) each require 3 retries "
                          "before parking.\n")
        self.assertEqual(len(found), 1)

    def test_a_version_number_does_not_end_a_sentence(self):
        found = claims_of("Relay requires Python 3.9 or newer on Linux.\n")
        self.assertEqual(len(found), 1)

    def test_separate_list_items_do_not_join(self):
        text = ("- The timeout is 30 seconds and applies per sink\n"
                "- The batch size defaults to 500 events per flush\n")
        found = claims_of(text)
        self.assertEqual(len(found), 2)


class TestComments(unittest.TestCase):
    def test_a_comment_claim_is_extracted(self):
        found = claims_of("# The upstream limit is 500 rows.\n"
                          "LIMIT = 1000\n", name="relay.py")
        self.assertEqual(len(found), 1)

    def test_a_todo_is_not_a_claim(self):
        self.assertEqual(
            claims_of("# TODO: the limit should be 500 rows.\n",
                      name="relay.py"), [])

    def test_a_directive_is_not_a_claim(self):
        self.assertEqual(
            claims_of("# noqa: E501 the limit is 500 rows\n",
                      name="relay.py"), [])

    def test_code_lines_are_not_claims(self):
        self.assertEqual(claims_of("TIMEOUT = 30  # seconds\n",
                                   name="relay.py"), [])


class TestCollect(unittest.TestCase):
    def _tree(self, d):
        os.makedirs(os.path.join(d, "docs"))
        os.makedirs(os.path.join(d, "docs", "plans"))
        os.makedirs(os.path.join(d, "src"))
        for rel, body in (("docs/a.md", "The timeout is 30 seconds here.\n"),
                          ("docs/plans/big.md", "The timeout will be 30 s.\n"),
                          ("src/relay.py", "# The timeout is 30 seconds.\n")):
            with open(os.path.join(d, rel), "w", encoding="utf-8") as fh:
                fh.write(body)

    def test_records_are_excluded_by_default(self):
        with tempfile.TemporaryDirectory() as d:
            self._tree(d)
            files, records = scan.collect([d])
            self.assertEqual([os.path.basename(f) for f in files], ["a.md"])
            self.assertEqual(len(records), 1)

    def test_records_included_on_request(self):
        with tempfile.TemporaryDirectory() as d:
            self._tree(d)
            files, records = scan.collect([d], include_records=True)
            self.assertEqual(len(files), 2)
            self.assertEqual(records, [])

    def test_code_joins_a_walk_only_with_the_flag(self):
        with tempfile.TemporaryDirectory() as d:
            self._tree(d)
            without, _ = scan.collect([d])
            with_code, _ = scan.collect([d], include_code=True)
            self.assertNotIn("relay.py", " ".join(without))
            self.assertIn("relay.py", " ".join(with_code))

    def test_a_named_code_file_needs_no_flag(self):
        with tempfile.TemporaryDirectory() as d:
            self._tree(d)
            files, _ = scan.collect([os.path.join(d, "src", "relay.py")])
            self.assertEqual(len(files), 1)


def population(n=8):
    return [{"id": "claim%02d" % i, "file": "d.md", "line": i,
             "class": "A", "label": "numeric or default",
             "text": "claim %d" % i} for i in range(n)]


class TestLottery(unittest.TestCase):
    def test_the_same_seed_draws_the_same_claims(self):
        first, _ = scan.draw(population(), "seed-1", 3)
        second, _ = scan.draw(population(), "seed-1", 3)
        self.assertEqual([c["id"] for c in first], [c["id"] for c in second])

    def test_a_different_seed_draws_differently(self):
        first, _ = scan.draw(population(40), "seed-1", 5)
        second, _ = scan.draw(population(40), "seed-2", 5)
        self.assertNotEqual([c["id"] for c in first],
                            [c["id"] for c in second])

    def test_the_draw_ignores_the_order_the_files_arrived_in(self):
        forward = population()
        backward = list(reversed(population()))
        a, _ = scan.draw(forward, "seed-1", 3)
        b, _ = scan.draw(backward, "seed-1", 3)
        self.assertEqual([c["id"] for c in a], [c["id"] for c in b])

    def test_the_queue_continues_the_same_order(self):
        sample, queue = scan.draw(population(), "seed-1", 3)
        full, _ = scan.draw(population(), "seed-1", 8)
        self.assertEqual([c["id"] for c in sample + queue],
                         [c["id"] for c in full])

    def test_asking_for_more_than_exists_draws_everything(self):
        sample, queue = scan.draw(population(4), "seed-1", 99)
        self.assertEqual(len(sample), 4)
        self.assertEqual(queue, [])

    def test_a_claim_id_survives_rewrapping(self):
        wrapped = claims_of("Relay retries a failed flush 5 times\n"
                            "before parking the batch entirely.\n")
        flowed = claims_of("Relay retries a failed flush 5 times before "
                           "parking the batch entirely.\n")
        self.assertEqual(wrapped[0]["id"], flowed[0]["id"])

    def test_a_claim_id_changes_with_the_claim(self):
        before = claims_of("The timeout is 30 seconds by default.\n")
        after = claims_of("The timeout is 10 seconds by default.\n")
        self.assertNotEqual(before[0]["id"], after[0]["id"])

    def test_the_same_sentence_twice_is_two_tickets(self):
        found = claims_of("The timeout is 30 seconds.\n"
                          "\n"
                          "The timeout is 30 seconds.\n")
        self.assertEqual(len(found), 2)
        self.assertNotEqual(found[0]["id"], found[1]["id"])


class TestDigestAndVerify(unittest.TestCase):
    def test_the_digest_moves_when_a_document_does(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.md")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("The timeout is 30 seconds.\n")
            before = scan.corpus_digest([path])
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("The timeout is 10 seconds.\n")
            self.assertNotEqual(before, scan.corpus_digest([path]))

    def test_verify_accepts_its_own_manifest(self):
        manifest = {"seed": "s", "corpus": "abc", "population": 8, "n": 3,
                    "sample": population(3)}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh)
            self.assertEqual(scan.do_verify(path, [], dict(manifest)), 0)

    def test_verify_rejects_a_different_sample(self):
        manifest = {"seed": "s", "corpus": "abc", "population": 8, "n": 3,
                    "sample": population(3)}
        recomputed = dict(manifest, sample=population(4)[1:])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh)
            self.assertEqual(scan.do_verify(path, [], recomputed), 1)

    def test_verify_rejects_a_moved_corpus(self):
        manifest = {"seed": "s", "corpus": "abc", "population": 8, "n": 3,
                    "sample": population(3)}
        recomputed = dict(manifest, corpus="def")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "m.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(manifest, fh)
            self.assertEqual(scan.do_verify(path, [], recomputed), 1)


class TestInterval(unittest.TestCase):
    def test_nothing_found_still_bounds_the_rate(self):
        lo, hi = scan.wilson(0, 20)
        self.assertEqual(round(lo, 3), 0.0)
        self.assertTrue(0.10 < hi < 0.20, hi)

    def test_a_wider_sample_narrows_the_bound(self):
        _, small = scan.wilson(0, 20)
        _, large = scan.wilson(0, 100)
        self.assertLess(large, small)

    def test_every_draw_false_does_not_claim_certainty(self):
        lo, hi = scan.wilson(10, 10)
        self.assertLess(lo, 1.0)
        self.assertEqual(hi, 1.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
