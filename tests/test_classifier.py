"""Aceitacao Etapa 4: metadados sinteticos em memoria, sem fixtures em disco."""

from copy import deepcopy
from itertools import permutations
import unittest
from unittest.mock import patch

from src.core.classifier import ClassificationConfig, ClassificationRule, ClassificationSession
from src.core.models import FileItem, ScanReport


def inventory(*items, errors=()):
    return ScanReport("not-a-filesystem-root", len(items), 0, list(items), errors=list(errors))


def item(path, modified=100):
    return FileItem(path, 0, modified)


def session(*rules, **kwargs):
    return ClassificationSession(ClassificationConfig(tuple(rules), **kwargs))


class ClassificationTests(unittest.TestCase):
    def test_default_categories_and_unknown(self):
        report = ClassificationSession().analyze(inventory(
            item("fiction/NOTE.PDF"), item("images/photo.JpG"), item("code/main.py"),
            item("track.wav"), item("movie.mp4"), item("archive.zip"), item("unknown.exe")))
        self.assertEqual(report.status, "complete")
        self.assertEqual(report.category_counts, dict.fromkeys(
            ["archives", "audio", "documents", "images", "source", "video"], 1))
        self.assertEqual(next(s for s in report.suggestions if s.path == "unknown.exe").status,
                         "unmatched")

    def test_all_conditions_required_and_date_bounds(self):
        rule = ClassificationRule("dated_report", "reports", extensions=(".TXT",),
                                  name_pattern="report-*.txt", modified_start=100, modified_end=200)
        report = session(rule).analyze(inventory(item("dir/REPORT-one.TXT", 100),
            item("report-two.txt", 199.9), item("report-end.txt", 200),
            item("report-old.txt", 99), item("other.txt", 150), item("report-one.pdf", 150)))
        self.assertEqual(report.category_counts, {"reports": 2})
        matched = [s for s in report.suggestions if s.status == "classified"]
        self.assertEqual(matched[0].matches[0].conditions, ("extension", "name", "modified_at"))

    def test_name_uses_basename_and_unicode_casefold(self):
        rule = ClassificationRule("names", "named", name_pattern="strasse-*.txt")
        report = session(rule).analyze(inventory(item("other/Straße-one.txt"),
                                                item("strasse-dir/other.txt")))
        self.assertEqual(report.category_counts, {"named": 1})

    def test_priority_and_all_matches_are_auditable(self):
        low = ClassificationRule("generic", "documents", extensions=(".txt",))
        high = ClassificationRule("special", "reports", 2, name_pattern="report-*")
        suggestion = session(low, high).analyze(inventory(item("report-a.txt"))).suggestions[0]
        self.assertEqual(suggestion.category, "reports")
        self.assertEqual([m.rule_id for m in suggestion.matches], ["special", "generic"])

    def test_conflict_does_not_choose_category_by_rule_id(self):
        rules = [ClassificationRule("a", "first", extensions=(".txt",)),
                 ClassificationRule("z", "second", name_pattern="*.txt")]
        for order in permutations(rules):
            suggestion = session(*order).analyze(inventory(item("a.txt"))).suggestions[0]
            self.assertEqual(suggestion.status, "ambiguous")
            self.assertIsNone(suggestion.category)
            self.assertEqual(suggestion.reason_code, "priority_conflict")

    def test_same_category_tie_is_classified(self):
        report = session(ClassificationRule("a", "same", name_pattern="*"),
                         ClassificationRule("b", "same", extensions=(".txt",))).analyze(
                             inventory(item("a.txt")))
        self.assertEqual(report.category_counts, {"same": 1})

    def test_rule_and_item_permutations_are_deterministic(self):
        rules = [ClassificationRule("text", "docs", extensions=(".txt",)),
                 ClassificationRule("pdf", "docs", extensions=(".pdf",))]
        items = [item("z.txt"), item("Á.pdf"), item("A.dat")]
        expected = session(*rules).analyze(inventory(*items))
        for order in permutations(rules):
            for files in permutations(items):
                self.assertEqual(session(*order).analyze(inventory(*files)), expected)

    def test_duplicates_are_all_refused_and_not_silently_deduplicated(self):
        items = [item("dir/A.txt"), item("DIR/a.txt"), item("good.pdf")]
        report = ClassificationSession().analyze(inventory(*items))
        self.assertEqual(report.status, "partial")
        self.assertEqual(len(report.suggestions), 3)
        self.assertEqual(report.category_counts, {"documents": 1})
        self.assertEqual([s.status for s in report.suggestions].count("invalid"), 2)
        self.assertEqual(report.errors[0].count, 2)
        for files in permutations(items):
            self.assertEqual(ClassificationSession().analyze(inventory(*files)), report)

    def test_large_duplicate_inventory_keeps_each_record(self):
        items = [item(f"pair-{i}.txt") for i in range(2500) for _ in range(2)]
        report = ClassificationSession().analyze(inventory(*items))
        self.assertEqual(len(report.errors), 2500)
        self.assertEqual(len(report.suggestions), 5000)
        self.assertEqual(report.category_counts, {})

    def test_duplicate_with_invalid_metadata_refuses_valid_entry(self):
        for invalid in [FileItem("A.TXT", -1, 100), item("A.TXT", float("nan")),
                        item("A.TXT", float("inf")), item("A.TXT", True)]:
            for entries in permutations([item("a.txt"), invalid]):
                with self.subTest(entries=entries):
                    report = ClassificationSession().analyze(inventory(*entries))
                    self.assertEqual(report.status, "partial")
                    self.assertEqual(report.total_items, 2)
                    self.assertEqual(report.category_counts, {})
                    self.assertEqual(len(report.suggestions), 1)
                    self.assertEqual(report.suggestions[0].status, "invalid")
                    self.assertEqual(report.suggestions[0].reason_code, "duplicate_path")
                    self.assertEqual([e.code for e in report.errors],
                                     ["invalid_metadata", "duplicate_path"])
                    self.assertEqual(report.errors[-1].count, 2)
                    self.assertEqual(report.errors[-1].path, "A.TXT")

    def test_hostile_paths_are_sanitized_without_echo(self):
        for path in ["C:/private-sensitive.txt", "../secret.txt", "\\\\host\\share\\file.txt",
                     "file.txt:private", "CON.txt", "trailing .txt/../x", "", None]:
            with self.subTest(path=path):
                report = ClassificationSession().analyze(inventory(item(path)))
                self.assertEqual(report.status, "partial")
                self.assertEqual(report.errors[0].code, "invalid_path")
                self.assertEqual(report.suggestions, ())
                self.assertNotIn("private", repr(report))
                self.assertNotIn("secret", repr(report))

    def test_invalid_metadata_and_items_preserve_valid_results(self):
        for bad in [FileItem("bad.txt", -1, 100), FileItem("bad.txt", True, 100),
                    item("bad.txt", float("nan")), item("bad.txt", float("inf")),
                    item("bad.txt", True), item("bad.txt", "date"), object()]:
            report = ClassificationSession().analyze(inventory(bad, item("good.txt")))
            self.assertEqual(report.status, "partial")
            self.assertEqual(report.category_counts, {"documents": 1})
            self.assertEqual(report.errors[0].item_index, 0)

    def test_inventory_errors_count_only_and_partial_scope(self):
        report = ClassificationSession().analyze(inventory(item("good.txt"),
                                           errors=["PRIVATE_SENTINEL C:/secret/runtime"]))
        self.assertEqual(report.status, "partial")
        self.assertEqual(report.scope, "provided_inventory")
        self.assertEqual(report.inventory_error_count, 1)
        self.assertNotIn("PRIVATE_SENTINEL", repr(report))
        self.assertEqual(report.category_counts, {"documents": 1})

    def test_item_limit_returns_no_suggestions(self):
        report = session(max_items=1).analyze(inventory(item("one.txt"), item("two.txt")))
        self.assertEqual(report.status, "limit_exceeded")
        self.assertEqual(report.total_items, 2)
        self.assertEqual(report.suggestions, ())

    def test_empty_inventory_and_empty_rules(self):
        self.assertEqual(ClassificationSession().analyze(inventory()).status, "complete")
        self.assertEqual(session().analyze(inventory(item("x.txt"))).suggestions[0].status,
                         "unmatched")

    def test_invalid_inventory_fails_closed(self):
        for value in [None, {}, [], inventory()]:
            if isinstance(value, ScanReport):
                value.items = iter([item("x.txt")])
            self.assertEqual(ClassificationSession().analyze(value).status, "invalid_inventory")
        malformed = inventory(item("x.txt"))
        malformed.errors = "sensitive"
        self.assertEqual(ClassificationSession().analyze(malformed).status, "invalid_inventory")

    def test_classification_does_not_mutate_metadata_hash_or_category(self):
        original = inventory(FileItem("x.txt", 3, 100, "untrusted-hash", "old-category"))
        before = deepcopy(original)
        report = ClassificationSession().analyze(original)
        self.assertEqual(original, before)
        self.assertEqual(report.category_counts, {"documents": 1})
        self.assertNotIn("untrusted-hash", repr(report))

    def test_no_filesystem_scanner_hash_or_plan_calls(self):
        original = inventory(item("does-not-exist.txt"))
        with patch("builtins.open", side_effect=AssertionError("I/O")), \
             patch("os.stat", side_effect=AssertionError("stat")), \
             patch("os.scandir", side_effect=AssertionError("scan")), \
             patch("src.core.scanner.DirectoryScanner.scan", side_effect=AssertionError("scanner")), \
             patch("src.core.hasher.HashSession.analyze",
                   side_effect=AssertionError("hash")), \
             patch("src.core.models.ExecutionPlan", side_effect=AssertionError("plan")):
            self.assertEqual(ClassificationSession().analyze(original).category_counts,
                             {"documents": 1})

    def test_invalid_rules_are_rejected_with_generic_codes(self):
        invalid = [{}, {"extensions": [".txt"]}, {"extensions": ("../x",)},
                   {"extensions": (".tar.gz",)}, {"name_pattern": "../private"},
                   {"name_pattern": ""}, {"modified_start": float("nan")},
                   {"modified_start": True}, {"modified_start": 2, "modified_end": 1},
                   {"priority": True, "extensions": (".txt",)}]
        for fields in invalid:
            with self.subTest(fields=fields), self.assertRaises(ValueError) as raised:
                ClassificationRule("valid", "valid", **fields)
            self.assertNotIn("private", str(raised.exception))
        for field in ["rule_id", "category"]:
            with self.assertRaises(ValueError):
                ClassificationRule(**{"rule_id": "valid", "category": "valid",
                                      "extensions": (".txt",), field: "../private"})

    def test_configuration_validation_and_extension_normalization(self):
        rule = ClassificationRule("a", "docs", extensions=(".TXT", ".txt", ".pdf"))
        self.assertEqual(rule.extensions, (".pdf", ".txt"))
        for kwargs in [{"rules": [rule]}, {"rules": (rule, rule)}, {"rules": (object(),)},
                       {"max_items": 0}, {"max_items": True}, {"max_items": 50_001}]:
            with self.assertRaises(ValueError):
                ClassificationConfig(**kwargs)
        with self.assertRaises(ValueError):
            ClassificationSession({})


if __name__ == "__main__":
    unittest.main()
