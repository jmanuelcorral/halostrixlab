import {test, expect} from '@playwright/test';

async function fixture(page: import('@playwright/test').Page, editable = true) {
  await page.route('**/runtime.json', route => route.fulfill({json: {workspace: '/fixture'}}));
  await page.addInitScript(({editable}) => {
    const state = {services: {gateway: 'active', comfyui: 'inactive', unsloth: 'inactive', llamafactory: 'inactive'}, halogen: 'loaded', gateway_health: true, jobs: [], errors: [], ssh_hosts: [], maintenance_available: false};
    const titles: Record<string, string> = {gateway: 'llama-swap', halogen: 'Halogen', comfyui: 'ComfyUI', unsloth: 'Unsloth Studio', llamafactory: 'LLaMA-Factory'};
    let values = {reserve_vram: 4};
    let revision = 'first';
    (window as any).saves = [];
    (window as any).cockpit = {spawn: (args: string[]) => {
      const engine = args[3];
      const detail = () => ({id: engine, title: titles[engine], state: editable ? 'inactive' : 'active', editable, reason: editable ? '' : 'Detén el servicio antes de editar', values, fields: [{name: 'reserve_vram', label: 'Reserva GPU (GiB)', type: 'integer', min: 1, max: 24}], revision, paths: ['/fixture/options.json'], saved: {apiKeys: '[oculto]'}, effective: {environment: ['API_KEY=[oculto]']}});
      if (args[2] === 'engine-save') {
        let resolve: (text: string) => void;
        const result = new Promise<string>(done => {resolve = done;}) as Promise<string> & {input: (text: string) => void};
        result.input = text => {const payload = JSON.parse(text); (window as any).saves.push({args, payload}); values = payload.values; revision = 'saved'; resolve(JSON.stringify(detail()));};
        return result;
      }
      const value = args[2] === 'history' ? [] : args[2] === 'engine-detail' ? detail() : args[2] === 'engine-reveal' ? {...detail(), effective: {environment: ['API_KEY=synthetic-secret']}} : args[2] === 'engine-logs' ? {text: '<script>untrusted log</script>\nsecond line', source: 'fixture journal'} : state;
      return Promise.resolve(JSON.stringify(value));
    }};
  }, {editable});
  await page.goto('/');
}

test('every engine opens its own detail and logs', async ({page}) => {
  await fixture(page);
  for (const title of ['llama-swap', 'Halogen', 'ComfyUI', 'Unsloth Studio', 'LLaMA-Factory']) {
    await page.getByRole('button', {name: 'Ficha y logs de ' + title, exact: true}).click();
    await expect(page.getByRole('heading', {name: title, exact: true})).toBeVisible();
    await page.getByRole('tab', {name: 'Logs', exact: true}).click();
    await expect(page.getByRole('tabpanel')).toContainText('<script>untrusted log</script>');
    await expect(page.locator('script').filter({hasText: 'untrusted log'})).toHaveCount(0);
    await page.getByRole('button', {name: 'Volver a servicios'}).click();
  }
});

test('stopped editor saves through stdin and secrets clear on navigation', async ({page}) => {
  await fixture(page);
  await page.getByRole('button', {name: 'Ficha y logs de ComfyUI', exact: true}).click();
  await page.getByRole('spinbutton').fill('6');
  await page.getByRole('button', {name: 'Guardar campos permitidos'}).click();
  await expect(page.getByRole('status')).toContainText('Guardado');
  expect(await page.evaluate(() => (window as any).saves)).toEqual([{args: ['/usr/bin/python3', '/fixture/control.py', 'engine-save', 'comfyui'], payload: {revision: 'first', values: {reserve_vram: 6}}}]);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await page.getByRole('tab', {name: 'Entorno', exact: true}).click();
  await expect(page.getByRole('tabpanel')).not.toContainText('synthetic-secret');
  await page.getByRole('button', {name: 'Mostrar secretos y valores privados'}).click();
  await expect(page.getByRole('tabpanel')).toContainText('API_KEY=synthetic-secret');
  expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain('synthetic-secret');
  await page.getByRole('tab', {name: 'Logs', exact: true}).click();
  await page.getByRole('tab', {name: 'Entorno', exact: true}).click();
  await expect(page.getByRole('tabpanel')).not.toContainText('synthetic-secret');
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});

test('Studio save explains stopped recreation and retained backup', async ({page}) => {
  await fixture(page);
  await page.getByRole('button', {name: 'Ficha y logs de Unsloth Studio', exact: true}).click();
  await expect(page.getByRole('tabpanel')).toContainText('Guardar recrea el contenedor detenido');
  await page.getByRole('button', {name: 'Guardar campos permitidos'}).click();
  await expect(page.getByRole('status')).toContainText('Studio recreado y detenido');
  await expect(page.getByRole('status')).toContainText('salud pendiente');
  await expect(page.getByRole('dialog')).toHaveCount(0);
});

test('running editor is disabled while consultation and logs remain available', async ({page}) => {
  await fixture(page, false);
  await page.getByRole('button', {name: 'Ficha y logs de ComfyUI', exact: true}).click();
  await expect(page.getByRole('spinbutton')).toBeDisabled();
  await expect(page.getByRole('button', {name: 'Guardar campos permitidos'})).toBeDisabled();
  await page.getByRole('tab', {name: 'Logs', exact: true}).click();
  await expect(page.getByRole('tabpanel')).toContainText('fixture journal');
});
