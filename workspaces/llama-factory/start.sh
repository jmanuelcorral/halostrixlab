#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/common.sh
source "${ROOT_DIR}/scripts/common.sh"

prepare_start_environment

for directory in hf-cache models datasets outputs cache config logs; do
  mkdir -p "${ROOT_DIR}/data/${directory}"
done

printf 'GPU: /dev/kfd + %s (GID suplementario %s)\n' "${RENDER_DEVICE}" "${DEVICE_GID}"
printf 'Arrancando %s sin reconstruir (no inicia entrenamiento)...\n' "${LLAMAFACTORY_IMAGE}"
compose up -d --no-build llamaboard

container_id="$(compose ps -q llamaboard)"
[[ -n "${container_id}" ]] || die "Compose no devolvió el contenedor de LlamaBoard"

printf 'Esperando healthcheck'
for _ in $(seq 1 60); do
  status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}")"
  case "${status}" in
    healthy)
      printf '\nLlamaBoard listo: http://%s:%s\n' "${WEB_BIND}" "${WEB_PORT}"
      [[ "${WEB_BIND}" == "0.0.0.0" ]] && printf 'LAN: abre http://IP_DEL_HOST:%s (protege el puerto con firewall).\n' "${WEB_PORT}"
      exit 0
      ;;
    unhealthy|exited|dead)
      printf '\nFallo de arranque (%s). Últimas líneas:\n' "${status}" >&2
      compose logs --tail=80 llamaboard >&2
      exit 1
      ;;
  esac
  printf '.'
  sleep 2
done

printf '\nHealthcheck aún pendiente. Consulta ./status.sh y ./logs.sh\n'
exit 1
