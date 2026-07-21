from __future__ import annotations

import unittest

from tu_runtime.core.errors import TUnderstandError
from tests.snapshot.common import SnapshotFixture, git


class ReviewTargetTests(unittest.TestCase):
    def test_static_review_target_binds_one_validated_snapshot(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            fx.snapshots.create_snapshot("SNAP_CURRENT")
            target = fx.snapshots.create_review_target("REVIEW_STATIC", "static-audit", "SNAP_CURRENT")
            self.assertEqual("STATIC_AUDIT", target["mode"])
            self.assertIsNone(target["baseline"])
            self.assertEqual("PASS", fx.snapshots.validate_review_target("REVIEW_STATIC")["status"])
        finally:
            fx.close()

    def test_diff_review_target_binds_branch_snapshots(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            initial = git(repo, "rev-parse", "HEAD")
            git(repo, "branch", "base")
            (repo / "feature.txt").write_text("feature\n", encoding="utf-8")
            git(repo, "add", "feature.txt")
            git(repo, "commit", "-qm", "feature")
            git(repo, "branch", "feature")
            fx.setup_single(repo)
            fx.snapshots.create_snapshot("SNAP_BASE", {"repo-a": {"type": "branch", "ref": "base"}})
            fx.snapshots.create_snapshot("SNAP_FEATURE", {"repo-a": {"type": "branch", "ref": "feature"}})
            target = fx.snapshots.create_review_target("REVIEW_DIFF", "diff", "SNAP_FEATURE", "SNAP_BASE")
            self.assertEqual("DIFF", target["mode"])
            self.assertEqual("SNAP_BASE", target["baseline"]["snapshot_id"])
            self.assertNotEqual(initial, target["candidate"]["content_digest"])
        finally:
            fx.close()

    def test_review_target_ids_are_immutable(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            fx.snapshots.create_snapshot("SNAP_ONE")
            fx.snapshots.create_review_target("REVIEW_ONE", "static-audit", "SNAP_ONE")
            with self.assertRaises(TUnderstandError) as raised:
                fx.snapshots.create_review_target("REVIEW_ONE", "static-audit", "SNAP_ONE")
            self.assertEqual("SNAP-REVIEW-005", raised.exception.code)
        finally:
            fx.close()

    def test_diff_requires_baseline_and_static_rejects_baseline(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            fx.snapshots.create_snapshot("SNAP_ONE")
            with self.assertRaises(TUnderstandError) as missing:
                fx.snapshots.create_review_target("REVIEW_DIFF", "diff", "SNAP_ONE")
            self.assertEqual("SNAP-REVIEW-004", missing.exception.code)
            with self.assertRaises(TUnderstandError) as extra:
                fx.snapshots.create_review_target("REVIEW_STATIC", "static-audit", "SNAP_ONE", "SNAP_ONE")
            self.assertEqual("SNAP-REVIEW-003", extra.exception.code)
        finally:
            fx.close()

    def test_review_target_validation_detects_snapshot_tampering(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            fx.snapshots.create_snapshot("SNAP_ONE")
            fx.snapshots.create_review_target("REVIEW_ONE", "static-audit", "SNAP_ONE")
            descriptor = fx.context / "snapshots" / "SNAP_ONE" / "application-snapshot.yaml"
            descriptor.write_text(descriptor.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            report = fx.snapshots.validate_review_target("REVIEW_ONE")
            self.assertEqual("FAIL", report["status"])
            self.assertEqual("SNAP-REVIEW-010", report["errors"][0]["code"])
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
