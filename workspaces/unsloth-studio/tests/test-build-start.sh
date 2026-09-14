#!/usr/bin/env bash
set -Eeuo pipefail
TEST_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SOURCE_ROOT="$(cd -- "${TEST_ROOT}/.." && pwd -P)"
SANDBOX="${TEST_ROOT}/build-start"
WORKSPACE="${SANDBOX}/workspace"
FAKE_BIN="${SANDBOX}/bin"
CALLS="${SANDBOX}/calls"
OLD="sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
NEW="sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
FOREIGN="sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"
trap 'rm -rf -- "${SANDBOX}"' EXIT

reset_sandbox() {
  rm -rf -- "${SANDBOX}"
  mkdir -p "${WORKSPACE}/scripts" "${FAKE_BIN}"
  cp "${SOURCE_ROOT}/build.sh" "${SOURCE_ROOT}/start.sh" "${SOURCE_ROOT}/compose.yaml" "${WORKSPACE}/"
  cp "${SOURCE_ROOT}/scripts/common.sh" "${WORKSPACE}/scripts/"
  cp "${SOURCE_ROOT}/.env.example" "${WORKSPACE}/.env"
  cat >"${FAKE_BIN}/docker" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"${FAKE_CALLS}"
revision=e18a069c15cde98c7af77ccdb952254db8b0315d
current_file="${FAKE_CURRENT}"
current="$(cat "${current_file}" 2>/dev/null || true)"
if [[ "$*" == "compose version" || "$*" == "info" ]]; then exit 0
elif [[ "$*" == "compose "*" build studio" ]]; then
  [[ "${FAKE_BUILD_FAIL:-0}" != 1 ]] || exit 42
  printf '%s' "${FAKE_BUILD_ID}" >"${current_file}"
elif [[ "$1 $2 $3" == "image inspect --format" ]]; then
  [[ -n "${current}" ]] || exit 1
  if [[ "$4" == '{{.Id}}' ]]; then printf '%s\n' "${FAKE_INSPECT_ID:-${current}}"
  elif [[ "${current}" == "${FAKE_FOREIGN_ID:-}" ]]; then
    printf '%s|foreign|studio|%s|%s\n' "${current}" "${revision}" "${revision}"
  else
    printf '%s|halostrix-unsloth-studio|studio|%s|%s\n' "${current}" "${revision}" "${revision}"
  fi
elif [[ "$1 $2" == "image inspect" ]]; then [[ -n "${current}" ]]
elif [[ "$*" == "compose "*" up --detach --no-build studio" ]]; then exit 0
fi
EOF
  cat >"${FAKE_BIN}/id" <<'EOF'
#!/usr/bin/env bash
[[ "$1" == -u ]] && printf 1001 || printf 1001
EOF
  cat >"${FAKE_BIN}/stat" <<'EOF'
#!/usr/bin/env bash
printf 1001
EOF
  cat >"${FAKE_BIN}/chown" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
  chmod +x "${FAKE_BIN}"/* "${WORKSPACE}/build.sh" "${WORKSPACE}/start.sh"
  : >"${CALLS}"
  export PATH="${FAKE_BIN}:${ORIGINAL_PATH}" FAKE_CALLS="${CALLS}"
  export FAKE_CURRENT="${SANDBOX}/current" FAKE_BUILD_ID="${NEW}"
  unset FAKE_BUILD_FAIL FAKE_INSPECT_ID FAKE_FOREIGN_ID RUN_IMAGE
}
ORIGINAL_PATH="${PATH}"

reset_sandbox
"${WORKSPACE}/build.sh" >/dev/null
[[ "$(<"${WORKSPACE}/.last-built-image")" == "${NEW}" ]]
[[ ! -e "${WORKSPACE}/.previous-built-image" ]]

printf '%s' "${OLD}" >"${FAKE_CURRENT}"
FAKE_BUILD_ID="${NEW}" "${WORKSPACE}/build.sh" >/dev/null
[[ "$(<"${WORKSPACE}/.last-built-image")" == "${NEW}" ]]
[[ "$(<"${WORKSPACE}/.previous-built-image")" == "${OLD}" ]]

cp "${WORKSPACE}/.last-built-image" "${SANDBOX}/last.before"
cp "${WORKSPACE}/.previous-built-image" "${SANDBOX}/previous.before"
printf '%s' "${NEW}" >"${FAKE_CURRENT}"
FAKE_BUILD_FAIL=1 "${WORKSPACE}/build.sh" >/dev/null 2>&1 && exit 1
cmp "${SANDBOX}/last.before" "${WORKSPACE}/.last-built-image"
cmp "${SANDBOX}/previous.before" "${WORKSPACE}/.previous-built-image"

printf '%s' "${NEW}" >"${FAKE_CURRENT}"
FAKE_BUILD_ID="${NEW}" "${WORKSPACE}/build.sh" >/dev/null
[[ "$(<"${WORKSPACE}/.previous-built-image")" == "${OLD}" ]]

printf '%s' "${OLD}" >"${FAKE_CURRENT}"
FAKE_INSPECT_ID=malformed "${WORKSPACE}/build.sh" >/dev/null 2>&1 && exit 1
cmp "${SANDBOX}/last.before" "${WORKSPACE}/.last-built-image"
cmp "${SANDBOX}/previous.before" "${WORKSPACE}/.previous-built-image"

rm -f "${FAKE_CURRENT}"
FAKE_INSPECT_ID=malformed "${WORKSPACE}/build.sh" >/dev/null 2>&1 && exit 1
cmp "${SANDBOX}/last.before" "${WORKSPACE}/.last-built-image"
cmp "${SANDBOX}/previous.before" "${WORKSPACE}/.previous-built-image"

mkdir -p "${WORKSPACE}/data/studio" "${WORKSPACE}/data/hf-cache" "${WORKSPACE}/data/projects" "${WORKSPACE}/data/tmp"
printf '%s' "${FOREIGN}" >"${FAKE_CURRENT}"
export FAKE_FOREIGN_ID="${FOREIGN}" RUN_IMAGE="${FOREIGN}"
"${WORKSPACE}/start.sh" >/dev/null 2>&1 && exit 1
! grep -q 'up --detach' "${CALLS}"
printf 'build rotation and start ownership: OK\n'
