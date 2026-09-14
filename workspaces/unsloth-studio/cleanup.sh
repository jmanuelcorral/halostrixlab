#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_NAME="halostrix-unsloth-studio"
SERVICE_NAME="studio"
NETWORK_NAME="${PROJECT_NAME}_default"
NETWORK_KEY="default"
REVISION="e18a069c15cde98c7af77ccdb952254db8b0315d"
BASE_IMAGE_EXACT="rocm/pytorch@sha256:a223aee17aef5d21c3b9f63436dd19d27d1c665ec8b2f40011c9546cabae2a80"
CONFIRM_PHRASE="BORRAR HALOSTRIX UNSLOTH STUDIO"
BASE_CONFIRM_PHRASE="BORRAR BASE ROCM COMPARTIDA"
ALL_REQUESTED=false
DRY_RUN=false
ASSUME_YES=false
INCLUDE_BASE=false

usage() {
  cat <<'EOF'
Uso: ./cleanup.sh [--dry-run] [--all [--yes] [--include-base]]
  --dry-run      Sólo inventario; domina --all/--yes en cualquier orden.
  --all          Autoriza limpieza tras confirmación.
  --yes          Omite confirmaciones; no tiene efecto sin --all.
  --include-base Incluye únicamente el digest base explícito; exige --all.
EOF
}
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

validate_workspace_layout() {
  local root="$1" project="$2" suffix repo_root
  [[ "${root}" == /* && "${root}" != */ ]] || return 1
  [[ "${HOME:-}" == /* && "${HOME}" != "/" && "${HOME}" != */ &&
     "${root}" == "${HOME}/ai/${project}" ]] && return 0
  suffix="/workspaces/${project}"
  [[ "${root}" == *"${suffix}" ]] || return 1
  repo_root="${root%"${suffix}"}"
  [[ "${repo_root}" == /* && "${repo_root}" != "/" ]]
}

validate_workspace_identity() {
  local compose_file="$1" dockerfile="$2"
  awk -v project="${PROJECT_NAME}" -v service="${SERVICE_NAME}" '
    {
      line = $0
      sub(/\r$/, "", line)
      if (line ~ /^name[[:space:]]*:/) {
        name_count++
        if (line == "name: " project) name_exact++
      }
      if (line ~ /^services[[:space:]]*:/) {
        services_count++
        in_services = (line == "services:")
        if (in_services) services_exact++
        next
      }
      if (line ~ /^[^[:space:]#]/) in_services = 0
      if (line ~ /^[[:space:]]*studio[[:space:]]*:/) {
        studio_count++
        if (in_services && line == "  " service ":") studio_exact++
      }
    }
    END {
      exit !(name_count == 1 && name_exact == 1 &&
             services_count == 1 && services_exact == 1 &&
             studio_count == 1 && studio_exact == 1)
    }
  ' "${compose_file}" || return 1

  awk '
    {
      line = $0
      sub(/\r$/, "", line)
      copy = line
      project_count += gsub(/com\.halostrix\.project=/, "", copy)
      copy = line
      service_count += gsub(/com\.halostrix\.service=/, "", copy)
      if (line == "      com.halostrix.project=\"halostrix-unsloth-studio\" \\") project_exact++
      if (line == "      com.halostrix.service=\"studio\" \\") service_exact++
    }
    END {
      exit !(project_count == 1 && project_exact == 1 &&
             service_count == 1 && service_exact == 1)
    }
  ' "${dockerfile}"
}

while (($#)); do
  case "$1" in
    --dry-run) DRY_RUN=true ;;
    --all) ALL_REQUESTED=true ;;
    --yes) ASSUME_YES=true ;;
    --include-base) INCLUDE_BASE=true ;;
    -h|--help) usage; exit 0 ;;
    *) die "Opción desconocida: $1" ;;
  esac
  shift
done
${INCLUDE_BASE} && ! ${ALL_REQUESTED} && die "--include-base exige --all"
DO_DELETE=${ALL_REQUESTED}
${DRY_RUN} && DO_DELETE=false

SCRIPT_PATH="${BASH_SOURCE[0]}"
[[ -n "${SCRIPT_PATH}" && ! -L "${SCRIPT_PATH}" ]] || die "cleanup.sh no puede ser un enlace simbólico"
SCRIPT_DIR_LOGICAL="$(cd -- "$(dirname -- "${SCRIPT_PATH}")" && pwd -L)"
SCRIPT_DIR="$(cd -- "$(dirname -- "${SCRIPT_PATH}")" && pwd -P)"
[[ "${SCRIPT_DIR_LOGICAL}" == "${SCRIPT_DIR}" ]] || die "La ruta del workspace atraviesa un symlink/reparse"
ROOT_DIR="${SCRIPT_DIR}"
[[ -n "${ROOT_DIR}" && "${ROOT_DIR}" != "/" ]] || die "ROOT_DIR inseguro"
HOME_REAL="$(cd -- "${HOME:?HOME no definido}" && pwd -P)"
[[ "${ROOT_DIR}" != "${HOME_REAL}" ]] || die "ROOT_DIR no puede ser HOME"
ROOT_RESOLVED="$(readlink -f -- "${ROOT_DIR}")"
[[ -n "${ROOT_RESOLVED}" && "${ROOT_RESOLVED}" == "${ROOT_DIR}" ]] || die "Workspace ambiguo o atravesado por symlinks/reparse"
[[ ! -L "${ROOT_DIR}" && ! -L "$(dirname -- "${ROOT_DIR}")" ]] ||
  die "El workspace y su parent deben ser directorios reales"
validate_workspace_layout "${ROOT_DIR}" "unsloth-studio" ||
  die "Workspace fuera de los layouts aprobados: ${ROOT_DIR}"
if [[ "${ROOT_DIR}" == */workspaces/unsloth-studio ]]; then
  REPO_ROOT="${ROOT_DIR%/workspaces/unsloth-studio}"
  [[ ! -L "${REPO_ROOT}" && "$(cd -- "${REPO_ROOT}" && pwd -P)" == "${REPO_ROOT}" ]] ||
    die "Repo root ambiguo o atravesado por symlinks"
fi
[[ -f "${ROOT_DIR}/compose.yaml" && -f "${ROOT_DIR}/Dockerfile" &&
   -f "${ROOT_DIR}/scripts/common.sh" ]] || die "Workspace incompleto"
validate_workspace_identity "${ROOT_DIR}/compose.yaml" "${ROOT_DIR}/Dockerfile" ||
  die "Identidad del workspace ausente, incorrecta o ambigua"

DATA_ROOT="${ROOT_DIR}/data"
if [[ -e "${DATA_ROOT}" || -L "${DATA_ROOT}" ]]; then
  [[ ! -L "${DATA_ROOT}" ]] || die "data no puede ser un symlink"
  DATA_ROOT_REAL="$(readlink -f -- "${DATA_ROOT}")"
else
  DATA_ROOT_REAL="${DATA_ROOT}"
fi
[[ "${DATA_ROOT_REAL}" == "${DATA_ROOT}" && "${DATA_ROOT_REAL}" != "${ROOT_DIR}" ]] || die "Raíz de datos insegura"
DATA_NAMES=(studio hf-cache projects tmp)
VALID_DATA_TARGETS=()
for name in "${DATA_NAMES[@]}"; do
  target="${DATA_ROOT}/${name}"
  [[ ! -L "${target}" ]] || die "Destino de datos es symlink: ${target}"
  resolved="${target}"
  [[ ! -e "${target}" ]] || resolved="$(readlink -f -- "${target}")"
  [[ "${resolved}" == "${DATA_ROOT_REAL}/"* && "${resolved}" != "${DATA_ROOT_REAL}" ]] ||
    die "Destino fuera de data: ${target} -> ${resolved}"
  VALID_DATA_TARGETS+=("${target}")
done

valid_id() { [[ "$1" =~ ^sha256:[0-9a-f]{64}$ || "$1" =~ ^[0-9a-f]{12,64}$ ]]; }
valid_image_ref() {
  [[ "$1" =~ ^[a-z0-9][a-z0-9._/-]*(\:[A-Za-z0-9_][A-Za-z0-9_.-]{0,127})?(@sha256:[0-9a-f]{64})?$ ]] &&
    [[ "$1" != *".."* && "$1" != */ && "$1" != -* ]]
}
env_image() {
  local value=""
  [[ -f "${ROOT_DIR}/.env" ]] || return 0
  value="$(sed -n -E 's/^[[:space:]]*UNSLOTH_IMAGE[[:space:]]*=[[:space:]]*([^#[:space:]]+).*$/\1/p' "${ROOT_DIR}/.env" 2>/dev/null | tail -n 1 || true)"
  value="${value%\"}"; value="${value#\"}"
  valid_image_ref "${value}" && printf '%s\n' "${value}"
}
add_unique() {
  local value="$1" existing
  [[ -n "${value}" ]] || return
  for existing in "${CANDIDATES[@]-}"; do [[ "${existing}" == "${value}" ]] && return; done
  CANDIDATES+=("${value}")
}
image_metadata() {
  docker image inspect --format '{{.Id}}|{{index .Config.Labels "com.halostrix.project"}}|{{index .Config.Labels "com.halostrix.service"}}|{{index .Config.Labels "org.opencontainers.image.revision"}}|{{index .Config.Labels "com.halostrix.commit"}}' "$1"
}
image_is_exact() {
  local metadata="$1"
  [[ "${metadata}" == sha256:*"|${PROJECT_NAME}|${SERVICE_NAME}|${REVISION}|${REVISION}" ]]
}

CONTAINERS=()
NETWORKS=()
CANDIDATES=()
IMAGES=()
ERRORS=0
DOCKER_READY=false
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  DOCKER_READY=true
  if ! output="$(docker container ls -a \
      --filter "label=com.docker.compose.project=${PROJECT_NAME}" \
      --filter "label=com.docker.compose.service=${SERVICE_NAME}" --format '{{.ID}}')"; then
    printf 'ERROR: no se pudo enumerar contenedores\n' >&2; ((ERRORS+=1))
  elif [[ -n "${output}" ]]; then mapfile -t CONTAINERS <<<"${output}"; fi
  if ! output="$(docker network ls \
      --filter "name=^${NETWORK_NAME}$" \
      --filter "label=com.docker.compose.project=${PROJECT_NAME}" \
      --filter "label=com.docker.compose.network=${NETWORK_KEY}" --format '{{.ID}}')"; then
    printf 'ERROR: no se pudo enumerar redes\n' >&2; ((ERRORS+=1))
  elif [[ -n "${output}" ]]; then mapfile -t NETWORKS <<<"${output}"; fi
  if ! output="$(docker image ls \
      --filter "label=com.halostrix.project=${PROJECT_NAME}" \
      --filter "label=com.halostrix.service=${SERVICE_NAME}" \
      --filter "label=org.opencontainers.image.revision=${REVISION}" \
      --filter "label=com.halostrix.commit=${REVISION}" --format '{{.ID}}')"; then
    printf 'ERROR: no se pudo enumerar imágenes\n' >&2; ((ERRORS+=1))
  else while IFS= read -r candidate; do valid_id "${candidate}" && add_unique "${candidate}"; done <<<"${output}"; fi
  while IFS= read -r candidate; do add_unique "${candidate}"; done < <(env_image)
  if [[ -f "${ROOT_DIR}/.last-built-image" ]]; then
    candidate="$(tr -d '[:space:]' <"${ROOT_DIR}/.last-built-image")"
    valid_id "${candidate}" && add_unique "${candidate}"
  fi
  if [[ -f "${ROOT_DIR}/.previous-built-image" ]]; then
    candidate="$(tr -d '[:space:]' <"${ROOT_DIR}/.previous-built-image")"
    valid_id "${candidate}" && add_unique "${candidate}"
  fi
  for candidate in "${CANDIDATES[@]-}"; do
    (valid_id "${candidate}" || valid_image_ref "${candidate}") || continue
    if metadata="$(image_metadata "${candidate}" 2>/dev/null)" && image_is_exact "${metadata}"; then
      id="${metadata%%|*}"
      valid_id "${id}" && add=false
      for existing in "${IMAGES[@]-}"; do [[ "${existing}" == "${id}" ]] && add=true; done
      ${add:-false} || IMAGES+=("${id}")
    fi
  done
fi

printf 'Modo: %s\nProyecto/servicio Compose exactos: %s / %s\n' \
  "$(${DO_DELETE} && printf borrado || printf dry-run)" "${PROJECT_NAME}" "${SERVICE_NAME}"
if ${DOCKER_READY}; then
  printf 'Contenedores:\n'; ((${#CONTAINERS[@]})) && printf '  %s\n' "${CONTAINERS[@]}" || printf '  (ninguno)\n'
  printf 'Red exacta %s:\n' "${NETWORK_NAME}"; ((${#NETWORKS[@]})) && printf '  %s\n' "${NETWORKS[@]}" || printf '  (ninguna)\n'
  printf 'Imágenes con todos los labels exactos:\n'; ((${#IMAGES[@]})) && printf '  %s\n' "${IMAGES[@]}" || printf '  (ninguna)\n'
else
  if ${DO_DELETE}; then
    printf 'ERROR: Docker no disponible; limpieza Docker omitida; resultado parcial.\n' >&2
    ((ERRORS+=1))
  else
    printf 'Docker: no disponible; se omiten recursos Docker.\n'
  fi
fi
printf 'Datos enumerados:\n'
for target in "${VALID_DATA_TARGETS[@]}"; do printf '  %s\n' "${target}"; done
${INCLUDE_BASE} && printf 'Base compartida explícita: %s\n' "${BASE_IMAGE_EXACT}" ||
  printf 'Base ROCm compartida: conservada.\n'

${DO_DELETE} || {
  ${DRY_RUN} && ${ALL_REQUESTED} && printf 'Aviso: --dry-run domina --all/--yes; no se borra nada.\n'
  ((ERRORS == 0)) || exit 1
  exit 0
}
if ! ${ASSUME_YES}; then
  [[ -t 0 ]] || die "Se requiere TTY para confirmar; en automatización usa --all --yes"
  printf 'Escribe exactamente "%s": ' "${CONFIRM_PHRASE}"; IFS= read -r answer
  [[ "${answer}" == "${CONFIRM_PHRASE}" ]] || die "Confirmación no válida; no se borró nada"
fi
if ${INCLUDE_BASE} && ! ${ASSUME_YES}; then
  printf 'Escribe exactamente "%s": ' "${BASE_CONFIRM_PHRASE}"; IFS= read -r answer
  [[ "${answer}" == "${BASE_CONFIRM_PHRASE}" ]] || die "Confirmación de base no válida"
fi

removed_containers=0 removed_networks=0 removed_images=0 cleaned_dirs=0
if ${DOCKER_READY}; then
  for id in "${CONTAINERS[@]}"; do
    if ! valid_id "${id}"; then printf 'ERROR: ID de contenedor rechazado: %s\n' "${id}" >&2; ((ERRORS+=1)); continue; fi
    if ! labels="$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}' "${id}" 2>/dev/null)" ||
       [[ "${labels}" != "${PROJECT_NAME}|${SERVICE_NAME}" ]]; then
      printf 'ERROR: contenedor %s no supera revalidación exacta\n' "${id}" >&2; ((ERRORS+=1)); continue
    fi
    if docker container rm --force "${id}"; then ((removed_containers+=1)); else ((ERRORS+=1)); fi
  done
  for id in "${NETWORKS[@]}"; do
    if ! valid_id "${id}"; then printf 'ERROR: ID de red rechazado: %s\n' "${id}" >&2; ((ERRORS+=1)); continue; fi
    if ! labels="$(docker network inspect --format '{{.Name}}|{{index .Labels "com.docker.compose.project"}}|{{index .Labels "com.docker.compose.network"}}' "${id}" 2>/dev/null)" ||
       [[ "${labels}" != "${NETWORK_NAME}|${PROJECT_NAME}|${NETWORK_KEY}" ]]; then
      printf 'ERROR: red %s no supera revalidación exacta\n' "${id}" >&2; ((ERRORS+=1)); continue
    fi
    if docker network rm "${id}"; then ((removed_networks+=1)); else ((ERRORS+=1)); fi
  done
  for id in "${IMAGES[@]}"; do
    if ! metadata="$(image_metadata "${id}" 2>/dev/null)" || ! image_is_exact "${metadata}" ||
       [[ "${metadata%%|*}" != "${id}" ]]; then
      printf 'ERROR: imagen %s no supera revalidación exacta\n' "${id}" >&2; ((ERRORS+=1)); continue
    fi
    if docker image rm "${id}"; then ((removed_images+=1)); else ((ERRORS+=1)); fi
  done
  if ${INCLUDE_BASE} && docker image inspect "${BASE_IMAGE_EXACT}" >/dev/null 2>&1; then
    if docker image rm "${BASE_IMAGE_EXACT}"; then ((removed_images+=1)); else ((ERRORS+=1)); fi
  fi
fi
for target in "${VALID_DATA_TARGETS[@]}"; do
  if [[ -L "${target}" ]]; then printf 'ERROR: symlink detectado al revalidar: %s\n' "${target}" >&2; ((ERRORS+=1)); continue; fi
  mkdir -p -- "${target}" || { ((ERRORS+=1)); continue; }
  resolved="$(readlink -f -- "${target}")"
  if [[ "${resolved}" != "${DATA_ROOT_REAL}/"* || "${resolved}" == "${DATA_ROOT_REAL}" ]]; then
    printf 'ERROR: destino fuera de data al revalidar: %s\n' "${target}" >&2; ((ERRORS+=1)); continue
  fi
  if find "${resolved}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; then
    ((cleaned_dirs+=1))
  else
    printf 'ERROR: no se pudo limpiar %s\n' "${resolved}" >&2; ((ERRORS+=1))
  fi
done

printf 'Resumen: contenedores=%d redes=%d imágenes=%d directorios_limpiados=%d errores=%d\n' \
  "${removed_containers}" "${removed_networks}" "${removed_images}" "${cleaned_dirs}" "${ERRORS}"
((ERRORS == 0))
