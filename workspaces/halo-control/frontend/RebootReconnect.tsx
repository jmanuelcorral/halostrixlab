import {useEffect, useState} from 'react';
import {createPortal} from 'react-dom';
import {probeBoot, probeWeb, receiptKey, reconnectLimit, reconnectTarget, retryDelay, type RebootReceipt} from './rebootReconnect';

export function RebootReconnect({receipt, onFinish}: {receipt: RebootReceipt; onFinish: (message: string) => void}) {
  const [seconds, setSeconds] = useState(5);
  const [attempts, setAttempts] = useState(0);
  const [message, setMessage] = useState('Esperando el nuevo arranque; todavía no se confirma el reinicio.');
  const [expired, setExpired] = useState(false);
  useEffect(() => {
    let stopped = false;
    let probing = false;
    let next = Date.now() + retryDelay;
    let controller: AbortController | undefined;
    let confirmed = false;
    let webWasDown = false;
    const finish = (text: string) => {stopped = true; sessionStorage.removeItem(receiptKey); onFinish(text);};
    const reload = () => {
      if (receipt.reloaded) {
        finish('Cockpit vuelve a responder, pero la sesión sigue desconectada. Vuelve a iniciar sesión para comprobar el arranque; no se repetirá el reinicio.');
        return;
      }
      sessionStorage.setItem(receiptKey, JSON.stringify({...receipt, reloaded: true}));
      stopped = true;
      reconnectTarget().location.reload();
    };
    const check = async () => {
      probing = true;
      setAttempts(value => value + 1);
      setMessage('Intentando reconectar con el equipo…');
      try {
        const boot = await probeBoot();
        if (stopped) return;
        if (boot !== receipt.boot_id) {
          if (receipt.reloaded) {finish('Reinicio confirmado: el identificador de arranque del equipo ha cambiado.'); return;}
          confirmed = true;
          setMessage('Reinicio confirmado. Actualizando la página…');
          next = Date.now() + 2000;
        } else {
          setMessage('El equipo sigue en el arranque anterior. Esperando; no se repetirá la orden.');
          next = Date.now() + retryDelay;
        }
      } catch {
        if (stopped) return;
        controller = new AbortController();
        const timeout = setTimeout(() => controller?.abort(), 4000);
        try {
          const available = await probeWeb(controller.signal);
          if (stopped) return;
          if (available && (receipt.reloaded || webWasDown || Date.now() - receipt.requested >= 30000)) {reload(); return;}
          if (!available) webWasDown = true;
        } catch {webWasDown = true;}
        finally {clearTimeout(timeout);}
        if (!stopped) {
          setMessage('El equipo aún no responde. Se reintentará automáticamente.');
          next = Date.now() + retryDelay;
        }
      } finally {probing = false;}
    };
    const tick = () => {
      if (stopped) return;
      if (Date.now() - receipt.requested >= reconnectLimit) {
        stopped = true; controller?.abort(); setExpired(true); setSeconds(0);
        setMessage('No se pudo confirmar el reinicio en 10 minutos. Comprueba red, Cockpit o sus permisos. No se enviará otra orden de reinicio.');
        return;
      }
      setSeconds(Math.max(0, Math.ceil((next - Date.now()) / 1000)));
      if (Date.now() >= next && !probing) {
        if (confirmed) {reload(); return;}
        void check();
      }
    };
    tick();
    const timer = setInterval(tick, 250);
    return () => {stopped = true; clearInterval(timer); controller?.abort();};
  }, [receipt, onFinish]);
  const target = reconnectTarget();
  return createPortal(<div role="dialog" aria-modal="true" aria-labelledby="halo-reconnect-title" onKeyDown={event => {if (event.key === 'Tab') {event.preventDefault(); event.currentTarget.querySelector('button')?.focus();}}} style={{position: 'fixed', inset: 0, zIndex: 10000, display: 'grid', placeItems: 'center', padding: 24, background: 'var(--pf-t--global--background--color--secondary--default)', color: 'var(--pf-t--global--text--color--regular)'}}>
    <div style={{maxWidth: 560, width: '100%', padding: 28, border: '1px solid var(--pf-t--global--border--color--default)', borderRadius: 8, background: 'var(--pf-t--global--background--color--primary--default)'}}>
      <h2 id="halo-reconnect-title">{expired ? 'Reconexión pendiente' : 'Reiniciando el equipo'}</h2>
      <p role="status" aria-live="polite">{message}</p>
      {!expired && <p role="timer" aria-live="off" style={{fontSize: 28, fontWeight: 600}}>Próximo intento en {seconds} s</p>}
      <p>Intentos de conexión: {attempts}. Cockpit puede solicitar iniciar sesión de nuevo.</p>
      <button autoFocus type="button" onClick={() => {sessionStorage.removeItem(receiptKey); onFinish('Seguimiento cerrado. No cancela el reinicio solicitado ni arranca servicios.');}} style={{padding: '8px 16px', color: 'inherit', background: 'var(--pf-t--global--background--color--secondary--default)', border: '1px solid var(--pf-t--global--border--color--default)', borderRadius: 6}}>Cerrar seguimiento</button>
    </div>
  </div>, target.document.body);
}
