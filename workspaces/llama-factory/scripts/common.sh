#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ROOT_DIR}/.env"
COMPOSE_FILE="${ROOT_DIR}/compose.yaml"

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

env_value() {
  local key="$1"
  local value
  value="$(sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*(.*)[[:space:]]*$/\1/p" "${ENV_FILE}" | tail -n 1)"
  value="${value%\"}"
  value="${value#\"}"
  printf '%s' "${value}"
}

prepare_control_environment() {
  command -v docker >/dev/null 2>&1 || die "docker no está en PATH"
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 no está disponible"
  docker info >/dev/null 2>&1 || die "Sin acceso al daemon Docker. Ejecuta este script con una cuenta autorizada (p. ej. sudo)."
}

load_environment() {
  [[ -f "${ENV_FILE}" ]] || die "Falta .env. Ejecuta: cp .env.example .env"
  export BASE_IMAGE="${BASE_IMAGE:-$(env_value BASE_IMAGE)}"
  export LLAMAFACTORY_COMMIT="${LLAMAFACTORY_COMMIT:-$(env_value LLAMAFACTORY_COMMIT)}"
  export LLAMAFACTORY_IMAGE="${LLAMAFACTORY_IMAGE:-$(env_value LLAMAFACTORY_IMAGE)}"
  export PIP_INDEX_URL="${PIP_INDEX_URL:-$(env_value PIP_INDEX_URL)}"
  export RENDER_DEVICE="${RENDER_DEVICE:-$(env_value RENDER_DEVICE)}"
  export WEB_BIND="${WEB_BIND:-$(env_value WEB_BIND)}"
  export WEB_PORT="${WEB_PORT:-$(env_value WEB_PORT)}"
  export SHM_SIZE="${SHM_SIZE:-$(env_value SHM_SIZE)}"
}

prepare_build_environment() {
  prepare_control_environment
  load_environment
  [[ "${BASE_IMAGE}" == *@sha256:* ]] || die "BASE_IMAGE debe estar fijada por digest sha256"
  [[ "${LLAMAFACTORY_COMMIT}" =~ ^[0-9a-f]{40}$ ]] || die "LLAMAFACTORY_COMMIT debe ser un SHA completo de 40 caracteres"
  [[ -n "${LLAMAFACTORY_IMAGE}" ]] || die "LLAMAFACTORY_IMAGE no puede estar vacía"
  [[ -n "${PIP_INDEX_URL}" ]] || die "PIP_INDEX_URL no puede estar vacía"
}

prepare_start_environment() {
  prepare_control_environment
  load_environment
  local run_image
  run_image="${RUN_IMAGE:-$(env_value RUN_IMAGE)}"
  if [[ -n "${run_image}" ]]; then
    export LLAMAFACTORY_IMAGE="${run_image}"
  fi

  [[ -n "${LLAMAFACTORY_IMAGE}" ]] || die "LLAMAFACTORY_IMAGE/RUN_IMAGE no puede estar vacía"
  [[ "${WEB_PORT}" =~ ^[0-9]+$ ]] && (( WEB_PORT >= 1 && WEB_PORT <= 65535 )) || die "WEB_PORT no es válido"
  [[ -c /dev/kfd ]] || die "No existe el dispositivo de carácter /dev/kfd"
  [[ -c "${RENDER_DEVICE}" ]] || die "RENDER_DEVICE no es un dispositivo de carácter: ${RENDER_DEVICE}"
  [[ -r /dev/kfd && -w /dev/kfd ]] || die "La cuenta actual no puede leer/escribir /dev/kfd"
  [[ -r "${RENDER_DEVICE}" && -w "${RENDER_DEVICE}" ]] || die "La cuenta actual no puede leer/escribir ${RENDER_DEVICE}"

  export DEVICE_GID="${DEVICE_GID:-$(env_value DEVICE_GID)}"
  DEVICE_GID="${DEVICE_GID:-$(stat -c '%g' "${RENDER_DEVICE}")}"
  export DEVICE_GID
  [[ "${DEVICE_GID}" =~ ^[0-9]+$ ]] || die "El GID detectado/configurado no es numérico"
  docker image inspect "${LLAMAFACTORY_IMAGE}" >/dev/null 2>&1 ||
    die "La imagen ${LLAMAFACTORY_IMAGE} no existe localmente. Ejecuta ./build.sh o configura RUN_IMAGE con una imagen conservada."
}

compose() {
  docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"
}

compose_control() {
  BASE_IMAGE="control.invalid@sha256:0" \
  LLAMAFACTORY_COMMIT="0000000000000000000000000000000000000000" \
  LLAMAFACTORY_IMAGE="halostrix-llamafactory:control" \
  RENDER_DEVICE="/dev/null" \
  DEVICE_GID="0" \
  WEB_BIND="127.0.0.1" \
  WEB_PORT="7860" \
  SHM_SIZE="1g" \
    docker compose -f "${COMPOSE_FILE}" "$@"
}
