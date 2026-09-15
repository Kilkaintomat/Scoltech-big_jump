"""Package completed P3 diagnosis and an explicitly partial main-label audit."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import ast
import json
import os
import re
import shutil
import subprocess
import zipfile

from onebigjump.e1.artifacts import digest, finish, read_json, verify_manifest, write_once
from onebigjump.e1.spans import mask_comments
from onebigjump.e1.stages import rows
from onebigjump.e1.verification import ALLOWED_AXIOMS

base = Path("/beegfs/home/denis.rakhmankin/onebigjump")
audit = base / "audit/revision_2026_09_13"
here = Path(__file__).resolve().parent
out = audit / "reviews/active-followthrough-v1"
out.mkdir(parents=True, exist_ok=False)
source = Path(os.environ["E1_SNAPSHOT"]) / "source-manifest.json"
p3 = base / "runs/p3_fit_diagnostics_20260913"
kimina = base / "runs/lean_reverification_20260913_local/kimina/main/verification/shard-000-of-008"
renderer = here / "renderer-input.py"
config = read_json(here / "protocol.json")
for path in [p3 / "manifest.json", kimina / "manifest.json"]:
    verify_manifest(path)
tree = ast.parse(renderer.read_text(encoding="utf-8"))
node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "native_policy_inventory")
exec(compile(ast.Module(body=[node], type_ignores=[]), str(renderer), "exec"))
native = native_policy_inventory(kimina / "labels.jsonl")
native["scope"] = "only completed Kimina main shard 0 of 8; not the full model population"
primary = read_json(kimina / "manifest.json")["metrics"]
assert native["attempts"] == primary["attempts"]
assert native["primary_categories"] == primary["categories"]
p3_metrics = read_json(p3 / "metrics.json")
p3_examples = read_json(p3 / "examples.json")
assert not p3_metrics["exact_replay_mismatches"]
reason = "nonregular endpoint solution: gamma <= -1; no usable GPD estimate"
cases = []
for example in p3_examples:
    grids = example["profile_grid_diagnostics"]
    current = next(x for x in grids if x["support_epsilon"] == 1e-12)
    interior = current["interior_grid_local_minima_gamma_above_minus_one"]
    best = min(interior, key=lambda x: x["profile_nll_normalized"]) if interior else None
    cases.append({
        "trace_id": example["trace_id"], "method": example["method"],
        "bootstrap_index": example["bootstrap_index"],
        "n_excesses": example["n_excesses"],
        "max_multiplicity": example["max_multiplicity"],
        "raw_gamma": example["fit"]["gamma"],
        "current_winner_left_boundary": current["grid_winner_index"] == 0,
        "best_interior_grid_minimum": best,
        "winner_boundary_by_epsilon": {
            str(x["support_epsilon"]): x["grid_winner_index"] == 0 for x in grids
        },
        "winner_gamma_by_epsilon": {
            str(x["support_epsilon"]): x["grid_winner_gamma"] for x in grids
        },
    })
mechanism = {
    "example_count": len(cases),
    "current_grid_left_boundary_count": sum(c["current_winner_left_boundary"] for c in cases),
    "interior_grid_minimum_count": sum(c["best_interior_grid_minimum"] is not None for c in cases),
    "boundary_winner_changes_with_epsilon": sum(
        len(set(c["winner_boundary_by_epsilon"].values())) > 1 for c in cases
    ),
    "original_method_bootstrap_rejections": sum(
        item["bootstrap"].get(reason, 0)
        for key, item in p3_metrics["scenarios_methods"].items() if key.endswith("/original")
    ),
    "both_methods_bootstrap_rejections": sum(
        item["bootstrap"].get(reason, 0)
        for item in p3_metrics["scenarios_methods"].values()
    ),
    "other_bootstrap_failure_reasons": sorted({
        r for item in p3_metrics["scenarios_methods"].values()
        for r in item["bootstrap"] if r not in ["success", reason]
    }),
    "cases": cases,
}
queue_copies = []
queues = {}
for name, relative in [
    ("main", "runs/lean_reverification_20260913_local/queue.json"),
    ("controls", "runs/controls_20260913_local/queue.json"),
]:
    path = out / (name + "-queue.json")
    shutil.copyfile(base / relative, path)
    queue_copies.append(path)
    queue = read_json(path)
    queues[name] = dict(Counter(t["state"] for t in queue["tasks"].values()))
stamp = datetime.now(timezone.utc).isoformat()
state = subprocess.check_output([
    "squeue", "-u", "denis.rakhmankin",
    "-o", "%.18i %.10T %.45j %.10M %.12R",
], text=True)
queue_text = out / "squeue.txt"
queue_text.write_text(stamp + "\n" + state, encoding="utf-8")
metrics = {
    "captured_utc": stamp, "config": config, "queues": queues,
    "p3_replay": p3_metrics, "p3_mechanism": mechanism,
    "kimina_partial_inventory": native, "kimina_partial_verification": primary,
    "main_method_changed": False, "primary_labels_changed": False,
}
metric = write_once(out / "metrics.json", metrics)
lines = [
    "# Что сделано параллельно основной серии",
    "",
    "Срез на Жоресе: " + stamp + ". Все вычисления и проверки выполнялись через Slurm.",
    "",
    "## P3: установлен механизм непригодных GPD-оценок",
    "",
    f"Заново выполнены {p3_metrics['bootstrap_fits']} bootstrap-оценок на {p3_metrics['datasets']} прежних наборах: первые десять индексов каждого сценария. Все точечные оценки, интервалы и числа пригодных повторов в точности воспроизведены.",
    f"Обе схемы порога дали в сумме {mechanism['both_methods_bootstrap_rejections']} непригодных bootstrap-оценок; для исходного порога — {mechanism['original_method_bootstrap_rejections']}. Единственная обнаруженная причина — уход оптимизации к границе поддержки с gamma <= -1, после чего код обоснованно отклоняет такой результат.",
    "",
    "| Сценарий | Непригодно при исходном пороге | Всего повторов |",
    "|---|---:|---:|",
]
for scenario in p3_metrics["protocol"]["scenarios"]:
    item = p3_metrics["scenarios_methods"][scenario + "/original"]["bootstrap"]
    lines.append(f"| {scenario} | {item.get(reason, 0)} | {sum(item.values())} |")
lines += [
    "",
    "Это воспроизведение части старой валидации, а не новая оценка покрытия. Две схемы порога используют связанные данные: суммарное число попыток не является числом независимых наблюдений.",
    f"Для {mechanism['example_count']} детально сохранённых примеров сеточный поиск выбирает левую границу в {mechanism['current_grid_left_boundary_count']} случаях, хотя внутренний сеточный минимум с gamma > -1 имеется в {mechanism['interior_grid_minimum_count']} случаях. При диагностическом изменении расстояния до границы сам выбор между границей и внутренней точкой меняется в {mechanism['boundary_winner_changes_with_epsilon']} случаях.",
    "Эти сеточные минимумы не заменяют оценки и не доказывают корректность альтернативного метода. Кратность максимума сохранена для каждой попытки; отказы встречаются и без повторяющегося максимума.",
    "",
    "Следующий обоснованный шаг: заранее определить отдельный оцениватель с явным правилом допустимой области и выбора внутреннего решения, проверить его на сохранённых случаях, затем провести независимую валидацию покрытия и доступности на новых seed. Сдвигать численный epsilon до получения нужного ответа или принимать отвергнутые gamma нельзя. Основной метод остаётся замороженным.",
    "",
    "## Первая завершённая часть основной Kimina",
    "",
    f"Проверено {native['attempts']} ответов. Расхождений без объяснения: {primary['unexplained_disagreements']}. Ресурсных ограничений: {primary['resource_limited']}.",
    f"Из категории sorry_invalid_proof ({primary['categories'].get('sorry_invalid_proof', 0)}) выявлены {native['native_policy_only_count']} случаев, где целое доказательство и пошаговое воспроизведение прошли, явных sorry/admit нет, а исключение связано с дополнительными native_decide-аксиомами.",
    "Это отдельный учёт политики доверия. Исходные метки сохранены. Шард не представляет всю основную выборку; после завершения основной серии автоматический отчёт посчитает такие исключения по всем моделям.",
    "",
    "## Что делаем дальше",
    "",
    "1. Основная серия продолжает верификацию, затем извлечение активаций и зафиксированные контроли whitening/позиции/surprisal. Завершения этих стадий действительно нужно дождаться.",
    "2. P3 уже имеет конкретную диагностированную проблему; следующая работа — отдельная спецификация и проверка регулярного решения, затем независимая валидация, а не изменение текущей основной оценки.",
    "3. Дедукцию пока не расширяем: следующий пилот должен проверять отдельно заданный протокол формата и его ограничения. Предыдущие свежие пилоты не были парными, поэтому различия между ними нельзя приписать одному изменению промпта.",
    "",
    "Состояния стадий очереди (включают переиспользованные результаты и зависимости): " + json.dumps(queues, ensure_ascii=False),
    "",
    "Это дополнение к substantive-review-v2. Для проверки доступны код, протокол, все повторные GPD-fit записи, исходная валидационная часть, частичная разметка Kimina и манифесты. Внешние пути в манифестах относятся к Жоресу; bundle-index.json содержит хеш каждого вложенного файла.",
]
report = out / "REPORT.md"
report.write_text("\n".join(lines) + "\n", encoding="utf-8")
finish(
    out, stage="active-work-p3-mechanism-and-partial-native-audit",
    context={"source": digest(source)},
    inputs=[source, p3 / "manifest.json", kimina / "manifest.json",
            Path(__file__), renderer, here / "protocol.json", here / "run.sbatch"],
    outputs=[metric, report, *queue_copies, queue_text],
    metrics={"p3_exact_replay": True, "main_method_changed": False,
             "partial_main_only": True, "captured_utc": stamp},
)
files = {}
def add(path, prefix):
    path = Path(path)
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if child.is_file() and not child.is_symlink():
                files[prefix + "/" + str(child.relative_to(path))] = child
    else:
        files[prefix] = path
add(out, "review")
add(p3, "p3-replay")
add(audit / "p3_fit_diagnostics_v1", "code/p3")
add(here, "code/review")
add(base / "runs/p3_validation_20260913/protocol.json", "original/protocol.json")
for filename in ["manifest.json", "replicates.jsonl", "replicates.identity.json"]:
    add(base / "runs/p3_validation_20260913/shard-00" / filename, "original/shard-00/" + filename)
for filename in ["manifest.json", "labels.jsonl", "labels.identity.json"]:
    add(kimina / filename, "kimina-shard-0/" + filename)
add(source, "source/source-manifest.json")
for relative in p3_metrics["protocol"]["source_files_required_identical"]:
    add(source.parent / relative, "source/" + relative)
for relative in ["src/onebigjump/e1/artifacts.py", "src/onebigjump/e1/analysis.py",
                 "src/onebigjump/e1/spans.py", "src/onebigjump/e1/verification.py"]:
    add(source.parent / relative, "source/" + relative)
index = {name: {"sha256": digest(path), "server_path": str(path), "bytes": path.stat().st_size}
         for name, path in files.items()}
archive = audit / "review-packages/active-followthrough-v1.zip"
with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as z:
    for name, path in files.items():
        z.write(path, name)
    z.writestr("bundle-index.json", json.dumps(index, sort_keys=True, indent=2) + "\n")
package = write_once(archive.with_suffix(".json"), {
    "archive_sha256": digest(archive), "files": len(index),
    "bytes": archive.stat().st_size, "report_manifest_sha256": digest(out / "manifest.json"),
})
print("ACTIVE_FOLLOWTHROUGH_COMPLETE", archive, package, flush=True)
