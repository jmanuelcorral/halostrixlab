import {useEffect, useState} from 'react';

export function resolvedTheme(preference: string | null, systemDark: boolean) {
  return preference === 'dark' || (preference !== 'light' && systemDark) ? 'dark' : 'light';
}

export function synchronizeCockpitTheme() {
  const media = window.matchMedia('(prefers-color-scheme: dark)');
  const stored = () => {
    try {return localStorage.getItem('shell:style');} catch {return null;}
  };
  const apply = (preference = stored()) => {
    const theme = resolvedTheme(preference, media.matches);
    document.documentElement.classList.toggle('pf-v6-theme-dark', theme === 'dark');
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    window.dispatchEvent(new Event('halo-theme-changed'));
  };
  const storage = (event: StorageEvent) => {if (event.key === 'shell:style' || event.key === null) apply();};
  const cockpitStyle = (event: Event) => {
    if (event instanceof CustomEvent) apply(event.detail?.style);
  };
  const system = () => apply();
  window.addEventListener('storage', storage);
  window.addEventListener('cockpit-style', cockpitStyle);
  media.addEventListener('change', system);
  apply();
  return () => {
    window.removeEventListener('storage', storage);
    window.removeEventListener('cockpit-style', cockpitStyle);
    media.removeEventListener('change', system);
  };
}

export function useCockpitTheme() {
  const [theme, setTheme] = useState(document.documentElement.dataset.theme);
  useEffect(() => {
    const update = () => setTheme(document.documentElement.dataset.theme);
    window.addEventListener('halo-theme-changed', update);
    return () => window.removeEventListener('halo-theme-changed', update);
  }, []);
  return theme;
}

export function themePalette() {
  const style = getComputedStyle(document.documentElement);
  const color = (name: string) => style.getPropertyValue('--halo-' + name).trim();
  return {text: color('text'), muted: color('muted'), border: color('border'), background: color('bg'), panel: color('panel'), brand: color('brand'), series: Array.from({length: 7}, (_, index) => color('series-' + index))};
}
