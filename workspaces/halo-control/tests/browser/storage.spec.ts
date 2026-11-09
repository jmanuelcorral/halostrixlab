import {test, expect} from '@playwright/test';

test('disk graphs, partial inventory and manual scan are accessible', async ({page}) => {
  await page.route('**/runtime.json', route => route.fulfill({json: {workspace: '/fixture'}}));
  await page.addInitScript(() => {
    (window as any).actions = [];
    const sample = {time: Date.now()/1000, cpu: {cpu: 5}, memory: {used: 10, total: 100, available: 90, swap_used: 0}, gpu: [], temperatures: [], disk_temperatures: [{sensor: 'nvme:nvme0:Composite', celsius: 35}], disk: {total: 100 * 2**30, used: 60 * 2**30, free: 40 * 2**30}, io: {nvme0n1: {read: 2**20, write: 0, busy_ms: 100}}, load: [], network: {}, pressure: {}};
    const report = {finished: Date.now()/1000, roots: [{label: 'Modelos', path: '/fixture', bytes: 50 * 2**30, partial: true, reason: 'Lectura parcial: permisos', directories: [{path: '/fixture/models', bytes: 50 * 2**30, depth: 1, category: 'Modelos y caché de Hugging Face'}]}], docker: {available: true, rows: [{Type: 'Images', TotalCount: 3, Active: 1, Size: '20GB', Reclaimable: '10GB'}]}, method: 'No sumar filas ni capas compartidas.'};
    (window as any).cockpit = {spawn: async (args: string[]) => {
      if (args[2] === 'submit') {(window as any).actions.push(args[3]); return JSON.stringify({job: 'scan'});}
      return JSON.stringify(args[2] === 'history' ? [sample] : {services: {}, jobs: [], errors: [], ssh_hosts: [], storage: {updated: Date.now()/1000, data: report}});
    }};
  });
  await page.goto('/');
  await expect(page.getByRole('heading', {name: 'Disco y almacenamiento'})).toBeVisible();
  for (const kind of ['disk-capacity', 'disk-busy', 'disk-throughput', 'disk-temperature']) await expect(page.getByRole('img', {name: 'Gráfica ' + kind, exact: true})).toBeVisible();
  await expect(page.getByText('Lectura parcial: permisos', {exact: true})).toBeVisible();
  await expect(page.getByText('/fixture/models', {exact: true})).toBeVisible();
  await expect(page.getByText('nvme:nvme0:Composite: 35.0 °C', {exact: true})).toBeVisible();
  await page.getByRole('button', {name: 'Analizar ocupación', exact: true}).click();
  expect(await page.evaluate(() => (window as any).actions)).toEqual(['analyze-storage']);
  await expect(page.getByRole('button', {name: 'Analizar ocupación', exact: true})).toBeDisabled();
  await page.setViewportSize({width: 390, height: 844});
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBeTruthy();
});
