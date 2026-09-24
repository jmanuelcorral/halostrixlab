import React, {useState} from 'react';
import {Sample} from './api';
import {networkInterfaces, networkRate} from './networkSeries';

export function NetworkPanel({samples, Chart}: {samples: Sample[]; Chart: React.ComponentType<{samples: Sample[]; kind: string; device?: string}>}) {
  const interfaces = networkInterfaces(samples);
  const [selection, setSelection] = useState('');
  const device = selection || interfaces[0] || '';
  const current = samples.at(-1)?.network?.[device];
  return <section aria-label="Red y tráfico">
    <div className="section-heading"><h2>Red y tráfico</h2><label>Interfaz de red <select aria-label="Interfaz de red" value={device} onChange={event => setSelection(event.target.value)} disabled={!interfaces.length}>
      {!interfaces.length && <option value="">Sin interfaces disponibles</option>}
      {selection && !interfaces.includes(selection) && <option value={selection}>{selection} (sin datos en este intervalo)</option>}
      {interfaces.map(name => <option key={name} value={name}>{name}</option>)}
    </select></label></div>
    <section className="kpis"><article><span>RECEPCIÓN</span><strong>{networkRate(current?.rx)}</strong><small>{device || 'Sin interfaz'} · tráfico entrante</small></article><article><span>ENVÍO</span><strong>{networkRate(current?.tx)}</strong><small>{device || 'Sin interfaz'} · tráfico saliente</small></article></section>
    <section className="chart-grid"><article className="panel"><h3>Red: recepción</h3><Chart samples={samples} kind="network-rx" device={device}/></article><article className="panel"><h3>Red: envío</h3><Chart samples={samples} kind="network-tx" device={device}/></article></section>
    <p className="muted">Tasas reales de /proc/net/dev en Mbit/s, con el mismo intervalo histórico. No es un test de velocidad de Internet. Selecciona una interfaz; no se suman puentes Docker, interfaces virtuales y físicas para evitar contar el mismo tráfico varias veces. Las muestras ausentes aparecen como huecos.</p>
  </section>;
}
