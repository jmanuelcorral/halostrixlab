import React, {createContext, useCallback, useContext, useEffect, useRef, useState} from 'react';
import {Alert, AlertActionCloseButton, AlertGroup} from '@patternfly/react-core';
import './notifications.css';

type Variant = 'info' | 'success' | 'danger' | 'warning';
type Toast = {id: number; message: string; variant: Variant};
const Notifications = createContext<(message: string, variant: Variant) => void>(() => {});

export function NotificationProvider({children}: {children: React.ReactNode}) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const sequence = useRef(0);
  const notify = useCallback((message: string, variant: Variant) => {
    const id = ++sequence.current;
    setToasts(current => [...current.filter(item => item.message !== message || item.variant !== variant), {id, message, variant}].slice(-4));
  }, []);
  const dismiss = (id: number) => setToasts(current => current.filter(item => item.id !== id));
  return <Notifications.Provider value={notify}>{children}<AlertGroup isToast isLiveRegion aria-label="Avisos" className="halo-toasts">{toasts.map(toast => <Alert key={toast.id} variant={toast.variant} title={toast.message} component="p" role={toast.variant === 'danger' ? 'alert' : 'status'} timeout={toast.variant === 'danger' ? 12000 : 8000} onTimeout={() => dismiss(toast.id)} actionClose={<AlertActionCloseButton aria-label="Cerrar aviso" onClose={() => dismiss(toast.id)}/>}/>)}</AlertGroup></Notifications.Provider>;
}

export function useToastMessage(message: string, variant: Variant = 'info') {
  const notify = useContext(Notifications);
  useEffect(() => {if (message) notify(message, variant);}, [message, variant, notify]);
}
