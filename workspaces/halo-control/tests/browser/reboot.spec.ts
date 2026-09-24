import {test, expect} from '@playwright/test';

async function fixture(page: import('@playwright/test').Page, mode = 'ok') {
  await page.route('**/runtime.json', route => route.fulfill({json: {workspace: '/fixture'}}));
  await page.addInitScript(({mode}) => {
    (window as any).calls = [];
    let prepared = false;
    (window as any).newBoot = sessionStorage.getItem('fixture-new-boot') === 'true';
    (window as any).offline = false;
    (window as any).cockpit = {spawn: async (args: string[], options: any) => {
      (window as any).calls.push({args, options});
      if (args[0] === '/usr/bin/cat') {
        if ((window as any).offline) throw {problem: 'disconnected'};
        return (window as any).newBoot ? 'new' : 'old';
      }
      if (args[0] === '/usr/bin/tmux') return mode === 'session-open' ? 'update\n' : '';
      if (args[0] === '/usr/bin/id') {if (mode === 'denied') throw new Error('access-denied'); return '0\n';}
      if (args[0] === '/usr/local/libexec/halo-maintenance') {
        if (args[1] === 'report') return JSON.stringify({state: mode === 'updating' ? 'running' : 'success'});
        if (mode === 'rejected') throw new Error('Update session still open');
        if (mode === 'disconnect') {(window as any).offline = true; throw {problem: 'disconnected'};}
        return '';
      }
      if (args[2] === 'submit') {prepared = true; return JSON.stringify({job: 'prepare'});}
      if (args[2] === 'reboot-verify') return JSON.stringify({ready: true, boot_id: 'old'});
      if (args[2] === 'reboot-release') return '{}';
      return JSON.stringify(args[2] === 'history' ? [] : {services: {}, jobs: prepared ? [{id: 'prepare', state: mode === 'stop-failed' ? 'failed' : 'success', action: 'prepare-reboot', message: 'Service stop failed'}] : [], errors: [], ssh_hosts: [], boot_id: (window as any).newBoot ? 'new' : 'old', maintenance_available: true, reboot: prepared ? {phase: 'ready', token: 'fixture'} : null});
    }};
  }, {mode});
  await page.goto('/');
  await page.getByRole('navigation').getByRole('button', {name: /Actualizaciones/}).click();
}

test('cancel reboot has no side effects', async ({page}) => {
  await fixture(page);
  page.once('dialog', async dialog => {expect(dialog.message()).toContain('entrenamientos'); await dialog.dismiss();});
  await page.getByRole('button', {name: 'Reiniciar equipo', exact: true}).click();
  expect(await page.evaluate(() => (window as any).calls.filter((call: any) => call.args[0] !== '/usr/bin/python3' || call.args[2] === 'submit'))).toEqual([]);
});

test('confirmed reboot checks privilege then stops, verifies and requests reboot once', async ({page}) => {
  await fixture(page);
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', {name: 'Reiniciar equipo', exact: true}).click();
  const reboot = page.getByRole('region', {name: 'Reinicio supervisado'});
  await expect(reboot.getByRole('status')).toContainText('todavía no se confirma');
  const calls = await page.evaluate(() => (window as any).calls.filter((call: any) => !['status', 'history'].includes(call.args[2])).map((call: any) => call.args));
  expect(calls).toEqual([['/usr/bin/id', '-u'], ['/usr/bin/tmux', '-S', '/run/halo-control/maintenance.sock', 'list-sessions', '-F', '#{session_name}'], ['/usr/local/libexec/halo-maintenance', 'report'], ['/usr/bin/python3', '/fixture/control.py', 'submit', 'prepare-reboot'], ['/usr/bin/python3', '/fixture/control.py', 'reboot-verify', 'fixture'], ['/usr/local/libexec/halo-maintenance', 'reboot']]);
  await expect(reboot.getByRole('button', {name: 'Reiniciar equipo', exact: true})).toBeDisabled();
  const overlay = page.getByRole('dialog', {name: 'Reiniciando el equipo'});
  await expect(overlay.getByRole('timer')).toContainText('Próximo intento en');
  await page.evaluate(() => {(window as any).newBoot = true; sessionStorage.setItem('fixture-new-boot', 'true');});
  await expect(overlay.getByRole('status')).toContainText('Reinicio confirmado', {timeout: 10000});
  await page.waitForEvent('load');
  await expect(page.getByRole('dialog', {name: 'Reiniciando el equipo'})).toHaveCount(0, {timeout: 10000});
  await page.getByRole('navigation').getByRole('button', {name: /Actualizaciones/}).click();
  await expect(reboot.getByRole('status')).toContainText('Reinicio confirmado');
  expect(await page.evaluate(() => sessionStorage.getItem('halo-reboot-request'))).toBeNull();
  expect(await page.evaluate(() => (window as any).calls.some((call: any) => call.args[1] === 'reboot'))).toBe(false);
});

test('disconnection during submission retries without repeating reboot and reloads when web returns', async ({page}) => {
  await fixture(page, 'disconnect');
  let webAvailable = false;
  let probes = 0;
  await page.route('**/', route => {
    if (route.request().resourceType() === 'fetch') {
      probes++;
      return route.fulfill({status: webAvailable ? 401 : 503, body: ''});
    }
    return route.continue();
  });
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', {name: 'Reiniciar equipo', exact: true}).click();
  const overlay = page.getByRole('dialog', {name: 'Reiniciando el equipo'});
  await expect(overlay.getByRole('timer')).toContainText('5 s');
  await expect(overlay.getByRole('timer')).toContainText('4 s');
  await expect(overlay.getByRole('status')).toContainText('aún no responde', {timeout: 10000});
  await expect.poll(() => probes).toBe(1);
  expect(await page.evaluate(() => (window as any).calls.filter((call: any) => call.args[1] === 'reboot').length)).toBe(1);
  expect(await page.evaluate(() => (window as any).calls.some((call: any) => call.args[2] === 'reboot-release'))).toBe(false);
  webAvailable = true;
  await page.waitForEvent('load', {timeout: 15000});
  expect(await page.evaluate(() => JSON.parse(sessionStorage.getItem('halo-reboot-request')!).reloaded)).toBe(true);
  await page.getByRole('dialog').getByRole('button', {name: 'Cerrar seguimiento'}).click();
  expect(await page.evaluate(() => (window as any).calls.some((call: any) => call.args[1] === 'reboot'))).toBe(false);
});

test('reconnection stays visible above a hidden Cockpit iframe and reloads the shell', async ({page}) => {
  await fixture(page);
  await page.route('**/shell-fixture', route => route.fulfill({contentType: 'text/html', body: '<html><body><iframe title="Halo Control" src="/"></iframe></body></html>'}));
  await page.goto('/shell-fixture');
  const frame = page.frameLocator('iframe');
  await frame.getByRole('navigation').getByRole('button', {name: /Actualizaciones/}).click();
  page.once('dialog', dialog => dialog.accept());
  await frame.getByRole('button', {name: 'Reiniciar equipo', exact: true}).click();
  await expect(page.getByRole('dialog', {name: 'Reiniciando el equipo'})).toBeVisible();
  await page.evaluate(() => {document.querySelector('iframe')!.style.display = 'none';});
  await expect(page.getByRole('timer')).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(page.getByRole('button', {name: 'Cerrar seguimiento'})).toBeFocused();
  await page.frames()[1].evaluate(() => {(window as any).newBoot = true; sessionStorage.setItem('fixture-new-boot', 'true');});
  await page.waitForEvent('load', {timeout: 15000});
  await expect(page.locator('iframe')).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(0, {timeout: 10000});
});

test('same boot times out with no reload or second reboot', async ({page}) => {
  await fixture(page);
  await page.clock.install();
  page.once('dialog', dialog => dialog.accept());
  await page.getByRole('button', {name: 'Reiniciar equipo', exact: true}).click();
  await page.clock.runFor(5250);
  await expect(page.getByRole('dialog').getByRole('status')).toContainText('arranque anterior');
  await page.clock.fastForward(600000);
  await expect(page.getByRole('dialog', {name: 'Reconexión pendiente'})).toBeVisible();
  await expect(page.getByRole('dialog').getByRole('status')).toContainText('10 minutos');
  expect(await page.evaluate(() => (window as any).calls.filter((call: any) => call.args[1] === 'reboot').length)).toBe(1);
  await page.getByRole('button', {name: 'Cerrar seguimiento'}).click();
  expect(await page.evaluate(() => sessionStorage.getItem('halo-reboot-request'))).toBeNull();
});

test('reloaded receipt with expired authentication never loops reloads', async ({page}) => {
  await fixture(page);
  await page.evaluate(() => sessionStorage.setItem('halo-reboot-request', JSON.stringify({boot_id: 'old', requested: Date.now(), reloaded: true})));
  await page.reload();
  await page.evaluate(() => {(window as any).offline = true;});
  await expect(page.getByRole('dialog')).toHaveCount(0, {timeout: 10000});
  await page.getByRole('navigation').getByRole('button', {name: /Actualizaciones/}).click();
  await expect(page.getByRole('region', {name: 'Reinicio supervisado'}).getByRole('status')).toContainText('Vuelve a iniciar sesión');
  expect(await page.evaluate(() => sessionStorage.getItem('halo-reboot-request'))).toBeNull();
});

for (const mode of ['denied', 'updating', 'stop-failed', 'rejected', 'session-open']) {
  test(`reboot ${mode} reports error without false success`, async ({page}) => {
    await fixture(page, mode);
    page.once('dialog', dialog => dialog.accept());
    await page.getByRole('button', {name: 'Reiniciar equipo', exact: true}).click();
    const reboot = page.getByRole('region', {name: 'Reinicio supervisado'});
    await expect(reboot.getByRole('alert')).toBeVisible();
    await expect(reboot.getByRole('status')).toContainText('Reinicio no confirmado');
    const calls = await page.evaluate(() => (window as any).calls.map((call: any) => call.args));
    if (mode === 'denied' || mode === 'updating' || mode === 'session-open') expect(calls.some((args: string[]) => args[2] === 'submit')).toBe(false);
    if (mode !== 'rejected') expect(calls.some((args: string[]) => args[0] === '/usr/local/libexec/halo-maintenance' && args[1] === 'reboot')).toBe(false);
    if (mode === 'rejected') expect(calls.some((args: string[]) => args[2] === 'reboot-release')).toBe(true);
    if (mode === 'session-open') {
      await expect(reboot.getByRole('alert')).toContainText('pulsa Enter');
      await page.evaluate(() => {
        (window as any).cockpit.user = async () => ({home: '/fixture', shell: '/bin/bash'});
        (window as any).cockpit.channel = (options: any) => {(window as any).attached = options; return {send() {}, close() {}, control() {}, addEventListener() {}};};
      });
      await reboot.getByRole('button', {name: 'Ver sesión de actualización existente'}).click();
      await expect.poll(() => page.evaluate(() => (window as any).attached?.spawn)).toEqual(['/usr/bin/tmux', '-S', '/run/halo-control/maintenance.sock', 'attach-session', '-t', 'update']);
    }
  });
}
