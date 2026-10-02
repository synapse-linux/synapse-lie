# SPDX-License-Identifier: MIT
# Fedora Minimal 44 + AMD's signed ROCm 10 gfx1150 RPMs, mirroring the
# distribution/package method observed in the Kyuz0 gfx1151 image on .157.
# This independently authored image contains no DS4 source or build artifact.
FROM registry.fedoraproject.org/fedora-minimal@sha256:dbc66957b83be679a2fb8ed8964a8b47c60a75567b527a7362976cc714e70a3c

RUN printf '%s\n' \
      '[amdrocm-stable]' \
      'name=AMD ROCm Core 10.0' \
      'baseurl=https://stable.repo.amd.com/rocm/core/packages/rhel10/x86_64' \
      'enabled=1' \
      'priority=50' \
      'gpgcheck=1' \
      'gpgkey=https://stable.repo.amd.com/rocm/gpg/packages.gpg' \
      > /etc/yum.repos.d/amdrocm-stable.repo && \
    microdnf -y --nodocs --setopt=install_weak_deps=0 install \
      amdrocm-core-devel10.0-gfx1150 \
      ca-certificates cmake gcc-c++ git libcurl-devel libdrm-devel \
      libicu-devel libjpeg-turbo-devel libpng-devel libuv-devel \
      llhttp-devel ninja-build openssl-devel pkgconf-pkg-config \
      python3 json-c-devel libgfortran numactl-libs && \
    microdnf clean all && \
    ln -s core-10.0 /opt/rocm/core && \
    ln -s core-10.0/bin /opt/rocm/bin && \
    ln -s core-10.0/include /opt/rocm/include && \
    ln -s core-10.0/lib /opt/rocm/lib && \
    ln -s core-10.0/lib/llvm /opt/rocm/llvm && \
    test -x /opt/rocm/bin/hipcc

ENV ROCM_PATH=/opt/rocm HIP_PATH=/opt/rocm \
    PATH=/opt/rocm/bin:/opt/rocm/core/bin:/opt/rocm/core/lib/llvm/bin:$PATH \
    LD_LIBRARY_PATH=/opt/rocm/core/lib/rocm_sysdeps/lib:/opt/rocm/core/lib
