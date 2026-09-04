# Convenience targets. Everything here is also a plain command; nothing is hidden in the Makefile.
.PHONY: help setup lean test lint figure1 p4 lean-verify clean-results

help:
	@grep -E '^[a-z0-9-]+:.*?##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/' | column -t -s "$$(printf '\t')"

setup:  ## install the environment and write docs/system_report.md
	./scripts/bootstrap.sh

lean:  ## install Lean 4 + Mathlib + the REPL in user space (slow: ~8 GB)
	./scripts/setup_lean.sh

test:  ## lint, typecheck and run the tests that need no external toolchain
	uv run ruff check src/ tests/ scripts/
	uv run ruff format --check src/ tests/
	uv run mypy src/
	uv run pytest tests/ -m "not lean and not ml" -q

test-all:  ## everything, including the live Lean and GPT-2 tests
	./scripts/run_tests.sh

figure1:  ## reproduce Figure 1 (about 2 minutes)
	uv run onebigjump run configs/simulation/figure1.yaml

p4:  ## run the grokking experiment (about 20 minutes on MPS)
	uv run onebigjump run configs/grokking/modular_addition.yaml

lean-verify:  ## label the fixture proofs with the Lean kernel
	uv run onebigjump lean-verify tests/fixtures/lean_proofs.jsonl --out-dir results/pilot/lean

doctor:  ## what this machine can and cannot run
	uv run onebigjump doctor
	uv run onebigjump lean-doctor

clean-results:  ## remove generated results, keeping the directory structure
	find results paper_outputs -type f ! -name '.gitkeep' -delete
