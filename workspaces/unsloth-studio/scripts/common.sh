#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
ENV_FILE="${ROOT_DIR}/.env"
COMPOSE_FILE="${ROOT_DIR}/compose.yaml"
PROJECT_NAME="halostrix-unsloth-studio"
SERVICE_NAME="studio"
EXPECTED_REVISION="e18a069c15cde98c7af77ccdb952254db8b0315d"

die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
env_value() {
  local key="$1" value=""
  [[ -f "${ENV_FILE}" ]] && value="$(sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*([^#[:space:]]+).*$/\1/p" "${ENV_FILE}" | tail -n 1)"
  value="${value%\"}"; value="${value#\"}"; printf '%s' "${value}"
}
prepare_docker() {
  command -v docker >/dev/null 2>&1 || die "docker no está en PATH"
  docker compose version >/dev/null 2>&1 || die "Docker Compose v2 no está disponible"
  docker info >/dev/null 2>&1 || die "Sin acceso al daemon Docker"
}
load_environment() {
  [[ -f "${ENV_FILE}" ]] || die "Falta .env. Ejecuta: cp .env.example .env"
  local key
  for key in BASE_IMAGE NODE_IMAGE UNSLOTH_COMMIT UNSLOTH_TARBALL_SHA256 UNSLOTH_IMAGE PIP_INDEX_URL UNSLOTH_STUDIO_PASSWORD RENDER_DEVICE DEVICE_GID WEB_BIND WEB_PORT SHM_SIZE; do
    printf -v "${key}" '%s' "${!key:-$(env_value "${key}")}"; export "${key}"
  done
}
prepare_build_environment() {
  prepare_docker; load_environment
  [[ "${BASE_IMAGE}" == *@sha256:* && "${NODE_IMAGE}" == *@sha256:* ]] || die "Las bases deben estar fijadas por digest"
  [[ "${UNSLOTH_COMMIT}" =~ ^[0-9a-f]{40}$ ]] || die "UNSLOTH_COMMIT no es un SHA completo"
  [[ "${UNSLOTH_TARBALL_SHA256}" =~ ^[0-9a-f]{64}$ ]] || die "Checksum de tarball no válido"
}
prepare_start_environment() {
  prepare_docker; load_environment
  local run_image="${RUN_IMAGE:-$(env_value RUN_IMAGE)}"
  case "${run_image}" in
    last) run_image="$(tracked_image_id "${ROOT_DIR}/.last-built-image")" ;;
    previous) run_image="$(tracked_image_id "${ROOT_DIR}/.previous-built-image")" ;;
  esac
  [[ -n "${run_image}" ]] && UNSLOTH_IMAGE="${run_image}" && export UNSLOTH_IMAGE
  [[ "${WEB_PORT}" =~ ^[0-9]+$ ]] && (( WEB_PORT > 0 && WEB_PORT < 65536 )) || die "WEB_PORT no válido"
  [[ -c /dev/kfd && -c "${RENDER_DEVICE}" ]] || die "Faltan /dev/kfd o ${RENDER_DEVICE}"
  [[ "${DEVICE_GID}" =~ ^[0-9]+$ ]] || die "DEVICE_GID no numérico"
  prepare_runtime_identity
  validate_owned_image "${UNSLOTH_IMAGE}" ||
    die "Imagen ausente, con ID inválido o ajena al workspace: ${UNSLOTH_IMAGE}"
}
valid_full_image_id() { [[ "$1" =~ ^sha256:[0-9a-f]{64}$ ]]; }
tracked_image_id() {
  local file="$1" value
  [[ -f "${file}" ]] || die "No existe el marcador de imagen: ${file##*/}"
  value="$(cat -- "${file}")"
  valid_full_image_id "${value}" || die "ID de imagen no válido en ${file##*/}"
  printf '%s' "${value}"
}
validate_owned_image() {
  local reference="$1" metadata id project service revision commit
  metadata="$(docker image inspect --format '{{.Id}}|{{index .Config.Labels "com.halostrix.project"}}|{{index .Config.Labels "com.halostrix.service"}}|{{index .Config.Labels "org.opencontainers.image.revision"}}|{{index .Config.Labels "com.halostrix.commit"}}' "${reference}" 2>/dev/null)" ||
    return 1
  IFS='|' read -r id project service revision commit <<<"${metadata}"
  valid_full_image_id "${id}" &&
    [[ "${project}" == "${PROJECT_NAME}" && "${service}" == "${SERVICE_NAME}" &&
       "${revision}" == "${EXPECTED_REVISION}" && "${commit}" == "${EXPECTED_REVISION}" ]]
}
prepare_runtime_identity() {
  HOST_UID="${HOST_UID:-${SUDO_UID:-$(id -u)}}"
  HOST_GID="${HOST_GID:-${SUDO_GID:-$(id -g)}}"
  [[ "${HOST_UID}" =~ ^[1-9][0-9]*$ && "${HOST_GID}" =~ ^[1-9][0-9]*$ ]] ||
    die "HOST_UID/HOST_GID deben ser IDs no-root"
  export HOST_UID HOST_GID
}
prepare_data_directories() {
  local path
  mkdir -p "${ROOT_DIR}"/data/{studio,hf-cache,projects,tmp}
  for path in "${ROOT_DIR}"/data/{studio,hf-cache,projects,tmp}; do
    [[ ! -L "${path}" ]] || die "Bind mount rechazado por ser symlink: ${path}"
    if [[ "$(stat -c %u "${path}")" != "${HOST_UID}" || "$(stat -c %g "${path}")" != "${HOST_GID}" ]]; then
      chown -R "${HOST_UID}:${HOST_GID}" "${path}" 2>/dev/null ||
        die "No se pudo asignar ${path} a ${HOST_UID}:${HOST_GID}; ejecuta start.sh con sudo"
    fi
    [[ -w "${path}" || "$(id -u)" == 0 ]] || die "El usuario actual no puede escribir ${path}"
  done
}
compose() { docker compose --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" "$@"; }
compose_control() {
  BASE_IMAGE="control.invalid@sha256:0" NODE_IMAGE="control.invalid@sha256:0" \
  UNSLOTH_COMMIT="0000000000000000000000000000000000000000" \
  UNSLOTH_TARBALL_SHA256="0000000000000000000000000000000000000000000000000000000000000000" \
  UNSLOTH_IMAGE="halostrix-unsloth-studio:control" RENDER_DEVICE="/dev/null" DEVICE_GID=0 \
  HOST_UID=10001 HOST_GID=10001 WEB_BIND=127.0.0.1 WEB_PORT=8888 SHM_SIZE=1g \
  docker compose -f "${COMPOSE_FILE}" "$@"
}
