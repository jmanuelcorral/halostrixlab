#!/usr/bin/env bash
set -Eeuo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
failed=0
while IFS= read -r -d '' script; do
  if LC_ALL=C grep -q $'\r' "${script}"; then
    printf 'CR detectado: %s\n' "${script}" >&2
    failed=1
  fi
  bash -n "${script}" || failed=1
done < <(find "${ROOT_DIR}" -path "${ROOT_DIR}/data" -prune -o -type f -name '*.sh' -print0)
((failed == 0))
printf 'shell LF and bash syntax: OK\n'
