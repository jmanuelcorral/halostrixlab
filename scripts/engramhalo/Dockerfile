# EngramHalo image recipe — NOT YET BUILT (see README.md "Build" section).
#
# This Dockerfile is a *repository artifact only*: it has not been built, no
# image has been pulled, and no build was executed to produce this file. It
# is prepared for a later, explicitly approved build phase run by a human
# operator against a real Docker/Podman daemon. Nothing in this file causes
# opencode or any agent in this repository to build, pull, or run it.
#
# Pinned source (read-only, verified via GitHub API on 2026-09-16, see
# scripts/engramhalo/README.md for exact commands used to confirm this):
#   repo:      https://github.com/Aristo94/EngramHalo.cpp.git
#   branch:    strix-halo-qwen4exp   (mutable ref, NOT trusted by itself)
#   commit:    15176583b358d791b7a73f210ef4ab9e167cfba7   (the actual pin)
#   .gitmodules at that commit: present but empty (size=0) — no submodules
#   to worry about; this build still verifies that fact defensively below.
#
# Packaging patches (same exact commit hash, shared commit object with the
# EngramHalo.cpp source repo via a fork relationship — this is not a
# coincidence, halo-box/strix-llama.cpp shares history with
# Aristo94/EngramHalo.cpp) pinned at:
#   repo:   https://github.com/halo-box/strix-llama.cpp.git
#   commit: 15176583b358d791b7a73f210ef4ab9e167cfba7
#   files:  docs/strix-halo/llama-cpp-25992-rocm-host-buffer.patch
#           docs/strix-halo/llama-cpp-qwen38-per-buffer-mmap.patch
#
# Base images are pinned by digest, fetched anonymously (no token published,
# no secret involved) from the Fedora registry on 2026-09-16T13:52Z. These
# digests point at multi-arch OCI image indexes; they will need to be
# re-verified at actual build time since they are not guaranteed to be
# immutable forever on a re-tagged registry, only the specific manifest
# digest recorded here is what was observed:
#   registry.fedoraproject.org/fedora:44
#     -> sha256:61beafd34111e1cb85fb49377ceadeee0a53622dbc20670ed8ca303f0e17ed9c
#   registry.fedoraproject.org/fedora-minimal:44
#     -> sha256:dd3488a176bb158bde9deeef3f687023fc83aaad91f523e3ce81e078bf5bb473
#
# KNOWN LIMITATION (documented, not solved here): repo.amd.com/rocm package
# repos are mutable by design (dnf resolves whatever is currently published
# under packages-multi-arch/rhel10/x86_64 at build time, GPG-verified against
# the existing repo.amd.com key but NOT pinned to an exact package NEVRA in
# this recipe). Pinning the git source commit does NOT make this Dockerfile
# bit-reproducible; only the source tree and base OS image are pinned here.
# A fully reproducible build would additionally need to pin every ROCm
# package NEVRA and re-verify their signatures/hashes out of band; that is
# explicitly out of scope for this pass.
#
# Network policy: this recipe only fetches (a) the two pinned git sources
# above, (b) the Fedora base images by digest, and (c) ROCm packages from
# the AMD RHEL10 repo via dnf/microdnf with GPG verification against the
# existing repo.amd.com key. It never fetches, converts, or mounts model
# weights, and it must never be extended to do so without separate review.
#
# Runtime image safety notes (see scripts/engramhalo/README.md /
# scripts/engramhalo/llama-server for the wrapper contract this image is
# meant to sit behind): the wrapper sets --entrypoint explicitly to the
# absolute path of llama-server inside the image on every real invocation
# and always passes --user <uid>:<gid> itself; nothing in this image should
# be relied upon to enforce identity — the ENTRYPOINT/CMD below exist only
# for --help/--version smoke and manual inspection, never as the trusted
# security boundary (that boundary is the wrapper + docker run flags).

# ---------------------------------------------------------------------------
# Global ARGs (must precede the FIRST FROM to be visible to every FROM line
# in this file, per Dockerfile ARG scoping rules: an ARG declared after a
# FROM is scoped only to that build stage and is NOT visible to a later
# FROM). Both base-image references are declared here, together, for that
# reason — previously RUNTIME_BASE_IMAGE was declared between the two
# stages, which is fragile/non-portable scoping even where a given
# BuildKit version tolerates it.
# ---------------------------------------------------------------------------
ARG BUILDER_BASE_IMAGE=registry.fedoraproject.org/fedora@sha256:61beafd34111e1cb85fb49377ceadeee0a53622dbc20670ed8ca303f0e17ed9c
ARG RUNTIME_BASE_IMAGE=registry.fedoraproject.org/fedora-minimal@sha256:dd3488a176bb158bde9deeef3f687023fc83aaad91f523e3ce81e078bf5bb473

# ---------------------------------------------------------------------------
# build stage
# ---------------------------------------------------------------------------
FROM ${BUILDER_BASE_IMAGE} AS builder

# Pinned, non-negotiable source references. Overriding these ARGs to a
# different commit defeats the entire point of this recipe; they are ARGs
# only so the exact pin is visible and grep-able in `docker history`, not
# so a caller is expected to change them casually.
ARG ENGRAM_REPO=https://github.com/Aristo94/EngramHalo.cpp.git
ARG ENGRAM_COMMIT=15176583b358d791b7a73f210ef4ab9e167cfba7
ARG PATCH_REPO=https://github.com/halo-box/strix-llama.cpp.git
ARG PATCH_COMMIT=15176583b358d791b7a73f210ef4ab9e167cfba7
# Parallel build worker cap. Default is a conservative fixed 4, NOT
# $(nproc) — the task explicitly calls out not to default to "max cpu all".
ARG BUILD_JOBS=4

# Portable POSIX RUN form (no Dockerfile-heredoc / BuildKit-only `RUN <<EOF`
# frontend assumed): a single classic RUN instruction using printf, so this
# builds under both BuildKit and legacy non-BuildKit Docker/Podman without
# guessing which frontend is active.
RUN set -eu; printf '%s\n' \
  '[rocm]' \
  'name=ROCm 7.14.0' \
  'baseurl=https://repo.amd.com/rocm/packages-multi-arch/rhel10/x86_64' \
  'enabled=1' \
  'priority=50' \
  'gpgcheck=1' \
  'gpgkey=https://repo.amd.com/rocm/packages-multi-arch/gpg/rocm.gpg' \
  > /etc/yum.repos.d/rocm.repo

RUN dnf -y --nodocs --setopt=install_weak_deps=False \
  install \
  make gcc gcc-c++ cmake libcurl-devel ninja-build rdma-core-devel \
  amdrocm-core-devel7.14-gfx1151 \
  git-core patch \
  && dnf clean all && rm -rf /var/cache/dnf/*

ENV ROCM_PATH=/opt/rocm \
  HIP_PATH=/opt/rocm \
  PATH=/opt/rocm/bin:/opt/rocm/core/bin:/opt/rocm/core/lib/llvm/bin:$PATH \
  LD_LIBRARY_PATH=/opt/rocm/core/lib/rocm_sysdeps/lib:/opt/rocm/core/lib

# --- fetch the pinned EngramHalo.cpp source by exact commit, never by branch ---
#
# git clone -b <branch> would silently track whatever the branch tip is at
# build time (mutable). Instead: git init, fetch the exact full SHA at
# depth 1 from origin, then hard-verify the checked-out HEAD matches the
# pin byte-for-byte before doing anything else. No submodules are expected
# (.gitmodules at this commit is a real, empty file); this is verified,
# not assumed, and the build fails closed if that ever changes upstream.
WORKDIR /opt/llama.cpp
RUN set -eu; \
  git init -q .; \
  git remote add origin "${ENGRAM_REPO}"; \
  git fetch --depth 1 origin "${ENGRAM_COMMIT}"; \
  git checkout -q FETCH_HEAD; \
  actual_sha="$(git rev-parse HEAD)"; \
  if [ "${actual_sha}" != "${ENGRAM_COMMIT}" ]; then \
    echo "FATAL: fetched EngramHalo.cpp HEAD ${actual_sha} does not match pinned ${ENGRAM_COMMIT}" >&2; \
    exit 1; \
  fi; \
  if [ -f .gitmodules ] && [ -s .gitmodules ]; then \
    echo "FATAL: .gitmodules is non-empty at the pinned commit; this recipe" >&2; \
    echo "does not support submodules and refuses to recurse into them unreviewed" >&2; \
    exit 1; \
  fi

# --- fetch the packaging patches from the same fixed commit, in a separate repo ---
RUN set -eu; \
  mkdir -p /tmp/patch-src; \
  git init -q /tmp/patch-src; \
  git -C /tmp/patch-src remote add origin "${PATCH_REPO}"; \
  git -C /tmp/patch-src fetch --depth 1 origin "${PATCH_COMMIT}"; \
  git -C /tmp/patch-src checkout -q FETCH_HEAD; \
  actual_sha="$(git -C /tmp/patch-src rev-parse HEAD)"; \
  if [ "${actual_sha}" != "${PATCH_COMMIT}" ]; then \
    echo "FATAL: fetched patch-source HEAD ${actual_sha} does not match pinned ${PATCH_COMMIT}" >&2; \
    exit 1; \
  fi; \
  cp /tmp/patch-src/docs/strix-halo/llama-cpp-25992-rocm-host-buffer.patch /tmp/; \
  cp /tmp/patch-src/docs/strix-halo/llama-cpp-qwen38-per-buffer-mmap.patch /tmp/; \
  rm -rf /tmp/patch-src

# Recorded content hash of the pinned upstream qwen38 patch file as fetched
# above, at the time this override was investigated (see
# scripts/engramhalo/patches/llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch
# for the full root-cause writeup). This is a full-content sha256 footprint
# check, not a superficial substring/"contains" check: if
# halo-box/strix-llama.cpp ever serves different bytes for this file at the
# SAME pinned commit (which should be impossible for an immutable git
# commit, but is checked defensively rather than assumed), the hash
# comparison below fails closed instead of silently reapplying a stale
# local override against a differently-shaped upstream file.
ARG UPSTREAM_QWEN38_PATCH_SHA256=971d428de98ecdf59941946bb391c257e82501ce98b7c71cc1f34803181fe133
ARG REVIEWED_QWEN38_OVERRIDE_SHA256=9d876ab2047910bc534cf9bdff564c82b39371873f04d049f2ad5433c64820c5

# Locally reviewed override for the qwen38 per-buffer-mmap patch (see the
# file's own header for the full investigation): at pinned commit
# 15176583b358d791b7a73f210ef4ab9e167cfba7 the upstream patch's third hunk
# in src/llama-model-loader.cpp no longer applies (forward or reverse)
# because that file already carries an independently-added upstream
# lazy-tensor-read feature (`TENSOR_READ_LAZY`) that generalized the exact
# `if (use_mmap)` gate the qwen38 patch rewrites. This is a rebase of that
# one hunk against the pinned commit's actual code, not a semantic
# invention: it is an experimental compatibility rebase, reviewed against
# the pinned source, with application and structural tests passing; it has
# NOT been compiled or runtime validated. Compiling it is the required
# next step before model deployment. It is used below only as an
# explicit, hash-checked fallback if the verbatim upstream patch file does
# not apply as-is.
COPY patches/llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch /tmp/llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch

# --- apply patches deterministically, fail on ambiguity ---
#
# The source commit is fixed and known, so "the patch no longer applies"
# is not an expected steady state the way it would be against a moving
# branch HEAD — it means the pin above is stale and must be re-verified by
# a human, not silently skipped. git apply --check (forward) is tried
# first; if that fails, --reverse --check detects "already applied
# upstream" as a distinct, explicitly logged case. For the qwen38 patch
# specifically, if neither the forward nor reverse check on the verbatim
# upstream file succeeds, a hash-verified local rebase override (see above)
# is tried as a THIRD explicit, logged case before failing; any other
# outcome (including the override itself not applying) is a hard build
# failure, never a silent skip.
RUN set -eu; \
  actual_upstream_qwen38_sha="$(sha256sum /tmp/llama-cpp-qwen38-per-buffer-mmap.patch | cut -d' ' -f1)"; \
  if [ "${actual_upstream_qwen38_sha}" != "${UPSTREAM_QWEN38_PATCH_SHA256}" ]; then \
    echo "FATAL: fetched upstream qwen38 patch sha256 ${actual_upstream_qwen38_sha} does not match recorded ${UPSTREAM_QWEN38_PATCH_SHA256} at pinned commit ${PATCH_COMMIT}; the override below assumes the old file shape and must be re-reviewed by hand before reuse" >&2; \
    exit 1; \
  fi; \
  actual_override_sha="$(sha256sum /tmp/llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch | cut -d' ' -f1)"; \
  if [ "${actual_override_sha}" != "${REVIEWED_QWEN38_OVERRIDE_SHA256}" ]; then \
    echo "FATAL: local reviewed override sha256 ${actual_override_sha} does not match recorded ${REVIEWED_QWEN38_OVERRIDE_SHA256}; refusing to apply an unreviewed override silently" >&2; \
    exit 1; \
  fi; \
  for p in /tmp/llama-cpp-25992-rocm-host-buffer.patch /tmp/llama-cpp-qwen38-per-buffer-mmap.patch; do \
    if git apply --check "$p" 2>/dev/null; then \
      git apply "$p"; \
      echo "applied: $p"; \
    elif git apply --reverse --check "$p" 2>/dev/null; then \
      echo "already applied upstream, skipping: $p"; \
    elif [ "$p" = "/tmp/llama-cpp-qwen38-per-buffer-mmap.patch" ] && \
         git apply --check /tmp/llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch 2>/dev/null; then \
      git apply /tmp/llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch; \
      echo "applied HASH-VERIFIED LOCAL REBASE OVERRIDE (upstream file at $p did not apply verbatim; see scripts/engramhalo/patches/llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch for why): $p"; \
    else \
      echo "FATAL: $p neither applies nor is already applied at pinned commit ${ENGRAM_COMMIT}, and the hash-verified local rebase override also does not apply; the pin is stale, re-verify by hand" >&2; \
      exit 1; \
    fi; \
  done

# -DGGML_RPC=OFF: the upstream toolbox recipe (kyuz0/amd-strix-halo-toolboxes,
# packaged in halo-box/strix-llama.cpp's Dockerfile.rocm-7.14) builds with
# GGML_RPC=ON. This recipe deliberately turns it OFF: the EngramHalo wrapper
# (scripts/engramhalo/llama-server) never forwards --rpc and explicitly
# denies it as a dangerous flag, so the RPC server feature is unused attack
# surface here. This is a documented, deliberate deviation from the pinned
# upstream Dockerfile, not an oversight.
#
# -DLLAMA_CURL=OFF: also a deliberate deviation from the pinned upstream
# Dockerfile (which leaves libcurl linked via libcurl-devel for the
# engine's own HF-download machinery). The EngramHalo wrapper's whole
# threat model is "never download a model at runtime"; the wrapper already
# denies -hf/--hf-repo/--model-url/etc. Building libcurl support out of the
# engine binary removes that entire code path at the source instead of
# relying solely on the wrapper's argv filter. NOTE: libcurl-devel is still
# installed as a build dependency above because the pinned CMakeLists.txt
# may probe for it even when disabled; if a future re-verification shows
# the build no longer needs it with LLAMA_CURL=OFF, that dependency can be
# dropped in a follow-up, not assumed here.
# Defensive validation of BUILD_JOBS: must be a positive integer and must
# not exceed the conservative fixed cap of 4 documented above. This is a
# resource-constrained build host concern (not a correctness requirement of
# llama.cpp/cmake itself); it fails closed rather than silently clamping or
# passing through an unbounded/garbage value to `-j`.
RUN set -eu; \
  case "${BUILD_JOBS}" in \
    ''|*[!0-9]*) echo "FATAL: BUILD_JOBS='${BUILD_JOBS}' is not a positive integer" >&2; exit 1 ;; \
  esac; \
  if [ "${BUILD_JOBS}" -lt 1 ] || [ "${BUILD_JOBS}" -gt 4 ]; then \
    echo "FATAL: BUILD_JOBS='${BUILD_JOBS}' out of allowed range 1..4 (resource-constrained build host)" >&2; \
    exit 1; \
  fi

RUN cmake -S . -B build \
  -DGGML_HIP=ON \
  -DAMDGPU_TARGETS=gfx1151 \
  -DCMAKE_BUILD_TYPE=Release \
  -DGGML_RPC=OFF \
  -DLLAMA_CURL=OFF \
  -DROCM_PATH=/opt/rocm \
  -DHIP_PLATFORM=amd \
  && cmake --build build --config Release -- -j"${BUILD_JOBS}" \
  && cmake --install build --config Release

RUN mkdir -p /usr/local/lib64 \
  && find /opt/llama.cpp/build -type f -name 'lib*.so*' -exec cp {} /usr/local/lib64/ \; \
  && ldconfig

# ---------------------------------------------------------------------------
# runtime stage
# ---------------------------------------------------------------------------
FROM ${RUNTIME_BASE_IMAGE}

# Re-declared so they are visible in this stage's history/labels too.
ARG ENGRAM_REPO=https://github.com/Aristo94/EngramHalo.cpp.git
ARG ENGRAM_COMMIT=15176583b358d791b7a73f210ef4ab9e167cfba7
ARG BUILD_TIMESTAMP=unknown

# Optional, operator-configurable non-root UID/GID for anything that reads
# them at image-build time (none of the security-relevant checks in the
# EngramHalo wrapper rely on this — the wrapper always passes its own
# `--user <uid>:<gid>` from ENGRAMHALO_CONFIG on every real docker run
# invocation, so a mismatched or default UID baked into the image here
# cannot silently grant a different identity at runtime).
ARG RUNTIME_UID=1000
ARG RUNTIME_GID=1000

LABEL org.opencontainers.image.title="engramhalo" \
  org.opencontainers.image.description="llama.cpp (EngramHalo.cpp fork) ROCm 7.14 gfx1151 runtime, pinned to a fixed source commit for the Halo Strix engramhalo wrapper. NOT a general-purpose llama.cpp image." \
  org.opencontainers.image.source="${ENGRAM_REPO}" \
  org.opencontainers.image.revision="${ENGRAM_COMMIT}" \
  org.opencontainers.image.created="${BUILD_TIMESTAMP}" \
  org.opencontainers.image.documentation="https://github.com/halo-box/strix-llama.cpp/blob/15176583b358d791b7a73f210ef4ab9e167cfba7/docs/strix-halo/Dockerfile.rocm-7.14"

# Same portable POSIX RUN form as the builder stage (see comment above);
# no `RUN <<EOF` Dockerfile-heredoc frontend assumed here either.
RUN set -eu; printf '%s\n' \
  '[rocm]' \
  'name=ROCm 7.14.0' \
  'baseurl=https://repo.amd.com/rocm/packages-multi-arch/rhel10/x86_64' \
  'enabled=1' \
  'priority=50' \
  'gpgcheck=1' \
  'gpgkey=https://repo.amd.com/rocm/packages-multi-arch/gpg/rocm.gpg' \
  > /etc/yum.repos.d/rocm.repo

# Runtime ROCm libraries are installed fresh in this stage from the same
# pinned repo/version string (7.14, gfx1151) as the builder stage, rather
# than assumed to match some host-installed ROCm version. This does NOT
# make the two stages byte-identical (repo.amd.com is mutable, see the
# top-of-file limitation note); it only avoids the stronger, unverified
# assumption that a host's ROCm 7.2-era libs would be ABI compatible.
RUN microdnf -y --nodocs --setopt=install_weak_deps=0 \
  install \
  bash ca-certificates libatomic libstdc++ libgcc libgomp libibverbs shadow-utils \
  amdrocm-runtime7.14 amdrocm-blas7.14-gfx1151 \
  procps-ng \
  && microdnf clean all && rm -rf /var/cache/dnf/* \
  && set -eu \
  && mkdir -p /opt/rocm \
  && cd /opt/rocm \
  && if [ ! -d core-7.14 ]; then \
       echo "FATAL: /opt/rocm/core-7.14 not found after ROCm package install; symlink targets missing" >&2; \
       exit 1; \
     fi \
  && for link in core:core-7.14 bin:core-7.14/bin include:core-7.14/include \
                 lib:core-7.14/lib libexec:core-7.14/libexec \
                 llvm:core-7.14/lib/llvm share:core-7.14/share \
                 amdgcn:core-7.14/lib/llvm/amdgcn; do \
       name="${link%%:*}"; target="${link#*:}"; \
       if [ -e "${name}" ] && [ ! -L "${name}" ]; then \
         echo "FATAL: /opt/rocm/${name} already exists and is not a symlink; refusing to overwrite" >&2; \
         exit 1; \
       fi; \
       ln -sfn "${target}" "${name}"; \
     done

ENV ROCM_PATH=/opt/rocm \
  HIP_PATH=/opt/rocm \
  PATH=/opt/rocm/bin:/opt/rocm/core/bin:/opt/rocm/core/lib/llvm/bin:$PATH \
  LD_LIBRARY_PATH=/opt/rocm/core/lib/rocm_sysdeps/lib:/opt/rocm/core/lib

COPY --from=builder /usr/local/ /usr/local/
RUN echo "/usr/local/lib" > /etc/ld.so.conf.d/local.conf \
  && echo "/usr/local/lib64" >> /etc/ld.so.conf.d/local.conf \
  && echo "/opt/rocm/core/lib" > /etc/ld.so.conf.d/rocm.conf \
  && echo "/opt/rocm/core/lib/rocm_sysdeps/lib" >> /etc/ld.so.conf.d/rocm.conf \
  && ldconfig \
  && find /usr/local/lib /usr/local/lib64 -maxdepth 1 -type f -name 'libllama*.so*' \
     -exec cp -n {} /usr/lib64/ \; \
  && ldconfig

# Non-root by default. This is a build-time default only: the engramhalo
# wrapper always forces --user <uid>:<gid> from its own config on every
# real `docker run`, so this USER is relevant only for ad-hoc manual
# inspection (`docker run --entrypoint /bin/bash`) or the --help/--version
# path, never as the mechanism the wrapper depends on for privilege
# dropping.
RUN set -eu; \
  if getent group "${RUNTIME_GID}" >/dev/null 2>&1; then \
    echo "group gid ${RUNTIME_GID} already exists, reusing"; \
  else \
    groupadd -g "${RUNTIME_GID}" engramhalo; \
  fi; \
  if getent passwd "${RUNTIME_UID}" >/dev/null 2>&1; then \
    echo "user uid ${RUNTIME_UID} already exists, reusing"; \
  else \
    useradd -u "${RUNTIME_UID}" -g "${RUNTIME_GID}" -M -s /sbin/nologin engramhalo; \
  fi
# Regardless of whether the getent/groupadd/useradd path above found or
# created a matching NSS entry, USER below is expressed numerically so
# container startup does not depend on /etc/passwd resolution succeeding;
# this avoids masking real groupadd/useradd failures behind a blanket
# `|| true` while still guaranteeing a non-root numeric identity is set.
USER ${RUNTIME_UID}:${RUNTIME_GID}

# The wrapper (scripts/engramhalo/llama-server) always sets its own
# --entrypoint <engine_server> to the absolute in-image path below and
# never relies on the image's default ENTRYPOINT/CMD for a real launch.
# These exist so `docker run --rm --pull=never --entrypoint
# /usr/local/bin/llama-server <image> --version` works for a no-GPU,
# no-model smoke test, and so a bare `docker run <image>` without an
# override still does something safe and informative instead of silently
# defaulting to a shell.
ENTRYPOINT ["/usr/local/bin/llama-server"]
CMD ["--version"]
