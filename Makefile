PYTHON ?= python3

.PHONY: schemas governance negative contracts economy phase1-summary runtime-static runtime-contract runtime-tests runtime-cli phase2-summary application-contract application-tests application-cli phase3-summary snapshot-contract snapshot-tests snapshot-cli phase4-summary discovery-contract discovery-tests discovery-cli phase5-summary adapter-tests phase6-summary analysis-contract analysis-tests knowledge-cli phase7-summary graph-contract graph-tests phase8-summary memory-contract memory-tests phase9-summary model-contract model-tests phase10-summary documentation-contract documentation-tests documentation-cli phase11-summary export-contract export-tests phase12-summary checksums verify-phase-1 verify-phase-2 verify-phase-3 verify-phase-4 verify-phase-5 verify-phase-6 verify-phase-7 verify-phase-8 verify-phase-9 verify-phase-10 verify-phase-11 verify-phase-12 verify package clean qna-contract qna-tests review-contract review-tests review-export-contract qna-review-cli verify-phase-13 verify-phase-14 verify-phase-15 quality-contract quality-tests qualification-contract qualification-tests installation-contract installation-tests final-cli integration-tests release-contract release-audit verify-phase-16 verify-phase-17 verify-phase-18 verify-phase-19 verify-phase-20

schemas:
	$(PYTHON) scripts/validate_schemas.py

governance:
	$(PYTHON) scripts/validate_governance.py --report reports/governance-report.json

negative:
	$(PYTHON) scripts/test_negative_governance.py --report reports/negative-test-report.json

contracts:
	$(PYTHON) scripts/test_contract_examples.py --report reports/contract-test-report.json

economy:
	$(PYTHON) scripts/test_economy_contract.py --report reports/economy-contract-report.json

phase1-summary:
	$(PYTHON) scripts/generate_phase1_summary.py

runtime-static:
	PYTHONPATH=runtime:. $(PYTHON) -m compileall -q runtime tests scripts
	bash -n bin/t-understand

runtime-contract:
	$(PYTHON) scripts/validate_runtime_contract.py --report reports/runtime-contract-report.json

runtime-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_runtime_tests.py --report reports/runtime-test-report.json

runtime-cli:
	$(PYTHON) scripts/test_runtime_cli.py --report reports/runtime-cli-report.json

phase2-summary:
	$(PYTHON) scripts/generate_phase2_summary.py

application-contract:
	$(PYTHON) scripts/validate_application_contract.py --report reports/application-contract-report.json

application-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_application_tests.py --report reports/application-test-report.json

application-cli:
	$(PYTHON) scripts/test_application_cli.py --report reports/application-cli-report.json

phase3-summary:
	$(PYTHON) scripts/generate_phase3_summary.py

snapshot-contract:
	$(PYTHON) scripts/validate_snapshot_contract.py --report reports/snapshot-contract-report.json

snapshot-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_snapshot_tests.py --report reports/snapshot-test-report.json

snapshot-cli:
	$(PYTHON) scripts/test_snapshot_cli.py --report reports/snapshot-cli-report.json

phase4-summary:
	$(PYTHON) scripts/generate_phase4_summary.py

discovery-contract:
	$(PYTHON) scripts/validate_discovery_contract.py --report reports/discovery-contract-report.json

discovery-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_discovery_tests.py --report reports/discovery-test-report.json

discovery-cli:
	$(PYTHON) scripts/test_discovery_cli.py --report reports/discovery-cli-report.json

phase5-summary:
	$(PYTHON) scripts/generate_phase5_summary.py

adapter-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_adapter_tests.py --report reports/adapter-test-report.json

phase6-summary:
	$(PYTHON) scripts/generate_phase6_summary.py

analysis-contract:
	$(PYTHON) scripts/validate_analysis_contract.py --report reports/analysis-contract-report.json

analysis-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_analysis_tests.py --report reports/analysis-test-report.json

knowledge-cli:
	$(PYTHON) scripts/test_knowledge_cli.py --report reports/knowledge-cli-report.json

phase7-summary:
	$(PYTHON) scripts/generate_phase7_summary.py

graph-contract:
	$(PYTHON) scripts/validate_graph_contract.py --report reports/graph-contract-report.json

graph-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_graph_tests.py --report reports/graph-test-report.json

phase8-summary:
	$(PYTHON) scripts/generate_phase8_summary.py

memory-contract:
	$(PYTHON) scripts/validate_memory_contract.py --report reports/memory-contract-report.json

memory-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_memory_tests.py --report reports/memory-test-report.json

phase9-summary:
	$(PYTHON) scripts/generate_phase9_summary.py

model-contract:
	$(PYTHON) scripts/validate_model_contract.py --report reports/model-contract-report.json

model-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_model_tests.py --report reports/model-test-report.json

phase10-summary:
	$(PYTHON) scripts/generate_phase10_summary.py

documentation-contract:
	$(PYTHON) scripts/validate_documentation_contract.py --report reports/documentation-contract-report.json

documentation-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_documentation_tests.py --report reports/documentation-test-report.json

documentation-cli:
	PYTHONPATH=runtime:. $(PYTHON) scripts/test_documentation_cli.py --report reports/documentation-cli-report.json

phase11-summary:
	$(PYTHON) scripts/generate_phase11_summary.py

export-contract:
	$(PYTHON) scripts/validate_export_contract.py --report reports/export-contract-report.json

export-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_export_tests.py --report reports/export-test-report.json

phase12-summary:
	$(PYTHON) scripts/generate_phase12_summary.py

verify-phase-10: model-contract model-tests documentation-cli phase10-summary

verify-phase-11: documentation-contract documentation-tests documentation-cli phase11-summary

verify-phase-12: export-contract export-tests documentation-cli phase12-summary

checksums:
	$(PYTHON) scripts/generate_checksums.py
	sha256sum -c CHECKSUMS.sha256

verify-phase-1: schemas governance negative contracts economy phase1-summary

verify-phase-2: runtime-static runtime-contract runtime-tests runtime-cli phase2-summary

verify-phase-3: application-contract application-tests application-cli phase3-summary

verify-phase-4: snapshot-contract snapshot-tests snapshot-cli phase4-summary

verify-phase-5: discovery-contract discovery-tests discovery-cli phase5-summary

verify-phase-6: discovery-contract adapter-tests discovery-cli phase6-summary

verify-phase-7: analysis-contract analysis-tests knowledge-cli phase7-summary

verify-phase-8: graph-contract graph-tests knowledge-cli phase8-summary

verify-phase-9: memory-contract memory-tests knowledge-cli phase9-summary

verify: verify-phase-1 verify-phase-2 verify-phase-3 verify-phase-4 verify-phase-5 verify-phase-6 verify-phase-7 verify-phase-8 verify-phase-9 verify-phase-10 verify-phase-11 verify-phase-12 verify-phase-13 verify-phase-14 verify-phase-15 quality-contract quality-tests qualification-contract qualification-tests installation-contract installation-tests final-cli integration-tests release-contract release-audit verify-phase-16 verify-phase-17 verify-phase-18 verify-phase-19 verify-phase-20 checksums

package: verify
	$(PYTHON) scripts/package_bundle.py

clean:
	rm -f reports/*.json CHECKSUMS.sha256
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete

qna-contract:
	$(PYTHON) scripts/validate_qna_contract.py --report reports/qna-contract-report.json

qna-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_qna_tests.py --report reports/qna-test-report.json

review-contract:
	$(PYTHON) scripts/validate_review_contract.py --report reports/review-contract-report.json

review-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_review_tests.py --report reports/review-test-report.json

review-export-contract:
	$(PYTHON) scripts/validate_review_export_contract.py --report reports/review-export-contract-report.json

qna-review-cli:
	PYTHONPATH=runtime:. $(PYTHON) scripts/test_qna_review_cli.py --report reports/qna-review-cli-report.json

verify-phase-13: qna-contract qna-tests qna-review-cli

verify-phase-14: review-contract review-tests qna-review-cli

verify-phase-15: review-export-contract review-tests qna-review-cli

quality-contract:
	PYTHONPATH=runtime:. $(PYTHON) scripts/validate_quality_contract.py --report reports/quality-contract-report.json

quality-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_quality_tests.py --report reports/quality-test-report.json

qualification-contract:
	PYTHONPATH=runtime:. $(PYTHON) scripts/validate_qualification_contract.py --report reports/qualification-contract-report.json

qualification-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_qualification_tests.py --report reports/qualification-test-report.json

installation-contract:
	PYTHONPATH=runtime:. $(PYTHON) scripts/validate_installation_contract.py --report reports/installation-contract-report.json

installation-tests:
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_installation_tests.py --report reports/installation-test-report.json

final-cli:
	PYTHONPATH=runtime:. $(PYTHON) scripts/test_final_cli.py --report reports/final-cli-report.json

integration-tests:
	rm -rf reports/integration-scenarios
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_integration_scenario.py --case single-repo-complete-pipeline
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_integration_scenario.py --case monorepo-module-coverage
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_integration_scenario.py --case multi-repo-contract-graph
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_integration_scenario.py --case diff-review-matrix
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_integration_scenario.py --case freshness-invalidation-refresh
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_integration_scenario.py --case platform-package-install-uninstall
	PYTHONPATH=runtime:. $(PYTHON) scripts/run_integration_scenario.py --case cheap-model-contract-qualification
	PYTHONPATH=runtime:. $(PYTHON) scripts/aggregate_integration_report.py

release-contract:
	PYTHONPATH=runtime:. $(PYTHON) scripts/validate_release_contract.py --report reports/release-contract-report.json

release-audit:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=runtime:. $(PYTHON) -c "from pathlib import Path; from tu_runtime.core.release import ReleaseManager; import json; r=ReleaseManager(Path('.').resolve()).audit(); print(json.dumps(r,indent=2)); raise SystemExit(0 if r['status']=='PASS' else 1)"

verify-phase-16: quality-contract quality-tests final-cli
verify-phase-17: qualification-contract qualification-tests final-cli
verify-phase-18: installation-contract installation-tests final-cli
verify-phase-19: integration-tests
verify-phase-20: release-contract release-audit checksums
