from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from tu_runtime.core.conversation import AgentConversationManager
from tu_runtime.core.documentation import DOCUMENT_CATALOG
from tu_runtime.core.workspace_discovery import resolve_workspace

ROOT = Path(__file__).resolve().parents[2]
PROMPT = (
    "Treat all repositories in this workspace as one application. "
    "Understand them deeply and generate comprehensive, detailed business, domain, "
    "application-flow, integration, repository, and operational documentation."
)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def make_repo(root: Path, name: str, files: dict[str, str]) -> Path:
    repo = root / name
    repo.mkdir(parents=True)
    git(repo, "init", "-q")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "user.name", "Test")
    for relative, content in files.items():
        path = repo / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    git(repo, "add", ".")
    git(repo, "commit", "-qm", "init")
    return repo


class MultiRepoDocumentationTests(unittest.TestCase):
    def _workspace(self, root: Path) -> tuple[Path, Path]:
        frontend = make_repo(
            root,
            "web-app",
            {
                "package.json": json.dumps({"name": "web-app", "dependencies": {"react": "19.0.0"}}),
                "src/submitOrder.ts": (
                    'export async function submitOrder(order: OrderRequest) { '
                    'return fetch("/api/orders", {method:"POST", body: JSON.stringify(order)}); }\n'
                ),
            },
        )
        backend = make_repo(
            root,
            "order-service",
            {
                "pom.xml": "<project><modelVersion>4.0.0</modelVersion><groupId>x</groupId><artifactId>order-service</artifactId><version>1</version></project>\n",
                "src/main/java/example/domain/Order.java": (
                    "package example.domain; public record Order(String id, OrderStatus status) {}\n"
                ),
                "src/main/java/example/domain/OrderStatus.java": (
                    "package example.domain; public enum OrderStatus { CREATED, SUBMITTED, CANCELLED }\n"
                ),
                "src/main/java/example/domain/SubmitOrderCommand.java": (
                    "package example.domain; public record SubmitOrderCommand(String customerId) {}\n"
                ),
                "src/main/java/example/domain/OrderSubmittedEvent.java": (
                    "package example.domain; public record OrderSubmittedEvent(String orderId) {}\n"
                ),
                "src/main/java/example/api/OrderResource.java": (
                    'package example.api; class OrderResource { @PostMapping("/api/orders") '
                    'void submit(){ kafkaTemplate.send("order.submitted.v1", "payload"); } }\n'
                ),
            },
        )
        return frontend, backend

    def test_prompt_expands_active_repository_to_sibling_application(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "quote-order-platform"
            root.mkdir()
            frontend, _ = self._workspace(root)
            discovery = resolve_workspace(frontend, PROMPT)
            self.assertEqual(discovery.workspace_root, root.resolve())
            self.assertEqual(discovery.workspace_model, "multi-repo")
            self.assertEqual(len(discovery.repositories), 2)
            roles = {item.repository_id: item.role for item in discovery.repositories}
            self.assertEqual(roles["web-app"], "frontend")
            self.assertEqual(roles["order-service"], "backend-service")

    def test_multi_repo_generation_has_complete_dynamic_plan_and_quality_gates(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "quote-order-platform"
            root.mkdir()
            frontend, _ = self._workspace(root)
            manager = AgentConversationManager(ROOT, frontend)
            completion = manager.generate_documentation(PROMPT)

            self.assertEqual(completion["status"], "PASS")
            self.assertEqual(completion["workspace_model"], "multi-repo")
            self.assertEqual(completion["repositories"], 2)
            self.assertTrue(all(value == 1.0 for value in completion["quality"].values()))
            self.assertEqual(manager.workspace, root.resolve())
            self.assertEqual(manager.context_root, (root / ".t-understand").resolve())

            latest = root / ".t-understand" / "output" / "documentation" / "latest"
            required_documents = (
                "business/goals-and-outcomes.md",
                "business/business-processes.md",
                "domain/bounded-contexts.md",
                "domain/invariants.md",
                "domain/commands.md",
                "domain/domain-events.md",
                "flows/flow-catalog.md",
                "repositories/web-app/overview.md",
                "repositories/order-service/overview.md",
                "integrations/http-contract-map.md",
                "integrations/event-topology.md",
                "reference/known-unknowns.md",
            )
            for relative in required_documents:
                self.assertTrue((latest / relative).is_file(), relative)

            requirements = yaml.safe_load((latest / "_meta" / "requirements.yaml").read_text())
            generation = [json.loads(line) for line in (latest / "_meta" / "generation-ledger.jsonl").read_text().splitlines() if line]
            ledger = yaml.safe_load((latest / "_meta" / "coverage-ledger.yaml").read_text())
            self.assertGreater(len(requirements["requirements"]), len(DOCUMENT_CATALOG))
            self.assertEqual(
                {item["requirement_id"] for item in requirements["requirements"]},
                {item["requirement_id"] for item in generation},
            )
            self.assertTrue(all(item["status"] == "GENERATED" for item in generation))
            for metric in ("coverage", "requirement_coverage", "section_coverage", "repository_coverage", "flow_coverage"):
                self.assertEqual(ledger[metric], 1.0, metric)
            self.assertFalse(ledger.get("uncovered_records"))
            self.assertFalse(ledger.get("missing_requirements"))

            known_unknowns = (latest / "reference" / "known-unknowns.md").read_text()
            self.assertIn("UNKNOWN_INTENT", known_unknowns)
            self.assertNotIn("All tests pass", completion["chat_response"])
            self.assertLess(len(completion["chat_response"]), 4000)


if __name__ == "__main__":
    unittest.main()
