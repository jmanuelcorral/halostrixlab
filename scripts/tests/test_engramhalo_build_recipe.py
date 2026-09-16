"""Offline regression tests for the EngramHalo *build recipe* artifacts.

No Docker, network, or GPU access. These tests only read the plain-text
Dockerfile, the example build manifest, and the README under
scripts/engramhalo/, and assert static properties about them:

- source/patch commit pins are present and consistent between the
  Dockerfile and the example manifest,
- both base-image ARGs are declared before the first FROM (global ARG
  scope), so the second stage does not silently lose its base-image
  override,
- no `RUN <<...` Dockerfile-heredoc (BuildKit-only) frontend is used,
- BUILD_JOBS defaults to a small fixed value and the Dockerfile enforces a
  1..4 range at build time (not $(nproc), not unbounded),
- no reference to model weight file extensions (.gguf/.safetensors) or
  HuggingFace download flags appears in the recipe files,
- the example manifest is valid JSON and still marks itself as not-yet-built.

This module intentionally never invokes `docker`/`podman` and never
performs a build; it is a pure static-content regression test for the
recipe pass reviewed here.
"""

import hashlib
import json
import re
import unittest
from pathlib import Path

ENGRAMHALO_DIR = Path(__file__).resolve().parents[1] / "engramhalo"
DOCKERFILE = ENGRAMHALO_DIR / "Dockerfile"
MANIFEST = ENGRAMHALO_DIR / "build-manifest.example.json"
README = ENGRAMHALO_DIR / "README.md"
QWEN38_REBASE_PATCH = (
    ENGRAMHALO_DIR / "patches" / "llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch"
)

EXPECTED_ENGRAM_COMMIT = "15176583b358d791b7a73f210ef4ab9e167cfba7"
EXPECTED_PATCH_COMMIT = "15176583b358d791b7a73f210ef4ab9e167cfba7"
FORBIDDEN_WEIGHT_EXTENSIONS = (".gguf", ".safetensors")
FORBIDDEN_HF_FLAGS = ("-hf ", "--hf-repo", "--model-url")


class DockerfileStaticChecksTest(unittest.TestCase):
    def setUp(self):
        self.text = DOCKERFILE.read_text(encoding="utf-8")
        self.lines = self.text.splitlines()
        # Instruction-only view: strips full-line comments so that
        # documentation prose mentioning things like "RUN <<EOF" or
        # "--hf-repo" as descriptive text does not trigger false positives
        # in the checks below, which care about actual Dockerfile
        # instructions, not comments about them.
        self.code_lines = [
            line for line in self.lines if not line.strip().startswith("#")
        ]
        self.code_text = "\n".join(self.code_lines)

    def test_dockerfile_exists(self):
        self.assertTrue(DOCKERFILE.is_file())

    def test_no_dockerfile_heredoc_run(self):
        # `RUN <<EOF` / `RUN <<'EOF'` is a BuildKit-only Dockerfile frontend
        # feature; this recipe must stay portable to classic/legacy
        # builders per the reviewed requirement, so no actual instruction
        # line may start with it (comments describing the old pattern are
        # fine and are excluded via self.code_text).
        self.assertNotRegex(
            self.code_text,
            r"^\s*RUN\s*<<",
            "Dockerfile must not use the BuildKit-only `RUN <<...` heredoc form",
        )

    def test_both_base_image_args_precede_first_from(self):
        first_from_idx = next(
            i for i, line in enumerate(self.lines) if line.strip().startswith("FROM ")
        )
        preamble = "\n".join(self.lines[:first_from_idx])
        self.assertIn("ARG BUILDER_BASE_IMAGE=", preamble)
        self.assertIn("ARG RUNTIME_BASE_IMAGE=", preamble)
        # And neither should be re-declared with a fresh default value
        # between the two FROM lines (that pattern is exactly the fragile
        # scoping this pass fixed).
        from_indices = [
            i for i, line in enumerate(self.lines) if line.strip().startswith("FROM ")
        ]
        self.assertEqual(len(from_indices), 2, "expected exactly two FROM stages")
        between_stages = "\n".join(self.lines[from_indices[0] : from_indices[1]])
        self.assertNotIn("ARG RUNTIME_BASE_IMAGE=registry", between_stages)

    def test_pinned_commits_match_expected(self):
        self.assertIn(f"ENGRAM_COMMIT={EXPECTED_ENGRAM_COMMIT}", self.text)
        self.assertIn(f"PATCH_COMMIT={EXPECTED_PATCH_COMMIT}", self.text)

    def test_build_jobs_default_is_small_and_validated(self):
        self.assertIn("ARG BUILD_JOBS=4", self.text)
        # The Dockerfile must not silently default to all-cores.
        self.assertNotIn("$(nproc)", self.code_text)
        self.assertNotIn("nproc", self.code_text)
        # And it must actually validate the range at build time.
        self.assertIn("BUILD_JOBS", self.text)
        self.assertRegex(self.code_text, r'-gt"?\s*4|"-gt"\s+4|-gt 4')

    def test_no_model_weight_or_hf_download_references_in_instructions(self):
        # Only actual instruction lines matter here; comments are allowed
        # to *describe* what is rejected (e.g. "-hf/--hf-repo/--model-url")
        # without that being a false-positive "reference" in the recipe.
        lowered = self.code_text.lower()
        for ext in FORBIDDEN_WEIGHT_EXTENSIONS:
            self.assertNotIn(ext, lowered)
        for flag in FORBIDDEN_HF_FLAGS:
            self.assertNotIn(flag.lower(), lowered)

    def test_rocm_symlinks_use_force_noderef_not_blind_ln(self):
        # `ln -s src dst` fails hard if dst already exists; the recipe was
        # reviewed to use `ln -sfn` (force, no-dereference) after an
        # explicit existence/type check, not a blind `ln -s`.
        self.assertNotRegex(
            self.code_text,
            r"ln -s core-7\.14",
            "expected the old blind `ln -s core-7.14 ...` pattern to be gone",
        )
        self.assertIn("ln -sfn", self.code_text)

    def test_groupadd_useradd_not_blanket_swallowed(self):
        # The old `2>/dev/null || true` pattern on both groupadd and
        # useradd unconditionally hid all failures. The fixed version
        # checks with getent first and does not blanket-swallow errors.
        self.assertNotIn(
            'groupadd -g "${RUNTIME_GID}" engramhalo 2>/dev/null || true', self.text
        )
        self.assertIn("getent group", self.text)
        self.assertIn("getent passwd", self.text)

    def test_qwen38_override_hash_matches_deposited_patch_file(self):
        # Regression for the step15 build failure fix: the Dockerfile's
        # recorded REVIEWED_QWEN38_OVERRIDE_SHA256 must always match the
        # actual bytes of the deposited override patch file, so a future
        # edit to that file without updating the Dockerfile's pin fails
        # this test instead of silently building with a stale hash guard.
        self.assertTrue(
            QWEN38_REBASE_PATCH.is_file(),
            "expected the qwen38 rebase override patch to exist",
        )
        match = re.search(
            r"ARG REVIEWED_QWEN38_OVERRIDE_SHA256=([0-9a-f]{64})", self.text
        )
        self.assertIsNotNone(
            match, "expected a REVIEWED_QWEN38_OVERRIDE_SHA256 ARG in the Dockerfile"
        )
        recorded_sha = match.group(1)
        actual_sha = hashlib.sha256(QWEN38_REBASE_PATCH.read_bytes()).hexdigest()
        self.assertEqual(
            recorded_sha,
            actual_sha,
            "Dockerfile's REVIEWED_QWEN38_OVERRIDE_SHA256 does not match the "
            "actual override patch file bytes; update the Dockerfile ARG "
            "after any change to the override patch",
        )

    def test_qwen38_override_is_used_only_as_hash_verified_fallback(self):
        # The override must never silently replace the verbatim upstream
        # attempt: both the forward and reverse checks against the
        # upstream-fetched file must be tried first in the loop.
        self.assertIn('git apply --check "$p"', self.text)
        self.assertIn('git apply --reverse --check "$p"', self.text)
        self.assertIn(
            "llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch", self.text
        )
        self.assertIn("HASH-VERIFIED LOCAL REBASE OVERRIDE", self.text)


class ManifestStaticChecksTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))

    def test_manifest_is_valid_json_and_not_yet_built(self):
        self.assertEqual(self.manifest["status"], "not_yet_built")
        self.assertIsNone(self.manifest["image_digest"])
        self.assertIsNone(self.manifest["built_at"])

    def test_manifest_commit_matches_dockerfile_pin(self):
        self.assertEqual(self.manifest["source"]["commit"], EXPECTED_ENGRAM_COMMIT)
        self.assertEqual(
            self.manifest["packaging_patches_source"]["commit"], EXPECTED_PATCH_COMMIT
        )

    def test_manifest_has_no_model_weight_references(self):
        raw = json.dumps(self.manifest).lower()
        for ext in FORBIDDEN_WEIGHT_EXTENSIONS:
            self.assertNotIn(ext, raw)

    def test_manifest_records_build_jobs_cap_consistently_with_dockerfile(self):
        cap = self.manifest.get("build_jobs_cap")
        self.assertIsNotNone(cap, "expected a build_jobs_cap entry in the manifest")
        self.assertEqual(cap["default"], 4)
        self.assertEqual(cap["allowed_range"], "1..4")


class ReadmeStaticChecksTest(unittest.TestCase):
    def setUp(self):
        self.text = README.read_text(encoding="utf-8")

    def test_readme_exists(self):
        self.assertTrue(README.is_file())

    def test_max_loaded_models_scoped_to_lemonade_not_all_containers(self):
        # Regression for the reviewed misleading phrasing: max_loaded_models
        # is a Lemonade-side (host process) setting, not a Docker/container
        # property of this wrapper/image.
        idx = self.text.find("max_loaded_models")
        self.assertNotEqual(idx, -1, "expected a max_loaded_models mention in README")
        window = self.text[idx : idx + 600]
        self.assertIn("Lemonade", window)
        self.assertNotRegex(
            window,
            r"l[oó]s mismos l[ií]mites de `max_loaded_models`.{0,40}contenedor",
        )

    def test_readme_does_not_claim_a_real_build_happened(self):
        lowered = self.text.lower()
        self.assertIn("no construida todavía", lowered)
        self.assertIn("no despliega nada", lowered)


if __name__ == "__main__":
    unittest.main()
