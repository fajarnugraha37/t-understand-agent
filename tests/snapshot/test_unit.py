from __future__ import annotations

import unittest

from tu_runtime.core.errors import TUnderstandError
from tu_runtime.core.snapshot import parse_target, parse_target_assignments


class SnapshotUnitTests(unittest.TestCase):
    def test_target_parser_supports_all_target_types(self) -> None:
        self.assertEqual({"type": "branch", "ref": "main"}, parse_target("branch:main"))
        self.assertEqual({"type": "tag", "ref": "v1.0.0"}, parse_target("tag:v1.0.0"))
        self.assertEqual({"type": "head", "ref": None}, parse_target("head"))
        self.assertEqual({"type": "index", "ref": None}, parse_target("index"))
        self.assertEqual({"type": "worktree", "ref": None}, parse_target("worktree"))

    def test_commit_target_rejects_revision_expressions(self) -> None:
        with self.assertRaises(TUnderstandError) as raised:
            parse_target("commit:HEAD~1")
        self.assertEqual("SNAP-TARGET-005", raised.exception.code)

    def test_duplicate_target_assignment_is_rejected(self) -> None:
        with self.assertRaises(TUnderstandError) as raised:
            parse_target_assignments(["repo-a=head", "repo-a=worktree"])
        self.assertEqual("SNAP-TARGET-008", raised.exception.code)

    def test_targets_requiring_refs_fail_without_them(self) -> None:
        with self.assertRaises(TUnderstandError) as raised:
            parse_target("branch")
        self.assertEqual("SNAP-TARGET-003", raised.exception.code)

    def test_non_ref_target_rejects_ref(self) -> None:
        with self.assertRaises(TUnderstandError) as raised:
            parse_target("worktree:main")
        self.assertEqual("SNAP-TARGET-004", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
