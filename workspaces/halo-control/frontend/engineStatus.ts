import type {State} from './api';

export type EngineId = 'gateway' | 'halogen' | 'comfyui' | 'unsloth' | 'llamafactory' | 'laya';
export type EngineStatus = {tone: 'success' | 'danger' | 'warning' | 'neutral'; label: string; detail: string; icon: 'check' | 'stop' | 'pause' | 'clock' | 'error' | 'unknown'};

export function runtimeStatus(raw?: string, health?: boolean): EngineStatus {
  if (raw === 'failed' || raw === 'dead') return {tone: 'danger', label: 'Fallo', detail: 'El servicio informa de un fallo. Revisa los logs.', icon: 'error'};
  if (['inactive', 'exited', 'created', 'stopped', 'unloaded'].includes(raw ?? '')) return {tone: 'danger', label: raw === 'unloaded' ? 'Descargado' : 'Parado', detail: 'No está en ejecución. Este estado no implica un fallo.', icon: 'stop'};
  if (raw === 'paused') return {tone: 'warning', label: 'Pausado', detail: 'El contenedor está suspendido, no detenido.', icon: 'pause'};
  const transition: Record<string, string> = {activating: 'Iniciando', deactivating: 'Deteniendo', restarting: 'Reiniciando', reloading: 'Recargando', refreshing: 'Recargando', removing: 'Eliminando'};
  if (raw && transition[raw]) return {tone: 'warning', label: transition[raw], detail: 'Operación en curso; espera antes de interpretar la disponibilidad.', icon: 'clock'};
  if (raw === 'legacy-active') return {tone: 'warning', label: 'Instancia anterior activa', detail: 'La instancia anterior requiere una parada explícita.', icon: 'error'};
  if (raw === 'missing' || raw === 'unconfigured') return {tone: 'neutral', label: raw === 'missing' ? 'No instalado' : 'Sin configurar', detail: 'El motor no está disponible para este panel.', icon: 'unknown'};
  if (raw === 'active' || raw === 'running') {
    if (health === true) return {tone: 'success', label: 'Activo', detail: 'En ejecución y con respuesta HTTP. No verifica inferencia ni entrenamiento.', icon: 'check'};
    return {tone: 'warning', label: health === false ? 'Sin respuesta HTTP' : 'Sin verificar', detail: 'En ejecución, pero sin disponibilidad HTTP confirmada. Puede estar iniciando; revisa los logs si persiste.', icon: 'clock'};
  }
  return {tone: 'neutral', label: 'Desconocido', detail: 'No hay información suficiente para confirmar el estado.', icon: 'unknown'};
}

export function engineStatus(engine: EngineId, state?: State): EngineStatus {
  if (!state) return runtimeStatus();
  if (engine === 'halogen') {
    if (state.halogen !== 'loaded') return runtimeStatus(state.halogen);
    if (state.services.gateway !== 'active' || state.gateway_health !== true) return {tone: 'warning', label: 'Cargado · revisar gateway', detail: 'Contenedor presente, pero gateway sin disponibilidad confirmada. No hay prueba individual de salud del modelo.', icon: 'error'};
    return {tone: 'success', label: 'Cargado', detail: 'Contenedor presente y gateway disponible. No verifica que el modelo haya terminado de cargar ni su inferencia.', icon: 'check'};
  }
  if (engine === 'laya') {
    if (state.laya?.state === 'running' && (!state.gateway_health || state.services.gateway !== 'active')) return {tone: 'warning', label: 'Revisar gateway', detail: 'Contenedor Laya activo, pero gateway compartido sin disponibilidad confirmada.', icon: 'error'};
    return runtimeStatus(state.laya?.state, state.laya?.health);
  }
  if (engine === 'gateway') return runtimeStatus(state.services.gateway, state.gateway_health);
  if (engine === 'comfyui') return runtimeStatus(state.services.comfyui, state.comfyui_health);
  const container = state[engine];
  const service = state.services[engine];
  if (['failed', 'activating', 'deactivating', 'reloading', 'restarting'].includes(service)) {
    const status = runtimeStatus(service);
    return {...status, detail: `${status.detail} Estado del contenedor: ${container?.state ?? 'desconocido'}.`};
  }
  return runtimeStatus(container?.state, container?.health);
}
