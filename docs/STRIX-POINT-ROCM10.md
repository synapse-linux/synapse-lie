<!-- SPDX-License-Identifier: MIT -->
# Strix Point ROCm 10.0.0 comparison

This experiment builds the unchanged LIE `gfx1150` numerical slice with ROCm
10.0.0 inside Fedora 43 on `pop@192.168.5.161`, then compares direct original
UD-Q4_K_XL inference against the recorded ROCm 7.2 baseline on the same HX 370.
The candidate changes the distribution, compiler, HIP runtime and math libraries
together. Throughput differences therefore describe this complete stack, not an
isolated ROCm library effect.

AMD publishes an official [ROCm 10.0.0 developer image for Ubuntu
24.04](https://hub.docker.com/r/rocm/dev-ubuntu-24.04/tags). The only AMD
`dev-fedora` image found is [Fedora 24 with ROCm
1.6.4](https://hub.docker.com/r/rocm/dev-fedora-24/tags), unsuitable for this
test. This experiment instead uses the [Fedora Project base
image](https://www.fedoraproject.org/wiki/Container_SIG) at the amd64 manifest
`sha256:71fb350cb108e8864a11ce70ae7ef2df9167570ba8215d8b7de839a680dea751`
and AMD's official [gfx1150 ROCm 10.0.0
tarball](https://rocm.docs.amd.com/projects/install-on-linux/en/latest/install/install-overview.html).
The tarball URL is
`https://stable.repo.amd.com/rocm/core/tarball/therock-dist-linux-gfx1150-10.0.0.tar.gz`;
the downloaded 1770580920 bytes have SHA-256
`e2fc089e2874dcff88384f387d5bb0553ac1392d5cd1c96d6ade0233a94a8c4b`.
The [Dockerfile](../docker/strix-point-rocm10-fedora43.Dockerfile) verifies that
hash before extraction. No host ROCm or driver packages are replaced.

AMD's [ROCm 10 compatibility
matrix](https://rocm.docs.amd.com/en/latest/compatibility/compatibility-matrix.html)
does not qualify Fedora or Pop!_OS for this Ryzen APU. Container build success
alone cannot establish kernel-driver/runtime compatibility. A GPU probe, exact
prompt/output parity, full output completion, thermal/client/lease receipts and
fresh collection remain required before performance claims.

The baseline is the completed [Strix Point direct benchmark
report](STRIX-POINT-BENCHMARK-RESULT.md). The comparison uses the same verified
four-shard model, fixed Gufo source pin, LIE source, benchmark executable,
workload profiles, `gfx1150` target, one-second observer, lower published sensor
limits and manifest-scoped 100 C ceiling. The new image is identified by its
local Docker image ID and each compiled artifact by SHA-256. `single`,
`fresh-128k`, `fresh-256k`, `multi` and the independent Gufo reference are the
intended matched profiles. A failure is retained as a failure; there is no
automatic retry or inferred throughput.

The [one-shot campaign runner](../tools/strix-point-campaign.py) selects ROCm 10
only for an explicit `rocm10-fedora43` manifest and pinned image ID. Its build
action runs without `/dev/kfd`, `/dev/dri` or network, under the same .161 lease,
foreign-client checks, service stop/restore and sensor guard as inference. The
ROCm 7.2 path remains the default for historical manifests. The
[compile helper](../tools/strix-point-rocm10-compile.py) retains actual exits,
logs, library hashes and linked binary hashes under the persistent .161 LIE
directory. The official Gufo source was independently fetched at
`f783fedb9bea2ec7de941f6da4e02f4a4596b29e`; no sibling project source
or artifact is used.

Results and comparison tables will be entered from collected raw receipts after
the image, compile, GPU probe and original-weight runs complete.
