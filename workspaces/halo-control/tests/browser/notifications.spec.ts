import {test, expect} from '@playwright/test';

async function fixture(page: import('@playwright/test').Page, failure = false) {
  await page.route('**/runtime.json', route => route.fulfill({json: {workspace: '/fixture'}}));
  await page.addInitScript(({failure}) => {
    (window as any).cockpit = {spawn: async (args: string[]) => {
      if (args[2] === 'submit') {
        if (failure) throw new Error('Error de prueba');
        return JSON.stringify({job: 'toast-fixture'});
      }
      return JSON.stringify(args[2] === 'history' ? [] : {services: {}, jobs: [], errors: [], ssh_hosts: []});
    }};
  }, {failure});
  await page.goto('/');
  await page.getByRole('navigation').getByRole('button', {name: /Actualizaciones/}).click();
  await page.getByRole('button', {name: 'Consultar paquetes', exact: true}).click();
  await page.mouse.move(0, 0);
}

test('toast dismisses automatically without moving widgets', async ({page}) => {
  await fixture(page);
  const toast = page.locator('.halo-toasts');
  await expect(toast.getByRole('status')).toContainText('Operación registrada');
  await expect(toast.getByRole('status')).toHaveCount(0, {timeout: 12000});
});

test('toast can be closed manually on mobile', async ({page}) => {
  await page.setViewportSize({width: 390, height: 844});
  await fixture(page);
  const toast = page.locator('.halo-toasts');
  await toast.getByRole('button', {name: 'Cerrar aviso'}).click();
  await expect(toast.getByRole('status')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
});

test('errors outlive status polling and disappear after their timeout', async ({page}) => {
  await fixture(page, true);
  const alert = page.locator('.halo-toasts').getByRole('alert');
  await expect(alert).toContainText('Error de prueba');
  await page.waitForTimeout(6000);
  await expect(alert).toBeVisible();
  await expect(alert).toHaveCount(0, {timeout: 10000});
});
