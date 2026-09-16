# Fixture: EngramHalo.cpp qwen38 patch conflict reproduction

Purpose: offline regression fixture for
`scripts/tests/test_engramhalo_qwen38_patch_rebase.py`. Proves, without any
network access, GPU, or Docker, that:

1. the verbatim upstream patch
   `docs/strix-halo/llama-cpp-qwen38-per-buffer-mmap.patch` from
   `https://github.com/halo-box/strix-llama.cpp.git` genuinely fails to
   apply (forward and reverse) against the pinned commit, and
2. the locally reviewed rebase override
   (`scripts/engramhalo/patches/llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch`)
   applies cleanly and produces the expected semantic result (per-buffer
   `is_mmap` tracking, `lazy.has(cur)` preserved).

## Provenance (public source, no secrets)

- `llama-model-loader.cpp`, `llama-model-loader.h`, `llama-model.cpp`: taken
  verbatim from `https://github.com/Aristo94/EngramHalo.cpp.git` at the
  exact pinned commit `15176583b358d791b7a73f210ef4ab9e167cfba7` (same
  commit the Dockerfile pins), with
  `docs/strix-halo/llama-cpp-25992-rocm-host-buffer.patch` (the FIRST
  packaging patch) already applied on top — exactly the state the
  Dockerfile's second patch-apply step sees. Fetched via an isolated,
  throwaway `git init` + `git fetch --depth 1 origin <commit>` +
  `git checkout FETCH_HEAD` in `/tmp`, never against the repository
  workspace. Verified with `git rev-parse HEAD` == the pinned commit before
  copying.
- `upstream-llama-cpp-qwen38-per-buffer-mmap.patch`: copied verbatim from
  `https://github.com/halo-box/strix-llama.cpp.git` at the same pinned
  commit, path `docs/strix-halo/llama-cpp-qwen38-per-buffer-mmap.patch`.
  Its sha256 (`971d428de98ecdf59941946bb391c257e82501ce98b7c71cc1f34803181fe133`)
  matches `UPSTREAM_QWEN38_PATCH_SHA256` recorded in
  `scripts/engramhalo/Dockerfile`.

No model weights, credentials, or private host state are present in this
directory. llama.cpp / EngramHalo.cpp is MIT-licensed upstream; this is a
small excerpt of source text used solely for an offline regression test of
this repository's own patch-rebase artifact, not a redistribution of the
whole project.

## What the test proves (not just string containment)

- The upstream patch fails via real `git apply --check` (forward) AND
  `git apply --reverse --check`, matching the exact failure mode reported
  by the user (`step15` in their build log).
- The local rebase override applies via real `git apply --check` with rc=0
  and no fuzz.
- After applying the override, `llama-model-loader.h` defines
  `struct llama_buf_info { ggml_backend_buffer_t buffer; bool is_mmap; };`
  and `llama_buf_map` is keyed to that struct (not a bare
  `ggml_backend_buffer_t`) — a structural/semantic assertion, not a
  substring check on the patch file itself.
- After applying, `llama-model-loader.cpp`'s `load_all_data` computes
  `tensor_uses_mmap` from `bufs.find(weight->idx)->second.is_mmap` and ORs
  it with the untouched `lazy.has(cur)` call, i.e. the independently-added
  upstream lazy-tensor-read gate is preserved verbatim rather than
  silently dropped by the rebase.
