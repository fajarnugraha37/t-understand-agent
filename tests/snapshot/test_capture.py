from __future__ import annotations

import unittest
from pathlib import Path

from tests.snapshot.common import SnapshotFixture, git, source_digest


class SnapshotCaptureTests(unittest.TestCase):
    def test_head_snapshot_ignores_dirty_worktree_and_preserves_source(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            (repo / "README.md").write_text("dirty\n", encoding="utf-8")
            before = source_digest(repo)
            snapshot = fx.snapshots.create_snapshot("SNAP_HEAD", {"repo-a": {"type": "head", "ref": None}}, "foundation")
            descriptor = fx.snapshots.show_snapshot("SNAP_HEAD")
            self.assertEqual("head", descriptor["repositories"][0]["target_type"])
            self.assertEqual(before, source_digest(repo))
            self.assertEqual("PASS", fx.snapshots.validate_snapshot("SNAP_HEAD")["status"])
            self.assertEqual(snapshot["content_digest"], descriptor["content_digest"])
        finally:
            fx.close()

    def test_branch_tag_and_commit_resolve_exact_commits(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            initial = git(repo, "rev-parse", "HEAD")
            git(repo, "branch", "release")
            git(repo, "tag", "v1")
            fx.setup_single(repo)
            branch = fx.snapshots.create_snapshot("SNAP_BRANCH", {"repo-a": {"type": "branch", "ref": "release"}})
            tag = fx.snapshots.create_snapshot("SNAP_TAG", {"repo-a": {"type": "tag", "ref": "v1"}})
            commit = fx.snapshots.create_snapshot("SNAP_COMMIT", {"repo-a": {"type": "commit", "ref": initial[:12]}})
            self.assertEqual(initial, branch["repositories"][0]["resolved_commit"])
            self.assertEqual(initial, tag["repositories"][0]["resolved_commit"])
            self.assertEqual(initial, commit["repositories"][0]["resolved_commit"])
        finally:
            fx.close()

    def test_index_snapshot_includes_only_staged_state(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo", files={"a.txt": "a\n", "b.txt": "b\n"})
            fx.setup_single(repo)
            (repo / "a.txt").write_text("staged\n", encoding="utf-8")
            git(repo, "add", "a.txt")
            (repo / "b.txt").write_text("unstaged\n", encoding="utf-8")
            (repo / "new.txt").write_text("untracked\n", encoding="utf-8")
            fx.snapshots.create_snapshot("SNAP_INDEX", {"repo-a": {"type": "index", "ref": None}}, "review")
            descriptor = __import__("yaml").safe_load((fx.context / "snapshots" / "SNAP_INDEX" / "repositories" / "repo-a.yaml").read_text())
            self.assertEqual(["commit-tree", "staged"], descriptor["capture"]["included"])
            self.assertEqual([], descriptor["capture"]["untracked_files"])
            kinds = [item["kind"] for item in descriptor["capture"]["artifacts"]]
            self.assertEqual(["staged-patch"], kinds)
            (repo / "b.txt").write_text("different unstaged\n", encoding="utf-8")
            (repo / "new.txt").write_text("different untracked\n", encoding="utf-8")
            self.assertEqual("UNCHANGED", fx.snapshots.drift("SNAP_INDEX")["status"])
        finally:
            fx.close()

    def test_worktree_snapshot_captures_patches_and_nonignored_untracked_files(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo", files={"a.txt": "a\n", ".gitignore": "ignored.txt\n"})
            fx.setup_single(repo)
            (repo / "a.txt").write_text("staged\n", encoding="utf-8")
            git(repo, "add", "a.txt")
            (repo / "a.txt").write_text("unstaged after staged\n", encoding="utf-8")
            (repo / "new.txt").write_text("untracked\n", encoding="utf-8")
            (repo / "ignored.txt").write_text("ignored\n", encoding="utf-8")
            fx.snapshots.create_snapshot("SNAP_WORKTREE", {"repo-a": {"type": "worktree", "ref": None}}, "review")
            descriptor = __import__("yaml").safe_load((fx.context / "snapshots" / "SNAP_WORKTREE" / "repositories" / "repo-a.yaml").read_text())
            kinds = {item["kind"] for item in descriptor["capture"]["artifacts"]}
            self.assertEqual({"staged-patch", "unstaged-patch", "status-manifest", "untracked-manifest"}, kinds)
            self.assertEqual(["new.txt"], [item["source_path"] for item in descriptor["capture"]["untracked_files"]])
            self.assertFalse((fx.context / "snapshots" / "SNAP_WORKTREE" / "repositories" / "repo-a" / "untracked" / "ignored.txt").exists())
            self.assertEqual("UNCHANGED", fx.snapshots.drift("SNAP_WORKTREE")["status"])
        finally:
            fx.close()

    def test_worktree_drift_is_detected(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            fx.snapshots.create_snapshot("SNAP_WORKTREE", {"repo-a": {"type": "worktree", "ref": None}})
            (repo / "README.md").write_text("changed\n", encoding="utf-8")
            report = fx.snapshots.drift("SNAP_WORKTREE")
            self.assertEqual("DRIFTED", report["status"])
            self.assertIn("captured_state_changed", report["repositories"][0]["changes"])
        finally:
            fx.close()

    def test_branch_movement_is_detected_as_drift(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            git(repo, "branch", "review-base")
            fx.setup_single(repo)
            fx.snapshots.create_snapshot("SNAP_BRANCH", {"repo-a": {"type": "branch", "ref": "review-base"}})
            git(repo, "checkout", "-q", "review-base")
            (repo / "next.txt").write_text("next\n", encoding="utf-8")
            git(repo, "add", "next.txt")
            git(repo, "commit", "-qm", "next")
            self.assertEqual("DRIFTED", fx.snapshots.drift("SNAP_BRANCH")["status"])
        finally:
            fx.close()

    def test_multi_repository_snapshot_is_sorted_and_portable(self) -> None:
        fx = SnapshotFixture()
        try:
            repo_z = fx.make_repo("repo-z")
            repo_a = fx.make_repo("repo-a")
            fx.setup_multi({"repo-z": repo_z, "repo-a": repo_a})
            snapshot = fx.snapshots.create_snapshot("SNAP_MULTI", purpose="foundation")
            self.assertEqual(["repo-a", "repo-z"], [item["repository_id"] for item in snapshot["repositories"]])
            text = (fx.context / "snapshots" / "SNAP_MULTI" / "application-snapshot.yaml").read_text(encoding="utf-8")
            self.assertNotIn(str(fx.sources), text)
        finally:
            fx.close()

    def test_same_repository_state_has_same_state_digest(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            fx.snapshots.create_snapshot("SNAP_ONE", {"repo-a": {"type": "worktree", "ref": None}})
            fx.snapshots.create_snapshot("SNAP_TWO", {"repo-a": {"type": "worktree", "ref": None}})
            import yaml
            one = yaml.safe_load((fx.context / "snapshots" / "SNAP_ONE" / "repositories" / "repo-a.yaml").read_text())
            two = yaml.safe_load((fx.context / "snapshots" / "SNAP_TWO" / "repositories" / "repo-a.yaml").read_text())
            self.assertEqual(one["capture"]["state_digest"], two["capture"]["state_digest"])
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
