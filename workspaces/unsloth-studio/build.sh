#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
# shellcheck source=scripts/common.sh
source "${ROOT_DIR}/scripts/common.sh"
prepare_build_environment
LAST_FILE="${ROOT_DIR}/.last-built-image"
PREVIOUS_FILE="${ROOT_DIR}/.previous-built-image"
TEMP_FILES=()
cleanup_temps() { ((${#TEMP_FILES[@]} == 0)) || rm -f -- "${TEMP_FILES[@]}"; }
trap cleanup_temps EXIT
resolve_image_id() {
  local reference="$1" id
  id="$(docker image inspect --format '{{.Id}}' "${reference}")" || return 1
  valid_full_image_id "${id}" || die "ID de imagen inesperado para ${reference}"
  printf '%s' "${id}"
}
atomic_write() {
  local destination="$1" value="$2" temporary
  temporary="$(mktemp "${destination}.tmp.XXXXXX")"
  TEMP_FILES+=("${temporary}")
  printf '%s\n' "${value}" >"${temporary}"
  mv -f -- "${temporary}" "${destination}"
}
old_image_id=""
if docker image inspect "${UNSLOTH_IMAGE}" >/dev/null 2>&1; then
  old_image_id="$(resolve_image_id "${UNSLOTH_IMAGE}")"
fi
printf 'Construyendo %s...\n' "${UNSLOTH_IMAGE}"
compose build studio
image_id="$(resolve_image_id "${UNSLOTH_IMAGE}")"
if [[ -n "${old_image_id}" && "${image_id}" != "${old_image_id}" ]]; then
  atomic_write "${PREVIOUS_FILE}" "${old_image_id}"
fi
atomic_write "${LAST_FILE}" "${image_id}"
printf 'Imagen: %s\nID para rollback: %s\n' "${UNSLOTH_IMAGE}" "${image_id}"
