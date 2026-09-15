"""Pure queue amendments for a finite saved-response continuation."""
import copy

MODELS = ("deepseek", "goedel", "kimina")
GATE = "saved-continuation-preflight"
BAD = {"FAILED", "CANCELLED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL", "BOOT_FAIL",
       "DEADLINE", "PREEMPTED", "BLOCKED"}


def activate(queue, receipt, wrapper):
    if not receipt.get("passed") or not str(receipt.get("job_id", "")).isdigit():
        raise ValueError("missing passed Slurm preflight")
    result = copy.deepcopy(queue)
    if not result["source"].endswith("/lean-local-toolchain-v7"):
        raise ValueError("unexpected downstream source")
    if result.get("saved_continuation"):
        raise ValueError("already activated")
    tasks = result["tasks"]
    tasks[GATE] = dict(external=True, model=None, job_id=receipt["job_id"],
                       state="COMPLETED", partition="ais-htc", dependencies=[])
    promoted = []
    for key, task in tasks.items():
        if task.get("stage") != "verify" or task.get("job_id"):
            continue
        if task["state"] != "WAITING" or task.get("submit_error"):
            raise ValueError("unsubmitted verifier needs manual review: " + key)
        task.setdefault("execution_history", []).append(copy.deepcopy(task.get("execution_amendment", {})))
        task["execution_amendment"] = dict(
            source=receipt["source"], preflight_job=receipt["job_id"],
            full_validation_job="8466227", semantic_acceptance_job="8466211",
            workers="adaptive 1-2", dispatch="shared-fifo", allocated_memory_gb=96,
            node_file_capacity_guard=True, source_core_unchanged=False,
            budgets_unchanged=True)
        task["script"] = wrapper
        task["cpus_per_task"] = 64
        task["dependencies"].append(GATE)
        task["job_name"] = "obj0913v9-" + key.replace("/", "-")
        promoted.append(key)
    for model in MODELS:
        task = tasks[model + "/gather-verify"]
        if task.get("job_id"):
            raise ValueError("gather already submitted")
        task["state"] = "BLOCKED"
        task["continuation_hold"] = "await accepted repaired merge from a successful Slurm pass"
    result["saved_continuation"] = dict(
        preflight=receipt, promoted=promoted, merged=[],
        original_partition_caps=copy.deepcopy(result["partition_submit_caps"]),
        cpu_policy="3 before main submission; 4 before repair submission; one repair maximum",
        scientific_protocol_unchanged=True)
    result["partition_submit_caps"]["ais-htc"] = 3
    result["partition_submit_caps"]["ais-gpu"] = 2
    return result


def release(queue, accepted, job_id, completed):
    if not completed or not str(job_id).isdigit():
        raise ValueError("repair job is not COMPLETED with exit 0:0")
    result = copy.deepcopy(queue)
    tasks = result["tasks"]
    for model, evidence in accepted.items():
        if model not in MODELS:
            raise ValueError("unknown model")
        metrics = evidence["metrics"]
        if (metrics.get("attempts") != 6672 or
                metrics.get("unexplained_disagreements") != 0 or
                metrics.get("all_planned_attempts_accounted") is not True or
                evidence.get("stage") != "gather-verification-repaired" or
                not evidence.get("manifest_sha256")):
            raise ValueError("incomplete or inconsistent merge")
        if model in result["saved_continuation"]["merged"]:
            continue
        task = tasks[model + "/gather-verify"]
        if task.get("job_id"):
            raise ValueError("cannot replace a submitted gather")
        task["superseded_raw_dependencies"] = task["dependencies"][:]
        task["dependencies"] = [GATE]
        task.update(job_id=str(job_id), state="COMPLETED", external=True,
                    repair_evidence=copy.deepcopy(evidence))
        task.pop("continuation_hold", None)
        result["saved_continuation"]["merged"].append(model)
    # Only descendants of accepted merges may be released, never failed jobs or submit errors.
    allowed = set()
    for model in result["saved_continuation"]["merged"]:
        allowed.update(model + "/main-extract-" + str(i) for i in range(8))
        allowed.update(model + "/" + suffix for suffix in ("gather-extract", "measure", "analyze"))
    changed = True
    while changed:
        changed = False
        for key in allowed:
            task = tasks[key]
            if (not task.get("job_id") and task["state"] == "BLOCKED"
                    and not task.get("submit_error")
                    and all(tasks[d]["state"] not in BAD for d in task["dependencies"])):
                task["state"] = "WAITING"
                changed = True
    if set(result["saved_continuation"]["merged"]) == set(MODELS):
        result["partition_submit_caps"]["ais-htc"] = 4
    return result
