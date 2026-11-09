import {Sample} from './api';

export function networkInterfaces(samples: Sample[]) {
  return [...new Set(samples.flatMap(sample => Object.keys(sample.network ?? {})))].sort((left, right) => {
    const virtual = (name: string) => /^(lo$|docker|br-|veth|virbr)/.test(name) ? 1 : 0;
    return virtual(left) - virtual(right) || left.localeCompare(right);
  });
}

export function networkSeries(samples: Sample[], kind: string, device: string) {
  const direction = kind === 'network-rx' ? 'rx' : 'tx';
  return [{name: device + (direction === 'rx' ? ' recepción' : ' envío'), values: samples.map(sample => {
    const value = sample.network?.[device]?.[direction];
    return value == null || !Number.isFinite(value) || value < 0 ? null : value * 8 / 1_000_000;
  })}];
}

export function networkRate(value: number | null | undefined) {
  return value == null || !Number.isFinite(value) ? 'Sin datos' : (value * 8 / 1_000_000).toFixed(2) + ' Mbit/s';
}
