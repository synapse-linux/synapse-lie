#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare one unchanged-tile SSM wave assignment and its matched fixture."""
import datetime
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ssm", ROOT / "tools/prepare-q2-ssm-row-group.py")
ssm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssm)


def main():
    inc = ROOT / "experiments/q2-ssm-wave-balance.inc"
    fixture = ROOT / "tests/q2_ssm_wave_balance.hip"
    out = ROOT / "evidence/q2-ssm-wave-balance-preparation"
    manifest = ROOT / "config/q2-ssm-wave-balance-source.json"
    if any(path.exists() for path in (inc, fixture, out, manifest)):
        raise ValueError("Preserve existing experiment")
    parent_path = ROOT / "config/q2-iq2-fixed-bounds-source.json"
    parent = json.loads(parent_path.read_text())["variants"]["iq2-fixed-bounds"]
    base = ROOT / parent["source"]
    if ssm.inventory(base) != parent["files"]:
        raise ValueError("Retained provider differs")
    original = (base / ssm.REL).read_text()
    kernel = ssm.function(original, "template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,")
    kernel = kernel.replace("DenseF16GEMMKernel", "DenseSsmWaveBalanceKernel")
    kernel = ssm.once(kernel,
        "          static_assert(BM == 256 && BN == 128 && BK == 2 && WM == 8 &&\n                        WN == 1);",
        "          static_assert(BM == 256 && BN == 128 && BK == 2 && WM == 4 &&\n                        WN == 2);")
    wrapper = ssm.function(original, "bool DenseF16SsmGemm(")
    wrapper = wrapper.replace("DenseF16SsmGemm", "DenseSsmWaveBalance")
    wrapper = ssm.once(wrapper,
        "DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, true>",
        "DenseSsmWaveBalanceKernel<256, 128, 2, 4, 2, 1, false, true>")
    source = ("// SPDX-License-Identifier: MIT\n"
              "// Private experiment derived from the retained Gufo provider.\n"
              "// Same tile, K16 accumulation order, Q8/F16 rounding and convolution.\n"
              + kernel + "\n" + wrapper + "\n")
    formatted = subprocess.run(["clang-format", "--style=file:" + str(base / ".clang-format")],
                               input=source, text=True, capture_output=True, check=True)
    inc.write_text(formatted.stdout)
    test = (ROOT / "tests/q2_ssm_resident.hip").read_text()
    test = test.replace("resident-fence composition", "wave-balance assignment")
    test = test.replace("experiments/q2-ssm-resident-fence-draft.inc", str(inc.relative_to(ROOT)))
    test = test.replace("DenseSsmResidentFence", "DenseSsmWaveBalance")
    test = test.replace("ssm_resident", "ssm_wave_balance").replace("results/ssm-resident-", "results/ssm-wave-balance-")
    test = ssm.once(test, "DenseSsmWaveBalanceKernel<128, 128, 2, 4, 2, 1, false,",
                         "DenseSsmWaveBalanceKernel<256, 128, 2, 4, 2, 1, false,")
    formatted = subprocess.run(["clang-format", "--style=file:" + str(base / ".clang-format")],
                               input=test, text=True, capture_output=True, check=True)
    fixture.write_text(formatted.stdout)
    out.mkdir()
    argv = json.loads((ROOT / "evidence/q2-ssm-resident-fixture-preparation/compile-argv.json").read_text())
    argv[argv.index("-c") + 1] = str(fixture.relative_to(ROOT))
    argv[argv.index("-o") + 1] = str(out / "fixture.o")
    commands = []
    for label, args in (("object", argv),
                        ("assembly", [a for a in argv if a != "-c"] + ["--offload-device-only", "-S"])):
        if label == "assembly":
            args[args.index("-o") + 1] = str(out / "candidate.s")
        started = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (out / (label + ".stdout")).open("x") as stdout, (out / (label + ".stderr")).open("x") as stderr:
            result = subprocess.run(args, cwd=ROOT, stdout=stdout, stderr=stderr)
        record = dict(argv=args, started_at=started,
                      finished_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      exit_code=result.returncode)
        commands.append(record)
        (out / "commands.json").write_text(json.dumps(commands, indent=2) + "\n")
        if result.returncode:
            raise RuntimeError("Compile failed: " + label)
    result = dict(schema="synapse-lie.q2-ssm-wave-balance-source.v1",
                  parent_manifest=str(parent_path.relative_to(ROOT)),
                  parent_manifest_sha256=ssm.sha(parent_path),
                  provider=parent["source"], provider_files=len(parent["files"]),
                  bindings={str(p.relative_to(ROOT)): ssm.sha(p) for p in
                            (inc, fixture, Path(__file__).resolve(),
                             ROOT / "experiments/q2-ssm-resident-oracle.inc")},
                  unchanged_tile=[256, 128, 2], waves_before=[8, 1], waves_candidate=[4, 2],
                  logical_lds_operand_bytes_per_lane_k32_before=640,
                  logical_lds_operand_bytes_per_lane_k32_candidate=512,
                  same_grid=True, same_rounding=True, same_k16_order=True,
                  changed_production_dispatch=False, gpu_run=False, model_run=False,
                  object_sha256=ssm.sha(out / "fixture.o"),
                  assembly_sha256=ssm.sha(out / "candidate.s"))
    manifest.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
