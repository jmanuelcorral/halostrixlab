import {describe, expect, it} from 'vitest';
import {storageSeries} from './storageSeries';
import {Sample} from './api';

const sample = {disk: {total: 100 * 2**30, free: 40 * 2**30}, temperatures: [{sensor: 'nvme:Composite', celsius: 35}, {sensor: 'k10temp:Tctl', celsius: 65}], io: {nvme0n1: {read: 2**20, write: 2 * 2**20, busy_ms: 250}, zram0: {read: 0, write: 0, busy_ms: 1}}} as unknown as Sample;
describe('disk graphs', () => {
  it('converts rates and active time without virtual device duplication', () => {
    expect(storageSeries([sample], 'disk-busy')).toEqual([{name: 'nvme0n1', values: [25]}]);
    expect(storageSeries([sample], 'disk-throughput').map(line => line.values)).toEqual([[1], [2]]);
  });
  it('supports old capacity and sensor history', () => {
    expect(storageSeries([sample], 'disk-capacity').map(line => line.values)).toEqual([[60], [40]]);
    expect(storageSeries([sample], 'disk-temperature')).toEqual([{name: 'nvme:Composite', values: [35]}]);
  });
  it('keeps missing samples unknown', () => {
    const missing = {...sample, io: {}, disk_temperatures: []};
    expect(storageSeries([sample, missing], 'disk-busy')[0].values).toEqual([25, null]);
    expect(storageSeries([missing], 'disk-temperature')).toEqual([]);
  });
});
