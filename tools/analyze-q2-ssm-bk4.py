#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate and summarize the completed original-Q8 SSM component."""
import hashlib
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence/q2-ssm-bk4-component-r1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    collected = json.loads((EVIDENCE / "collection.json").read_text())
    for name, expected in collected.items():
        assert sha(EVIDENCE / name) == expected, name
    plan = json.loads((EVIDENCE / "plan.json").read_text())
    assert sha(EVIDENCE / "plan.json") == sha(ROOT / "config/q2-ssm-bk4-plan.json")
    for name, expected in plan["staged_sha256"].items():
        assert sha(EVIDENCE / name) == expected, name
    result = json.loads((EVIDENCE / "result.json").read_text())
    released = json.loads((EVIDENCE / "release.json").read_text())
    assert result["exit_code"] in (0, 1) and result["stop_reason"] is None
    assert released["component_result_sha256"] == sha(EVIDENCE / "result.json")
    assert released["kfd"] == [] and released["leases_free"] == 5
    assert released["models_unchanged"] == 7 and not released["remote_cleanup"]
    assert any(row["pid"] == result["pid"] and row["start_ticks"] == result["start_ticks"]
               for row in released["retired_identities"])
    lines = (EVIDENCE / "component.stdout").read_text().splitlines()
    rows = [json.loads(line) for line in lines if line.startswith("{")]
    replay = [row for row in rows if row["event"] == "ssm_bk4_replay"]
    # Reuse the unchanged independent oracle, including its original event name.
    oracle = [row for row in rows if row["event"] == "ssm_resident_oracle"]
    timing = [row for row in rows if row["event"] == "ssm_bk4_timing"]
    completed = [row for row in rows if row["event"] == "ssm_bk4_complete"]
    assert len(replay) == 72 and all(row["guards_exact"] for row in replay)
    replay_pass = all(row["exact"] for row in replay)
    assert len(oracle) == 144 and all(row["limit"] == 0.002 for row in oracle)
    oracle_pass = all(row["pass"] for row in oracle)
    assert len(timing) == 14 and len(completed) == 1
    assert completed[0]["safe_completion"]
    numerical_pass = replay_pass and oracle_pass
    assert bool(completed[0]["numerical_pass"]) == numerical_pass
    assert result["exit_code"] == (0 if numerical_pass else 1)
    assert all(row["tokens"] == 2048 and row["weight_bytes"] == 133693440 and
               row["iterations"] == 3 and row["completed_wall_us"] > 0 for row in timing)
    assert all(not row["gpu_event_valid"] or row["gpu_event_us"] > 0 for row in timing)
    measured = [row for row in timing if not row["warmup"]]
    arms = {}
    for candidate, name in ((False, "retained"), (True, "bk4")):
        values = [row["completed_wall_us"] for row in measured if row["candidate"] == candidate]
        assert len(values) == 5
        arms[name] = dict(samples_us=values, median_us=statistics.median(values),
                          mean_us=statistics.mean(values), minimum_us=min(values), maximum_us=max(values))
    pairs = []
    for rep in sorted({row["rep"] for row in measured}):
        pair = {row["candidate"]: row for row in measured if row["rep"] == rep}
        assert len(pair) == 2
        pairs.append(dict(rep=rep, time_change_percent=100 *
                          (pair[True]["completed_wall_us"] / pair[False]["completed_wall_us"] - 1)))
    report = dict(schema="synapse-lie.q2-ssm-bk4-results.v1",
                  evidence=str(EVIDENCE.relative_to(ROOT)),
                  raw_artifacts_sha256=collected,
                  release_sha256=sha(EVIDENCE / "release.json"),
                  component_exit_code=result["exit_code"],
                  exact_output_pairs=len(replay), independent_oracle_checks=len(oracle),
                  max_oracle_relative_rms=max(row["relative_rms"] for row in oracle),
                  timer="completed host monotonic wall time, per complete projection/convolution call",
                  numerical_pass=numerical_pass,
                  invalid_gpu_events=sum(not row["gpu_event_valid"] for row in timing),
                  resources=[row for row in rows if row["event"] == "ssm_bk4_resources"],
                  all_timings=timing,
                  measured=arms, paired_changes=pairs,
                  median_time_change_percent=100 *
                  (arms["bk4"]["median_us"] / arms["retained"]["median_us"] - 1),
                  decision=("Component improves; model qualification still required"
                            if numerical_pass and all(p["time_change_percent"] < 0 for p in pairs)
                            else "No component promotion; retain current production dispatch"),
                  model_trial=False, model_throughput_gain=False, goal_met=False)
    output = ROOT / "config/q2-ssm-bk4-results.json"
    with output.open("x") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({key: report[key] for key in (
        "exact_output_pairs", "independent_oracle_checks", "max_oracle_relative_rms",
        "median_time_change_percent", "decision")}))


if __name__ == "__main__":
    main()
