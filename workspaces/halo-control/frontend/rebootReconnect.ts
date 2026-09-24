export const receiptKey = 'halo-reboot-request';
export const retryDelay = 5000;
export const reconnectLimit = 10 * 60 * 1000;
export type RebootReceipt = {boot_id: string; requested: number; reloaded?: boolean};

export function readReceipt(storage: Storage, now = Date.now()): RebootReceipt | null {
  try {
    const value = JSON.parse(storage.getItem(receiptKey) || 'null');
    if (!value || typeof value.boot_id !== 'string' || !value.boot_id || !Number.isFinite(value.requested) || value.requested > now || now - value.requested > 24 * 60 * 60 * 1000) {
      storage.removeItem(receiptKey);
      return null;
    }
    return {boot_id: value.boot_id, requested: value.requested, reloaded: value.reloaded === true};
  } catch {return null;}
}

export function connectionLost(reason: unknown): boolean {
  const problem = (reason as {problem?: string} | null)?.problem;
  return ['disconnected', 'terminated', 'no-cockpit', 'timeout'].includes(problem ?? '') || /disconnected|connection.*closed|connection.*lost|transport.*closed/i.test(String(reason));
}

export function reconnectTarget(): Window {
  try {
    if (window.top && window.top.location.origin === window.location.origin) return window.top;
  } catch {}
  return window;
}

export async function probeBoot(): Promise<string> {
  if (!window.cockpit) throw new Error('disconnected');
  const process = window.cockpit.spawn(['/usr/bin/cat', '/proc/sys/kernel/random/boot_id'], {err: 'message'});
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    const value = await Promise.race([Promise.resolve(process), new Promise<never>((_resolve, reject) => {
      timer = setTimeout(() => {process.close?.('timeout'); reject(new Error('disconnected: timeout'));}, 4000);
    })]);
    if (!value.trim()) throw new Error('No se recibió el identificador de arranque');
    return value.trim();
  } finally {clearTimeout(timer);}
}

export async function probeWeb(signal: AbortSignal): Promise<boolean> {
  const url = new URL(reconnectTarget().location.href);
  url.hash = '';
  const response = await fetch(url, {cache: 'no-store', credentials: 'same-origin', redirect: 'follow', signal});
  return response.ok || response.status === 401;
}
