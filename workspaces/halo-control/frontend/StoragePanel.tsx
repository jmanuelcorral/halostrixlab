import React from 'react';
import {Button} from '@patternfly/react-core';
import {bytes, percent, Sample, State, stamp} from './api';
import './storage.css';

export function StoragePanel({samples, state, disabled, analyze, Chart}: {samples: Sample[]; state?: State; disabled: boolean; analyze: () => void; Chart: React.ComponentType<{samples: Sample[]; kind: string}>}) {
  const latest = samples.at(-1);
  const used = latest ? latest.disk.used ?? latest.disk.total - latest.disk.free : undefined;
  const occupation = latest && latest.disk.total > 0 && used != null ? used / latest.disk.total * 100 : null;
  const sensors = latest?.disk_temperatures ?? latest?.temperatures.filter(sensor => /^(nvme|drivetemp):/.test(sensor.sensor)) ?? [];
  const report = state?.storage?.data;
  const directories = [...new Map((report?.roots.flatMap(root => root.directories) ?? []).map(item => [item.path, item])).values()].sort((left, right) => right.bytes - left.bytes).slice(0, 25);
  const largest = directories[0]?.bytes ?? 1;
  return <section aria-label="Almacenamiento">
    <div className="section-heading"><h2>Disco y almacenamiento</h2><Button isDisabled={disabled} onClick={analyze}>Analizar ocupación</Button></div>
    <section className="kpis"><article><span>OCUPACIÓN</span><strong>{percent(occupation)}</strong><small>Sistema de archivos del workspace</small></article><article><span>ESPACIO OCUPADO</span><strong>{bytes(used)}</strong><small>de {bytes(latest?.disk.total)}</small></article><article><span>ESPACIO DISPONIBLE</span><strong>{bytes(latest?.disk.free)}</strong><small>Incluye límites y reservas del sistema de archivos</small></article></section>
    <section className="chart-grid"><article className="panel"><h3>Disco ocupado y disponible</h3><Chart samples={samples} kind="disk-capacity"/></article><article className="panel"><h3>Actividad del disco</h3><Chart samples={samples} kind="disk-busy"/><p className="muted">Porcentaje de tiempo con E/S activa, no porcentaje de capacidad ni garantía de saturación NVMe.</p></article><article className="panel"><h3>Lectura y escritura</h3><Chart samples={samples} kind="disk-throughput"/><p className="muted">MiB/s por dispositivo; sin sumar dispositivos virtuales ni particiones.</p></article><article className="panel"><h3>Temperatura del disco</h3><Chart samples={samples} kind="disk-temperature"/>{sensors.length ? sensors.map(sensor => <p key={sensor.sensor}>{sensor.sensor}: {sensor.celsius == null ? 'Sin datos' : sensor.celsius.toFixed(1) + ' °C'}</p>) : <p className="muted">Sin sensor de disco accesible. No se necesita instalar ni ejecutar SMART privilegiado.</p>}</article></section>
    <article className="panel"><h3>¿Qué ocupa principalmente el espacio?</h3><p>El análisis recorre metadatos de carpetas con prioridad baja, sin leer contenidos ni borrar archivos. Es manual, puede tardar varios minutos y no se repite con cada refresco de las gráficas.</p>
      {!report ? <p className="muted">Pulsa Analizar ocupación para obtener las carpetas más grandes y el inventario Docker.</p> : <>
        <p>Último análisis: {stamp(report.finished)}. {Date.now()/1000 - report.finished > 3600 ? 'Resultado antiguo: vuelve a analizar para actualizarlo.' : 'Es una instantánea, no un recuento continuo.'}</p>
        <div className="storage-roots">{report.roots.map(root => <div key={root.path}><strong>{root.label}: {bytes(root.bytes)}</strong><p><code>{root.path}</code></p>{root.partial && <p className="warning">{root.reason}</p>}</div>)}</div>
        <p className="warning">Carpetas inclusivas: una carpeta padre contiene a sus hijas. No sumar las barras. Categorías orientativas según la ruta, no análisis de contenido.</p>
        <div className="storage-ranking">{directories.map(item => <div className="storage-row" key={item.path}><div><code>{item.path}</code><small>{item.category}</small></div><div><strong>{bytes(item.bytes)}</strong><meter min={0} max={Math.max(1, largest)} value={item.bytes} aria-label={'Ocupación de ' + item.path}/></div></div>)}</div>
        {!directories.length && <p>No hay carpetas legibles en este análisis.</p>}
        <h3>Docker: imágenes, contenedores, volúmenes y caché de compilación</h3>{report.docker.available ? <div className="storage-table"><table><thead><tr><th>Tipo</th><th>Total</th><th>Activos</th><th>Tamaño</th><th>Recuperable informado</th></tr></thead><tbody>{report.docker.rows.map(row => <tr key={row.Type}><td>{row.Type}</td><td>{row.TotalCount}</td><td>{row.Active}</td><td>{row.Size}</td><td>{row.Reclaimable}</td></tr>)}</tbody></table></div> : <p className="warning">Inventario Docker no disponible; no se interpreta como cero.</p>}
        <p className="muted">{report.method} “Recuperable” no significa que sea seguro borrar: puede incluir imágenes o cachés necesarias.</p>
      </>}
    </article>
  </section>;
}
