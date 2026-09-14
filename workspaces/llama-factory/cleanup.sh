#!/usr/bin/env bash
set -Euo pipefail

readonly PROJECT_NAME="halostrix-llamafactory"
readonly SERVICE_NAME="llamaboard"
readonly NETWORK_NAME="${PROJECT_NAME}_default"
readonly DEFAULT_PROJECT_IMAGE="halostrix-llamafactory:v0.9.5-rocm7.14"
readonly DEFAULT_REVISION="7af909522a951e3ad9f022ea6f88b6755257eaa5"
readonly DEFAULT_BASE_IMAGE="rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad"
readonly CONFIRM_PHRASE="ELIMINAR halostrix-llamafactory SIN RECUPERACION"

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

usage() {
  cat <<'EOF'
Uso: ./cleanup.sh [--dry-run] [--all [--yes] [--include-base]]

Sin opciones (o con --dry-run) sólo muestra lo que se eliminaría.
--all          elimina recursos atribuidos exactamente y el contenido de data.
--yes          omite ambas confirmaciones; por sí solo nunca elimina nada.
--include-base incluye la base ROCm fijada por digest (requiere --all).
EOF
}

requested_all=false
dry_run=false
assume_yes=false
include_base=false
for arg in "$@"; do
  case "${arg}" in
    --dry-run) dry_run=true ;;
    --all) requested_all=true ;;
    --yes) assume_yes=true ;;
    --include-base) include_base=true ;;
    -h|--help) usage; exit 0 ;;
    *) die "Opción desconocida: ${arg}" ;;
  esac
done
${include_base} && ! ${requested_all} && die "--include-base sólo se permite junto a --all"
do_all="${requested_all}"
# Deliberadamente se aplica después de procesar todos los argumentos: --dry-run siempre domina.
${dry_run} && do_all=false

script_source="${BASH_SOURCE[0]}"
[[ -n "${script_source}" && ! -L "${script_source}" ]] || die "cleanup.sh no puede ejecutarse mediante un symlink"
script_dir_logical="$(cd -- "$(dirname -- "${script_source}")" && pwd -L)" || die "No se pudo resolver el workspace"
ROOT_DIR="$(cd -- "$(dirname -- "${script_source}")" && pwd -P)" || die "No se pudo resolver el workspace"
readonly ROOT_DIR
[[ "${ROOT_DIR}" == /* && "${ROOT_DIR}" != "/" && "${ROOT_DIR}" != "${HOME:-/__unset__}" ]] ||
  die "ROOT_DIR inseguro: ${ROOT_DIR}"
[[ "${script_dir_logical}" == "${ROOT_DIR}" ]] || die "La ruta del workspace contiene symlinks"
[[ ! -L "${ROOT_DIR}" && ! -L "$(dirname -- "${ROOT_DIR}")" ]] ||
  die "El workspace y su parent deben ser directorios reales"
validate_workspace_layout "${ROOT_DIR}" "llama-factory" ||
  die "Workspace fuera de los layouts aprobados: ${ROOT_DIR}"
if [[ "${ROOT_DIR}" == */workspaces/llama-factory ]]; then
  repo_root="${ROOT_DIR%/workspaces/llama-factory}"
  [[ ! -L "${repo_root}" && "$(cd -- "${repo_root}" && pwd -P)" == "${repo_root}" ]] ||
    die "Repo root ambiguo o atravesado por symlinks"
fi
[[ -f "${ROOT_DIR}/compose.yaml" && -f "${ROOT_DIR}/Dockerfile" &&
   -f "${ROOT_DIR}/scripts/common.sh" ]] ||
  die "No se reconoce la raíz de LLaMA-Factory"
grep -Eq '^[[:space:]]*name:[[:space:]]*halostrix-llamafactory[[:space:]]*$' "${ROOT_DIR}/compose.yaml" ||
  die "compose.yaml no declara el proyecto exacto"
grep -Eq '^[[:space:]]{2}llamaboard:[[:space:]]*$' "${ROOT_DIR}/compose.yaml" ||
  die "compose.yaml no declara el servicio exacto"

readonly DATA_ROOT="${ROOT_DIR}/data"
readonly ENV_FILE="${ROOT_DIR}/.env"
readonly -a DATA_NAMES=(hf-cache models datasets outputs cache config logs)

env_value() {
  local key="$1" line value=""
  [[ -r "${ENV_FILE}" && ! -L "${ENV_FILE}" ]] || return 0
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%$'\r'}"
    [[ "${line}" =~ ^[[:space:]]*${key}[[:space:]]*=(.*)$ ]] && value="${BASH_REMATCH[1]}"
  done <"${ENV_FILE}"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  if [[ "${value}" =~ ^\"([^\"]*)\"$ || "${value}" =~ ^\'([^\']*)\'$ ]]; then value="${BASH_REMATCH[1]}"; fi
  [[ "${value}" != *$'\n'* && "${value}" != *$'\r'* ]] && printf '%s' "${value}"
}

bytes_for_path() {
  local result
  if result="$(du -sb -- "$1" 2>/dev/null)"; then printf '%s' "${result%%[[:space:]]*}"
  elif result="$(du -sk -- "$1" 2>/dev/null)"; then printf '%s' "$(( ${result%%[[:space:]]*} * 1024 ))"
  else printf 'unknown'
  fi
}

validate_data_path() {
  local path="$1" resolved_data resolved_path
  [[ "${path}" == "${DATA_ROOT}/"* && "${path}" != "${DATA_ROOT}" ]] ||
    die "Ruta de datos fuera del ámbito permitido: ${path}"
  [[ ! -L "${DATA_ROOT}" && ! -L "${path}" ]] || die "Symlink/reparse ambiguo rechazado: ${path}"
  [[ -d "${path}" ]] || return 0
  resolved_data="$(cd -- "${DATA_ROOT}" && pwd -P)" || die "No se pudo validar data"
  resolved_path="$(cd -- "${path}" && pwd -P)" || die "No se pudo validar ${path}"
  [[ "${resolved_data}" == "${DATA_ROOT}" && "$(dirname -- "${path}")" == "${DATA_ROOT}" &&
     "${resolved_path}" == "${resolved_data}/$(basename -- "${path}")" ]] ||
    die "Ruta no contenida de forma segura: ${path}"
}

declare -a data_paths=() container_ids=() network_ids=() image_ids=()
data_bytes_before=0
data_size_known=true
if [[ -e "${DATA_ROOT}" || -L "${DATA_ROOT}" ]]; then
  [[ -d "${DATA_ROOT}" && ! -L "${DATA_ROOT}" ]] || die "data debe ser un directorio real"
  [[ "$(cd -- "${DATA_ROOT}" && pwd -P)" == "${DATA_ROOT}" ]] || die "data resuelve fuera del workspace"
fi
for name in "${DATA_NAMES[@]}"; do
  path="${DATA_ROOT}/${name}"
  validate_data_path "${path}"
  data_paths+=("${path}")
  if [[ -d "${path}" ]]; then
    size="$(bytes_for_path "${path}")"
    if [[ "${size}" =~ ^[0-9]+$ ]]; then data_bytes_before=$((data_bytes_before + size)); else data_size_known=false; fi
  fi
done

failures=0
docker_ready=false
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then docker_ready=true; fi

append_unique() {
  local -n target="$1"
  local value="$2" existing
  [[ -n "${value}" ]] || return
  for existing in "${target[@]}"; do [[ "${existing}" == "${value}" ]] && return; done
  target+=("${value}")
}

expected_revision="${LLAMAFACTORY_COMMIT:-$(env_value LLAMAFACTORY_COMMIT)}"
expected_revision="${expected_revision:-${DEFAULT_REVISION}}"
expected_base="${BASE_IMAGE:-$(env_value BASE_IMAGE)}"
expected_base="${expected_base:-${DEFAULT_BASE_IMAGE}}"
[[ "${expected_revision}" =~ ^[0-9a-f]{40}$ ]] || expected_revision="${DEFAULT_REVISION}"
[[ "${expected_base}" =~ ^[^[:space:]@]+@sha256:[0-9a-f]{64}$ ]] || expected_base="${DEFAULT_BASE_IMAGE}"

image_record() {
  docker image inspect --format '{{.Id}}|{{index .Config.Labels "com.halostrix.project"}}|{{index .Config.Labels "com.halostrix.service"}}|{{index .Config.Labels "org.opencontainers.image.revision"}}|{{index .Config.Labels "com.halostrix.base-image"}}' "$1" 2>/dev/null
}

image_record_is_owned() {
  local record="$1" id project service revision base extra
  IFS='|' read -r id project service revision base extra <<<"${record}"
  [[ -z "${extra:-}" && "${id}" =~ ^sha256:[0-9a-f]{64}$ &&
     "${project}" == "${PROJECT_NAME}" && "${service}" == "${SERVICE_NAME}" &&
     "${revision}" == "${expected_revision}" && "${base}" == "${expected_base}" ]]
}

container_record() {
  docker inspect --format '{{.Id}}|{{index .Config.Labels "com.docker.compose.project"}}|{{index .Config.Labels "com.docker.compose.service"}}|{{index .Config.Labels "com.halostrix.project"}}|{{index .Config.Labels "com.halostrix.service"}}' "$1" 2>/dev/null
}

container_record_is_owned() {
  local record="$1" id compose_project compose_service project service extra
  IFS='|' read -r id compose_project compose_service project service extra <<<"${record}"
  [[ -z "${extra:-}" && "${id}" =~ ^[0-9a-f]{12,64}$ &&
     "${compose_project}" == "${PROJECT_NAME}" && "${compose_service}" == "${SERVICE_NAME}" &&
     "${project}" == "${PROJECT_NAME}" && "${service}" == "${SERVICE_NAME}" ]]
}

network_record() {
  docker network inspect --format '{{.Id}}|{{.Name}}|{{index .Labels "com.docker.compose.project"}}|{{index .Labels "com.docker.compose.network"}}' "$1" 2>/dev/null
}

network_record_is_owned() {
  local record="$1" id name project network extra
  IFS='|' read -r id name project network extra <<<"${record}"
  [[ -z "${extra:-}" && "${id}" =~ ^[0-9a-f]{12,64}$ && "${name}" == "${NETWORK_NAME}" &&
     "${project}" == "${PROJECT_NAME}" && "${network}" == "default" ]]
}

base_image_id=""
if ${docker_ready}; then
  if container_list="$(docker ps -aq --filter "label=com.docker.compose.project=${PROJECT_NAME}" --filter "label=com.docker.compose.service=${SERVICE_NAME}")"; then
    while IFS= read -r id; do
      [[ -n "${id}" ]] || continue
      if record="$(container_record "${id}")" && container_record_is_owned "${record}"; then
        append_unique container_ids "${id}"
      else
        printf 'AVISO: contenedor no atribuible ignorado: %s\n' "${id}" >&2
      fi
    done <<<"${container_list}"
  else
    printf 'FALLO: no se pudo inventariar contenedores.\n' >&2; failures=$((failures + 1))
  fi

  if network_list="$(docker network ls -q --filter "name=^${NETWORK_NAME}$" --filter "label=com.docker.compose.project=${PROJECT_NAME}" --filter "label=com.docker.compose.network=default")"; then
    while IFS= read -r id; do
      [[ -n "${id}" ]] || continue
      if record="$(network_record "${id}")" && network_record_is_owned "${record}"; then
        append_unique network_ids "${id}"
      else
        printf 'FALLO: red no atribuible ignorada: %s\n' "${id}" >&2; failures=$((failures + 1))
      fi
    done <<<"${network_list}"
  else
    printf 'FALLO: no se pudo inventariar la red exacta.\n' >&2; failures=$((failures + 1))
  fi

  declare -a image_candidates=()
  configured_image="${LLAMAFACTORY_IMAGE:-$(env_value LLAMAFACTORY_IMAGE)}"
  configured_run_image="${RUN_IMAGE:-$(env_value RUN_IMAGE)}"
  append_unique image_candidates "${configured_image:-${DEFAULT_PROJECT_IMAGE}}"
  append_unique image_candidates "${configured_run_image}"
  if [[ -r "${ROOT_DIR}/.last-built-image" && ! -L "${ROOT_DIR}/.last-built-image" ]]; then
    last_image="$(tr -d '\r\n' <"${ROOT_DIR}/.last-built-image")"
    append_unique image_candidates "${last_image}"
  fi
  if image_list="$(docker image ls -q --filter "label=com.halostrix.project=${PROJECT_NAME}" --filter "label=com.halostrix.service=${SERVICE_NAME}")"; then
    while IFS= read -r id; do append_unique image_candidates "${id}"; done <<<"${image_list}"
  else
    printf 'FALLO: no se pudo inventariar imágenes.\n' >&2; failures=$((failures + 1))
  fi
  for candidate in "${image_candidates[@]}"; do
    [[ -n "${candidate}" ]] || continue
    if record="$(image_record "${candidate}")" && image_record_is_owned "${record}"; then
      append_unique image_ids "${record%%|*}"
    else
      printf 'AVISO: imagen no atribuible ignorada: %s\n' "${candidate}" >&2
    fi
  done

  if ${include_base}; then
    base_reference="${BASE_IMAGE:-$(env_value BASE_IMAGE)}"
    [[ "${base_reference}" =~ ^[^[:space:]@]+@sha256:[0-9a-f]{64}$ ]] ||
      die "BASE_IMAGE no contiene una referencia exacta por digest"
    if base_record="$(docker image inspect --format '{{.Id}}|{{join .RepoDigests "\n"}}' "${base_reference}" 2>/dev/null)"; then
      base_image_id="${base_record%%|*}"
      repo_digests="${base_record#*|}"
      [[ "${base_image_id}" =~ ^sha256:[0-9a-f]{64}$ ]] &&
        grep -Fxq -- "${base_reference}" <<<"${repo_digests}" ||
        die "Docker no confirmó el digest exacto de BASE_IMAGE"
    else
      die "La imagen base exacta no existe localmente"
    fi
  fi
elif ${do_all}; then
  printf 'FALLO: Docker no está disponible; sólo se procesarán datos explícitos.\n' >&2
  failures=$((failures + 1))
fi

mode="DRY-RUN"; ${do_all} && mode="BORRADO"
printf 'Modo: %s\nRaíz validada: %s\nProyecto/servicio: %s / %s\n' "${mode}" "${ROOT_DIR}" "${PROJECT_NAME}" "${SERVICE_NAME}"
printf '\nDatos que %s:\n' "$(${do_all} && printf 'se eliminarán' || printf 'se eliminarían')"
for path in "${data_paths[@]}"; do
  if [[ -d "${path}" ]]; then printf '  %s/ (contenido; %s bytes)\n' "${path}" "$(bytes_for_path "${path}")"
  else printf '  %s/ (no existe)\n' "${path}"; fi
done
printf '\nDocker que %s:\n' "$(${do_all} && printf 'se eliminará' || printf 'se eliminaría')"
printf '  contenedores:'; printf ' %s' "${container_ids[@]:-}"; printf '\n'
printf '  red exacta:'; printf ' %s' "${network_ids[@]:-}"; printf '\n'
printf '  imágenes:'; printf ' %s' "${image_ids[@]:-}"; printf '\n'
${include_base} && printf '  base ROCm: %s (%s)\n' "${base_reference}" "${base_image_id}"
printf '  volúmenes Docker: no administrados (Compose sólo declara bind mounts).\n'
${data_size_known} && printf 'Uso estimado de data antes: %s bytes\n' "${data_bytes_before}"

if ! ${do_all}; then
  printf 'DRY-RUN terminado; no se eliminó nada.\n'
  (( failures == 0 ))
  exit $?
fi

if ! ${assume_yes}; then
  printf '\nEscribe exactamente "%s" para continuar: ' "${CONFIRM_PHRASE}" >&2
  IFS= read -r answer
  [[ "${answer}" == "${CONFIRM_PHRASE}" ]] || die "Confirmación incorrecta; no se eliminó nada"
  if ${include_base}; then
    base_phrase="ELIMINAR BASE ROCM ${base_reference#*@}"
    printf 'Segunda confirmación: escribe exactamente "%s": ' "${base_phrase}" >&2
    IFS= read -r answer
    [[ "${answer}" == "${base_phrase}" ]] || die "Confirmación de base incorrecta; no se eliminó nada"
  fi
fi

attempted=0
succeeded=0
for id in "${container_ids[@]}"; do
  attempted=$((attempted + 1))
  if record="$(container_record "${id}")" && container_record_is_owned "${record}"; then
    if docker rm -f -- "${id}" >/dev/null; then succeeded=$((succeeded + 1))
    else printf 'FALLO: no se pudo borrar contenedor %s\n' "${id}" >&2; failures=$((failures + 1)); fi
  else
    printf 'FALLO: cambió ownership del contenedor %s; no se borra.\n' "${id}" >&2; failures=$((failures + 1))
  fi
done
for id in "${network_ids[@]}"; do
  attempted=$((attempted + 1))
  if record="$(network_record "${id}")" && network_record_is_owned "${record}"; then
    if docker network rm -- "${id}" >/dev/null; then succeeded=$((succeeded + 1))
    else printf 'FALLO: no se pudo borrar red %s\n' "${id}" >&2; failures=$((failures + 1)); fi
  else
    printf 'FALLO: cambió ownership de la red %s; no se borra.\n' "${id}" >&2; failures=$((failures + 1))
  fi
done
for id in "${image_ids[@]}"; do
  attempted=$((attempted + 1))
  if record="$(image_record "${id}")" && image_record_is_owned "${record}" && [[ "${record%%|*}" == "${id}" ]]; then
    if docker image rm -- "${id}" >/dev/null; then succeeded=$((succeeded + 1))
    else printf 'FALLO: no se pudo borrar imagen %s\n' "${id}" >&2; failures=$((failures + 1)); fi
  else
    printf 'FALLO: cambió ownership de la imagen %s; no se borra.\n' "${id}" >&2; failures=$((failures + 1))
  fi
done
if ${include_base}; then
  attempted=$((attempted + 1))
  if base_record="$(docker image inspect --format '{{.Id}}|{{join .RepoDigests "\n"}}' "${base_reference}" 2>/dev/null)" &&
     [[ "${base_record%%|*}" == "${base_image_id}" ]] &&
     grep -Fxq -- "${base_reference}" <<<"${base_record#*|}"; then
    if docker image rm -- "${base_image_id}" >/dev/null; then succeeded=$((succeeded + 1))
    else printf 'FALLO: no se pudo borrar base %s\n' "${base_image_id}" >&2; failures=$((failures + 1)); fi
  else
    printf 'FALLO: cambió el digest/ID de la base; no se borra.\n' >&2; failures=$((failures + 1))
  fi
fi

for path in "${data_paths[@]}"; do
  validate_data_path "${path}"
  if [[ -d "${path}" ]]; then
    if find "${path}" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +; then :;
    else printf 'FALLO: limpieza parcial de %s\n' "${path}" >&2; failures=$((failures + 1)); fi
  fi
done

data_bytes_after=0
after_known=true
for path in "${data_paths[@]}"; do
  if [[ -d "${path}" ]]; then
    size="$(bytes_for_path "${path}")"
    if [[ "${size}" =~ ^[0-9]+$ ]]; then data_bytes_after=$((data_bytes_after + size)); else after_known=false; fi
  fi
done
printf '\nResumen parcial: Docker intentados=%s, correctos=%s, fallidos=%s; fallos totales=%s.\n' \
  "${attempted}" "${succeeded}" "$((attempted - succeeded))" "${failures}"
if ${data_size_known} && ${after_known}; then
  printf 'Data antes=%s bytes; después=%s bytes; diferencia=%s bytes.\n' \
    "${data_bytes_before}" "${data_bytes_after}" "$((data_bytes_before - data_bytes_after))"
fi
printf 'Para reconstruir: cp .env.example .env (si falta), ./build.sh, ./start.sh\n'
(( failures == 0 ))
