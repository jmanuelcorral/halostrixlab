import './api';

export async function checkMaintenanceSession() {
  try {
    const sessions = await window.cockpit!.spawn(['/usr/bin/tmux', '-S', '/run/halo-control/maintenance.sock', 'list-sessions', '-F', '#{session_name}'], {superuser: 'require', err: 'message', environ: ['LC_ALL=C']});
    return sessions.split('\n').some(name => name.trim() === 'update');
  } catch (reason) {
    const failure = reason as {exit_status?: number; message?: string; problem?: string};
    if (failure.exit_status === 1 && !failure.problem && /no server running|No such file or directory/.test(failure.message ?? String(reason))) return false;
    throw new Error('No se pudo comprobar la sesión de mantenimiento: ' + String(reason));
  }
}

export function rebootError(reason: unknown) {
  const text = String(reason);
  if (/Close the update session|Update session still open/.test(text)) return 'La consola de actualización sigue abierta. Abre la sesión existente; si muestra que la actualización terminó y pide Enter, pulsa Enter para cerrarla. Después vuelve a confirmar el reinicio. No se ha forzado ni cancelado ninguna actualización.';
  if (/access-denied/.test(text)) return 'Cockpit ha denegado la autorización. Activa Acceso administrativo en la cabecera antes de volver a confirmar el reinicio.';
  return text;
}
