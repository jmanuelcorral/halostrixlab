import {describe, expect, it} from 'vitest';
import {networkInterfaces, networkRate, networkSeries} from './networkSeries';
import {Sample} from './api';

const sample = {network: {docker0: {rx: 100, tx: 200}, wlan0: {rx: 1_000_000, tx: 250_000}, lo: {rx: 0, tx: 0}}} as unknown as Sample;
describe('network charts', () => {
  it('converts bytes per second to decimal megabits without adding virtual interfaces', () => {
    expect(networkSeries([sample], 'network-rx', 'wlan0')[0].values).toEqual([8]);
    expect(networkSeries([sample], 'network-tx', 'wlan0')[0].values).toEqual([2]);
    expect(networkRate(1_000_000)).toBe('8.00 Mbit/s');
  });
  it('prioritizes non-loopback, non-Docker interface names', () => {
    expect(networkInterfaces([sample])).toEqual(['wlan0', 'docker0', 'lo']);
  });
  it('keeps missing and invalid rates as gaps rather than zero', () => {
    const missing = {network: {wlan0: {rx: null, tx: NaN}}} as unknown as Sample;
    expect(networkSeries([sample, missing], 'network-rx', 'wlan0')[0].values).toEqual([8, null]);
    expect(networkSeries([sample], 'network-rx', 'absent')[0].values).toEqual([null]);
    expect(networkRate(null)).toBe('Sin datos');
    expect(networkRate(0)).toBe('0.00 Mbit/s');
    expect(networkInterfaces([])).toEqual([]);
  });
});
