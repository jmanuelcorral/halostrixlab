#!/usr/bin/env bash
set -Eeuo pipefail

SOURCE_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
SANDBOX_ROOT="${SOURCE_DIR}/tests/.sandbox"
WORKSPACE="${SANDBOX_ROOT}/workspaces/llama-factory"
FAKEBIN="${SANDBOX_ROOT}/fakebin"
LOG="${SANDBOX_ROOT}/docker.log"

cleanup() { rm -rf -- "${SANDBOX_ROOT}"; }
trap cleanup EXIT
cleanup
mkdir -p "${WORKSPACE}/tests" "${WORKSPACE}/scripts" "${FAKEBIN}"
mkdir -p "${SANDBOX_ROOT}/symlink-target"
if ! ln -s "${SANDBOX_ROOT}/symlink-target" "${SANDBOX_ROOT}/symlink-probe" ||
   [[ ! -L "${SANDBOX_ROOT}/symlink-probe" ]]; then
  printf 'ERROR: cleanup tests require real symlinks. Use Linux, or Git Bash with MSYS=winsymlinks:nativestrict and existing native symlink permission. Copies are not valid fixtures.\n' >&2
  exit 1
fi
rm -- "${SANDBOX_ROOT}/symlink-probe"
rmdir -- "${SANDBOX_ROOT}/symlink-target"
cp "${SOURCE_DIR}/cleanup.sh" "${SOURCE_DIR}/compose.yaml" "${SOURCE_DIR}/Dockerfile" \
  "${SOURCE_DIR}/README.md" "${WORKSPACE}/"
cp "${SOURCE_DIR}/scripts/common.sh" "${WORKSPACE}/scripts/common.sh"
cat >"${WORKSPACE}/.env" <<'EOF'
BASE_IMAGE=rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad
LLAMAFACTORY_COMMIT=7af909522a951e3ad9f022ea6f88b6755257eaa5
LLAMAFACTORY_IMAGE=halostrix-llamafactory:foreign
RENDER_DEVICE=/dev/null
EOF

cat >"${FAKEBIN}/docker" <<'EOF'
#!/usr/bin/env bash
set -u
printf '%s\n' "$*" >>"${FAKE_DOCKER_LOG}"
a="$(printf 'a%.0s' {1..64})"; b="$(printf 'b%.0s' {1..64})"
c="$(printf 'c%.0s' {1..64})"; d="$(printf 'd%.0s' {1..64})"
e="$(printf 'e%.0s' {1..64})"
last="${!#}"
if [[ "$1" == info ]]; then exit 0; fi
if [[ "$1" == compose && "${last}" == version ]]; then printf 'Docker Compose fake\n'; exit 0; fi
if [[ "$1" == compose && "${last}" == config ]]; then cat "${FAKE_COMPOSE_FILE}"; exit 0; fi
if [[ "$1" == ps ]]; then printf '%s\n%s\n' "${a}" "${b}"; exit 0; fi
if [[ "$1" == inspect && "${last}" == "${a}" ]]; then
  printf '%s|halostrix-llamafactory|llamaboard|halostrix-llamafactory|llamaboard\n' "${a}"; exit 0
fi
if [[ "$1" == inspect && "${last}" == "${b}" ]]; then
  printf '%s|halostrix-llamafactory|other|halostrix-llamafactory|other\n' "${b}"; exit 0
fi
if [[ "$1" == network && "$2" == ls ]]; then printf '%s\n' "${c}"; exit 0; fi
if [[ "$1" == network && "$2" == inspect ]]; then
  printf '%s|halostrix-llamafactory_default|halostrix-llamafactory|default\n' "${c}"; exit 0
fi
if [[ "$1" == image && "$2" == ls ]]; then printf '%s\n' "${d}"; exit 0; fi
if [[ "$1" == image && "$2" == inspect && "${last}" == halostrix-llamafactory:foreign ]]; then
  printf 'sha256:%s||||\n' "${e}"; exit 0
fi
if [[ "$1" == image && "$2" == inspect && ( "${last}" == "${d}" || "${last}" == "sha256:${d}" ) ]]; then
  printf 'sha256:%s|halostrix-llamafactory|llamaboard|7af909522a951e3ad9f022ea6f88b6755257eaa5|rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad\n' "${d}"; exit 0
fi
# Recurso señuelo: si cleanup consultara volumes, sería del mismo proyecto.
if [[ "$1" == volume && "$2" == ls ]]; then printf 'same-project-volume\n'; exit 0; fi
if [[ "$1" == volume && "$2" == inspect ]]; then printf 'halostrix-llamafactory\n'; exit 0; fi
if [[ "$1" == volume && "$2" == rm ]]; then exit 0; fi
if [[ "$1" == rm ]]; then [[ "${FAKE_CASE:-}" == partial ]] && exit 42; exit 0; fi
if [[ "$1" == network && "$2" == rm ]]; then exit 0; fi
if [[ "$1" == image && "$2" == rm ]]; then exit 0; fi
exit 1
EOF
chmod +x "${FAKEBIN}/docker" "${WORKSPACE}/cleanup.sh"
export PATH="${FAKEBIN}:${PATH}" FAKE_DOCKER_LOG="${LOG}" FAKE_COMPOSE_FILE="${WORKSPACE}/compose.yaml"
command -v docker >/dev/null
docker info

mkdir -p "${WORKSPACE}/data/models"
printf 'keep\n' >"${WORKSPACE}/data/models/model.bin"
: >"${LOG}"
(cd "${WORKSPACE}" && ./cleanup.sh --all --yes --dry-run >/dev/null)
grep -Fxq 'keep' "${WORKSPACE}/data/models/model.bin"
! grep -Eq '(^| )(rm|network rm|image rm|volume)( |$)' "${LOG}"

: >"${LOG}"
(cd "${WORKSPACE}" && ./cleanup.sh --dry-run --yes --all >/dev/null)
grep -Fxq 'keep' "${WORKSPACE}/data/models/model.bin"
! grep -Eq '(^| )(rm|network rm|image rm|volume)( |$)' "${LOG}"

: >"${LOG}"
set +e
(cd "${WORKSPACE}" && FAKE_CASE=partial ./cleanup.sh --all --yes >"${SANDBOX_ROOT}/partial.out" 2>&1)
status=$?
set -e
[[ "${status}" -ne 0 ]]
grep -q 'Resumen parcial: Docker intentados=3, correctos=2, fallidos=1; fallos totales=1.' "${SANDBOX_ROOT}/partial.out" ||
  { cat "${SANDBOX_ROOT}/partial.out"; false; }
! test -e "${WORKSPACE}/data/models/model.bin"
! grep -q "rm -f -- $(printf 'b%.0s' {1..64})" "${LOG}"
! grep -q "image rm -- sha256:$(printf 'e%.0s' {1..64})" "${LOG}"
! grep -Eq '(^| )volume( |$)' "${LOG}"

mkdir -p "${WORKSPACE}/data" "${SANDBOX_ROOT}/outside"
rmdir "${WORKSPACE}/data/models"
ln -s "${SANDBOX_ROOT}/outside" "${WORKSPACE}/data/models"
set +e
(cd "${WORKSPACE}" && ./cleanup.sh --all --yes >"${SANDBOX_ROOT}/symlink.out" 2>&1)
status=$?
set -e
[[ "${status}" -ne 0 ]]
grep -q 'Symlink/reparse ambiguo rechazado' "${SANDBOX_ROOT}/symlink.out"

rm -rf "${WORKSPACE}/data"
ln -s "${SANDBOX_ROOT}/outside" "${WORKSPACE}/data"
if "${WORKSPACE}/cleanup.sh" --dry-run >/dev/null 2>&1; then
  echo "El symlink data no fue rechazado" >&2; exit 1
fi

source <(sed -n '/^validate_workspace_layout()/,/^}/p' "${SOURCE_DIR}/cleanup.sh")
(
  HOME="/home/test-operator"
  validate_workspace_layout "${HOME}/ai/llama-factory" llama-factory
  ! validate_workspace_layout "/home/other-operator/ai/llama-factory" llama-factory
  ! HOME="" validate_workspace_layout "/ai/llama-factory" llama-factory
  ! HOME="/" validate_workspace_layout "/ai/llama-factory" llama-factory
)
validate_workspace_layout "/repo with spaces/workspaces/llama-factory" llama-factory
! validate_workspace_layout "/evil/ai/llama-factory" llama-factory
! validate_workspace_layout "/tmp/llama-factory" llama-factory

SPACE_WORKSPACE="${SANDBOX_ROOT}/repo with spaces/workspaces/llama-factory"
mkdir -p "${SPACE_WORKSPACE}/scripts"
cp "${SOURCE_DIR}/cleanup.sh" "${SOURCE_DIR}/compose.yaml" "${SOURCE_DIR}/Dockerfile" "${SPACE_WORKSPACE}/"
cp "${SOURCE_DIR}/scripts/common.sh" "${SPACE_WORKSPACE}/scripts/common.sh"
(cd "${SPACE_WORKSPACE}" && ./cleanup.sh --dry-run >/dev/null)

ln -s "${SANDBOX_ROOT}/repo with spaces" "${SANDBOX_ROOT}/linked-parent"
if "${SANDBOX_ROOT}/linked-parent/workspaces/llama-factory/cleanup.sh" --dry-run >/dev/null 2>&1; then
  echo "El parent symlink no fue rechazado" >&2; exit 1
fi
mkdir -p "${SANDBOX_ROOT}/symlink-case/workspaces"
ln -s "${SPACE_WORKSPACE}" "${SANDBOX_ROOT}/symlink-case/workspaces/llama-factory"
if "${SANDBOX_ROOT}/symlink-case/workspaces/llama-factory/cleanup.sh" --dry-run >/dev/null 2>&1; then
  echo "El workspace symlink no fue rechazado" >&2; exit 1
fi

(cd "${WORKSPACE}" && docker compose --env-file .env -f compose.yaml config >/dev/null)
printf 'PASS: cleanup, layouts aprobados/rechazados, rutas con espacios y symlinks.\n'
