"""Offline regression test for the EngramHalo qwen38 per-buffer-mmap patch
rebase (see scripts/engramhalo/patches/llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch
for the full root-cause writeup).

This reproduces, offline and deterministically, the real `step15` build
failure a user hit: the upstream
`docs/strix-halo/llama-cpp-qwen38-per-buffer-mmap.patch` from
halo-box/strix-llama.cpp no longer applies (forward or reverse) against the
pinned EngramHalo.cpp commit, because that commit already carries an
independently-added `TENSOR_READ_LAZY` feature that generalized the exact
`if (use_mmap)` gate the patch rewrites.

No network, Docker, or GPU access: this test only invokes `git apply
--check`/`git apply` against small, offline fixture files under
scripts/tests/fixtures/engramhalo-qwen38-patch/ (see that directory's
README.md for provenance) inside a throwaway temporary git repository, and
a real `git` binary must be on PATH (skipped otherwise).
"""

import shutil
import subprocess
import unittest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "engramhalo-qwen38-patch"
PATCHES_DIR = Path(__file__).resolve().parents[1] / "engramhalo" / "patches"
REBASED_PATCH = PATCHES_DIR / "llama-cpp-qwen38-per-buffer-mmap.rebased-for-15176583.patch"
UPSTREAM_PATCH = FIXTURES / "upstream-llama-cpp-qwen38-per-buffer-mmap.patch"

EXPECTED_UPSTREAM_SHA256 = (
    "971d428de98ecdf59941946bb391c257e82501ce98b7c71cc1f34803181fe133"
)
EXPECTED_REBASED_SHA256 = (
    "9d876ab2047910bc534cf9bdff564c82b39371873f04d049f2ad5433c64820c5"
)


def _git_available():
    return shutil.which("git") is not None


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(_git_available(), "git binary not available")
class Qwen38PatchRebaseTest(unittest.TestCase):
    def setUp(self):
        import tempfile

        self.tmp = Path(tempfile.mkdtemp(prefix="engramhalo-qwen38-fixture-"))
        src_dir = self.tmp / "src"
        src_dir.mkdir()
        for name in (
            "llama-model-loader.cpp",
            "llama-model-loader.h",
        ):
            shutil.copy(FIXTURES / name, src_dir / name)
        shutil.copy(FIXTURES / "llama-model.cpp", src_dir / "llama-model.cpp")
        subprocess.run(["git", "init", "-q", str(self.tmp)], check=True)
        subprocess.run(
            ["git", "-C", str(self.tmp), "add", "-A"], check=True
        )
        subprocess.run(
            [
                "git",
                "-C",
                str(self.tmp),
                "-c",
                "user.email=test@example.invalid",
                "-c",
                "user.name=test",
                "commit",
                "-q",
                "-m",
                "fixture baseline (pinned commit + first patch already applied)",
            ],
            check=True,
        )

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_fixture_files_present_and_hashes_recorded(self):
        self.assertTrue(REBASED_PATCH.is_file(), "rebased patch artifact missing")
        self.assertTrue(UPSTREAM_PATCH.is_file(), "upstream patch fixture missing")
        self.assertEqual(_sha256(UPSTREAM_PATCH), EXPECTED_UPSTREAM_SHA256)
        self.assertEqual(_sha256(REBASED_PATCH), EXPECTED_REBASED_SHA256)

    def test_upstream_patch_fails_forward_and_reverse(self):
        # This is the real step15 failure, reproduced offline.
        fwd = subprocess.run(
            ["git", "-C", str(self.tmp), "apply", "--check", str(UPSTREAM_PATCH)],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(fwd.returncode, 0, "expected upstream patch to fail forward")
        rev = subprocess.run(
            [
                "git",
                "-C",
                str(self.tmp),
                "apply",
                "--reverse",
                "--check",
                str(UPSTREAM_PATCH),
            ],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(rev.returncode, 0, "expected upstream patch to fail reverse too")

    def test_rebased_override_applies_cleanly(self):
        chk = subprocess.run(
            ["git", "-C", str(self.tmp), "apply", "--check", str(REBASED_PATCH)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(
            chk.returncode,
            0,
            f"expected rebased override to apply cleanly, stderr={chk.stderr!r}",
        )
        apply = subprocess.run(
            ["git", "-C", str(self.tmp), "apply", str(REBASED_PATCH)],
            capture_output=True,
            text=True,
        )
        self.assertEqual(apply.returncode, 0, apply.stderr)

    def test_rebased_override_result_is_semantically_correct(self):
        subprocess.run(
            ["git", "-C", str(self.tmp), "apply", str(REBASED_PATCH)], check=True
        )
        header_text = (self.tmp / "src" / "llama-model-loader.h").read_text(
            encoding="utf-8"
        )
        loader_text = (self.tmp / "src" / "llama-model-loader.cpp").read_text(
            encoding="utf-8"
        )
        model_text = (self.tmp / "src" / "llama-model.cpp").read_text(
            encoding="utf-8"
        )

        # Structural assertion, not a substring/contains-only check: the
        # buffer map value type must now be the wrapper struct...
        self.assertIn("struct llama_buf_info {", header_text)
        self.assertIn("ggml_backend_buffer_t buffer;", header_text)
        self.assertIn("bool is_mmap;", header_text)
        self.assertIn(
            "using llama_buf_map = std::unordered_map<uint32_t, llama_buf_info>;",
            header_text,
        )
        # ... and no old bare-buffer usage should remain in the touched
        # region of llama-model-loader.cpp: every bufs.at(...)/bufs.count(0)
        # ? bufs.at(0) call in that file must now go through `.buffer`.
        self.assertNotIn("bufs.at(0) : nullptr", loader_text)
        self.assertIn("bufs.at(0).buffer : nullptr", loader_text)
        self.assertIn("ggml_backend_buffer_get_type(bufs.at(0).buffer)", loader_text)

        # The independently-added upstream lazy-tensor gate must be
        # preserved verbatim (not dropped by the rebase): `from_mapping`
        # must still OR in `lazy.has(cur)`, and the new `tensor_uses_mmap`
        # must be derived from the per-buffer `is_mmap` flag, not a blanket
        # `use_mmap`.
        self.assertIn(
            "const bool from_mapping = tensor_uses_mmap || lazy.has(cur);",
            loader_text,
        )
        self.assertIn("buf_it->second.is_mmap", loader_text)
        self.assertIn(
            "use_mmap && buf_it != bufs.end() && buf_it->second.is_mmap",
            loader_text,
        )

        # llama-model.cpp must tag each buffer with the correct is_mmap
        # value (true for the mmap-backed path, false for the non-mmap
        # path) instead of the old untyped `buf` insertion.
        self.assertIn("llama_buf_info { buf, true }", model_text)
        self.assertIn("llama_buf_info { buf, false }", model_text)
        self.assertIn("ml.init_mappings(false,", model_text)


if __name__ == "__main__":
    unittest.main()
