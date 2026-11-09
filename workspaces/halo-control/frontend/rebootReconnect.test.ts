import {afterEach, describe, expect, it, vi} from 'vitest';
import {connectionLost, probeBoot, probeWeb, readReceipt, receiptKey} from './rebootReconnect';

afterEach(() => {vi.unstubAllGlobals(); vi.useRealTimers();});

function storage(value: string | null) {
  return {getItem: vi.fn(() => value), removeItem: vi.fn()} as unknown as Storage;
}

describe('reboot receipt and transport', () => {
  it('restores only a bounded credential-free receipt', () => {
    const receipt = {boot_id: 'before', requested: 100, reloaded: true, secret: 'discard'};
    expect(readReceipt(storage(JSON.stringify(receipt)), 200)).toEqual({boot_id: 'before', requested: 100, reloaded: true});
  });
  it.each(['invalid', 'null', '{}', '{"boot_id":"before","requested":"100"}', '{"boot_id":"before","requested":300}', '{"boot_id":"","requested":100}'])('ignores invalid receipt %s', value => {
    expect(readReceipt(storage(value), 200)).toBeNull();
  });
  it('expires old receipts and tolerates blocked storage', () => {
    const saved = storage('{"boot_id":"before","requested":100}');
    expect(readReceipt(saved, 90000000)).toBeNull();
    expect(saved.removeItem).toHaveBeenCalledWith(receiptKey);
    expect(readReceipt({getItem() {throw new Error('blocked');}} as unknown as Storage)).toBeNull();
  });
  it('distinguishes lost transport from explicit rejection', () => {
    expect(connectionLost({problem: 'disconnected'})).toBe(true);
    expect(connectionLost(new Error('connection closed'))).toBe(true);
    expect(connectionLost({problem: 'access-denied'})).toBe(false);
    expect(connectionLost(new Error('Update session still open'))).toBe(false);
  });
  it('probes boot ID without administrative privileges', async () => {
    const spawn = vi.fn(() => Promise.resolve('new-boot\n'));
    vi.stubGlobal('window', {cockpit: {spawn}});
    expect(await probeBoot()).toBe('new-boot');
    expect(spawn).toHaveBeenCalledWith(['/usr/bin/cat', '/proc/sys/kernel/random/boot_id'], {err: 'message'});
  });
  it('bounds stalled bridge calls and closes the channel', async () => {
    vi.useFakeTimers();
    const process = Object.assign(new Promise<string>(() => {}), {close: vi.fn()});
    vi.stubGlobal('window', {cockpit: {spawn: () => process}});
    const outcome = expect(probeBoot()).rejects.toThrow('timeout');
    await vi.advanceTimersByTimeAsync(4000);
    await outcome;
    expect(process.close).toHaveBeenCalledWith('timeout');
  });
  it('checks the current same-origin page without cache and accepts a login challenge', async () => {
    const target = {location: {href: 'https://panel.example.test/cockpit/#/halo_control', origin: 'https://panel.example.test'}};
    vi.stubGlobal('window', {...target, top: target});
    const fetch = vi.fn(async (_url: URL, _options: RequestInit) => ({ok: false, status: 401}));
    vi.stubGlobal('fetch', fetch);
    const controller = new AbortController();
    expect(await probeWeb(controller.signal)).toBe(true);
    expect(String(fetch.mock.calls[0][0])).toBe('https://panel.example.test/cockpit/');
    expect(fetch.mock.calls[0][1]).toMatchObject({cache: 'no-store', credentials: 'same-origin', signal: controller.signal});
  });
});
