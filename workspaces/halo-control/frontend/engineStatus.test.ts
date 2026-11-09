import {describe, expect, it} from 'vitest';
import type {State} from './api';
import {engineStatus, runtimeStatus} from './engineStatus';

const fixture = (overrides: Partial<State> = {}) => ({services: {gateway: 'active'}, gateway_health: true, halogen: 'loaded', ...overrides}) as State;

describe('runtime status', () => {
  it.each(['active', 'running'])('requires HTTP readiness for %s', raw => {
    expect(runtimeStatus(raw, true)).toMatchObject({tone: 'success', label: 'Activo', icon: 'check'});
    expect(runtimeStatus(raw, false)).toMatchObject({tone: 'warning', label: 'Sin respuesta HTTP'});
    expect(runtimeStatus(raw)).toMatchObject({tone: 'warning', label: 'Sin verificar'});
  });
  it.each(['inactive', 'exited', 'created', 'stopped', 'unloaded'])('marks %s stopped without calling it a failure', raw => {
    expect(runtimeStatus(raw, true)).toMatchObject({tone: 'danger', icon: 'stop'});
    expect(runtimeStatus(raw).detail).toContain('no implica un fallo');
  });
  it.each(['failed', 'dead'])('distinguishes %s from a normal stop', raw => {
    expect(runtimeStatus(raw)).toMatchObject({tone: 'danger', label: 'Fallo', icon: 'error'});
  });
  it.each(['activating', 'deactivating', 'restarting', 'reloading', 'refreshing', 'removing'])('shows %s as a transition', raw => {
    expect(runtimeStatus(raw, true)).toMatchObject({tone: 'warning', icon: 'clock'});
  });
  it('distinguishes pause and legacy instance from a stop', () => {
    expect(runtimeStatus('paused')).toMatchObject({tone: 'warning', label: 'Pausado', icon: 'pause'});
    expect(runtimeStatus('legacy-active')).toMatchObject({tone: 'warning', label: 'Instancia anterior activa'});
  });
  it.each([undefined, 'unknown', 'unexpected', 'missing', 'unconfigured'])('keeps %s neutral instead of guessing', raw => {
    expect(runtimeStatus(raw, true)).toMatchObject({tone: 'neutral', icon: 'unknown'});
  });
});

describe('engine adapters', () => {
  it('does not confuse gateway health with model inference readiness', () => {
    expect(engineStatus('halogen', fixture())).toMatchObject({tone: 'success', label: 'Cargado'});
    expect(engineStatus('halogen', fixture()).detail).toContain('No verifica');
    expect(engineStatus('halogen', fixture({gateway_health: false}))).toMatchObject({tone: 'warning'});
    expect(engineStatus('halogen', fixture({services: {gateway: 'inactive'}}))).toMatchObject({tone: 'warning'});
    expect(engineStatus('halogen', fixture({halogen: 'unloaded'}))).toMatchObject({tone: 'danger', label: 'Descargado'});
    expect(engineStatus('halogen', fixture({halogen: 'unknown'}))).toMatchObject({tone: 'neutral'});
  });
  it('uses the matching HTTP check for each service', () => {
    const state = fixture({services: {gateway: 'active', comfyui: 'active'}, comfyui_health: false});
    expect(engineStatus('gateway', state).tone).toBe('success');
    expect(engineStatus('comfyui', state).tone).toBe('warning');
  });
  it.each(['unsloth', 'llamafactory'] as const)('checks container readiness and unit transitions for %s', engine => {
    const state = fixture({[engine]: {available: true, state: 'running', health: true, url: null, error: ''}});
    expect(engineStatus(engine, state).tone).toBe('success');
    state.services[engine] = 'deactivating';
    expect(engineStatus(engine, state)).toMatchObject({tone: 'warning', label: 'Deteniendo'});
    state.services[engine] = 'failed';
    expect(engineStatus(engine, state)).toMatchObject({tone: 'danger', label: 'Fallo'});
    expect(engineStatus(engine, state).detail).toContain('running');
  });
  it('tolerates absent initial data and older responses', () => {
    expect(engineStatus('gateway').tone).toBe('neutral');
    expect(engineStatus('unsloth', fixture()).tone).toBe('neutral');
  });
});
