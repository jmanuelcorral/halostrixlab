#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${ROOT_DIR}/scripts/common.sh"

prepare_control_environment
compose_control stop llamaboard
printf 'LlamaBoard detenido. Los datos de %s/data no se han borrado.\n' "${ROOT_DIR}"
