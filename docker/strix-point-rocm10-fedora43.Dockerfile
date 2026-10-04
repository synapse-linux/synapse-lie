# SPDX-License-Identifier: MIT
# Fedora build/runtime environment for the isolated gfx1150 ROCm 10 comparison.
# The Fedora amd64 manifest and AMD tarball SHA-256 are pinned at build time.
FROM registry.fedoraproject.org/fedora@sha256:71fb350cb108e8864a11ce70ae7ef2df9167570ba8215d8b7de839a680dea751

RUN dnf -y --setopt=install_weak_deps=False install \
      ca-certificates cmake gcc-c++ git libcurl-devel libdrm-devel \
      libicu-devel libjpeg-turbo-devel libpng-devel libuv-devel \
      llhttp-devel ninja-build openssl-devel pkgconf-pkg-config \
      python3 json-c-devel libgfortran numactl-libs && \
    dnf clean all

ARG ROCM_TARBALL_SHA256
COPY therock-dist-linux-gfx1150-10.0.0.tar.gz /tmp/rocm.tar.gz
RUN test -n "$ROCM_TARBALL_SHA256" && \
    echo "$ROCM_TARBALL_SHA256  /tmp/rocm.tar.gz" | sha256sum -c - && \
    mkdir -p /opt/rocm && \
    tar -xzf /tmp/rocm.tar.gz -C /opt/rocm && \
    test -x /opt/rocm/bin/hipcc && \
    rm /tmp/rocm.tar.gz

ENV ROCM_PATH=/opt/rocm HIP_PATH=/opt/rocm \
    PATH=/opt/rocm/bin:$PATH LD_LIBRARY_PATH=/opt/rocm/lib
