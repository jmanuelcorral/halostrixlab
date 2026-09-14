#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=scripts/common.sh
source "${ROOT_DIR}/scripts/common.sh"
prepare_start_environment
prepare_data_directories
compose up --detach --no-build studio
printf 'Studio solicitado en http://%s:%s\n' "${WEB_BIND}" "${WEB_PORT}"
