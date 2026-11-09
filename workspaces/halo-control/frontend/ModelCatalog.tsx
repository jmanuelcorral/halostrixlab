import {useState} from 'react';
import {Button} from '@patternfly/react-core';
import type {State} from './api';
import {bytes} from './api';
import {EngineIdentity} from './EngineIdentity';

export function selectionAction(selected: string[]): string | undefined {
  const key = [...selected].sort().join(',');
  return ({halogen: 'catalog-halogen'} as Record<string,string>)[key];
}

export function ModelCatalog({state, busy, perform, detail, logs}: {
  state?: State; busy: boolean; perform: (action: string) => void;
  detail: () => void; logs: () => void;
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const catalog = state?.catalog;
  const action = selectionAction(selected);
  const blockedStack = state?.services.comfyui === 'active' || state?.comfyui_health ||
    ['running','paused','legacy-active'].includes(state?.unsloth?.state ?? '') ||
    ['running','paused','legacy-active'].includes(state?.llamafactory?.state ?? '');
  const disabled = busy || !catalog?.available || state?.services.gateway !== 'active';
  const loadDisabled = disabled || blockedStack;
  const ids = ['halogen'] as const;
  const load = {halogen:'catalog-halogen'};
  const unload = {halogen:'halogen-unload'};
  const loadLabel = {halogen:'Cargar Halogen'};
  const unloadLabel = {halogen:'Descargar Halogen'};
  const total = selected.reduce((sum, id) => sum + (catalog?.models.find(model => model.id === id)?.weights_bytes ?? 0), 0);
  const format = (value: number|null|undefined) => value == null ? 'No verificado' : value.toLocaleString('es-ES');
  return <section aria-label="Catálogo de modelos" className="model-catalog">
    <div className="section-heading"><h2>Catálogo de modelos · llama-swap</h2><span className="muted">Un único modelo GPU: Halogen</span></div>
    <div className="panel"><p>Halogen sirve el modelo de texto y visión en la GPU. Cargarlo descarga cualquier otro modelo GPU del gateway.</p>
      <p>Los modelos del NPU (decisiones, embeddings y rerank) se sirven desde Halogen como peers: no requieren carga propia, pero dependen de que Halogen esté cargado.</p>
      <p>No detiene automáticamente ComfyUI, Studio ni LLaMA-Factory. Detener llama-swap descarga todos sus modelos.</p>
      {state?.services.gateway !== 'active' && <p className="warning">Arranca primero el gateway compartido.</p>}
      {blockedStack && <p className="warning">Otro stack ocupa recursos GPU. Deténlo explícitamente antes de cargar el catálogo.</p>}
      {!catalog?.available && <p className="warning">{catalog?.reason || 'Catálogo activo no disponible; controles bloqueados.'}</p>}
      <p>Límite global configurado: {format(catalog?.global_slots)} peticiones. Pesos seleccionados en disco: {selected.length ? bytes(total) : 'Ninguno'}.</p>
      <p className="muted">No es una estimación de RAM/GPU libre: faltan KV, buffers, activaciones y cachés. En UMA no sumes contadores de RAM y GTT. B = mil millones de parámetros, no billones españoles.</p>
      <Button variant="primary" isDisabled={Boolean(loadDisabled || !action)} onClick={() => action && perform(action)}>Arrancar selección compatible</Button>
      <p className="muted">Operación secuencial supervisada, no transacción atómica. Si falla, puede quedar un modelo cargado. Clientes externos pueden cambiar la residencia. La parada GPU puede tardar un minuto.</p>
    </div>
    <div className="service-grid model-grid">{ids.map(id => {
      const model = catalog?.models.find(value => value.id === id);
      return <article className="panel model" key={id} aria-label={`Modelo ${id}`}>
        <EngineIdentity engine={id} state={state}/>
        <h4>{model?.name ?? 'Modelo sin verificar'}</h4><p><code>{model?.alias ?? id}</code></p>
        <label><input type="checkbox" checked={selected.includes(id)} disabled={busy || !catalog?.available} onChange={event => setSelected(current => event.target.checked ? [...current,id] : current.filter(value => value !== id))}/> Seleccionar Halogen</label>
        <dl><dt>Recurso / motor</dt><dd>{model ? `${model.device} / ${model.engine}` : 'No verificado'}</dd>
          <dt>Máximo tokens por sesión</dt><dd>{format(model?.context)} (entrada + salida)</dd>
          <dt>Máximo slots configurados</dt><dd>{format(model?.slots)}</dd>
          <dt>Salida configurada</dt><dd>{model?.output == null ? 'No aplica / no verificado' : format(model.output)}</dd>
          <dt>Pesos en disco</dt><dd>{model ? bytes(model.weights_bytes) : 'No verificado'}</dd>
          <dt>Parámetros nominales</dt><dd>{model?.parameters_b == null ? 'No verificado' : `${model.parameters_b.toLocaleString('es-ES')} B`}</dd>
          <dt>Formato</dt><dd>{model?.quantization ?? 'No verificado'}</dd>
          {model?.kv_pool != null && <><dt>Pool KV compartido</dt><dd>{format(model.kv_pool)} posiciones</dd></>}
        </dl><p className="muted">{model?.note}</p>
        <div className="actions"><Button variant="primary" isDisabled={Boolean(loadDisabled)} onClick={() => perform(load[id])}>{loadLabel[id]}</Button><Button variant="secondary" isDisabled={disabled} onClick={() => perform(unload[id])}>{unloadLabel[id]}</Button></div>
        <Button variant="link" onClick={detail}>Ficha y logs de Halogen</Button>
        <Button variant="link" onClick={logs}>Logs compartidos de Halogen</Button>
        <p className="muted">Descargar conserva el catálogo; otra petición puede cargarlo.</p>
      </article>;
    })}</div>
  </section>;
}
