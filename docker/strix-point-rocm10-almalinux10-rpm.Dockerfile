# SPDX-License-Identifier: MIT
# Official AlmaLinux 10.2 minimal amd64 image with AMD's signed gfx1150 RPMs.
FROM docker.io/library/almalinux@sha256:385fe0d1cd8434c6051ee4cd6317e6035c043f32f042b84a5e38521b8d37d4cf

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
      amdrocm-core-devel10.0-gfx1150 gcc-c++ python3 && \
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

COPY hip-smoke.cpp /src/hip-smoke.cpp
RUN mkdir -p /opt/lie && \
    /opt/rocm/bin/hipcc --offload-arch=gfx1150 -std=c++17 -O2 \
      /src/hip-smoke.cpp -o /opt/lie/hip-smoke
