#!/usr/bin/env bash
set -Eeuo pipefail

managed_venv="${UNSLOTH_STUDIO_HOME:?}/unsloth_studio"
if [[ ! -e "${managed_venv}" && ! -L "${managed_venv}" ]]; then
  ln -s /opt/venv "${managed_venv}"
elif [[ ! -L "${managed_venv}" || "$(readlink "${managed_venv}")" != /opt/venv ]]; then
  printf 'ERROR: ruta de venv administrado inesperada: %s\n' "${managed_venv}" >&2
  exit 1
fi

auth_db="${UNSLOTH_STUDIO_HOME}/auth/auth.db"
if [[ -f "${auth_db}" ]] && python3 - "${auth_db}" <<'PY'
import sqlite3
import sys

connection = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
try:
    has_admin = connection.execute("SELECT EXISTS(SELECT 1 FROM auth_user)").fetchone()[0]
finally:
    connection.close()
raise SystemExit(0 if has_admin else 1)
PY
then
  unset UNSLOTH_STUDIO_PASSWORD
fi

exec unsloth studio -H 0.0.0.0 -p 8888
