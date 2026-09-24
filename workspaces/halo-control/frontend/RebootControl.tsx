import React, {useCallback, useEffect, useRef, useState} from 'react';
import {Button} from '@patternfly/react-core';
import {api, State} from './api';
import {checkMaintenanceSession, rebootError} from './rebootPreflight';

type RebootState = State & {reboot?: {phase: string; token?: string; boot_id: string; expires: number}};
import {connectionLost, readReceipt, receiptKey, type RebootReceipt} from './rebootReconnect';
import {RebootReconnect} from './RebootReconnect';

export function RebootControl({disabled, state, onBusy, onMaintenance}: {disabled: boolean; state?: State; onBusy: (busy: boolean) => void; onMaintenance: () => void}) {
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [pending, setPending] = useState(false);
  const inFlight = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {mounted.current = true; return () => {mounted.current = false;};}, []);
  const [receipt, setReceipt] = useState<RebootReceipt | null>(() => readReceipt(sessionStorage));
  useEffect(() => {
    if (receipt) {setPending(true); inFlight.current = true; onBusy(true);}
  }, [receipt, onBusy]);
  const finishReconnect = useCallback((text: string) => {
    setReceipt(null); setMessage(text); setPending(false); inFlight.current = false; onBusy(false);
  }, [onBusy]);
  const restart = async () => {
    if (disabled || inFlight.current) return;
    if (!window.confirm('¿Detener los servicios IA y reiniciar este equipo? Se interrumpirán solicitudes, generaciones y entrenamientos activos. Se conservarán contenedores y datos. No se interrumpirá una actualización de paquetes.')) return;
    inFlight.current = true; setPending(true); onBusy(true); setError('');
    let token: string | undefined;
    let submitted = false;
    let rebootReceipt: RebootReceipt | undefined;
    try {
      setMessage('1/4 · Comprobando acceso administrativo antes de detener servicios…');
      const identity = await window.cockpit!.spawn(['/usr/bin/id', '-u'], {superuser: 'require', err: 'message'});
      if (identity.trim() !== '0') throw new Error('No se obtuvo acceso administrativo. No se han detenido servicios.');
      if (await checkMaintenanceSession()) throw new Error('Close the update session before rebooting');
      const report = JSON.parse(await window.cockpit!.spawn(['/usr/local/libexec/halo-maintenance', 'report'], {superuser: 'require', err: 'message'}));
      if (report.state === 'running') throw new Error('El informe indica una actualización en curso. Revisa la consola; no se detendrá ni reiniciará el equipo.');
      setMessage('2/4 · Deteniendo y verificando llama-swap, Halogen, ComfyUI, Studio y LlamaBoard…');
      const job = await api<{job: string}>('submit', 'prepare-reboot');
      const deadline = Date.now() + 900000;
      let prepared: RebootState | undefined;
      while (Date.now() < deadline) {
        const current = await api<RebootState>('status');
        const operation = current.jobs.find(item => item.id === job.job);
        if (operation?.state === 'failed' || operation?.state === 'unknown') throw new Error(operation.message || 'No se confirmó la parada de servicios.');
        if (operation?.state === 'success') {prepared = current; break;}
        if (current.reboot?.phase) setMessage('2/4 · ' + current.reboot.phase);
        if (!mounted.current) throw new Error('Visor cerrado; no se solicitará el reinicio. Los servicios pueden haberse detenido.');
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      token = prepared?.reboot?.token;
      if (!token) throw new Error('No se confirmó la preparación del reinicio. No se ha solicitado reiniciar.');
      if (!mounted.current) throw new Error('Visor cerrado; reinicio no solicitado.');
      setMessage('3/4 · Verificando parada final y solicitando reinicio al sistema…');
      const verification = await api<{ready: boolean; boot_id: string}>('reboot-verify', token);
      if (!verification.ready) throw new Error('Verificación final rechazada.');
      rebootReceipt = {boot_id: verification.boot_id, requested: Date.now()};
      sessionStorage.setItem(receiptKey, JSON.stringify(rebootReceipt));
      setReceipt(rebootReceipt);
      await window.cockpit!.spawn(['/usr/local/libexec/halo-maintenance', 'reboot'], {superuser: 'require', err: 'message'});
      submitted = true;
      setReceipt(rebootReceipt);
      setMessage('4/4 · El sistema aceptó la orden. Esperando desconexión y un nuevo arranque; todavía no se confirma que haya reiniciado.');
    } catch (reason) {
      if (rebootReceipt && connectionLost(reason)) {
        submitted = true; setReceipt(rebootReceipt);
        setMessage('Conexión interrumpida al solicitar el reinicio; comprobando el nuevo arranque.');
        return;
      }
      sessionStorage.removeItem(receiptKey);
      setReceipt(null);
      setError(rebootError(reason));
      setMessage('Reinicio no confirmado. Si la conexión se cortó al solicitarlo, vuelve a conectar para comprobar el arranque. Los servicios detenidos no se arrancan automáticamente.');
      if (token) {
        try {await api('reboot-release', token);} catch {setMessage('Conexión perdida o bloqueo pendiente; comprueba el arranque al reconectar.');}
      }
    } finally {
      if (!submitted) {inFlight.current = false; if (mounted.current) {setPending(false); onBusy(false);}}
    }
  };
  return <div className="reboot-control">{receipt && <RebootReconnect receipt={receipt} onFinish={finishReconnect}/>}<Button variant="danger" isDisabled={disabled || pending} onClick={() => void restart()}>Reiniciar equipo</Button>{message && <p role="status" aria-live="polite">{message}</p>}{error && <><p className="warning" role="alert">{error}</p><Button variant="secondary" onClick={onMaintenance}>Ver sesión de actualización existente</Button></>}</div>;
}
