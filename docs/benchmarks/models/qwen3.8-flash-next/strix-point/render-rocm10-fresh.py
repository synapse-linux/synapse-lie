#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify collected Point campaigns and render portable fresh-prompt results."""

import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import statistics
import tarfile
import tempfile


ROOT = Path(__file__).resolve().parent
SOURCE = "1877b03"
IMAGE = "sha256:89c6f9da64694da226948bca7b50d5e4e38caab9e138cb5cbe8678b7778cbe7e"
SIZES = {"fresh128": (1500, 8000, 8192, 32768, 131072),
         "fresh256": (258794,)}
NAMES = ("manifest.json", "runner.py", "result.json", "measurements.jsonl",
         "telemetry.jsonl", "supervisor.exit", "supervisor.stdout",
         "supervisor.stderr", "stdout.log", "stderr.log",
         "distrobox-create.log", "distrobox.stdout.log", "distrobox.stderr.log",
         "remote-files.json")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def collect(evidence, profile, arm):
    path = evidence / f"rocm10-point-distrobox-fresh{profile[-3:]}-{arm}-k715-r1"
    if not path.is_dir():
        raise ValueError(f"Missing completed campaign: {path}")
    remote = json.loads((path / "remote-files.json").read_text())
    files = {name: (path / name).read_bytes() for name in NAMES}
    for name, content in files.items():
        if name != "remote-files.json" and digest(content) != remote[name]:
            raise ValueError(f"Collected file differs from remote: {name}")
    local = {str(file.relative_to(path)): digest(file.read_bytes())
             for file in path.rglob("*") if file.is_file() and file.name != "remote-files.json"}
    if local != remote:
        raise ValueError("Full remote file inventory differs from local collection")
    destination = ROOT / "data" / f"rocm10-{profile}-{arm}.tar.gz"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destination, "w:gz") as archive:
        for name, content in files.items():
            info = tarfile.TarInfo(name)
            info.size = len(content)
            info.mtime = 0
            info.mode = 0o644
            archive.addfile(info, io.BytesIO(content))
    return destination


def read_archive(path, profile, arm):
    with tarfile.open(path, "r:gz") as archive:
        if sorted(archive.getnames()) != sorted(NAMES):
            raise ValueError("Unexpected portable campaign inventory")
        files = {name: archive.extractfile(name).read() for name in NAMES}
    remote = json.loads(files["remote-files.json"])
    for name, content in files.items():
        if name != "remote-files.json" and digest(content) != remote[name]:
            raise ValueError(f"Portable file differs from verified remote: {name}")
    manifest = json.loads(files["manifest.json"])
    result = json.loads(files["result.json"])
    if (manifest["source_commit"] != SOURCE or manifest["image"] != IMAGE or
        manifest["bench_profile"] != f"fresh-{profile[-3:]}k" or
        manifest["bench_impl"] != arm or manifest["stack"] != "rocm10-fedora43"):
        raise ValueError("Campaign identity mismatch")
    if (result["state"] != "PASSED" or result["exit_code"] != 0 or
        result["child_exit_code"] != 0 or files["supervisor.exit"].strip() != b"0" or
        not result["model_stat_unchanged"] or result["cleanup_failures"] or
        result["service_after"]["ActiveState"] != "active" or
        not result.get("lease_released_at")):
        raise ValueError("Campaign exit or cleanup incomplete")
    if (result["manifest_sha256"] != digest(files["manifest.json"]) or
        result["runner_sha256"] != digest(files["runner.py"]) or
        result["bench_result"]["measurements_sha256"] != digest(files["measurements.jsonl"])):
        raise ValueError("Campaign provenance mismatch")
    rows = [json.loads(line) for line in files["measurements.jsonl"].splitlines()]
    samples = [row for row in rows if row.get("event") == "sample"]
    inputs = [row for row in rows if row.get("event") == "input"]
    expected = len(SIZES[profile]) * 2
    if (rows[-1] != {"event": "complete", "exit_code": 0} or
        len(samples) != expected or len(inputs) != len(SIZES[profile]) or
        result["bench_result"]["samples"] != expected):
        raise ValueError("Campaign sample count or completion mismatch")
    temperatures = {}
    for line in files["telemetry.jsonl"].splitlines():
        for sensor in json.loads(line)["temperatures"]:
            name = sensor["name"]
            temperatures[name] = max(temperatures.get(name, -1), sensor["value_c"])
    return samples, inputs, temperatures, {"archive_sha256": digest(path.read_bytes()),
                                   "remote_file_inventory_count": len(remote),
                                   "measurements_sha256": digest(files["measurements.jsonl"]),
                                   "lease_released_at": result["lease_released_at"]}


def render(profile):
    arms = {}
    receipt = {"schema": "synapse-lie.point-rocm10-fresh.v1",
               "source_commit": SOURCE, "image": IMAGE, "profile": profile, "arms": {}}
    for arm in ("lie", "gufo"):
        archive = ROOT / "data" / f"rocm10-{profile}-{arm}.tar.gz"
        arms[arm], inputs, temperatures, identity = read_archive(archive, profile, arm)
        if arm == "lie":
            reference_inputs = inputs
        else:
            for index, (left, right) in enumerate(zip(reference_inputs, inputs)):
                for field in ("physical_ids_sha256", "prompt_tokens", "context_capacity"):
                    if left[field] != right[field]:
                        raise ValueError(f"Physical input mismatch at point {index}: {field}")
        receipt["arms"][arm] = {**identity, "temperatures_max_c": temperatures}
    for index, (left, right) in enumerate(zip(arms["lie"], arms["gufo"])):
        for field in ("prompt_tokens", "prefill_tokens_per_user", "output_tokens_per_user",
                      "full_output_budget", "output_ids", "prefill_logits_sha256",
                      "decode_logits_sha256"):
            if left[field] != right[field]:
                raise ValueError(f"Same-stack parity failure at sample {index}: {field}")
        if (left["prompt_tokens"] != SIZES[profile][index // 2] or
            left["output_tokens_per_user"] != 128 or not left["full_output_budget"]):
            raise ValueError(f"Incomplete output at sample {index}")
    receipt["matched_samples"] = len(arms["lie"])
    summary = []
    for size in SIZES[profile]:
        for arm in ("lie", "gufo"):
            samples = [row for row in arms[arm] if row["prompt_tokens"] == size]
            row = {"prompt_tokens": size, "arm": arm, "repetitions": len(samples)}
            for column, field, scale in (("prefill_tps", "prefill_tps", 1),
                                         ("decode_tps", "decode_tps", 1),
                                         ("prefill_seconds", "prefill_ns", 1e-9),
                                         ("decode_seconds", "decode_ns", 1e-9)):
                values = [sample[field] * scale for sample in samples]
                row.update({column + "_median": statistics.median(values),
                            column + "_min": min(values), column + "_max": max(values)})
            summary.append(row)
    charts = ROOT / "charts"
    charts.mkdir(exist_ok=True)
    csv_path = charts / f"rocm10-{profile}.csv"
    with csv_path.open("w", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(summary[0]),
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(summary)
    (charts / f"rocm10-{profile}.json").write_text(json.dumps(receipt, indent=2) + "\n")
    os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="lie-point-mpl-"))
    import matplotlib
    matplotlib.use("Agg")
    matplotlib.rcParams["svg.hashsalt"] = "synapse-lie-strix-point-rocm10"
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    for arm, color, marker in (("lie", "#1663a1", "o"), ("gufo", "#b25b17", "s")):
        selected = [row for row in summary if row["arm"] == arm]
        x = list(range(len(selected)))
        for ax, column in zip(axes, ("prefill_tps", "decode_tps")):
            center = [row[column + "_median"] for row in selected]
            lower = [row[column + "_median"] - row[column + "_min"] for row in selected]
            upper = [row[column + "_max"] - row[column + "_median"] for row in selected]
            ax.errorbar(x, center, yerr=[lower, upper], label=arm.upper(),
                        color=color, marker=marker, capsize=3)
    axes[0].set_ylabel("Prefill tokens/s")
    axes[1].set_ylabel("Decode tokens/s")
    axes[1].set_xlabel("Fresh physical prompt tokens")
    for ax in axes:
        ax.set_xticks(list(range(len(SIZES[profile]))),
                      [f"{size:,}" for size in SIZES[profile]])
        ax.set_ylim(bottom=0)
        ax.grid(alpha=0.2)
        ax.legend()
    label = "through 128K" if profile == "fresh128" else "near 256K"
    figure.suptitle(f"Strix Point ROCm 10 fresh prompt {label}; two samples per arm")
    figure.tight_layout()
    for extension in ("svg", "png"):
        metadata = {"Date": None} if extension == "svg" else None
        figure.savefig(charts / f"rocm10-{profile}.{extension}", dpi=180,
                       metadata=metadata)
    for ax, column in zip(axes, ("prefill_tps", "decode_tps")):
        low = min(row[column + "_min"] for row in summary)
        high = max(row[column + "_max"] for row in summary)
        margin = max((high - low) * 0.15, high * 0.005)
        ax.set_ylim(low - margin, high + margin)
    for extension in ("svg", "png"):
        metadata = {"Date": None} if extension == "svg" else None
        figure.savefig(charts / f"rocm10-{profile}-detail.{extension}", dpi=180,
                       metadata=metadata)
    plt.close(figure)
    print(f"Verified {receipt['matched_samples']} LIE/Gufo pairs; wrote {csv_path}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=SIZES)
    parser.add_argument("--collect", type=Path,
                        help="Verified local evidence directory; omit to reproduce published archives")
    args = parser.parse_args()
    if args.collect:
        for arm in ("lie", "gufo"):
            collect(args.collect, args.profile, arm)
    render(args.profile)


if __name__ == "__main__":
    main()
