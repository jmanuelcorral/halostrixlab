import {test, expect} from '@playwright/test';

for (const width of [390, 768, 1024, 1440]) {
  test(`widgets keep spacing and network selection works at ${width}px`, async ({page}) => {
    await page.setViewportSize({width, height: 900});
    await page.route('**/runtime.json', route => route.fulfill({json: {workspace: '/fixture'}}));
    await page.addInitScript(() => {
      const sample = {time: Date.now()/1000, cpu: {cpu: 10}, memory: {used: 40*2**30, total: 128*2**30, available: 88*2**30, swap_used: 0}, gpu: [], temperatures: [], disk: {total: 2000*2**30, used: 900*2**30, free: 1100*2**30}, network: {wlan0: {rx: 1_000_000, tx: 250_000}, docker0: {rx: 125_000, tx: 0}}, load: [], pressure: {}};
      (window as any).cockpit = {spawn: async (args: string[]) => JSON.stringify(args[2] === 'history' ? [sample] : {services: {}, jobs: [], errors: [], ssh_hosts: []})};
    });
    await page.goto('/');
    const network = page.getByRole('region', {name: 'Red y tráfico'});
    await expect(network.getByText('8.00 Mbit/s', {exact: true})).toBeVisible();
    await expect(network.getByText('2.00 Mbit/s', {exact: true})).toBeVisible();
    await expect(network.getByRole('img', {name: 'Gráfica network-rx', exact: true})).toBeVisible();
    await expect(network.getByRole('img', {name: 'Gráfica network-tx', exact: true})).toBeVisible();
    await page.getByLabel('Interfaz de red', {exact: true}).selectOption('docker0');
    await expect(network.getByText('1.00 Mbit/s', {exact: true})).toBeVisible();
    await expect(network.getByText('0.00 Mbit/s', {exact: true})).toBeVisible();
    for (const screen of ['Resumen', 'Métricas']) {
      if (screen === 'Métricas') await page.getByRole('navigation').getByRole('button', {name: /Métricas/}).click();
      await expect(network.getByRole('img', {name: 'Gráfica network-rx', exact: true})).toBeVisible();
      const collisions = await page.evaluate(() => {
        const issues: string[] = [];
        const widgets = [...document.querySelectorAll('main .panel, main .kpis > article')];
        for (let index = 0; index < widgets.length; index++) {
          const first = widgets[index].getBoundingClientRect();
          for (const widget of widgets.slice(index + 1)) {
            const second = widget.getBoundingClientRect();
            if (Math.min(first.right, second.right) - Math.max(first.left, second.left) > 1 && Math.min(first.bottom, second.bottom) - Math.max(first.top, second.top) > 1) issues.push('Widgets overlap');
          }
        }
        for (const grid of document.querySelectorAll('main .kpis, main .chart-grid, main .service-grid')) {
          const next = grid.nextElementSibling;
          if (next && next.getBoundingClientRect().top - grid.getBoundingClientRect().bottom < 15) issues.push('Insufficient gap after grid');
        }
        for (const chart of document.querySelectorAll('main .chart')) {
          const bounds = chart.getBoundingClientRect();
          const panel = chart.closest('.panel')!.getBoundingClientRect();
          if (bounds.right > panel.right || bounds.left < panel.left || bounds.bottom > panel.bottom) issues.push('Chart outside panel');
        }
        if (document.documentElement.scrollWidth > window.innerWidth) issues.push('Horizontal overflow');
        return issues;
      });
      expect(collisions).toEqual([]);
    }
    if (width === 1440) await page.screenshot({path: 'data/network-layout-review.png', fullPage: false});
  });
}
