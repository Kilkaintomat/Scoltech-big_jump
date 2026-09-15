"""Host-only admission policy. Never writes to any protected queue."""
MODELS = ("deepseek", "goedel", "kimina")


def release_reason(queue, active_gpu_jobs, manifests_present):
    tasks = queue.get("tasks", {})
    required = [m + "/main-extract-" + str(s) for m in MODELS for s in range(8)]
    if any(tasks.get(k, {}).get("state") != "COMPLETED" for k in required):
        return False, "waiting_for_all_protected_main_extraction_shards"
    if not manifests_present:
        return False, "waiting_for_protected_extraction_manifests"
    if active_gpu_jobs:
        return False, "waiting_for_idle_gpu_submission_slots"
    return True, "protected_gpu_extraction_complete"
