export type StorageReport = {started: number; finished: number; filesystem: {path: string; total: number; used: number; free: number}; roots: {label: string; path: string; bytes: number | null; partial: boolean; reason: string; directories: {path: string; bytes: number; depth: number; category: string}[]}[]; docker: {available: boolean; rows: {Type: string; TotalCount: string | number; Active: string | number; Size: string; Reclaimable: string}[]}; method: string};
export type Job = { id: string; action: string; state: string; message: string; created: number };
export type State = { laya?: {available: boolean; state: string; health: boolean; error: string}; services: Record<string, string>; halogen: string; gateway_health: boolean; gateway_ui_url: string; comfyui_health: boolean; comfyui_url: string; unsloth: {available: boolean; state: string; health: boolean; url: string | null; error: string}; llamafactory: {available: boolean; state: string; health: boolean; url: string | null; error: string}; jobs: Job[]; errors: string[]; ssh_hosts: string[]; boot_id: string; maintenance_available: boolean; updates?: {updated: number; data: {ok: boolean; packages: {name: string; from: string; to: string}[]; error: string}}; images?: {updated: number; data: unknown}; storage?: {updated: number; data: StorageReport} };
export type Sample = { time: number; cpu: Record<string, number | null>; memory: {used: number; total: number; available: number; swap_used: number}; gpu: {device: string; busy: number | null; gtt_used: number; gtt_total: number; vram_used: number; watts: number | null}[]; temperatures: {sensor: string; celsius: number | null; critical: number | null}[]; disk: {free: number; total: number; used?: number}; io?: Record<string, {read: number | null; write: number | null; busy_ms: number | null}>; disk_temperatures?: {sensor: string; celsius: number | null}[]; load: number[]; network: Record<string, {rx: number | null; tx: number | null; errors?: number | null}>; pressure: Record<string, {some: {avg10: number}} | null> };
export type Channel = {send: (data: string | Uint8Array) => void; close: () => void; control: (options: unknown) => void; addEventListener: (name: string, callback: (event: unknown, data: any) => void) => void};
type Cockpit = { spawn: (args: string[], options?: Record<string, unknown>) => PromiseLike<string> & {input: (text: string) => void; close?: (problem?: string) => void}; channel: (options: Record<string, unknown>) => Channel; user: () => PromiseLike<{name: string; home: string; shell: string}>; jump: (path: string) => void; logout: () => void };
declare global { interface Window { cockpit?: Cockpit } }
let root = '';
export function available() { return Boolean(window.cockpit); }
export async function initialize() {
  if (!window.cockpit) throw new Error('Abre Halo Control dentro de Cockpit. La vista previa no puede administrar el equipo.');
  const response = await fetch('./runtime.json');
  if (!response.ok) throw new Error('Falta configuración de instalación: ejecuta install.py.');
  const settings = await response.json();
  if (typeof settings.workspace !== 'string' || !settings.workspace.startsWith('/')) throw new Error('Workspace inválido');
  root = settings.workspace;
}
export async function api<T>(command: string, argument?: string, payload?: unknown): Promise<T> {
  if (!window.cockpit || !root) throw new Error('Sesión no inicializada');
  const args = ['/usr/bin/python3', `${root}/control.py`, command];
  if (argument !== undefined) args.push(argument);
  const process = window.cockpit.spawn(args, {err: 'message'});
  if (payload !== undefined) process.input(JSON.stringify(payload));
  const text = await process;
  return JSON.parse(text) as T;
}
export function bytes(value: number | undefined | null) { return value == null ? 'Sin datos' : `${(value / 2 ** 30).toFixed(1)} GiB`; }
export function percent(value: number | undefined | null) { return value == null ? 'Sin datos' : `${value.toFixed(1)} %`; }
export function stamp(value: number) { return new Date(value * 1000).toLocaleString(); }
