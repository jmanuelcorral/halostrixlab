import React, {useEffect, useRef, useState} from 'react';
import {createRoot} from 'react-dom/client';
import {EngineDetails} from './EngineDetails';
import {EngineIdentity} from './EngineIdentity';
import {StoragePanel} from './StoragePanel';
import {storageSeries} from './storageSeries';
import {NetworkPanel} from './NetworkPanel';
import {RebootControl} from './RebootControl';
import {NotificationProvider, useToastMessage} from './Notifications';
import {networkSeries, networkRate} from './networkSeries';
import {synchronizeCockpitTheme, themePalette, useCockpitTheme} from './theme';
import {Button, TextInput} from '@patternfly/react-core';
import * as echarts from 'echarts/core';
import {LineChart} from 'echarts/charts';
import {GridComponent, TooltipComponent, LegendComponent, DataZoomComponent} from 'echarts/components';
import {CanvasRenderer} from 'echarts/renderers';
echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent, DataZoomComponent, CanvasRenderer]);
import {Terminal as XTerminal} from '@xterm/xterm';
import {FitAddon} from '@xterm/addon-fit';
import '@patternfly/react-core/dist/styles/base.css';
import '@xterm/xterm/css/xterm.css';
import './style.css';
import {api, available, bytes, initialize, percent, stamp, State, Sample, Channel} from './api';

synchronizeCockpitTheme();

const pages = ['Resumen', 'Servicios IA', 'Métricas', 'Logs', 'Terminal', 'Actualizaciones', 'Actividad'];
const labels: Record<string, string> = {'laya-start':'Arrancar Laya', 'laya-stop':'Detener Laya', 'gateway-start':'Arrancar gateway', 'gateway-stop':'Detener gateway', 'gateway-restart':'Reiniciar gateway', 'halogen-load':'Cargar Halogen', 'halogen-unload':'Descargar Halogen', 'comfyui-start':'Arrancar ComfyUI', 'comfyui-stop':'Detener ComfyUI', 'switch-text':'ON graceful', 'switch-images':'ON graceful', 'check-updates':'Consultar paquetes', 'check-images':'Consultar imágenes', 'update':'Aplicar actualización completa', 'reboot':'Reiniciar equipo', 'unsloth-start':'Arrancar Studio', 'unsloth-stop':'Detener Studio', 'switch-studio':'Cambiar a Studio', 'llamafactory-start':'Arrancar LlamaBoard', 'llamafactory-stop':'Detener LlamaBoard', 'switch-llamafactory':'Cambiar a LlamaBoard', 'analyze-storage':'Analizar ocupación de disco'};

function Chart({samples, kind, device = ''}: {samples: Sample[]; kind: string; device?: string}) {
  const element = useRef<HTMLDivElement>(null);
  const instance = useRef<echarts.EChartsType>();
  const theme = useCockpitTheme();
  useEffect(() => {
    instance.current = echarts.init(element.current!, undefined, {renderer:'canvas'});
    const observer = new ResizeObserver(() => instance.current?.resize());
    observer.observe(element.current!);
    return () => { observer.disconnect(); instance.current?.dispose(); };
  }, []);
  useEffect(() => {
    let series: {name: string; values: (number | null)[]}[] = [];
    if (kind === 'usage') series = [{name:'CPU',values:samples.map(item=>item.cpu.cpu)},{name:'GPU',values:samples.map(item=>item.gpu[0]?.busy ?? null)}];
    if (kind === 'memory') series = [{name:'RAM utilizada',values:samples.map(item=>item.memory.used/2**30)},{name:'GTT utilizada',values:samples.map(item=>item.gpu[0]?.gtt_used == null ? null : item.gpu[0].gtt_used/2**30)}];
    if (kind === 'temperature') {
      const names = [...new Set(samples.flatMap(item=>item.temperatures.map(sensor=>sensor.sensor)))];
      series = names.map(name=>({name,values:samples.map(item=>item.temperatures.find(sensor=>sensor.sensor===name)?.celsius ?? null)}));
    }
    if (kind.startsWith('disk-')) series = storageSeries(samples, kind);
    if (kind.startsWith('network-')) series = networkSeries(samples, kind, device);
    const unit = kind.startsWith('network-') ? 'Mbit/s' : kind === 'usage' || kind === 'disk-busy' ? '%' : kind === 'memory' || kind === 'disk-capacity' ? 'GiB' : kind === 'disk-throughput' ? 'MiB/s' : '°C';
    const palette = themePalette();
    instance.current?.setOption({animation:false, color:palette.series, backgroundColor:'transparent', textStyle:{color:palette.text}, tooltip:{trigger:'axis',backgroundColor:palette.panel,borderColor:palette.border,textStyle:{color:palette.text}}, legend:{top:0,left:8,right:8,textStyle:{color:palette.muted},pageTextStyle:{color:palette.text},pageIconColor:palette.brand,type:'scroll'},grid:{left:16,right:24,top:60,bottom:58,containLabel:true},xAxis:{type:'time',axisLabel:{color:palette.muted},axisLine:{lineStyle:{color:palette.border}}},yAxis:{type:'value',name:unit,nameTextStyle:{color:palette.muted},max:unit==='%'?100:undefined,axisLabel:{color:palette.muted},splitLine:{lineStyle:{color:palette.border}}},dataZoom:[{type:'inside'},{type:'slider',height:16,bottom:6,borderColor:palette.border,backgroundColor:palette.background,textStyle:{color:palette.text},handleStyle:{color:palette.brand},dataBackground:{lineStyle:{color:palette.muted},areaStyle:{color:palette.border}}}],series:series.map(line=>({name:line.name,type:'line',showSymbol:false,connectNulls:false,lineStyle:{width:2},data:samples.map((item,index)=>[item.time*1000,line.values[index]])}))}, true);
  }, [samples, kind, device, theme]);
  return <div className="chart" ref={element} role="img" aria-label={`Gráfica ${kind}`} />;
}

function TerminalPane({target,maintenance,attachOnly=false}: {target: string; maintenance: boolean; attachOnly?: boolean}) {
  const element = useRef<HTMLDivElement>(null);
  const [error,setError] = useState('');
  const [connection,setConnection] = useState('Preparando consola…');
  useEffect(()=>{
    if (!window.cockpit) { setError('Terminal disponible solo en sesión Cockpit autenticada'); return; }
    let channel: Channel | undefined;
    let disposed = false;
    const terminal = new XTerminal({cursorBlink:true,fontSize:14,fontFamily:'ui-monospace, monospace',scrollback:3000,screenReaderMode:true});
    let received = false;
    let closed = false;
    setError('');
    setConnection(maintenance ? 'Solicitando acceso administrativo a Cockpit…' : 'Conectando consola…');
    const updateTerminalTheme = () => {
      const palette = themePalette();
      terminal.options.theme = {background:palette.panel,foreground:palette.text,cursor:palette.text,selectionBackground:palette.border};
    };
    updateTerminalTheme();
    window.addEventListener('halo-theme-changed', updateTerminalTheme);
    const fit = new FitAddon(); terminal.loadAddon(fit); terminal.open(element.current!); fit.fit();
    terminal.writeln(maintenance ? 'Abriendo actualización completa. Esperando autorización y comprobaciones del servidor…' : 'Conectando…');
    const waitingTimer = setTimeout(()=>{if(!disposed&&!closed&&!received)setConnection('Sin salida todavía. Comprueba el acceso administrativo de Cockpit; la actualización no está confirmada.');},15000);
    terminal.attachCustomKeyEventHandler(event=> !(event.type==='keydown' && event.ctrlKey && event.key==='v'));
    const onPaste = (event: ClipboardEvent) => {
      const text = event.clipboardData?.getData('text/plain') ?? '';
      if (text.includes('\n') && !window.confirm('Pegar múltiples líneas puede ejecutar comandos. ¿Continuar?')) { event.preventDefault(); event.stopImmediatePropagation(); }
    };
    element.current!.addEventListener('paste',onPaste,true);
    let lastInput = Date.now();
    const idleTimer = setInterval(()=>{
      if (!maintenance && Date.now()-lastInput > 15*60*1000) {
        channel?.close(); setError('Sesión cerrada tras 15 minutos sin entrada. El trabajo de actualización sigue en tmux.');
        clearInterval(idleTimer);
      }
    },10000);
    const input = terminal.onData(data=>{lastInput=Date.now();channel?.send(data);});
    const resize = new ResizeObserver(()=>{if(!element.current?.clientWidth||!element.current?.clientHeight)return;fit.fit();channel?.control({window:{rows:terminal.rows,cols:terminal.cols}});});
    resize.observe(element.current!);
    Promise.resolve(window.cockpit.user()).then(user=>{
      if(disposed)return;
      const spawn = maintenance ? (attachOnly ? ['/usr/bin/tmux','-S','/run/halo-control/maintenance.sock','attach-session','-t','update'] : ['/usr/local/libexec/halo-maintenance','update']) : target==='local' ? [user.shell || '/bin/bash'] : ['/usr/bin/ssh','-o','StrictHostKeyChecking=yes','-o','ForwardAgent=no','--',target];
      channel = window.cockpit!.channel({payload:'stream',spawn,pty:true,binary:true,err:'out',environ:['TERM=xterm-256color'],directory:user.home,window:{rows:terminal.rows,cols:terminal.cols},...(maintenance?{superuser:'require'}:{})});
      channel.addEventListener('ready',()=>{if(!disposed)setConnection(maintenance ? 'Consola administrativa conectada. Revisa la salida y responde a pacman.' : 'Consola conectada.');});
      channel.addEventListener('message',(_event,data)=>{
        if(disposed)return;
        received = true;
        clearTimeout(waitingTimer);
        setConnection(maintenance ? 'Salida del servidor recibida. Revisa las comprobaciones y preguntas de pacman.' : 'Consola conectada.');
        terminal.write(data instanceof ArrayBuffer ? new Uint8Array(data) : data);
      });
      channel.addEventListener('close',(_event,data)=>{
        if(disposed)return;
        closed = true;
        clearTimeout(waitingTimer);
        const detail = [data?.message,data?.problem,data?.['exit-status'] != null ? `Código de salida: ${data['exit-status']}` : '',data?.['exit-signal']].filter(Boolean).join(' · ');
        const message = 'Consola cerrada. ' + (detail || 'Sin resultado confirmado.') + (maintenance ? ' Si tmux llegó a iniciarse, puede seguir activo; revisa la salida antes de reconectar.' : '');
        setConnection(message);
        if(data?.problem || (data?.['exit-status'] != null && data['exit-status'] !== 0))setError(message);
        terminal.writeln('\r\n' + message);
      });
      channel.control({window:{rows:terminal.rows,cols:terminal.cols}});
      terminal.focus();
    }).catch(reason=>{if(!disposed){closed=true;clearTimeout(waitingTimer);setError(String(reason));setConnection('No se pudo abrir la consola. No se confirma ninguna actualización.');}});
    return ()=>{disposed=true;clearTimeout(waitingTimer);window.removeEventListener('halo-theme-changed', updateTerminalTheme);clearInterval(idleTimer);channel?.close();input.dispose();resize.disconnect();element.current?.removeEventListener('paste',onPaste,true);terminal.dispose();};
  },[target,maintenance,attachOnly]);
  return <><p className="warning">{maintenance?'Consola administrativa de actualización. Desconectar no detiene tmux. Revisa cada pregunta de pacman.':'Consola real con los permisos de tu usuario. Docker/sudo pueden equivaler a root. No se graban pulsaciones.'}</p><p role="status" aria-live="polite">{connection}</p>{error&&<p role="alert">{error}</p>}<div ref={element} className="terminal" aria-label={maintenance?'Salida de actualización completa':'Consola interactiva'} /></>;
}

function App() {
  const [page,setPage] = useState('Resumen');
  const [engine,setEngine] = useState<string>();
  const [state,setState] = useState<State>();
  const [samples,setSamples] = useState<Sample[]>([]);
  const [error,setError] = useState('');
  const [initialized,setInitialized] = useState(false);
  const [range,setRange] = useState(900);
  const [submitting,setSubmitting] = useState(false);
  const [rebootBusy,setRebootBusy] = useState(false);
  const actionInFlight = useRef(false);
  const [logSource,setLogSource] = useState('gateway');
  const [logs,setLogs] = useState('');
  const [filter,setFilter] = useState('');
  const [paused,setPaused] = useState(false);
  const [terminal,setTerminal] = useState(false);
  const [target,setTarget] = useState('local');
  const [maintenance,setMaintenance] = useState(false);
  const [maintenanceAttempt,setMaintenanceAttempt] = useState(0);
  const [maintenanceAttachOnly,setMaintenanceAttachOnly] = useState(false);
  const maintenancePanel = useRef<HTMLElement>(null);
  useEffect(()=>{
    if(!maintenance || page!=='Actualizaciones')return;
    const frame=requestAnimationFrame(()=>maintenancePanel.current?.scrollIntoView({block:'start',behavior:'instant'}));
    return()=>cancelAnimationFrame(frame);
  },[maintenance,page]);
  const [lastUpdate,setLastUpdate] = useState(0);
  const [notice,setNotice] = useState('');
  useToastMessage(notice);
  useToastMessage(error, 'danger');
  useEffect(()=>{initialize().then(()=>setInitialized(true)).catch(reason=>setError(String(reason)));},[]);
  useEffect(()=>{
    if(!initialized)return;
    let stopped=false; let timer: ReturnType<typeof setTimeout>;
    const refresh=async()=>{try {const [next,history]=await Promise.all([api<State>('status'),api<Sample[]>('history',String(range))]); if(!stopped){setState(next);setSamples(history);setLastUpdate(Date.now());setError('');}} catch(reason){if(!stopped)setError(String(reason));} finally {if(!stopped)timer=setTimeout(refresh,5000);}};
    void refresh(); return()=>{stopped=true;clearTimeout(timer);};
  },[initialized,range]);
  useEffect(()=>{
    if(page!=='Logs'||paused||!initialized)return;
    let stopped=false;let timer:ReturnType<typeof setTimeout>;
    const refresh=async()=>{try {const value=await api<{text:string}>('logs',logSource);if(!stopped)setLogs(value.text);}catch(reason){if(!stopped)setError(String(reason));}finally{if(!stopped)timer=setTimeout(refresh,3000);}};
    void refresh();return()=>{stopped=true;clearTimeout(timer);};
  },[page,paused,logSource,initialized]);
  const latest=samples.at(-1);
  const stale=!latest || Date.now()/1000-latest.time>20;
  const busy=submitting || rebootBusy || (state?.jobs.some(job=>['queued','running'].includes(job.state)) ?? false);
  const perform=async(action:string)=>{
    if (!initialized || busy || actionInFlight.current) return;
    actionInFlight.current=true;
    setSubmitting(true);
    setError('');
    try {
      if(action==='update'){setMaintenanceAttachOnly(false);setMaintenance(true);setPage('Actualizaciones');maintenancePanel.current?.scrollIntoView({block:'start',behavior:'instant'});setNotice('Consola de actualización abierta debajo de los controles. Si Cockpit rechaza permisos, activa Acceso administrativo y vuelve a conectar.');return;}
      const result=await api<{job:string}>('submit',action);
      setState(current=>current?{...current,jobs:[{id:result.job,action,state:'queued',message:'Operación enviada',created:Date.now()/1000},...current.jobs]}:current);
      setNotice(`Operación registrada: ${result.job.slice(0,8)}. Sigue el progreso en Actividad.`);
    } catch(reason){setError(String(reason));}
    finally {actionInFlight.current=false;setSubmitting(false);}
  };
  const actionButton=(action:string,variant:'primary'|'secondary'|'danger'='secondary')=><Button variant={variant} isDisabled={!initialized||busy||((action==='laya-start'||action==='laya-stop')&&(!state?.laya?.available||state?.services.gateway!=='active'))||((action==='unsloth-start'||action==='switch-studio')&&!state?.unsloth?.available)||((action==='llamafactory-start'||action==='switch-llamafactory')&&!state?.llamafactory?.available)} onClick={()=>void perform(action)}>{labels[action]}</Button>;
  const detailButton=(id:string,title:string)=><Button className="detail-button" variant="link" isDisabled={!initialized} onClick={()=>{setEngine(id);setPage('Ficha del motor');}}>Ficha y logs de {title}</Button>;
  const heat=latest?.temperatures.filter(sensor=>sensor.celsius!=null&&sensor.critical!=null&&sensor.celsius>=sensor.critical).map(sensor=>sensor.sensor)??[];
  const exportLogs=()=>{const url=URL.createObjectURL(new Blob([logs],{type:'text/plain'}));const link=document.createElement('a');link.href=url;link.download=`halo-${logSource}.log`;link.click();URL.revokeObjectURL(url);};
  return <div className="shell"><aside><div className="brand"><span className="halo-mark">H</span><div>HALO<span>CONTROL PLANE</span></div></div><nav aria-label="Principal">{pages.map((name,index)=><button key={name} className={page===name?'selected':''} onClick={()=>setPage(name)}><span className="nav-number">0{index+1}</span>{name}</button>)}</nav><div className="sidebar-foot"><span className="dot"/> STRIX HALO / gfx1151<br/><small>Administración local · Cockpit</small></div></aside><main><header><div><div className="eyebrow">TU LABORATORIO, EN TIEMPO REAL</div><h1>{page}</h1></div><div className="header-actions"><span className={'pill '+(stale?'amber':'green')}>{stale?'Sin telemetría reciente':'Telemetría activa'}</span></div></header>
    {!available()&&<div className="banner">Vista previa sin sesión. Instala el paquete en Cockpit para conectar métricas y controles reales.</div>}
    {heat.length>0&&<div className="banner danger">Sensores en umbral crítico: {heat.join(', ')}. Sin apagado automático.</div>}
    {state?.errors.map(message=><div className="banner amber" key={message}>{message}</div>)}
    {(page==='Resumen'||page==='Métricas')&&<><section className="kpis"><article><span>CPU</span><strong>{percent(latest?.cpu.cpu)}</strong><small>{latest?.load.map(value=>value.toFixed(2)).join(' / ')??'Esperando datos'} · carga</small></article><article><span>GPU · RADEON 8060S</span><strong>{percent(latest?.gpu[0]?.busy)}</strong><small>{latest?.gpu[0]?.watts?.toFixed(1)??'—'} W · lectura APU/GPU</small></article><article><span>MEMORIA RAM</span><strong>{bytes(latest?.memory.used)}</strong><small>{bytes(latest?.memory.available)} disponibles</small></article><article><span>GPU GTT</span><strong>{bytes(latest?.gpu[0]?.gtt_used)}</strong><small>de {bytes(latest?.gpu[0]?.gtt_total)} · no sumar a RAM</small></article></section><div className="section-heading"><h2>Ritmo del sistema</h2><select aria-label="Intervalo" value={range} onChange={event=>setRange(Number(event.target.value))}><option value={900}>15 minutos</option><option value={3600}>1 hora</option><option value={86400}>24 horas</option><option value={604800}>7 días</option></select></div><section className="chart-grid"><article className="panel"><h3>CPU y GPU</h3><Chart samples={samples} kind="usage"/></article><article className="panel"><h3>Memoria unificada</h3><Chart samples={samples} kind="memory"/></article><article className="panel wide"><h3>Temperaturas · sensores independientes</h3><Chart samples={samples} kind="temperature"/></article></section></>}
    {(page==='Resumen'||page==='Servicios IA')&&<><div className="section-heading"><h2>Motores de inferencia</h2><span className="muted">Una reserva de GPU · cambios supervisados</span></div><section className="service-grid"><article className="panel service"><EngineIdentity engine="gateway" state={state}/>{detailButton('gateway','llama-swap')}<p>Gateway y ciclo de vida de los modelos.</p><p className="muted">API: {state?.gateway_health?'disponible':'no comprobada'}</p><div className="actions">{actionButton('gateway-start')}{actionButton('gateway-stop')}{actionButton('gateway-restart')}</div>{state?.gateway_health&&<a href={state.gateway_ui_url} target="_blank" rel="noreferrer">Abrir interfaz llama-swap ↗</a>}</article><article className="panel service"><EngineIdentity engine="halogen" state={state}/>{detailButton('halogen','Halogen')}<p>Texto y herramientas. Depende de llama-swap.</p><p className="muted">Una petición puede volver a cargarlo tras descargar.</p><div className="actions">{actionButton('halogen-load')}{actionButton('halogen-unload')}{actionButton('switch-text','primary')}</div></article><article className="panel service"><EngineIdentity engine="laya" state={state}/><Button className="detail-button" variant="link" onClick={()=>{setLogSource('gateway');setPage('Logs');}}>Logs compartidos de Laya</Button><p>Decisiones multilingual en CPU. Convive con Halogen en el mismo llama-swap.</p><p className="muted">4 CPU · límite 8 GiB · API /upstream/laya/v1/systemone</p>{state?.laya?.error&&<p className="warning">{state.laya.error}</p>}<div className="actions">{actionButton('laya-start','primary')}{actionButton('laya-stop')}</div><p className="muted">Detener Laya no descarga Halogen. Las peticiones pueden volver a cargarlo. Detener el gateway descarga ambos.</p>{state?.services.gateway!=='active'&&<p className="warning">Arranca primero el gateway compartido desde su tarjeta.</p>}</article><article className="panel service"><EngineIdentity engine="comfyui" state={state}/>{detailButton('comfyui','ComfyUI')}<p>Imágenes con ROCm y offload a RAM.</p><p className="muted">Cola protegida; no cancelación silenciosa.</p><div className="actions">{actionButton('comfyui-start')}{actionButton('comfyui-stop')}{actionButton('switch-images','primary')}</div>{state?.comfyui_health&&<a href={state.comfyui_url} target="_blank" rel="noreferrer">Abrir interfaz ComfyUI ↗</a>}</article><article className="panel service"><EngineIdentity engine="unsloth" state={state}/>{detailButton('unsloth','Unsloth Studio')}<p>Studio existente · PyTorch 2.11 / ROCm 7.14.</p><p className="muted">UI y GPU verificadas históricamente; entrenamiento y QLoRA 4-bit no validados.</p>{state?.unsloth?.error&&<p className="warning">{state.unsloth.error}</p>}<div className="actions">{actionButton('unsloth-start')}{actionButton('unsloth-stop')}{actionButton('switch-studio','primary')}</div><p className="warning">Detener Studio interrumpe sus procesos: finaliza entrenamiento y exportaciones dentro de Studio primero. No se cambia desde Studio automáticamente.</p>{state?.unsloth?.health&&state.unsloth.url&&<a href={state.unsloth.url} target="_blank" rel="noreferrer">Abrir interfaz Unsloth Studio ↗</a>}</article><article className="panel service"><EngineIdentity engine="llamafactory" state={state}/>{detailButton('llamafactory','LLaMA-Factory')}<p>LlamaBoard 0.9.5 · PyTorch 2.12 / ROCm 7.14.</p><p className="muted">Imagen y datos existentes; ejecución no-root. Entrenamiento no validado.</p>{state?.llamafactory?.error&&<p className="warning">{state.llamafactory.error}</p>}<div className="actions">{actionButton('llamafactory-start')}{actionButton('llamafactory-stop')}{actionButton('switch-llamafactory','primary')}</div><p className="warning">Solo LAN de confianza, sin login propio. Cambiar a LlamaBoard detiene Studio (puede interrumpir entrenamientos) y detiene ComfyUI/gateway tras comprobar su actividad. Finaliza trabajos antes de cambiar.</p>{state?.llamafactory?.url&&<a href={state.llamafactory.url} target="_blank" rel="noreferrer">Abrir interfaz LlamaBoard ↗</a>}{state?.llamafactory?.url&&<p className="muted">{state.llamafactory.url} · {state.llamafactory.health?'HTTP disponible':state.llamafactory.state==='running'?'HTTP pendiente de comprobación':'Servicio detenido; enlace configurado'}</p>}</article></section><p className="muted">Verde: activo o cargado · Rojo: parado, descargado o fallo · Naranja: pausa, transición o disponibilidad sin confirmar · Gris: sin datos o configuración. Parado y detenido describen el mismo estado; el texto distingue un fallo. <a href="./engine-art/ATTRIBUTION.txt" target="_blank" rel="noreferrer">Imágenes oficiales y atribuciones</a>.</p><p className="warning">Drenaje con comprobación previa. El gateway directo admite peticiones hasta la parada; v255 limita su drenaje final a 30 s. Reserva clientes antes de cambiar. No hay una cola de mantenimiento global.</p></>}
    {(page==='Resumen'||page==='Métricas')&&<StoragePanel samples={samples} state={state} disabled={!initialized||busy} analyze={()=>void perform('analyze-storage')} Chart={Chart}/>}
    {(page==='Resumen'||page==='Métricas')&&<NetworkPanel samples={samples} Chart={Chart}/>}
    {page==='Ficha del motor'&&engine&&<EngineDetails key={engine} engine={engine} busy={busy} onClose={()=>{setEngine(undefined);setPage('Servicios IA');}}/>}
    {page==='Métricas'&&<section className="panel"><h3>Detalle de sensores</h3><table><thead><tr><th>Sensor</th><th>Temperatura</th><th>Crítico informado</th></tr></thead><tbody>{latest?.temperatures.map(sensor=><tr key={sensor.sensor}><td>{sensor.sensor}</td><td>{sensor.celsius?.toFixed(1)??'—'} °C</td><td>{sensor.critical?.toFixed(1)??'No disponible'}</td></tr>)}</tbody></table><p>Disco libre: {bytes(latest?.disk.free)} · Swap usada: {bytes(latest?.memory.swap_used)}</p><h3>Red</h3><table><tbody>{Object.entries(latest?.network??{}).map(([name,value])=><tr key={name}><td>{name}</td><td>↓ {networkRate(value.rx)}</td><td>↑ {networkRate(value.tx)}</td></tr>)}</tbody></table><p className="muted">PSI 10 s: {Object.entries(latest?.pressure??{}).map(([name,value])=>`${name}: ${value?.some?.avg10??'—'}%`).join(' · ')}</p></section>}
    {page==='Logs'&&<section className="panel"><div className="toolbar"><select aria-label="Servicio de logs" value={logSource} onChange={event=>setLogSource(event.target.value)}><option value="gateway">llama-swap / Halogen / Laya</option><option value="comfyui">ComfyUI</option><option value="unsloth">Unsloth Studio</option><option value="llamafactory">LlamaBoard</option><option value="metrics">Métricas</option><option value="jobs">Operaciones</option></select><TextInput aria-label="Filtrar logs" value={filter} onChange={(_event,value)=>setFilter(value)} placeholder="Filtrar texto…"/><Button variant="secondary" onClick={()=>setPaused(!paused)}>{paused?'Reanudar':'Pausar'}</Button><Button variant="secondary" onClick={exportLogs}>Descargar</Button></div><pre className="logs" aria-live="off">{logs.split('\n').filter(line=>line.toLowerCase().includes(filter.toLowerCase())).join('\n')||'No hay registros disponibles.'}</pre><p className="muted">Últimas 250 líneas. Pueden contener prompts; trata la exportación como privada.</p></section>}
    {page==='Terminal'&&<section className="panel"><div className="toolbar"><select aria-label="Destino SSH" value={target} onChange={event=>{setTarget(event.target.value);setTerminal(false);}}><option value="local">Consola local del Halo</option>{state?.ssh_hosts.map(host=><option key={host}>{host}</option>)}</select><Button isDisabled={!initialized} onClick={()=>{setTerminal(!terminal);}}>{terminal?'Cerrar sesión':'Abrir consola'}</Button><span className="muted">SSH: StrictHostKeyChecking · sin agent forwarding</span></div>{terminal?<TerminalPane key={target} target={target} maintenance={false}/>:<div className="empty"><h3>Tu terminal, sin salir del panel</h3><p>La sesión se abre solo al pulsar el botón. No se guardan claves en el navegador.</p></div>}</section>}
    {page==='Actualizaciones'&&<><section className="panel"><div className="section-heading"><h2>Mantenimiento del sistema</h2>{actionButton('check-updates','primary')}</div><p>Consulta aislada con checkupdates. Última lectura: {state?.updates?stamp(state.updates.updated):'sin consultar'}</p>{state?.updates?.data.ok===false&&<p className="warning">Consulta fallida: {state.updates.data.error}</p>}<table><thead><tr><th>Paquete</th><th>Instalado</th><th>Disponible</th></tr></thead><tbody>{state?.updates?.data.packages.map(item=><tr key={item.name}><td>{item.name}</td><td>{item.from}</td><td>{item.to}</td></tr>)}</tbody></table><p className="muted">{state?.updates?.data.ok&&state.updates.data.packages.length===0?'Sin actualizaciones de repositorios en la última consulta.':''} AUR no se actualiza automáticamente. Reinicio necesario: revisar kernel y firmware, no inferido.</p><div className="actions"><Button variant="danger" isDisabled={!initialized||busy||!state?.maintenance_available} onClick={()=>void perform('update')}>Aplicar actualización completa</Button></div>{!state?.maintenance_available&&<p className="warning">Helper administrativo no instalado. Requiere instalación root revisada; no se eleva el panel completo.</p>}<p className="muted">Drena y detén IA antes de mantenimiento. Revisa avisos CachyOS y recuperación; no hay rollback automático.</p></section><section className="panel"><div className="section-heading"><h2>Imágenes de IA</h2>{actionButton('check-images')}</div><p>Solo consulta manifiestos. No cambia digests, descarga ni activa imágenes.</p><pre className="logs">{state?.images?JSON.stringify(state.images.data,null,2):'Todavía no consultadas.'}</pre></section></>}
    <section className="panel" hidden={page!=='Actualizaciones'} aria-label="Reinicio supervisado"><h2>Reinicio supervisado</h2><p>Solicita confirmación, comprueba permisos, detiene los motores IA y verifica su parada antes de reiniciar. Las tareas activas pueden interrumpirse; no se fuerza un gestor de paquetes ni una sesión de actualización.</p><RebootControl disabled={!initialized||busy||!state?.maintenance_available} state={state} onBusy={setRebootBusy} onMaintenance={()=>{setMaintenanceAttachOnly(true);setMaintenanceAttempt(value=>value+1);setMaintenance(true);maintenancePanel.current?.scrollIntoView({block:'start',behavior:'instant'});}}/></section>
    {maintenance&&<section ref={maintenancePanel} className="panel" hidden={page!=='Actualizaciones'} aria-label="Consola de actualización"><div className="section-heading"><h2>{maintenanceAttachOnly?'Sesión de actualización existente':'Actualización completa: salida en directo'}</h2><div className="actions"><Button variant="secondary" onClick={()=>setMaintenanceAttempt(value=>value+1)}>Reconectar consola de actualización</Button><Button variant="secondary" onClick={()=>setMaintenance(false)}>Cerrar visor de actualización</Button></div></div>{maintenanceAttachOnly&&<p className="warning">Solo conecta a la sesión existente; no inicia una nueva actualización. Si ya terminó y pide Enter, pulsa Enter para cerrar tmux. Si pacman sigue trabajando, espera.</p>}<p className="muted">No se aplica en segundo plano sin preguntas: pacman es interactivo. Un rechazo por IA activa, permisos o bloqueo de paquetes aparece aquí. Reconectar se une a tmux si existe; si terminó, puede iniciar una nueva actualización. Cerrar el visor no cancela un trabajo ya iniciado.</p><TerminalPane key={maintenanceAttempt} target="local" maintenance attachOnly={maintenanceAttachOnly}/></section>}
    {(page==='Actividad'||page==='Resumen')&&<section className="panel activity"><div className="section-heading"><h2>Actividad</h2><span className="muted">Persistente aunque cierres el navegador</span></div>{state?.jobs.length?<table><thead><tr><th>Operación</th><th>Estado</th><th>Fecha</th><th>Resultado</th></tr></thead><tbody>{state.jobs.slice(0,page==='Resumen'?5:30).map(job=><tr key={job.id}><td>{labels[job.action]??job.action}</td><td><span className={'pill '+(job.state==='failed'?'red':job.state==='success'?'green':'amber')}>{job.state}</span></td><td>{stamp(job.created)}</td><td>{job.message}</td></tr>)}</tbody></table>:<div className="empty">Sin operaciones registradas.</div>}</section>}
    <footer>Halo Control · {lastUpdate?`Última conexión ${new Date(lastUpdate).toLocaleTimeString()}`:'Esperando conexión'} · Datos privados, sin CDN</footer>
  </main></div>;
}

createRoot(document.getElementById('root')!).render(<NotificationProvider><App/></NotificationProvider>);
