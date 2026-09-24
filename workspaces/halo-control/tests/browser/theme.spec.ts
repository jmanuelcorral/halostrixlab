import {test, expect} from '@playwright/test';

async function fixture(page: import('@playwright/test').Page, preference: string) {
  await page.route('**/runtime.json', route => route.fulfill({json: {workspace: '/fixture'}}));
  await page.addInitScript(({preference}) => {
    localStorage.setItem('shell:style', preference);
    localStorage.setItem('halo-theme', 'obsolete');
    const samples = Array.from({length: 20}, (_, index) => ({time: Date.now()/1000-(20-index)*5, cpu: {cpu: 10+index}, memory: {used: 40*2**30, total: 128*2**30, available: 88*2**30, swap_used: 0}, gpu: [], temperatures: [], disk: {total: 2000*2**30, free: 1100*2**30}, network: {wlan0: {rx: 1_000_000, tx: 250_000}}, load: [], pressure: {}}));
    (window as any).channels = 0;
    (window as any).cockpit = {
      spawn: async (args: string[]) => JSON.stringify(args[2] === 'history' ? samples : {services: {}, jobs: [], errors: [], ssh_hosts: []}),
      user: async () => ({name: 'fixture', home: '/fixture', shell: '/bin/bash'}),
      channel: () => { (window as any).channels++; return {send() {}, close() {}, control() {}, addEventListener() {}}; },
    };
  }, {preference});
  await page.goto('/');
  await expect(page.getByRole('img', {name: 'Gráfica usage', exact: true})).toBeVisible();
}

for (const preference of ['light', 'dark']) {
  test(`Cockpit ${preference} colors apply to widgets, charts and controls`, async ({page}) => {
    await page.emulateMedia({colorScheme: preference === 'light' ? 'dark' : 'light'});
    await fixture(page, preference);
    await expect(page.locator('html')).toHaveAttribute('data-theme', preference);
    await expect(page.getByRole('button', {name: 'Cambiar tema'})).toHaveCount(0);
    const palette = await page.evaluate(() => {
      const root = getComputedStyle(document.documentElement);
      const panel = getComputedStyle(document.querySelector('.panel')!);
      const body = getComputedStyle(document.body);
      const resolve = (variable: string) => {
        const probe = document.createElement('div');
        probe.style.color = `var(${variable})`;
        document.body.appendChild(probe);
        const value = getComputedStyle(probe).color;
        probe.remove();
        return value;
      };
      const luminance = (color: string) => {
        const channels = color.match(/[\d.]+/g)!.slice(0, 3).map(Number).map(value => {const channel = value/255; return channel <= 0.04045 ? channel/12.92 : ((channel+0.055)/1.055)**2.4;});
        return channels[0]*0.2126 + channels[1]*0.7152 + channels[2]*0.0722;
      };
      const background = luminance(panel.backgroundColor);
      const contrasts = Array.from({length: 7}, (_, index) => {
        const foreground = luminance(resolve('--halo-series-' + index));
        return (Math.max(foreground, background)+0.05)/(Math.min(foreground, background)+0.05);
      });
      if (contrasts.some(value => value < 3)) throw new Error('Chart series contrast below 3:1: ' + contrasts);
      return {panel: panel.backgroundColor, expectedPanel: resolve('--pf-t--global--background--color--primary--default'), background: body.backgroundColor, expectedBackground: resolve('--pf-t--global--background--color--secondary--default'), foreground: body.color, expectedForeground: resolve('--pf-t--global--text--color--regular'), font: root.fontFamily, gradient: getComputedStyle(document.querySelector('.kpis article')!).backgroundImage};
    });
    expect(palette.panel).toBe(palette.expectedPanel);
    expect(palette.background).toBe(palette.expectedBackground);
    expect(palette.foreground).toBe(palette.expectedForeground);
    expect(palette.font).toContain('Red Hat');
    expect(palette.gradient).toBe('none');
    expect(palette.foreground).not.toBe(palette.panel);
    await page.screenshot({path: `data/cockpit-theme-${preference}.png`, fullPage: false});
    await page.setViewportSize({width: 390, height: 844});
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
  });
}

test('Cockpit storage and style events update an open page without reconnecting its terminal', async ({page}) => {
  await fixture(page, 'light');
  const before = await page.locator('body').evaluate(element => getComputedStyle(element).backgroundColor);
  await page.evaluate(() => {
    localStorage.setItem('shell:style', 'dark');
    window.dispatchEvent(new StorageEvent('storage', {key: 'shell:style', newValue: 'dark'}));
  });
  await expect(page.locator('html')).toHaveClass(/pf-v6-theme-dark/);
  expect(await page.locator('body').evaluate(element => getComputedStyle(element).backgroundColor)).not.toBe(before);
  await page.getByRole('navigation').getByRole('button', {name: /Terminal/}).click();
  await page.getByRole('button', {name: 'Abrir consola', exact: true}).click();
  await expect(page.locator('.xterm')).toBeVisible();
  await expect.poll(() => page.evaluate(() => (window as any).channels)).toBe(1);
  await page.evaluate(() => window.dispatchEvent(new CustomEvent('cockpit-style', {detail: {style: 'light'}})));
  await expect(page.locator('html')).not.toHaveClass(/pf-v6-theme-dark/);
  await expect(page.locator('.xterm')).toBeVisible();
  expect(await page.evaluate(() => (window as any).channels)).toBe(1);
  expect(await page.evaluate(() => localStorage.getItem('halo-theme'))).toBe('obsolete');
});

test('automatic theme follows OS changes but explicit Cockpit choice wins', async ({page}) => {
  await page.emulateMedia({colorScheme: 'light'});
  await fixture(page, 'auto');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.emulateMedia({colorScheme: 'dark'});
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.evaluate(() => {
    localStorage.setItem('shell:style', 'light');
    window.dispatchEvent(new StorageEvent('storage', {key: 'shell:style'}));
  });
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
  await page.emulateMedia({colorScheme: 'light'});
  await page.emulateMedia({colorScheme: 'dark'});
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'light');
});
