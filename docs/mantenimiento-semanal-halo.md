# Mantenimiento semanal del Halo y rollback

[Índice principal](../README.md) | [Validación Halogen 0.20](validacion-halogen-0.20.md)

**Estado: programado y verificado en el Halo.** Regla de sudoers instalada (sección 2),
reinicio de prueba completado con avisos de apagado y encendido recibidos, y timer
semanal activo. Las notificaciones van a un tema de ntfy privado, cuyo nombre no está
en el repositorio.

## 1. Qué hace

Cada domingo a las **20:00** (timer de usuario `halo-weekly-update.timer`):

1. Espera hasta 30 minutos a que no haya peticiones de inferencia en curso. Si no
   hay hueco, **no actualiza ni reinicia** y avisa.
2. Crea un snapshot de Btrfs con snapper (`weekly-maintenance`) como punto de rollback.
3. Ejecuta `pacman -Syu --noconfirm`: actualiza **todos los paquetes del sistema**.
   Cada transacción de pacman crea además sus propios snapshots (`snap-pac`).
4. Reinicia el equipo con `systemctl reboot`.

**No se actualizan las imágenes de Docker.** Halogen, el NPU y los demás motores siguen
fijados por digest. Cambiar una imagen es una decisión manual.

Antes de reiniciar, al parar `llama-swap.service` se para también Halogen a través de su
runtime. Al arrancar, llama-swap vuelve a estar disponible y Halogen se carga con la
primera petición.

## 2. Instalación de la regla de sudoers (una vez, con tu contraseña)

El timer no puede pedir contraseña. Hay que dar permiso **solo** a los tres comandos
exactos, con una regla en `/etc/sudoers.d`. Desde tu terminal, en el Halo:

```bash
! sudo sh -c 'printf "%s\n" "jose ALL=(root) NOPASSWD: /usr/bin/snapper -c root create -d weekly-maintenance, /usr/bin/pacman -Syu --noconfirm, /usr/bin/systemctl reboot" > /etc/sudoers.d/halo-maintenance && chmod 440 /etc/sudoers.d/halo-maintenance && visudo -cf /etc/sudoers.d/halo-maintenance'
```

`visudo -cf` debe responder `parsed OK`. Si no, borra ese fichero con `sudo rm` y repítelo.
Comprueba que funciona sin pedir contraseña:

```bash
sudo -n /usr/bin/snapper -c root list | head -3
```

## 3. Notificaciones (ntfy)

| Cuándo | Título | Prioridad |
| --- | --- | --- |
| Empieza el mantenimiento semanal | Mantenimiento semanal | normal |
| Hay inferencia en curso durante 30 min | Mantenimiento omitido | alta |
| No se puede crear el snapshot previo | Mantenimiento cancelado | urgente |
| pacman falla (no se reinicia) | Actualización fallida | urgente |
| Actualización completada, reinicio en curso | Actualización completada | normal |
| El reinicio falla | Reinicio fallido | urgente |
| Apagado o reinicio iniciado | Halo apagándose | alta (mejor esfuerzo) |
| Equipo encendido, con estado de llama-swap y del colector | Halo encendido | normal |
| Sábado a las 12:00: paquetes pendientes para el domingo (o sistema al día) | Actualizaciones pendientes / Sistema al día | normal |

El aviso de apagado es una unidad de sistema (`halo-shutdown-notify.service`, sección 3.1) y se verificó en un reinicio de prueba. Un reinicio manual también avisa.
El aviso de encendido se reintenta durante cinco minutos mientras el gateway arranca.

Unidades (en `~/.config/systemd/user`): `halo-weekly-update.timer`,
`halo-weekly-update.service`, `halo-boot-notify.service`, `halo-update-check.timer` (sábados 12:00) y `halo-update-check.service`. El aviso de apagado es una unidad de sistema (`halo-shutdown-notify.service`), instalada con sudo (sección 3.1).

Topic: fichero `workspaces/inference/data/ntfy-topic` (permisos 600, ignorado por git).
Para cambiarlo, edita ese fichero; no lo pongas en el repositorio.
Dirección del gateway para el aviso de arranque: `workspaces/inference/data/gateway-url` (mismo criterio; si falta, usa `127.0.0.1:18080`).

### 3.1. Aviso de apagado (unidad de sistema)

Unidad: `/etc/systemd/system/halo-shutdown-notify.service`. Se ejecuta al arrancar, no hace
nada, y al parar el sistema envía el aviso. Va ordenada antes de `shutdown.target` y
después de `network-online.target`, así que el aviso sale antes de que se corte la red.

Instalación (una vez, con sudo):

```bash
! sudo install -m 644 ~/halo-shutdown-notify.service /etc/systemd/system/halo-shutdown-notify.service && sudo systemctl daemon-reload && sudo systemctl enable halo-shutdown-notify.service && systemctl --user disable --now halo-shutdown-notify.service
```

El último paso desactiva la copia de usuario, que no llegaba a enviar aviso.
La plantilla de la unidad está en el repositorio, en `docs/mantenimiento-semanal-halo.md`
(ver sección 3.2), con rutas sustituibles.

### 3.2. Plantilla de la unidad de apagado

```ini
[Unit]
Description=Halo shutdown notification (system unit)
DefaultDependencies=no
Wants=network-online.target
After=network-online.target
Before=shutdown.target reboot.target halt.target

[Service]
Type=oneshot
User=__USER__
RemainAfterExit=yes
ExecStart=/bin/true
ExecStop=/usr/bin/python3 __REPO__/workspaces/halo-control/weekly_maintenance.py shutdown
TimeoutStopSec=30

[Install]
WantedBy=multi-user.target
```

Sustituye `__USER__` por el usuario del Halo y `__REPO__` por la ruta del clon, antes de
copiarla a `/etc/systemd/system/`.

### 3.3. Aviso de actualizaciones pendientes

Timer de usuario `halo-update-check.timer`: los sábados a las 12:00 consulta los paquetes
pendientes con `checkupdates`, sin aplicar nada, y avisa del número y de los primeros
nombres, o de que el sistema está al día.

## 4. Operación

```bash
systemctl --user list-timers halo-weekly-update.timer     # próxima ejecución
systemctl --user start halo-weekly-update.service        # lanzar el mantenimiento ya
systemctl --user stop halo-weekly-update.timer           # desactivar temporalmente
systemctl --user start halo-weekly-update.timer          # reactivar
python3 ~/gitrepos/halostrixlab/workspaces/halo-control/weekly_maintenance.py test   # prueba de ntfy
```

Lanzar `halo-weekly-update.service` a mano hace lo mismo que el domingo, incluido el reinicio.

## 5. Rollback

Hay dos formas. Las dos necesitan un reinicio.

### 5.1. Desde el menú de arranque (preferido)

Si el sistema arranca pero algo no funciona, reinicia y elige un snapshot anterior en el
menú del gestor de arranque, si está configurado para mostrar snapshots de snapper
(`limine-snapper-sync` u otro equivalente). El snapshot `pre` de la actualización
es el que hay que elegir.

### 5.2. Restaurar un snapshot desde el sistema

```bash
sudo snapper -c root list | tail -20                      # localiza el snapshot 'pre' de pacman
#                                                         # o el 'weekly-maintenance' de la semana
sudo snapper -c root rollback <NUMERO>                    # deja el snapshot como subvolumen por defecto
sudo systemctl reboot
```

`rollback` no borra datos del directorio de usuario ni de los volúmenes de modelos: solo
revierte el sistema de `/`. Confirma en el arranque que el sistema vuelve al estado
esperado. Tras el rollback, la siguiente actualización semanal volverá a aplicar las
versiones nuevas: para evitarlo, detén el timer hasta resolver la causa.

### 5.3. Revertir un solo paquete

Si el fallo es de un paquete concreto, pacman conserva las versiones descargadas:

```bash
ls /var/cache/pacman/pkg | grep <paquete>                 # versiones disponibles en caché
sudo pacman -U /var/cache/pacman/pkg/<paquete-version>.pkg.tar.zst
```

Después bloquea ese paquete en `/etc/pacman.conf` (`IgnorePkg = <paquete>`) para que la
siguiente actualización no lo vuelva a subir.

### 5.4. Comprobar el estado tras un rollback

- `systemctl --user is-active llama-swap.service halo-metrics.service`
- `curl -s http://127.0.0.1:18080/v1/models`
- Panel `halo-control`: estado de servicios y gráficas.

## 6. Verificación en el Halo

- Reinicio de prueba con la regla de sudoers: el equipo vuelve en menos de dos minutos,
  el colector de métricas (`halo-metrics`) está activo desde el arranque, y el gateway
  (`llama-swap`) responde.
- Avisos recibidos en ntfy durante ese reinicio: «Halo apagándose», «Halo encendido»
  (aviso de arranque) y «Sistema al día» (aviso de actualizaciones).
- Corregido durante la prueba: el aviso de arranque usaba la dirección de loopback, pero
  llama-swap escucha en la IP de la LAN. La dirección se lee ahora de
  `workspaces/inference/data/gateway-url`.

## 7. Pendientes

- Actualizar Halogen o cualquier imagen Docker: manual, con su digest, según la validación.
- Retención de snapshots de snapper: la configuración actual limita a 50 snapshots, y
  `snap-pac` crea uno por transacción. Revisar si hace falta ajustar `NUMBER_LIMIT`.
