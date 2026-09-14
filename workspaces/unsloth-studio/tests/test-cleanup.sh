#!/usr/bin/env bash
set -Eeuo pipefail
TEST_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SOURCE_ROOT="$(cd -- "${TEST_ROOT}/.." && pwd -P)"
SANDBOX="${TEST_ROOT}/sandbox/workspaces/unsloth-studio"
FAKE_BIN="${TEST_ROOT}/sandbox/bin"
CALLS="${TEST_ROOT}/sandbox/docker.calls"
IMAGE_ID="sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
OWNED_PREVIOUS="sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
FOREIGN_PREVIOUS="sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
trap 'rm -rf -- "${TEST_ROOT}/sandbox"' EXIT

reset_sandbox() {
  rm -rf -- "${TEST_ROOT}/sandbox"
  mkdir -p "${SANDBOX}/data/studio" "${SANDBOX}/data/hf-cache" \
    "${SANDBOX}/data/projects" "${SANDBOX}/data/tmp" "${SANDBOX}/scripts" "${FAKE_BIN}"
  cp "${SOURCE_ROOT}/cleanup.sh" "${SANDBOX}/cleanup.sh"
  cp "${SOURCE_ROOT}/compose.yaml" "${SANDBOX}/compose.yaml"
  cp "${SOURCE_ROOT}/Dockerfile" "${SANDBOX}/Dockerfile"
  cp "${SOURCE_ROOT}/scripts/common.sh" "${SANDBOX}/scripts/common.sh"
  printf x >"${SANDBOX}/data/studio/keep"
  cat >"${FAKE_BIN}/docker" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"${FAKE_DOCKER_CALLS}"
revision=e18a069c15cde98c7af77ccdb952254db8b0315d
image=sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc
owned_previous=sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee
foreign_previous=sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd
args="$*"; last="${!#}"
if [[ "${args}" == info ]]; then [[ "${FAKE_DOCKER_UNAVAILABLE:-0}" != 1 ]]
elif [[ "${args}" == container\ ls* && "${args}" == *label=com.docker.compose.project=halostrix-unsloth-studio* &&
        "${args}" == *label=com.docker.compose.service=studio* ]]; then printf '%s\n' aaaaaaaaaaaa
elif [[ "${args}" == network\ ls* && "${args}" == *name=\^halostrix-unsloth-studio_default\$* &&
        "${args}" == *label=com.docker.compose.project=halostrix-unsloth-studio* &&
        "${args}" == *label=com.docker.compose.network=default* ]]; then printf '%s\n' bbbbbbbbbbbb
elif [[ "${args}" == image\ ls* && "${args}" == *label=com.halostrix.project=halostrix-unsloth-studio* &&
        "${args}" == *label=com.halostrix.service=studio* &&
        "${args}" == *label=org.opencontainers.image.revision=${revision}* &&
        "${args}" == *label=com.halostrix.commit=${revision}* ]]; then printf '%s\n' cccccccccccc
elif [[ "$1 $2" == "inspect --format" && "${last}" == aaaaaaaaaaaa ]]; then
  printf '%s\n' "halostrix-unsloth-studio|studio"
elif [[ "$1 $2" == "network inspect" && "${last}" == bbbbbbbbbbbb ]]; then
  printf '%s\n' "halostrix-unsloth-studio_default|halostrix-unsloth-studio|default"
elif [[ "$1 $2" == "image inspect" && ( "${last}" == cccccccccccc || "${last}" == "${image}" ) ]]; then
  printf '%s\n' "$image|halostrix-unsloth-studio|studio|$revision|$revision"
elif [[ "$1 $2" == "image inspect" && "${last}" == "${owned_previous}" ]]; then
  printf '%s\n' "$owned_previous|halostrix-unsloth-studio|studio|$revision|$revision"
elif [[ "$1 $2" == "image inspect" && "${last}" == "${foreign_previous}" ]]; then
  printf '%s\n' "$foreign_previous|foreign|studio|$revision|$revision"
elif [[ "$1 $2" == "image inspect" && "${last}" == foreign:latest ]]; then
  printf '%s\n' "sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd|foreign|studio|$revision|$revision"
elif [[ "${args}" == image\ inspect\ rocm/pytorch@* ]]; then exit 1
elif [[ "${args}" == "container rm --force aaaaaaaaaaaa" ]]; then
  [[ "${FAKE_FAIL_CONTAINER:-0}" != 1 ]]
fi
EOF
  chmod +x "${FAKE_BIN}/docker" "${SANDBOX}/cleanup.sh"
  bash -n "${FAKE_BIN}/docker"
  export PATH="${FAKE_BIN}:${ORIGINAL_PATH}" FAKE_DOCKER_CALLS="${CALLS}"
  unset FAKE_FAIL_CONTAINER FAKE_DOCKER_UNAVAILABLE
}
ORIGINAL_PATH="${PATH}"

mkdir -p "${TEST_ROOT}/sandbox/symlink-target"
if ! ln -s "${TEST_ROOT}/sandbox/symlink-target" "${TEST_ROOT}/sandbox/symlink-probe" ||
   [[ ! -L "${TEST_ROOT}/sandbox/symlink-probe" ]]; then
  printf 'ERROR: cleanup tests require real symlinks. Use Linux, or Git Bash with MSYS=winsymlinks:nativestrict and existing native symlink permission. Copies are not valid fixtures.\n' >&2
  exit 1
fi
rm -- "${TEST_ROOT}/sandbox/symlink-probe"
rmdir -- "${TEST_ROOT}/sandbox/symlink-target"

assert_identity_rejected() {
  local case_name="$1"
  : >"${CALLS}"
  if "${SANDBOX}/cleanup.sh" --all --yes >"${TEST_ROOT}/sandbox/identity.out" 2>&1; then
    echo "Identidad inválida aceptada: ${case_name}" >&2; exit 1
  fi
  [[ -f "${SANDBOX}/data/studio/keep" ]] || {
    echo "Se borraron datos con identidad inválida: ${case_name}" >&2; exit 1
  }
  [[ ! -s "${CALLS}" ]] || {
    echo "Se llamó Docker con identidad inválida: ${case_name}" >&2; exit 1
  }
  grep -q 'Identidad del workspace' "${TEST_ROOT}/sandbox/identity.out"
}

reset_sandbox
: >"${SANDBOX}/compose.yaml"
assert_identity_rejected "compose vacío"

reset_sandbox
: >"${SANDBOX}/Dockerfile"
assert_identity_rejected "Dockerfile vacío"

reset_sandbox
sed -i 's/^name: halostrix-unsloth-studio/name: otro-proyecto/' "${SANDBOX}/compose.yaml"
assert_identity_rejected "project incorrecto"

reset_sandbox
sed -i '/^name: halostrix-unsloth-studio/d' "${SANDBOX}/compose.yaml"
assert_identity_rejected "project ausente"

reset_sandbox
sed -i 's/^  studio:/  otro-servicio:/' "${SANDBOX}/compose.yaml"
assert_identity_rejected "service incorrecto"

reset_sandbox
sed -i '/^  studio:/d' "${SANDBOX}/compose.yaml"
assert_identity_rejected "service ausente"

reset_sandbox
sed -i 's/com\.halostrix\.project="halostrix-unsloth-studio"/com.halostrix.project="otro-proyecto"/' "${SANDBOX}/Dockerfile"
assert_identity_rejected "label project incorrecto"

reset_sandbox
sed -i '/com\.halostrix\.project=/d' "${SANDBOX}/Dockerfile"
assert_identity_rejected "label project ausente"

reset_sandbox
sed -i 's/com\.halostrix\.service="studio"/com.halostrix.service="otro-servicio"/' "${SANDBOX}/Dockerfile"
assert_identity_rejected "label service incorrecto"

reset_sandbox
sed -i '/com\.halostrix\.service=/d' "${SANDBOX}/Dockerfile"
assert_identity_rejected "label service ausente"

reset_sandbox
printf '\nname: halostrix-unsloth-studio\n' >>"${SANDBOX}/compose.yaml"
assert_identity_rejected "project duplicado engañoso"

reset_sandbox
printf '\n# com.halostrix.service="studio" \\\n' >>"${SANDBOX}/Dockerfile"
assert_identity_rejected "label duplicado engañoso"

reset_sandbox
"${SANDBOX}/cleanup.sh" --all --dry-run --yes >"${TEST_ROOT}/sandbox/dry.out"
[[ -f "${SANDBOX}/data/studio/keep" ]]
grep -q -- '--dry-run domina' "${TEST_ROOT}/sandbox/dry.out"
[[ ! -f "${CALLS}" ]] || ! grep -Eq 'container rm|network rm|image rm' "${CALLS}"

: >"${CALLS}"
"${SANDBOX}/cleanup.sh" --yes --dry-run --all >/dev/null
[[ -f "${SANDBOX}/data/studio/keep" ]]
[[ ! -f "${CALLS}" ]] || ! grep -Eq 'container rm|network rm|image rm' "${CALLS}"

reset_sandbox
printf 'UNSLOTH_IMAGE=foreign:latest\n' >"${SANDBOX}/.env"
printf '%s\n' "${FOREIGN_PREVIOUS}" >"${SANDBOX}/.previous-built-image"
"${SANDBOX}/cleanup.sh" --all --yes >"${TEST_ROOT}/sandbox/all.out"
[[ ! -e "${SANDBOX}/data/studio/keep" ]]
grep -q 'container rm --force aaaaaaaaaaaa' "${CALLS}"
grep -q 'network rm bbbbbbbbbbbb' "${CALLS}"
grep -q "image rm ${IMAGE_ID}" "${CALLS}"
! grep -q "image rm ${FOREIGN_PREVIOUS}" "${CALLS}"
! grep -Eq 'system prune|image prune|container prune|volume prune|volume (ls|rm)' "${CALLS}"
grep -q 'label=com.docker.compose.service=studio' "${CALLS}"

reset_sandbox
printf '%s\n' "${OWNED_PREVIOUS}" >"${SANDBOX}/.previous-built-image"
"${SANDBOX}/cleanup.sh" --all --yes >/dev/null
grep -q "image rm ${OWNED_PREVIOUS}" "${CALLS}"

reset_sandbox
export FAKE_FAIL_CONTAINER=1
if "${SANDBOX}/cleanup.sh" --all --yes >"${TEST_ROOT}/sandbox/partial.out" 2>&1; then
  echo "Un fallo parcial no produjo exit nonzero" >&2; exit 1
fi
grep -q 'network rm bbbbbbbbbbbb' "${CALLS}"
grep -q "image rm ${IMAGE_ID}" "${CALLS}"
[[ ! -e "${SANDBOX}/data/studio/keep" ]]
grep -q 'errores=1' "${TEST_ROOT}/sandbox/partial.out"

reset_sandbox
export FAKE_DOCKER_UNAVAILABLE=1
if "${SANDBOX}/cleanup.sh" --all --yes >"${TEST_ROOT}/sandbox/docker-unavailable.out" 2>&1; then
  echo "Docker ausente no produjo exit nonzero" >&2; exit 1
fi
[[ ! -e "${SANDBOX}/data/studio/keep" ]]
grep -q 'limpieza Docker omitida; resultado parcial' "${TEST_ROOT}/sandbox/docker-unavailable.out"
grep -q 'Resumen:' "${TEST_ROOT}/sandbox/docker-unavailable.out"
grep -q 'errores=1' "${TEST_ROOT}/sandbox/docker-unavailable.out"
! grep -Eq 'container rm|network rm|image rm' "${CALLS}"

reset_sandbox
outside="${TEST_ROOT}/sandbox/outside"
mkdir -p "${outside}"
rm -rf "${SANDBOX}/data/projects"
ln -s "${outside}" "${SANDBOX}/data/projects"
if "${SANDBOX}/cleanup.sh" --all --yes >"${TEST_ROOT}/sandbox/link.out" 2>&1; then
  echo "El symlink peligroso no fue rechazado" >&2; exit 1
fi
[[ ! -f "${CALLS}" ]] || ! grep -Eq 'container rm|network rm|image rm' "${CALLS}"

reset_sandbox
outside="${TEST_ROOT}/sandbox/outside"
mkdir -p "${outside}"
rm -rf "${SANDBOX}/data"
ln -s "${outside}" "${SANDBOX}/data"
if "${SANDBOX}/cleanup.sh" --dry-run >/dev/null 2>&1; then
  echo "El symlink data no fue rechazado" >&2; exit 1
fi

source <(sed -n '/^validate_workspace_layout()/,/^}/p' "${SOURCE_ROOT}/cleanup.sh")
(
  HOME="/home/test-operator"
  validate_workspace_layout "${HOME}/ai/unsloth-studio" unsloth-studio
  ! validate_workspace_layout "/home/other-operator/ai/unsloth-studio" unsloth-studio
  ! HOME="" validate_workspace_layout "/ai/unsloth-studio" unsloth-studio
  ! HOME="/" validate_workspace_layout "/ai/unsloth-studio" unsloth-studio
)
validate_workspace_layout "/repo with spaces/workspaces/unsloth-studio" unsloth-studio
! validate_workspace_layout "/evil/ai/unsloth-studio" unsloth-studio
! validate_workspace_layout "/tmp/unsloth-studio" unsloth-studio

SPACE_WORKSPACE="${TEST_ROOT}/sandbox/repo with spaces/workspaces/unsloth-studio"
mkdir -p "${SPACE_WORKSPACE}/scripts"
cp "${SOURCE_ROOT}/cleanup.sh" "${SOURCE_ROOT}/compose.yaml" "${SOURCE_ROOT}/Dockerfile" "${SPACE_WORKSPACE}/"
cp "${SOURCE_ROOT}/scripts/common.sh" "${SPACE_WORKSPACE}/scripts/common.sh"
"${SPACE_WORKSPACE}/cleanup.sh" --dry-run >/dev/null

ln -s "${TEST_ROOT}/sandbox/repo with spaces" "${TEST_ROOT}/sandbox/linked-parent"
if "${TEST_ROOT}/sandbox/linked-parent/workspaces/unsloth-studio/cleanup.sh" --dry-run >/dev/null 2>&1; then
  echo "El parent symlink no fue rechazado" >&2; exit 1
fi
mkdir -p "${TEST_ROOT}/sandbox/symlink-case/workspaces"
ln -s "${SPACE_WORKSPACE}" "${TEST_ROOT}/sandbox/symlink-case/workspaces/unsloth-studio"
if "${TEST_ROOT}/sandbox/symlink-case/workspaces/unsloth-studio/cleanup.sh" --dry-run >/dev/null 2>&1; then
  echo "El workspace symlink no fue rechazado" >&2; exit 1
fi

grep -q 'com.halostrix.service="studio"' "${SOURCE_ROOT}/Dockerfile"
grep -q 'com.halostrix.commit="${UNSLOTH_COMMIT}"' "${SOURCE_ROOT}/Dockerfile"
printf 'cleanup adversarial sandbox and layouts: OK\n'
