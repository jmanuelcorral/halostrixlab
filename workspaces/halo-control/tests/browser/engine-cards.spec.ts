import {test, expect, type Page} from '@playwright/test';

async function fixture(page: Page, theme = 'light') {
  await page.route('**/runtime.json', route => route.fulfill({json: {workspace: '/fixture'}}));
  await page.addInitScript(({theme}) => {
    localStorage.setItem('shell:style', theme);
    (window as any).engineState = {services: {gateway: 'active', comfyui: 'inactive', unsloth: 'active', llamafactory: 'failed'}, laya: {available: true, state: 'running', health: true, error: ''}, halogen: 'unloaded', gateway_health: true, comfyui_health: false, unsloth: {available: true, state: 'paused', health: false}, llamafactory: {available: true, state: 'dead', health: false}, jobs: [], errors: [], ssh_hosts: []};
    (window as any).cockpit = {spawn: async (args: string[]) => JSON.stringify(args[2] === 'history' ? [] : args[2] === 'logs' ? {text: 'Shared gateway log fixture'} : (window as any).engineState)};
  }, {theme});
  await page.goto('/');
  await page.getByRole('navigation').getByRole('button', {name: /Servicios IA/}).click();
  await expect(page.locator('.engine-status').first()).toHaveText('Activo');
}

for (const action of ['start', 'stop']) {
  test(`Laya ${action} submits only its shared-gateway action`, async ({page}) => {
    await fixture(page);
    await page.evaluate(() => {
      const original = window.cockpit!.spawn;
      (window as any).submitted = [];
      window.cockpit!.spawn = ((args: string[]) => {
        if (args[2] === 'submit') {(window as any).submitted.push(args[3]); return Promise.resolve(JSON.stringify({job: 'laya-fixture'}));}
        return original(args);
      }) as typeof original;
    });
    const card = page.locator('article.service').filter({has: page.getByRole('heading', {name: 'Laya', exact: true})});
    await card.getByRole('button', {name: action === 'start' ? 'Arrancar Laya' : 'Detener Laya', exact: true}).click();
    expect(await page.evaluate(() => (window as any).submitted)).toEqual(['laya-' + action]);
    await expect(card.getByRole('button', {name: 'Arrancar Laya', exact: true})).toBeDisabled();
    await expect(card.getByRole('button', {name: 'Detener Laya', exact: true})).toBeDisabled();
  });
}

test('Laya controls require the shared gateway and expose shared logs', async ({page}) => {
  await fixture(page);
  await page.evaluate(() => {(window as any).engineState.services.gateway = 'inactive';});
  const card = page.locator('article.service').filter({has: page.getByRole('heading', {name: 'Laya', exact: true})});
  await expect(card.getByRole('button', {name: 'Arrancar Laya', exact: true})).toBeDisabled({timeout: 10000});
  await expect(card.getByText('Arranca primero el gateway compartido desde su tarjeta.')).toBeVisible();
  await card.getByRole('button', {name: 'Logs compartidos de Laya'}).click();
  await expect(page.getByRole('heading', {name: 'Logs', exact: true})).toBeVisible();
  await expect(page.getByLabel('Servicio de logs')).toHaveValue('gateway');
});

for (const theme of ['light', 'dark']) {
  test(`official local images and accessible status colors in ${theme}`, async ({page}) => {
    const remote: string[] = [];
    page.on('request', request => {if (request.resourceType() === 'image' && !request.url().startsWith('http://127.0.0.1:')) remote.push(request.url());});
    await fixture(page, theme);
    const images = page.locator('.engine-art img');
    await expect(images).toHaveCount(6);
    await expect(page.locator('.engine-art--laya img')).toHaveAttribute('src', `./engine-art/laya-${theme}.png`);
    await expect.poll(() => images.evaluateAll(elements => elements.every(element => (element as HTMLImageElement).complete && (element as HTMLImageElement).naturalWidth > 0))).toBe(true);
    expect(remote).toEqual([]);
    await expect(page.locator('.engine-art--unsloth img')).toHaveAttribute('src', `./engine-art/unsloth-studio-${theme}.png`);
    await expect(page.locator('.engine-status')).toHaveText(['Activo', 'Descargado', 'Activo', 'Parado', 'Pausado', 'Fallo']);
    for (const status of await page.locator('.engine-status').all()) {
      await expect(status).toHaveAttribute('aria-label', /.+: .+\./);
      await expect(status.locator('svg')).toHaveAttribute('aria-hidden', 'true');
    }
    const contrasts = await page.locator('.engine-status').evaluateAll(elements => {
      const luminance = (color: string) => {
        const channels = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map(value => {const channel = value/255; return channel <= 0.04045 ? channel/12.92 : ((channel+0.055)/1.055)**2.4;});
        return channels[0]*0.2126 + channels[1]*0.7152 + channels[2]*0.0722;
      };
      return elements.map(element => {
        const style = getComputedStyle(element);
        const foreground = luminance(style.color);
        const background = luminance(style.backgroundColor);
        return (Math.max(foreground, background)+0.05)/(Math.min(foreground, background)+0.05);
      });
    });
    expect(contrasts.every(value => value >= 4.5), String(contrasts)).toBe(true);
    for (const width of [390, 768, 1024, 1440]) {
      await page.setViewportSize({width, height: 1000});
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      for (const card of await page.locator('article.service').all()) {
        expect(await card.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
      }
    }
    await page.screenshot({path: `data/engine-cards-${theme}.png`, fullPage: true});
    const attribution = await page.request.get('/engine-art/ATTRIBUTION.txt');
    expect(attribution.ok()).toBe(true);
    expect(await attribution.text()).toContain('Peonist');
  });
}

test('image failure preserves identity and controls without remote fallback', async ({page}) => {
  await page.route('**/engine-art/halogen.jpg', route => route.abort());
  await fixture(page);
  const card = page.locator('article.service').filter({has: page.getByRole('heading', {name: 'Halogen', exact: true})});
  await expect(card.getByText('Imagen no disponible')).toBeVisible();
  await expect(card.getByRole('button', {name: 'Cargar Halogen', exact: true})).toBeEnabled();
  await expect(card.locator('.engine-status')).toHaveText('Descargado');
  expect(await card.locator('.engine-art').evaluate(element => element.getBoundingClientRect().height)).toBe(156);
});

test('polling and Cockpit theme changes repaint cards without reloading', async ({page}) => {
  await fixture(page);
  await page.evaluate(() => {
    const state = (window as any).engineState;
    state.gateway_health = false;
    state.halogen = 'loaded';
    state.services.comfyui = 'deactivating';
    state.unsloth.state = 'unknown';
    window.dispatchEvent(new CustomEvent('cockpit-style', {detail: {style: 'dark'}}));
  });
  await expect(page.locator('.engine-art--unsloth img')).toHaveAttribute('src', './engine-art/unsloth-studio-dark.png');
  await expect(page.locator('.engine-status')).toHaveText(['Sin respuesta HTTP', 'Cargado · revisar gateway', 'Revisar gateway', 'Deteniendo', 'Desconocido', 'Fallo'], {timeout: 10000});
  await expect(page.locator('.engine-status--neutral')).toHaveCount(1);
});
