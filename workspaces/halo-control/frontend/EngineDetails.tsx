import React, {useEffect, useRef, useState} from 'react';
import {Button} from '@patternfly/react-core';
import {api} from './api';
import {useToastMessage} from './Notifications';
import './engine-details.css';

export type EngineDetail = {
  id: string; title: string; state: string; editable: boolean; reason: string;
  values: Record<string, number | boolean>;
  fields: {name: string; label: string; type: string; min: number | null; max: number | null}[];
  revision: string; paths: string[]; saved: unknown; effective: unknown; revealed: boolean;
};

export function EngineDetails({engine, busy, onClose}: {engine: string; busy: boolean; onClose: () => void}) {
  const [detail, setDetail] = useState<EngineDetail>();
  const [draft, setDraft] = useState<Record<string, number | boolean>>({});
  const [revision, setRevision] = useState('');
  const [tab, setTab] = useState('Configuración');
  const [privateDetail, setPrivateDetail] = useState<EngineDetail>();
  const [logs, setLogs] = useState({text: '', source: ''});
  const [paused, setPaused] = useState(false);
  const [filter, setFilter] = useState('');
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  useToastMessage(notice, 'success');
  useToastMessage(error, 'danger');
  const action = useRef(false);
  const alive = useRef(true);
  const secretRequest = useRef(0);
  useEffect(() => {
    alive.current = true;
    let timer: ReturnType<typeof setTimeout>;
    let first = true;
    const refresh = async () => {
      try {
        const value = await api<EngineDetail>('engine-detail', engine);
        if (alive.current) {
          setDetail(value);
          if (first) {setDraft(value.values); setRevision(value.revision); first = false;}
        }
      } catch (reason) {
        if (alive.current) {setError(String(reason)); setDetail(undefined); setPrivateDetail(undefined); secretRequest.current++;}
      } finally {if (alive.current) timer = setTimeout(refresh, 5000);}
    };
    void refresh();
    return () => {alive.current = false; secretRequest.current++; clearTimeout(timer);};
  }, [engine]);
  useEffect(() => {
    if (tab !== 'Logs' || paused) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    const refresh = async () => {
      try {
        const value = await api<{text: string; source: string}>('engine-logs', engine);
        if (!stopped) setLogs(value);
      } catch (reason) {if (!stopped) setError(String(reason));}
      finally {if (!stopped) timer = setTimeout(refresh, 3000);}
    };
    void refresh();
    return () => {stopped = true; clearTimeout(timer);};
  }, [engine, tab, paused]);
  const changeTab = (value: string) => {setTab(value); setPrivateDetail(undefined); secretRequest.current++;};
  const reveal = async () => {
    if (privateDetail) {setPrivateDetail(undefined); secretRequest.current++; return;}
    if (action.current) return;
    action.current = true; setPending(true); setError('');
    const request = ++secretRequest.current;
    try {
      const value = await api<EngineDetail>('engine-reveal', engine);
      if (alive.current && request === secretRequest.current) setPrivateDetail(value);
    } catch (reason) {if (alive.current) setError(String(reason));}
    finally {action.current = false; if (alive.current) setPending(false);}
  };
  const save = async () => {
    if (action.current || busy || !detail?.editable) return;
    action.current = true; setPending(true); setError(''); setNotice(''); setPrivateDetail(undefined); secretRequest.current++;
    try {
      const value = await api<EngineDetail>('engine-save', engine, {revision, values: draft});
      if (alive.current) {setDetail(value); setDraft(value.values); setRevision(value.revision); setNotice(engine === 'unsloth' ? 'Studio recreado y detenido. Contenedor anterior conservado; salud pendiente del próximo arranque manual.' : 'Guardado. Se aplicará en el próximo arranque manual; no se ha arrancado ni detenido ningún servicio.');}
    } catch (reason) {if (alive.current) setError(String(reason));}
    finally {action.current = false; if (alive.current) setPending(false);}
  };
  const shown = privateDetail ?? detail;
  const stale = detail && detail.revision !== revision;
  return <section className="panel engine-details" aria-label="Ficha del motor">
    <div className="section-heading"><div><span className="eyebrow">FICHA DEL MOTOR</span><h2>{detail?.title ?? engine}</h2></div><Button variant="secondary" onClick={onClose}>Volver a servicios</Button></div>
    <div className="engine-tabs" role="tablist" aria-label="Detalle del motor">{['Configuración', 'Entorno', 'Logs'].map(name => <button key={name} role="tab" aria-selected={tab === name} onClick={() => changeTab(name)}>{name}</button>)}</div>
    <div role="tabpanel" aria-label={tab}>
      {tab === 'Configuración' && <>
        <p>Estado de la unidad: <strong>{detail?.state ?? 'consultando'}</strong>. Guardar nunca reinicia el servicio.</p>
        {detail?.reason && <p className="warning">{detail.reason}</p>}
        {engine === 'unsloth' && <p className="warning">Guardar recrea el contenedor detenido con la misma imagen, montajes, permisos, dispositivos y credenciales. Conserva el anterior para recuperación; no arranca Studio ni verifica salud. Los contenedores comparten datos, no son copias de seguridad de esos datos. No usar Compose para recrearlo sin reconciliar estos cambios.</p>}
        {stale && <p className="warning">La configuración cambió desde que abriste el editor. Recarga los campos antes de guardar.</p>}
        <form onSubmit={event => {event.preventDefault(); void save();}}>
          <fieldset disabled={!detail?.editable || busy || pending || Boolean(stale)} className="engine-fields">
            <legend>Campos permitidos para el próximo arranque</legend>
            {detail?.fields.map(field => <label key={field.name} className="engine-field" htmlFor={'engine-' + field.name}><span>{field.label}<small>{field.name}</small></span>{field.type === 'boolean' ? <input id={'engine-' + field.name} type="checkbox" checked={draft[field.name] === true} onChange={event => setDraft({...draft, [field.name]: event.target.checked})}/> : <input id={'engine-' + field.name} type="number" required step="1" min={field.min ?? undefined} max={field.max ?? undefined} value={typeof draft[field.name] === 'number' && Number.isFinite(draft[field.name]) ? String(draft[field.name]) : ''} onChange={event => setDraft({...draft, [field.name]: event.target.valueAsNumber})}/>}</label>)}
          </fieldset>
          {detail?.fields.length === 0 && <p>Solo consulta. No hay campos permitidos para esta configuración.</p>}
          <div className="actions"><Button type="submit" isDisabled={!detail?.editable || busy || pending || Boolean(stale) || !detail?.fields.length}>Guardar campos permitidos</Button><Button variant="secondary" isDisabled={!detail || pending} onClick={() => {if (detail) {setDraft(detail.values); setRevision(detail.revision); setError('');}}}>Recargar campos</Button></div>
        </form>
        <p className="muted">Red, imágenes, comandos, montajes y credenciales son de consulta, no campos de edición libre. Los slots comparten GPU y memoria; no garantizan capacidad independiente.</p>
        <h3>Fuentes de configuración</h3><ul>{detail?.paths.map(path => <li key={path}><code>{path}</code></li>)}</ul>
        <h3>Configuración guardada (valores sensibles ocultos)</h3><pre className="logs">{JSON.stringify(detail?.saved ?? {}, null, 2)}</pre>
      </>}
      {tab === 'Entorno' && <>
        <p>La configuración Docker describe el contenedor existente, no todos los cambios internos del proceso. Sin contenedor, no se inventa un entorno efectivo.</p>
        <Button variant="secondary" isDisabled={!detail || pending} onClick={() => void reveal()}>{privateDetail ? 'Ocultar valores privados' : 'Mostrar secretos y valores privados'}</Button>
        <p className="warning">Solo dentro de tu sesión Cockpit. No se guardan en el navegador ni en el historial de edición. Ocúltalos antes de compartir pantalla.</p>
        <h3>Entorno y ejecución observados</h3><pre className="logs">{JSON.stringify(shown?.effective ?? {}, null, 2)}</pre>
        <h3>Configuración guardada</h3><pre className="logs">{JSON.stringify(shown?.saved ?? {}, null, 2)}</pre>
      </>}
      {tab === 'Logs' && <>
        <div className="toolbar"><label>Filtrar logs <input value={filter} onChange={event => setFilter(event.target.value)}/></label><Button variant="secondary" onClick={() => setPaused(!paused)}>{paused ? 'Reanudar logs' : 'Pausar logs'}</Button></div>
        <p className="muted">{logs.source}. Últimas 250 líneas por fuente, hasta 80 KB. Refresco cada 3 s. Pueden contener prompts o datos privados; la redacción no es exhaustiva.</p>
        <pre className="logs" aria-live="off">{logs.text.split('\n').filter(line => line.toLowerCase().includes(filter.toLowerCase())).join('\n') || 'Sin registros disponibles.'}</pre>
      </>}
    </div>
  </section>;
}
