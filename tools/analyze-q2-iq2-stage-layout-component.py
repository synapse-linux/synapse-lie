#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reduce the collected stage-layout GPU component without model claims."""

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
LABEL = "q2-iq2-stage-layout-r2-component-r1"
EVIDENCE = ROOT / "evidence" / LABEL
REPORT = ROOT / "config/q2-iq2-stage-layout-component-results.json"
EXPECTED_CASES = {
    *(f"fixed-edge-n{n}" for n in (1, 17, 65, 145, 255, 256, 257, 409, 512)),
    "uniform-e160", "uniform-e512", "skew-e64",
    "real-layer0", "real-layer3", "real-layer22",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def main() -> None:
    require(not REPORT.exists(), "Preserve the existing component report")
    plan = json.loads((ROOT / "config/q2-iq2-stage-layout-r2-plan.json").read_text())
    require(plan["components"] == [{"label": LABEL, "mode": "iq2-stage-layout-check",
                                     "variant": "iq2-stage-layout"}], "Frozen scope changed")
    release_path = ROOT / "config/q2-iq2-stage-layout-r2-window-release.json"
    release = json.loads(release_path.read_text())
    require(release["state"] == "Q2_IQ2_STAGE_LAYOUT_WINDOW_RELEASED" and
            release["plan_sha256"] == sha(ROOT / "config/q2-iq2-stage-layout-r2-plan.json") and
            release["kfd"] == [] and release["model_stats_unchanged"] and
            len(release["cohorts"]) == 2 and
            release["cohorts"][1]["label"] == LABEL and
            release["cohorts"][1]["command_exits"] == [0, 0, 0],
            "GPU release or component closure differs")
    result = json.loads((EVIDENCE / "results/result.json").read_text())
    collection = json.loads((EVIDENCE / "collection.json").read_text())
    require(result["mode"] == "iq2-stage-layout-check" and
            result["state"] == "SYNTHETIC_OPERATORS_PASS_NOT_MODEL_QUALIFIED" and
            result["finished_at"] and not result["model_access"] and
            [row["exit_code"] for row in result["commands"]] == [0, 0, 0] and
            result["postflight_kfd"] == [], "Component result differs")
    require(collection["verified_artifacts"] == 4 and
            collection["sha256"] == sha(EVIDENCE / "results.tar.gz"),
            "Component archive differs")
    log = EVIDENCE / "results/03.log"
    require(sha(log) == result["artifacts"]["03.log"]["sha256"],
            "Timed log differs from remote receipt")
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    count = Counter(row["event"] for row in rows)
    require(count == {"iq2_stage_layout_map": 15, "iq2_stage_layout_replay": 51,
                      "iq2_stage_layout_timing": 84, "iq2_stage_layout_complete": 1},
            "Component event census differs")
    maps = [row for row in rows if row["event"] == "iq2_stage_layout_map"]
    require({row["case"] for row in maps} == EXPECTED_CASES and
            all(row["row_coverage_exact"] and
                row["candidate_wide128"] == row["reference_wide128"] and
                row["candidate_tail64"] == row["reference_tail64"] for row in maps),
            "Original route maps changed")
    replays = [row for row in rows if row["event"] == "iq2_stage_layout_replay"]
    require(all(row["exact"] and row["guards_exact"] and
                row["changed_values"] == row["nonfinite_values"] ==
                row["unwritten_values"] == 0 and
                row["reference_sha256"] == row["candidate_sha256"]
                for row in replays), "Whole-output or guard parity failed")
    completions = [row for row in rows if row["event"] == "iq2_stage_layout_complete"]
    require(completions[0]["numerical_pass"] and
            not completions[0]["model_inference"], "Fixture did not complete")
    timings = [row for row in rows if row["event"] == "iq2_stage_layout_timing"]
    require(all(not row["hip_timer_valid"] and row["raw_hip_ms"] == 0 and
                row["raw_hip_bits"] == 0 and row["iterations"] == 3 and
                row["wall_us_per_iteration"] > 0 for row in timings),
            "Timer validity or iteration count differs")
    samples = defaultdict(lambda: defaultdict(dict))
    for row in timings:
        require(row["case"] in EXPECTED_CASES and 0 <= row["rep"] < 7,
                "Unexpected timing case or repetition")
        key = "candidate" if row["candidate"] else "retained"
        require(key not in samples[row["case"]][row["rep"]], "Duplicate arm")
        samples[row["case"]][row["rep"]][key] = row["wall_us_per_iteration"]
    summary = {}
    for name in sorted(samples):
        by_rep = samples[name]
        require(set(by_rep) == set(range(7)) and
                all(set(pair) == {"retained", "candidate"} for pair in by_rep.values()),
                "Missing arm or repetition")
        measured = [by_rep[rep] for rep in range(2, 7)]
        old = [pair["retained"] for pair in measured]
        new = [pair["candidate"] for pair in measured]
        paired = [(b / a - 1) * 100 for a, b in zip(old, new)]
        summary[name] = {
            "retained_wall_us": old,
            "candidate_wall_us": new,
            "retained_median_us": median(old),
            "candidate_median_us": median(new),
            "median_time_change_percent": (median(new) / median(old) - 1) * 100,
            "paired_time_change_percent": paired,
            "paired_median_percent": median(paired),
        }
    report = {
        "schema": "synapse-lie.q2-iq2-stage-layout-component-results.v1",
        "plan_sha256": sha(ROOT / "config/q2-iq2-stage-layout-r2-plan.json"),
        "release_sha256": sha(release_path),
        "archive_sha256": collection["sha256"],
        "timed_log_sha256": sha(log),
        "command_exits": [0, 0, 0],
        "event_counts": dict(count),
        "exact_route_maps": len(maps),
        "exact_guarded_whole_output_replays": len(replays),
        "hip_event_durations_valid": 0,
        "wall_time_repetitions_per_arm": 5,
        "cases": summary,
        "model_run": False,
        "production_dispatch_changed": False,
        "decision": "Do not promote: saved routing layers are effectively flat or slower; no complete-model gain established.",
    }
    REPORT.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({name: round(row["median_time_change_percent"], 3)
                      for name, row in summary.items()}))


if __name__ == "__main__":
    main()
