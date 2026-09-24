import {afterEach, describe, expect, it, vi} from 'vitest';
import {checkMaintenanceSession, rebootError} from './rebootPreflight';

afterEach(() => vi.unstubAllGlobals());
describe('maintenance session preflight', () => {
  it('detects retained update session without executing the helper', async () => {
    const spawn = vi.fn().mockResolvedValue('update\n');
    vi.stubGlobal('window', {cockpit: {spawn}});
    expect(await checkMaintenanceSession()).toBe(true);
    expect(spawn.mock.calls[0][0]).toEqual(['/usr/bin/tmux', '-S', '/run/halo-control/maintenance.sock', 'list-sessions', '-F', '#{session_name}']);
  });
  it('accepts only an explicitly absent server as no session', async () => {
    vi.stubGlobal('window', {cockpit: {spawn: vi.fn().mockRejectedValue({exit_status: 1, message: 'no server running on /run/halo-control/maintenance.sock'})}});
    expect(await checkMaintenanceSession()).toBe(false);
  });
  it('does not treat denied or unknown failures as an absent session', async () => {
    for (const error of [{problem: 'access-denied'}, {exit_status: 1, message: 'Permission denied'}, {exit_status: 127, message: 'No such file or directory'}]) {
      vi.stubGlobal('window', {cockpit: {spawn: vi.fn().mockRejectedValue(error)}});
      await expect(checkMaintenanceSession()).rejects.toThrow('No se pudo comprobar');
    }
  });
  it('explains closing a completed session instead of forcing a reboot', () => {
    expect(rebootError(new Error('Close the update session before rebooting'))).toContain('pulsa Enter');
    expect(rebootError(new Error('access-denied'))).toContain('Acceso administrativo');
  });
});
