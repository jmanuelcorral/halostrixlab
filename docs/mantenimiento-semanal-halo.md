# Mantenimiento semanal del Halo y rollback

[Índice principal](../README.md) | [Validación Halogen 0.20](validacion-halogen-0.20.md)

**Estado: programado. Falta instalar una regla de sudoers (sección 2) para que el domingo
se ejecute completo.** Las notificaciones van a un tema de ntfy privado, cuyo nombre
no está en el repositorio.

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

El aviso de apagado no se verificó en el reinicio de prueba: el servicio de apagado no dejó traza y no llegó a ntfy. Para un reinicio manual no hay garantía; el mantenimiento semanal sí avisa antes de reiniciar.
El aviso de encendido se reintenta durante cinco minutos mientras el gateway arranca.

Unidades (en `~/.config/systemd/user`): `halo-weekly-update.timer`,
`halo-weekly-update.service`, `halo-boot-notify.service`, `halo-shutdown-notify.service`.

Topic: fichero `workspaces/inference/data/ntfy-topic` (permisos 600, ignorado por git).
Para cambiarlo, edita ese fichero; no lo pongas en el repositorio.
Dirección del gateway para el aviso de arranque: `workspaces/inference/data/gateway-url` (mismo criterio; si falta, usa `127.0.0.1:18080`).

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

## 6. Pendientes

- Actualizar Halogen o cualquier imagen Docker: manual, con su digest, según la validación.
- Retención de snapshots de snapper: la configuración actual limita a 50 snapshots, y
  `snap-pac` crea uno por transacción. Revisar si hace falta ajustar `NUMBER_LIMIT`.
