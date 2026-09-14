#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${ROOT_DIR}/scripts/common.sh"

prepare_build_environment

printf 'Construyendo %s...\n' "${LLAMAFACTORY_IMAGE}"
compose build llamaboard

image_id="$(docker image inspect --format '{{.Id}}' "${LLAMAFACTORY_IMAGE}")"
[[ "${image_id}" =~ ^sha256:[0-9a-f]{64}$ ]] || die "Docker devolvió un identificador de imagen inesperado"
printf '%s\n' "${image_id}" >"${ROOT_DIR}/.last-built-image"
printf 'Imagen construida: %s\nIdentificador inmutable guardado en .last-built-image: %s\n' \
  "${LLAMAFACTORY_IMAGE}" "${image_id}"
