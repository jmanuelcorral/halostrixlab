import {useState} from 'react';
import type {State} from './api';
import {engineStatus, type EngineId, type EngineStatus} from './engineStatus';
import {useCockpitTheme} from './theme';

const identities: Record<EngineId, {name: string; image: string; dark?: string; category: string; surface?: string}> = {
  laya: {name: 'Laya', image: 'laya-light.png', dark: 'laya-dark.png', category: 'DECISIONES · CPU MULTILINGÜE'},
  gateway: {name: 'llama-swap', image: 'llama-swap.png', category: 'GATEWAY DE MODELOS', surface: 'light'},
  halogen: {name: 'Halogen', image: 'halogen.jpg', category: 'INFERENCIA DE TEXTO'},
  comfyui: {name: 'ComfyUI', image: 'comfyui.svg', category: 'GENERACIÓN VISUAL'},
  unsloth: {name: 'Unsloth Studio', image: 'unsloth-studio-light.png', dark: 'unsloth-studio-dark.png', category: 'STUDIO Y ENTRENAMIENTO'},
  llamafactory: {name: 'LLaMA-Factory', image: 'llamafactory.png', category: 'LLAMABOARD · FINE-TUNING', surface: 'light'},
};

function StatusIcon({kind}: {kind: EngineStatus['icon']}) {
  const paths: Record<EngineStatus['icon'], string> = {
    check: 'm6 12 4 4 8-8',
    stop: 'M8 8h8v8H8z',
    pause: 'M9 8v8m6-8v8',
    clock: 'M12 6v6l4 2',
    error: 'M12 7v6m0 3v1',
    unknown: 'M9 9a3 3 0 0 1 6 0c0 2-3 2-3 4m0 3v1',
  };
  return <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d={paths[kind]}/></svg>;
}

export function EngineIdentity({engine, state}: {engine: EngineId; state?: State}) {
  const identity = identities[engine];
  const theme = useCockpitTheme();
  const source = './engine-art/' + (theme === 'dark' && identity.dark ? identity.dark : identity.image);
  const [failedSource, setFailedSource] = useState('');
  const status = engineStatus(engine, state);
  return <div className="engine-identity">
    <div className={`engine-art engine-art--${engine}${identity.surface ? ' engine-art--' + identity.surface : ''}`}>
      {failedSource === source ? <span className="engine-art-fallback">{identity.name}<small>Imagen no disponible</small></span> : <img key={source} src={source} alt={`Identidad visual de ${identity.name}`} decoding="async" onError={() => setFailedSource(source)}/>}
    </div>
    <div className="engine-meta"><span className="engine-category">{identity.category}</span><span className={`engine-status engine-status--${status.tone}`} title={status.detail} aria-label={`${identity.name}: ${status.label}. ${status.detail}`}><StatusIcon kind={status.icon}/>{status.label}</span></div>
    <h3>{identity.name}</h3>
  </div>;
}
