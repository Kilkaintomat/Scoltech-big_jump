"""CPU-only validation, immutable source freeze, and saved-pilot reanalysis."""
import ast
import datetime
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

BASE = Path("/beegfs/home/denis.rakhmankin/onebigjump")
HERE = BASE / "audit/p5_repair_20260914_v2"
SOURCE_ROOT = HERE / "source"
RUNS = BASE / "runs/p5_repair_20260914_v2"
JOB = os.environ["SLURM_JOB_ID"]
OUT = HERE / ("preflight-" + JOB)


def command(args, name):
    result = subprocess.run(args, cwd=SOURCE_ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    (OUT / (name + ".log")).write_text(result.stdout, encoding="utf-8")
    print(name, result.returncode, result.stdout[-5000:], flush=True)
    if result.returncode:
        raise RuntimeError(name + " failed")
    return result


def node(source, name):
    return ast.dump(next(n for n in ast.parse(source).body
                         if isinstance(n, ast.FunctionDef) and n.name == name))


def grammar_checks(deduction, grammar_for_length, tokenizer, vocab_size):
    import xgrammar as xgr
    from vllm.sampling_params import GuidedDecodingParams, SamplingParams
    from vllm.config import DecodingConfig
    from vllm.v1.engine.processor import Processor
    from types import SimpleNamespace
    from onebigjump.readiness.deduction_format import DECODING_BACKEND, guided_decoding_for_length
    assert os.environ.get("VLLM_USE_V1") == "1"
    processor = SimpleNamespace(decoding_config=DecodingConfig(guided_decoding_backend=DECODING_BACKEND))

    info = xgr.TokenizerInfo.from_huggingface(
        tokenizer, vocab_size=vocab_size, stop_token_ids=[tokenizer.eos_token_id])
    compiler = xgr.GrammarCompiler(info, max_threads=2)
    checks = []
    def accepts(compiled, text):
        matcher = xgr.GrammarMatcher(compiled)
        for token in tokenizer.encode(text, add_special_tokens=False):
            if not matcher.accept_token(token):
                return False
        return matcher.accept_token(tokenizer.eos_token_id)
    for length in range(3, 13):
        problem = deduction.make_problem(length, "runtime", 0, seed=2026091405)
        grammar = grammar_for_length(length)
        compiled = compiler.compile_grammar(grammar)
        gold = "\n".join("Mira is " + fact + "." for fact in problem["gold_chain"]) + "\nAnswer: true"
        wrong = "\n".join(["Mira is " + problem["initial"] + "."] * length) + "\nAnswer: true"
        invented = "\n".join(["Mira is p9999."] * length) + "\nAnswer: true"
        short = "\n".join(gold.splitlines()[1:])
        long = gold.replace("\nAnswer: true", "\nMira is p1234.\nAnswer: true")
        params = guided_decoding_for_length(length)
        sampling = SamplingParams(max_tokens=1024, guided_decoding=params)
        Processor._validate_structured_output(processor, sampling)
        legacy = SamplingParams(max_tokens=1024, guided_decoding=GuidedDecodingParams(grammar=grammar, backend="xgrammar:no-fallback"))
        try:
            Processor._validate_structured_output(processor, legacy)
        except ValueError as exc:
            assert "Request-level" in str(exc)
        else:
            raise AssertionError("legacy mismatch was not rejected")
        result = dict(length=length, gold=accepts(compiled, gold),
                      wrong_inference=accepts(compiled, wrong),
                      invented_fact=accepts(compiled, invented),
                      rejects_short=not accepts(compiled, short),
                      rejects_long=not accepts(compiled, long),
                      no_fallback=params.backend == "xgrammar" and not params.backend_options(),
                      engine_request_validation=True, rejects_legacy_mismatch=True,
                      gold_completion_tokens=len(tokenizer.encode(gold, add_special_tokens=False)))
        assert all(result[k] for k in ("gold", "wrong_inference", "invented_fact",
                                      "rejects_short", "rejects_long", "no_fallback")), result
        assert result["gold_completion_tokens"] < 1024
        checks.append(result)
    return checks


def main():
    OUT.mkdir()
    changed = [
        SOURCE_ROOT / "src/onebigjump/experiments/p5_rate.py",
        SOURCE_ROOT / "src/onebigjump/readiness/deduction_format.py",
        SOURCE_ROOT / "src/onebigjump/readiness/deduction.py",
        SOURCE_ROOT / "tests/unit/test_p5_rate_repair.py",
        HERE / "pipeline.py", HERE / "gpu_entry.py",
    ]
    # Format only the unconsumed isolated copy, before freezing any artifacts.
    command([sys.executable, "-m", "ruff", "check", "--fix", *map(str, changed)], "ruff-fix")
    command([sys.executable, "-m", "ruff", "format", *map(str, changed)], "ruff-format")
    command([sys.executable, "-m", "ruff", "check", *map(str, changed)], "ruff")
    command([sys.executable, "-m", "mypy", "--cache-dir", str(HERE / ".mypy-cache"),
             "src/onebigjump/experiments/p5_rate.py",
             "src/onebigjump/readiness/deduction_format.py",
             "src/onebigjump/readiness/deduction.py"], "mypy")
    junit = OUT / "pytest.xml"
    command([sys.executable, "-m", "pytest",
             "tests/unit/test_p5_rate_repair.py",
             "tests/unit/test_readiness.py",
             "tests/unit/test_development_protocols_0913.py",
             str(HERE / "test_release_policy.py"),
             "--junitxml=" + str(junit)], "pytest")
    # Host scripts must retain Python 3.6 syntax.
    for path in (HERE / "controller.py", HERE / "release_policy.py"):
        ast.parse(path.read_text(encoding="utf-8"), feature_version=(3, 6))
    command(["bash", "-n", str(HERE / "pilot.sbatch")], "shell")
    from onebigjump.e1.artifacts import (
        digest, environment, finish, identity, read_json, verify_manifest, write_once,
    )
    from onebigjump.readiness import deduction
    from onebigjump.readiness.deduction_format import grammar_for_length
    from onebigjump.experiments.p5_rate import diagnose_records
    from transformers import AutoConfig, AutoTokenizer
    import pipeline

    original = (BASE / "audit/revision_2026_09_13/snapshots/lean-io-v9/src/onebigjump/readiness/deduction.py").read_text(encoding="utf-8")
    edited = (SOURCE_ROOT / "src/onebigjump/readiness/deduction.py").read_text(encoding="utf-8")
    preserved = ("check", "prompt", "make_problem", "gate", "verify", "extract", "measure")
    assert all(node(original, name) == node(edited, name) for name in preserved)
    info = deduction.model_info(RUNS / "guided")
    tokenizer = AutoTokenizer.from_pretrained(info["model_path"], local_files_only=True)
    config = AutoConfig.from_pretrained(info["model_path"], local_files_only=True)
    grammar = grammar_checks(deduction, grammar_for_length, tokenizer, config.vocab_size)
    old_roots = {
        "worked-example-v2": BASE / "runs/development_20260913/deduction",
        "numbered-slots-v3": BASE / "runs/development_20260913_exactlength/deduction",
    }
    # Complete actual-data integrity and rate calculations before freezing source.
    historical = {}
    for name, root in old_roots.items():
        records, _ = pipeline.records_for(root)
        historical[name] = diagnose_records(records)

    baseline = HERE / "baseline-source-manifest.json"
    verify_manifest(baseline)
    oldmeta = read_json(baseline)["metrics"]
    source_files = sorted(p for p in SOURCE_ROOT.rglob("*") if p.is_file()
                          and not any(part.startswith(".") or part == "__pycache__"
                                      for part in p.relative_to(SOURCE_ROOT).parts)
                          and p.name != "source-manifest.json")
    source_manifest = write_once(SOURCE_ROOT / "source-manifest.json", {
        "stage": "isolated-P5-repair-source",
        "inputs": {str(baseline.resolve()): digest(baseline)},
        "outputs": {str(p.resolve()): digest(p) for p in source_files},
        "environment": environment(),
        "metrics": {**oldmeta, "dirty": True, "amendment": "isolated-p5-rate-and-syntax-v2-engine-backend",
                    "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat()},
    })
    verify_manifest(source_manifest)
    for p in source_files:
        p.chmod(p.stat().st_mode & ~0o222)

    for arm in ("unguided", "guided"):
        deduction.population(RUNS / arm, source_manifest)
    u = deduction.requests(RUNS / "unguided", "pilot")
    g = deduction.requests(RUNS / "guided", "pilot")
    assert u == g and len(u) == 80
    old_tasks = {identity(p) for root in old_roots.values()
                 for p in read_json(root / "inputs/problems.json")}
    assert not any(identity(r["problem"]) in old_tasks for r in u)
    prompt_tokens = []
    for r in u:
        text = deduction.prompt(r["problem"], "worked-example-v2")
        toks = tokenizer.apply_chat_template([{"role": "user", "content": text}],
                                             tokenize=True, add_generation_prompt=True)
        assert len(toks) + 1024 <= 4096
        prompt_tokens.append(len(toks))
    old_manifests = []
    for name, root in old_roots.items():
        folder = OUT / name
        pipeline.rate_analysis(root, folder)
        old_manifests.append(folder / "manifest.json")

    test_suites = ET.parse(junit).getroot()
    suites = list(test_suites.iter("testsuite"))
    tests = {key: sum(int(s.attrib.get(key, 0)) for s in suites)
             for key in ("tests", "failures", "errors", "skipped")}
    operational = [HERE / name for name in (
        "pipeline.py", "controller.py", "release_policy.py", "test_release_policy.py",
        "gpu_entry.py", "pilot.sbatch", "preflight.py", "preflight.sbatch", "study-protocol.json", "runtime-amendment.json",
    )] + [RUNS / arm / "protocol.json" for arm in ("unguided", "guided")]
    metrics = {
        "passed": True, "tests": tests, "grammar_runtime": grammar,
        "xgrammar": importlib.metadata.version("xgrammar"),
        "vllm": importlib.metadata.version("vllm"),
        "model_revision": info["revision"],
        "source_sha256": digest(source_manifest),
        "operational_files": {str(p.resolve()): digest(p) for p in operational},
        "historical": historical, "preserved_functions": list(preserved),
        "paired_attempts_per_arm": len(u), "paired_factors_equal": True,
        "max_prompt_tokens": max(prompt_tokens), "max_new_tokens": 1024,
        "fresh_tasks": True, "allow_main": False,
    }
    metric_file = write_once(OUT / "metrics.json", metrics)
    report = ["# P5: изолированное исправление и проверка", "",
              "Расчёт c в P(успех|L)=exp(-cL) отделён от GPD. Граничные случаи обрабатываются явно.",
              "Правила проверки, разметка после первой ошибки и технический порог допуска сохранены.", "",
              "## Проверки CPU", "",
              f'Тесты: {tests["tests"]}, ошибок: {tests["errors"]}, не пройдено: {tests["failures"]}, пропущено: {tests["skipped"]}.',
              f'Синтаксическая грамматика проверена настоящим токенизатором и xgrammar {metrics["xgrammar"]} на всех длинах 3–12.',
              "Она принимает правильные и неправильные по смыслу цепочки, но запрещает неправильное число строк.",
              "Ruff, mypy, совместимость синтаксиса управляющего кода с Python 3.6 и синтаксис sbatch проверены.", "",
              "## Сохранённые пилоты", "",
              "| Пилот | Попытки | Категории |", "|---|---:|---|"]
    for name, result in historical.items():
        report.append(f'| {name} | {result["attempts"]} | {result["categories"]} |')
        for t in result["temperatures"]:
            ev = t["evaluation"]
            fit = ev["rate_fit"]
            successes = sum(v[0] for v in ev["counts"].values())
            report.append(f'\nEvaluation T={t["temperature"]}: {successes}/{ev["attempts"]}; статус оценки — {fit["status"]}; c={fit["rate_per_step"] if not fit["rate_is_infinite"] else "∞"}.')
    report.extend(["", "## Исправление совместимости vLLM", "",
        "Первая GPU-попытка сохранена отдельно. vLLM V1 отклонил backend, заданный на уровне запроса.",
        "В этой версии xgrammar явно выбран на уровне движка; request не переопределяет backend. Ветка V1 не использует fallback.",
        "CPU-регрессия воспроизводит отказ старой настройки и проверяет новую через настоящий Processor._validate_structured_output.",
        "Повторены те же задачи и seed; изменение обусловлено инфраструктурной ошибкой, не результатами успешности.",
        "", "## Отдельный парный запуск", "",
        f'{len(u)} попыток на вариант, всего {2*len(u)}. Одинаковые свежие задачи, запросы, температуры, seed и лимит {metrics["max_new_tokens"]} токена.',
        "Обычная генерация сравнивается с ограничением только синтаксиса. Ни правильная цепочка, ни обратная связь проверяющего не подаются в маску.",
        "Грамматика меняет распределение генерации; результаты относятся к отдельному синтетическому пилоту.",
        "GPU-запуск разрешён только после завершения всех основных извлечений активаций и освобождения GPU-очереди пользователя.",
        "Большая серия не разрешена. Статистическая значимость, интервалы, θ, τ и подтверждение P5 этим исправлением не устанавливаются.",
        "Результат свежего GPU-пилота сохраняется отдельно в runs/p5_repair_20260914_v2/summary.",
    ])
    report_file = OUT / "REPORT.md"
    report_file.write_text("\n".join(report) + "\n", encoding="utf-8")
    outputs = [metric_file, report_file, junit, *sorted(OUT.glob("*.log"))]
    manifest = finish(OUT, stage="P5-repair-CPU-preflight",
        context={"source": digest(source_manifest)},
        inputs=[source_manifest, *operational, *old_manifests,
                *[RUNS / arm / "inputs/manifest.json" for arm in ("unguided", "guided")]],
        outputs=outputs, metrics=metrics)
    write_once(HERE / "preflight-result.json", {
        "job_id": JOB, "manifest": str(manifest),
        "manifest_sha256": digest(manifest), "source_sha256": digest(source_manifest),
    })
    print(json.dumps({"passed": True, "tests": tests, "manifest": str(manifest)}), flush=True)


if __name__ == "__main__":
    main()
