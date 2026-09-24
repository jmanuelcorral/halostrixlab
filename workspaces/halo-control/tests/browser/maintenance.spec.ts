import {test, expect} from '@playwright/test';

async function fixture(page: import('@playwright/test').Page, mode: string) {
  await page.route('**/runtime.json', route => route.fulfill({json: {workspace: '/fixture'}}));
  await page.addInitScript(({mode}) => {
    (window as any).channels = [];
    (window as any).input = [];
    (window as any).submissions = [];
    (window as any).cockpit = {
      spawn: async (args: string[]) => {
        if (args[2] === 'submit') {(window as any).submissions.push(args[3]); return JSON.stringify({job: 'fixture-check'});}
        return JSON.stringify(args[2] === 'history' ? [] : {services: {}, jobs: [], errors: [], ssh_hosts: ['fixture-remote'], maintenance_available: true, updates: {updated: Date.now()/1000, data: {ok: true, packages: [{name: 'fixture', from: '1', to: '2'}]}}});
      },
      user: async () => ({name: 'fixture', home: '/fixture', shell: '/bin/bash'}),
      channel: (options: any) => {
        (window as any).channels.push(options);
        const listeners: Record<string, (event: unknown, data: any) => void> = {};
        setTimeout(() => {
          if (mode === 'denied') {listeners.close?.({}, {problem: 'access-denied'}); return;}
          if (mode === 'silent') return;
          listeners.ready?.({}, {});
          const text = mode === 'blocked' ? 'Stop and drain AI services before maintenance\r\n' : ':: Sincronizando paquetes\r\n¿Continuar con la instalación? [S/n]\r\n';
          listeners.message?.({}, new TextEncoder().encode(text));
          if (mode === 'blocked') listeners.close?.({}, {'exit-status': 1});
        }, 80);
        return {send: (text: string) => (window as any).input.push(text), control() {}, close() {}, addEventListener: (name: string, callback: any) => {listeners[name] = callback;}};
      },
    };
  }, {mode});
  await page.goto('/');
  await page.getByRole('navigation').getByRole('button', {name: /Actualizaciones/}).click();
}

test('package check then full update shows interactive output locally and survives navigation', async ({page}) => {
  await fixture(page, 'output');
  await page.getByRole('button', {name: 'Consultar paquetes', exact: true}).click();
  await expect.poll(() => page.evaluate(() => (window as any).submissions)).toEqual(['check-updates']);
  await expect(page.getByRole('button', {name: 'Aplicar actualización completa', exact: true})).toBeEnabled({timeout: 10000});
  await page.getByRole('button', {name: 'Aplicar actualización completa', exact: true}).click();
  await expect(page.getByRole('heading', {name: 'Actualizaciones', exact: true})).toBeVisible();
  const console = page.getByRole('region', {name: 'Consola de actualización', exact: true});
  await expect(console).toBeInViewport();
  await expect(console.locator('.xterm-accessibility')).toContainText('Sincronizando paquetes');
  await expect(console.locator('.xterm-accessibility')).toContainText('Continuar con la instalación');
  const options = await page.evaluate(() => (window as any).channels[0]);
  expect(options.spawn).toEqual(['/usr/local/libexec/halo-maintenance', 'update']);
  expect(options).toMatchObject({superuser: 'require', pty: true, binary: true, err: 'out'});
  await console.locator('.xterm-helper-textarea').fill('s');
  await page.keyboard.press('Enter');
  await expect.poll(() => page.evaluate(() => (window as any).input.join(''))).toContain('\r');
  await page.getByRole('navigation').getByRole('button', {name: /Resumen/}).click();
  await page.getByRole('navigation').getByRole('button', {name: /Actualizaciones/}).click();
  await expect(console.locator('.xterm-accessibility')).toContainText('Sincronizando paquetes');
  expect(await page.evaluate(() => (window as any).channels.length)).toBe(1);
  await page.getByRole('button', {name: 'Aplicar actualización completa', exact: true}).click();
  expect(await page.evaluate(() => (window as any).channels.length)).toBe(1);
});

for (const mode of ['denied', 'blocked']) {
  test(`update ${mode} is visible and does not claim success`, async ({page}) => {
    await fixture(page, mode);
    await page.getByRole('button', {name: 'Aplicar actualización completa', exact: true}).click();
    const console = page.getByRole('region', {name: 'Consola de actualización', exact: true});
    await expect(console.getByRole('alert')).toContainText(mode === 'denied' ? 'access-denied' : 'Código de salida: 1');
    if (mode === 'blocked') await expect(console.locator('.xterm-accessibility')).toContainText('Stop and drain AI services');
    await expect(page.getByRole('heading', {name: 'Actualizaciones', exact: true})).toBeVisible();
    await console.getByRole('button', {name: 'Reconectar consola de actualización'}).click();
    await expect.poll(() => page.evaluate(() => (window as any).channels.length)).toBe(2);
  });
}

test('silent authorization leaves an explicit pending state', async ({page}) => {
  await fixture(page, 'silent');
  await page.getByRole('button', {name: 'Aplicar actualización completa', exact: true}).click();
  const console = page.getByRole('region', {name: 'Consola de actualización', exact: true});
  await expect(console.getByRole('status')).toContainText('Solicitando acceso administrativo');
  await expect(console.getByRole('status')).toContainText('actualización no está confirmada', {timeout: 20000});
});
