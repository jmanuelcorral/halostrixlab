#!/usr/bin/env bash
set -Eeuo pipefail
TEST_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SOURCE_ROOT="$(cd -- "${TEST_ROOT}/.." && pwd -P)"
SANDBOX="${TEST_ROOT}/ownership"
FAKE_BIN="${SANDBOX}/bin"
CALLS="${SANDBOX}/calls"
trap 'rm -rf -- "${SANDBOX}"' EXIT
rm -rf -- "${SANDBOX}"
mkdir -p "${SANDBOX}/workspaces/unsloth-studio/scripts" "${FAKE_BIN}"
cp "${SOURCE_ROOT}/scripts/common.sh" "${SANDBOX}/workspaces/unsloth-studio/scripts/common.sh"
cp "${SOURCE_ROOT}/compose.yaml" "${SANDBOX}/workspaces/unsloth-studio/compose.yaml"
cp "${SOURCE_ROOT}/.env.example" "${SANDBOX}/workspaces/unsloth-studio/.env"
cat >"${FAKE_BIN}/docker" <<'EOF'
#!/usr/bin/env bash
printf 'UID=%s GID=%s %s\n' "${HOST_UID:-}" "${HOST_GID:-}" "$*" >>"${FAKE_CALLS}"
case "$*" in
  "compose version"|"info"|"image inspect"*) exit 0 ;;
esac
EOF
cat >"${FAKE_BIN}/id" <<'EOF'
#!/usr/bin/env bash
[[ "$1" == -u ]] && printf 2001 || printf 2002
EOF
cat >"${FAKE_BIN}/chown" <<'EOF'
#!/usr/bin/env bash
printf 'chown %s\n' "$*" >>"${FAKE_CALLS}"
EOF
cat >"${FAKE_BIN}/stat" <<'EOF'
#!/usr/bin/env bash
[[ "$2" == %u ]] && printf '1\n' || printf '2\n'
EOF
chmod +x "${FAKE_BIN}"/*
export PATH="${FAKE_BIN}:${PATH}" FAKE_CALLS="${CALLS}" SUDO_UID=3001 SUDO_GID=3002
unset HOST_UID HOST_GID
source "${SANDBOX}/workspaces/unsloth-studio/scripts/common.sh"
prepare_runtime_identity
prepare_data_directories
grep -q 'chown -R 3001:3002' "${CALLS}"
[[ "${HOST_UID}:${HOST_GID}" == 3001:3002 ]]
grep -q 'user: "${HOST_UID:-10001}:${HOST_GID:-10001}"' "${SOURCE_ROOT}/compose.yaml"
grep -A2 'group_add:' "${SOURCE_ROOT}/compose.yaml" | grep -q DEVICE_GID
! grep -q 'chmod 777' "${SOURCE_ROOT}/Dockerfile" "${SOURCE_ROOT}"/*.sh "${SOURCE_ROOT}"/scripts/*.sh
printf 'ownership sudo simulation: OK\n'
