import {test, expect, type Page} from '@playwright/test';

async function fixture(page: Page, theme = 'light') {
  await page.route('**/runtime.json', route => route.fulfill({json: {workspace: '/fixture'}}));
  await page.addInitScript(({theme}) => {
    localStorage.setItem('shell:style', theme);
    (window as any).engineState = {services: {gateway: 'active', comfyui: 'inactive', unsloth: 'active', llamafactory: 'failed'}, laya: {available: true, state: 'running', health: true, error: ''}, halogen: 'unloaded', gateway_health: true, comfyui_health: false, unsloth: {available: true, state: 'paused', health: false}, llamafactory: {available: true, state: 'dead', health: false}, jobs: [], errors: [], ssh_hosts: []};
    (window as any).engineState.catalog = {available: true, global_slots: 7, reason: '', models: ['halogen','gufo','laya'].map(id => ({id, alias: id, name: id, engine: id, device: id === 'laya' ? 'CPU' : 'GPU', context: id === 'laya' ? 1024 : 131072, slots: id === 'halogen' ? 4 : id === 'gufo' ? 2 : 1, output: id === 'laya' ? null : 2048, weights_bytes: 17559178144, parameters_b: id === 'gufo' ? 27 : null, quantization: 'fixture', note: 'Fixture, no memoria de ejecución', kv_pool: null}))};
    (window as any).cockpit = {spawn: async (args: string[]) => JSON.stringify(args[2] === 'history' ? [] : args[2] === 'logs' ? {text: 'Shared gateway log fixture'} : (window as any).engineState)};
  }, {theme});
  await page.goto('/');
  await page.getByRole('navigation').getByRole('button', {name: /Servicios IA/}).click();
  await expect(page.locator('.engine-status').first()).toHaveText('Activo');
}

for (const action of ['load', 'unload']) {
  test(`Gufo catalog ${action} is supervised and preserves the model entry`, async ({page}) => {
    await fixture(page);
    await page.evaluate(() => {
      (window as any).engineState.gufo = {available: true, loaded: false};
      (window as any).engineState.unsloth.state = 'stopped';
      (window as any).submitted = [];
      const original = window.cockpit!.spawn;
      window.cockpit!.spawn = ((args: string[]) => {
        if (args[2] === 'submit') {(window as any).submitted.push(args[3]); return Promise.resolve(JSON.stringify({job: 'gufo-fixture'}));}
        return original(args);
      }) as typeof original;
    });
    const catalog = page.getByRole('region', {name: 'Catálogo de modelos'});
    await expect(catalog.getByRole('button', {name: 'Activar Gufo', exact: true})).toBeEnabled({timeout: 10000});
    await expect(catalog).toContainText('131.072');
    await expect(catalog).toContainText('Máximo slots configurados');
    await expect(catalog).toContainText('otra petición puede cargarlo');
    await catalog.getByRole('button', {name: action === 'load' ? 'Activar Gufo' : 'Desactivar Gufo', exact: true}).click();
    expect(await page.evaluate(() => (window as any).submitted)).toEqual([action === 'load' ? 'catalog-gufo' : 'gufo-unload']);
    await expect(catalog.getByRole('button', {name: 'Activar Gufo', exact: true})).toBeDisabled();
  });
}

test('Gufo catalog refuses absent configuration and inactive gateway', async ({page}) => {
  await fixture(page);
  const catalog = page.getByRole('region', {name: 'Catálogo de modelos'});
  await expect(catalog.getByRole('button', {name: 'Activar Gufo', exact: true})).toBeDisabled();
  await page.evaluate(() => {(window as any).engineState.gufo = {available: true, loaded: true}; (window as any).engineState.services.gateway = 'inactive';});
  await expect(catalog.getByText('Arranca primero el gateway compartido.')).toBeVisible({timeout: 10000});
  await expect(catalog.getByRole('button', {name: 'Desactivar Gufo', exact: true})).toBeDisabled();
});

for (const action of ['start', 'stop']) {
  test(`Laya ${action} submits only its shared-gateway action`, async ({page}) => {
    await fixture(page);
    await page.evaluate(() => {
      (window as any).engineState.unsloth.state = 'stopped';
      const original = window.cockpit!.spawn;
      (window as any).submitted = [];
      window.cockpit!.spawn = ((args: string[]) => {
        if (args[2] === 'submit') {(window as any).submitted.push(args[3]); return Promise.resolve(JSON.stringify({job: 'laya-fixture'}));}
        return original(args);
      }) as typeof original;
    });
    const card = page.locator('article.model').filter({has: page.getByRole('heading', {name: 'Laya', exact: true})});
    await expect(card.getByRole('button', {name: 'Arrancar Laya', exact: true})).toBeEnabled({timeout: 10000});
    await card.getByRole('button', {name: action === 'start' ? 'Arrancar Laya' : 'Detener Laya', exact: true}).click();
    expect(await page.evaluate(() => (window as any).submitted)).toEqual([action === 'start' ? 'catalog-laya' : 'laya-stop']);
    await expect(card.getByRole('button', {name: 'Arrancar Laya', exact: true})).toBeDisabled();
    await expect(card.getByRole('button', {name: 'Detener Laya', exact: true})).toBeDisabled();
  });
}

test('Laya controls require the shared gateway and expose shared logs', async ({page}) => {
  await fixture(page);
  await page.evaluate(() => {(window as any).engineState.services.gateway = 'inactive';});
  const card = page.locator('article.model').filter({has: page.getByRole('heading', {name: 'Laya', exact: true})});
  await expect(card.getByRole('button', {name: 'Arrancar Laya', exact: true})).toBeDisabled({timeout: 10000});
  await expect(page.getByText('Arranca primero el gateway compartido.', {exact: true})).toBeVisible({timeout: 10000});
  await card.getByRole('button', {name: 'Logs compartidos de Laya'}).click();
  await expect(page.getByRole('heading', {name: 'Logs', exact: true})).toBeVisible();
  await expect(page.getByLabel('Servicio de logs')).toHaveValue('gateway');
});

for (const gpu of ['Halogen', 'Gufo']) {
  test(`catalog loads ${gpu} with Laya as one supervised action`, async ({page}) => {
    await fixture(page);
    await page.evaluate(() => {
      const state = (window as any).engineState;
      state.unsloth.state = 'stopped';
      state.services.unsloth = 'inactive';
      (window as any).submitted = [];
      const original = window.cockpit!.spawn;
      window.cockpit!.spawn = ((args: string[]) => {
        if (args[2] === 'submit') {(window as any).submitted.push(args[3]); return Promise.resolve(JSON.stringify({job:'pair-fixture'}));}
        return original(args);
      }) as typeof original;
    });
    const stacks = page.getByRole('region', {name:'Stacks de servicios IA'});
    await expect(stacks.locator('article')).toHaveCount(4);
    await expect(stacks.getByRole('heading', {name:'Halogen',exact:true})).toHaveCount(0);
    const catalog = page.getByRole('region', {name:'Catálogo de modelos'});
    await expect(catalog.locator('article.model')).toHaveCount(3);
    await catalog.getByLabel('Seleccionar ' + gpu, {exact:true}).check();
    await catalog.getByLabel('Seleccionar Laya', {exact:true}).check();
    const launch = catalog.getByRole('button', {name:'Arrancar selección compatible'});
    await expect(launch).toBeEnabled({timeout:10000});
    await launch.click();
    expect(await page.evaluate(() => (window as any).submitted)).toEqual(['catalog-' + gpu.toLowerCase() + '-laya']);
    await expect(launch).toBeDisabled();
  });
}

test('catalog rejects both GPU models and distinguishes disk from memory', async ({page}) => {
  await fixture(page);
  const catalog = page.getByRole('region', {name:'Catálogo de modelos'});
  await catalog.getByLabel('Seleccionar Halogen', {exact:true}).check();
  await catalog.getByLabel('Seleccionar Gufo', {exact:true}).check();
  await expect(catalog.getByRole('alert')).toContainText('Selección incompatible');
  await expect(catalog.getByRole('button', {name:'Arrancar selección compatible'})).toBeDisabled();
  await expect(catalog).toContainText('No es una estimación de RAM/GPU libre');
  await expect(catalog).toContainText('27 B');
  for (const width of [390,768,1440]) {
    await page.setViewportSize({width,height:1000});
    for (const model of await catalog.locator('article.model').all()) {
      expect(await model.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
    }
  }
});

for (const theme of ['light', 'dark']) {
  test(`official local images and accessible status colors in ${theme}`, async ({page}) => {
    const remote: string[] = [];
    page.on('request', request => {if (request.resourceType() === 'image' && !request.url().startsWith('http://127.0.0.1:')) remote.push(request.url());});
    await fixture(page, theme);
    const images = page.locator('.engine-art img');
    await expect(images).toHaveCount(7);
    await expect(page.locator('.engine-art--gufo img')).toHaveAttribute('src', './engine-art/gufo.jpg');
    await expect(page.locator('.engine-art--laya img')).toHaveAttribute('src', `./engine-art/laya-${theme}.png`);
    await expect.poll(() => images.evaluateAll(elements => elements.every(element => (element as HTMLImageElement).complete && (element as HTMLImageElement).naturalWidth > 0))).toBe(true);
    expect(remote).toEqual([]);
    await expect(page.locator('.engine-art--unsloth img')).toHaveAttribute('src', `./engine-art/unsloth-studio-${theme}.png`);
    await expect(page.locator('.engine-status')).toHaveText(['Activo', 'Parado', 'Pausado', 'Fallo', 'Descargado', 'Sin configurar', 'Activo']);
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

test('Gufo logo failure keeps model identity and controls', async ({page}) => {
  await page.route('**/engine-art/gufo.jpg', route => route.abort());
  await fixture(page);
  const card = page.getByRole('article', {name: 'Modelo gufo'});
  await expect(card.getByText('Imagen no disponible')).toBeVisible();
  await expect(card.getByRole('heading', {name: 'Gufo', exact: true})).toBeVisible();
  await expect(card.getByRole('button', {name: 'Activar Gufo', exact: true})).toBeVisible();
});

test('image failure preserves identity and controls without remote fallback', async ({page}) => {
  await page.route('**/engine-art/halogen.jpg', route => route.abort());
  await fixture(page);
  const card = page.locator('article.model').filter({has: page.getByRole('heading', {name: 'Halogen', exact: true})});
  await expect(card.getByText('Imagen no disponible')).toBeVisible();
  await expect(card.getByRole('button', {name: 'Cargar Halogen', exact: true})).toBeDisabled();
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
  await expect(page.locator('.engine-status')).toHaveText(['Sin respuesta HTTP', 'Deteniendo', 'Desconocido', 'Fallo', 'Cargado · revisar gateway', 'Sin configurar', 'Revisar gateway'], {timeout: 10000});
  await expect(page.locator('.engine-status--neutral')).toHaveCount(2);
});
