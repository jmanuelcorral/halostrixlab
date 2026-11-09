import {Sample} from './api';

export function storageSeries(samples: Sample[], kind: string) {
  if (kind === 'disk-capacity') return [
    {name: 'Ocupado', values: samples.map(item => (item.disk.used ?? item.disk.total - item.disk.free) / 2 ** 30)},
    {name: 'Disponible', values: samples.map(item => item.disk.free / 2 ** 30)},
  ];
  if (kind === 'disk-temperature') {
    const sensors = (item: Sample) => item.disk_temperatures ?? item.temperatures.filter(sensor => /^(nvme|drivetemp):/.test(sensor.sensor));
    const names = [...new Set(samples.flatMap(item => sensors(item).map(sensor => sensor.sensor)))];
    return names.map(name => ({name, values: samples.map(item => sensors(item).find(sensor => sensor.sensor === name)?.celsius ?? null)}));
  }
  const devices = [...new Set(samples.flatMap(item => Object.keys(item.io ?? {})))].filter(name => !/^(loop|ram|zram|dm-)/.test(name));
  if (kind === 'disk-busy') return devices.map(name => ({name, values: samples.map(item => {
    const value = item.io?.[name]?.busy_ms;
    return value == null ? null : Math.min(100, Math.max(0, value / 10));
  })}));
  return devices.flatMap(name => (['read', 'write'] as const).map(direction => ({name: name + (direction === 'read' ? ' lectura' : ' escritura'), values: samples.map(item => {
    const value = item.io?.[name]?.[direction];
    return value == null ? null : value / 2 ** 20;
  })})));
}
