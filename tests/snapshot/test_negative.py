from __future__ import annotations

import os
import unittest
from pathlib import Path

from tu_runtime.core.errors import TUnderstandError
from tests.snapshot.common import SnapshotFixture, git


class SnapshotNegativeTests(unittest.TestCase):
    def test_snapshot_ids_are_immutable(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            fx.snapshots.create_snapshot("SNAP_ONE")
            with self.assertRaises(TUnderstandError) as raised:
                fx.snapshots.create_snapshot("SNAP_ONE")
            self.assertEqual("SNAP-ID-002", raised.exception.code)
        finally:
            fx.close()

    def test_unknown_repository_target_is_rejected(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            with self.assertRaises(TUnderstandError) as raised:
                fx.snapshots.create_snapshot("SNAP_ONE", {"unknown": {"type": "head", "ref": None}})
            self.assertEqual("SNAP-TARGET-009", raised.exception.code)
        finally:
            fx.close()

    def test_missing_branch_is_rejected_without_partial_snapshot(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            with self.assertRaises(TUnderstandError) as raised:
                fx.snapshots.create_snapshot("SNAP_BAD", {"repo-a": {"type": "branch", "ref": "missing"}})
            self.assertEqual("SNAP-REF-001", raised.exception.code)
            self.assertFalse((fx.context / "snapshots" / "SNAP_BAD").exists())
        finally:
            fx.close()

    def test_untracked_symlink_is_rejected(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            (repo / "target.txt").write_text("target\n", encoding="utf-8")
            os.symlink("target.txt", repo / "link.txt")
            with self.assertRaises(TUnderstandError) as raised:
                fx.snapshots.create_snapshot("SNAP_BAD", {"repo-a": {"type": "worktree", "ref": None}})
            self.assertEqual("SNAP-SYMLINK-001", raised.exception.code)
        finally:
            fx.close()

    def test_protected_untracked_file_is_rejected(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            (repo / ".env.local").write_text("SECRET=x\n", encoding="utf-8")
            with self.assertRaises(TUnderstandError) as raised:
                fx.snapshots.create_snapshot("SNAP_BAD", {"repo-a": {"type": "worktree", "ref": None}})
            self.assertEqual("SNAP-PROTECTED-001", raised.exception.code)
        finally:
            fx.close()

    def test_protected_tracked_change_is_rejected(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo", files={"config.pem": "public placeholder\n"})
            fx.setup_single(repo)
            (repo / "config.pem").write_text("changed\n", encoding="utf-8")
            git(repo, "add", "config.pem")
            with self.assertRaises(TUnderstandError) as raised:
                fx.snapshots.create_snapshot("SNAP_BAD", {"repo-a": {"type": "index", "ref": None}})
            self.assertEqual("SNAP-PROTECTED-001", raised.exception.code)
        finally:
            fx.close()

    def test_oversized_untracked_file_is_rejected(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            with (repo / "large.bin").open("wb") as handle:
                handle.truncate(10 * 1024 * 1024 + 1)
            with self.assertRaises(TUnderstandError) as raised:
                fx.snapshots.create_snapshot("SNAP_BAD", {"repo-a": {"type": "worktree", "ref": None}})
            self.assertEqual("SNAP-SIZE-003", raised.exception.code)
        finally:
            fx.close()

    def test_unborn_repository_rejects_index_snapshot(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.sources / "unborn"
            repo.mkdir()
            git(repo, "init", "-q")
            fx.application.initialize("application-a", "Application A", "single-repo", "machine-a")
            fx.application.add_repository("repo-a", "Repo", "backend", identity_key="local/repo-a")
            fx.application.bind_repository("repo-a", repo)
            with self.assertRaises(TUnderstandError) as raised:
                fx.snapshots.create_snapshot("SNAP_BAD", {"repo-a": {"type": "index", "ref": None}})
            self.assertEqual("SNAP-REF-005", raised.exception.code)
        finally:
            fx.close()

    def test_tampered_snapshot_fails_integrity_validation(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            fx.snapshots.create_snapshot("SNAP_ONE", {"repo-a": {"type": "worktree", "ref": None}})
            patch = fx.context / "snapshots" / "SNAP_ONE" / "repositories" / "repo-a" / "staged.patch"
            patch.write_bytes(b"tampered")
            report = fx.snapshots.validate_snapshot("SNAP_ONE")
            self.assertEqual("FAIL", report["status"])
            self.assertEqual("SNAP-INTEGRITY-005", report["errors"][0]["code"])
        finally:
            fx.close()

    def test_dirty_submodule_is_rejected_for_worktree_snapshot(self) -> None:
        fx = SnapshotFixture()
        try:
            sub = fx.make_repo("sub")
            parent = fx.make_repo("parent")
            git(parent, "-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub), "vendor/sub")
            git(parent, "commit", "-qm", "add submodule")
            fx.setup_single(parent)
            (parent / "vendor" / "sub" / "README.md").write_text("dirty\n", encoding="utf-8")
            with self.assertRaises(TUnderstandError) as raised:
                fx.snapshots.create_snapshot("SNAP_BAD", {"repo-a": {"type": "worktree", "ref": None}})
            self.assertEqual("SNAP-SUBMODULE-001", raised.exception.code)
        finally:
            fx.close()

    def test_invalid_snapshot_id_is_rejected(self) -> None:
        fx = SnapshotFixture()
        try:
            repo = fx.make_repo("repo")
            fx.setup_single(repo)
            with self.assertRaises(TUnderstandError) as raised:
                fx.snapshots.create_snapshot("bad-id")
            self.assertEqual("SNAP-ID-001", raised.exception.code)
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
