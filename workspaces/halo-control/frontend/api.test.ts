import {describe,it,expect} from 'vitest';
import {bytes,percent} from './api';
describe('telemetry formatting',()=>{
  it('distinguishes absent values from zero',()=>{
    expect(bytes(null)).toBe('Sin datos');
    expect(percent(undefined)).toBe('Sin datos');
    expect(percent(0)).toBe('0.0 %');
  });
  it('uses binary memory units',()=>expect(bytes(2**30)).toBe('1.0 GiB'));
});
