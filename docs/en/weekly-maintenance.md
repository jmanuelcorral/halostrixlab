# Weekly Halo maintenance and rollback

[Project overview](../../README.en.md) | [Halogen 0.20 validation](validation-halogen-0.20.md)

**Status: scheduled and verified on the Halo.** The sudoers rule is installed
(section 2), a test reboot completed with shutdown and power-on notices received,
and the weekly timer is active. Notifications go to a private ntfy topic whose
name is not in the repository.

## 1. What it does

Every Sunday at **20:00** (user timer `halo-weekly-update.timer`):

1. Waits up to 30 minutes for no inference requests to be in progress. If there
   is no gap, it **does not update or reboot** and sends a notice.
2. Creates a Btrfs snapshot with snapper (`weekly-maintenance`) as the rollback point.
3. Runs `pacman -Syu --noconfirm`, which updates **all system packages**.
   Each pacman transaction also creates its own snapshots (`snap-pac`).
4. Reboots the machine with `systemctl reboot`.

**Docker images are not updated.** Halogen, the NPU and the other engines stay
pinned by digest. Changing an image is a manual decision.

Before rebooting, stopping `llama-swap.service` also stops Halogen through its
runtime. On startup, llama-swap becomes available again and Halogen loads on the
first request.

## 2. Installing the sudoers rule (once, with your password)

The timer cannot ask for a password. It needs permission for **only** the three
exact commands, granted by a rule in `/etc/sudoers.d`. From your terminal, on the Halo:

```bash
! sudo sh -c 'printf "%s\n" "<USER> ALL=(root) NOPASSWD: /usr/bin/snapper -c root create -d weekly-maintenance, /usr/bin/pacman -Syu --noconfirm, /usr/bin/systemctl reboot" > /etc/sudoers.d/halo-maintenance && chmod 440 /etc/sudoers.d/halo-maintenance && visudo -cf /etc/sudoers.d/halo-maintenance'
```

Replace `<USER>` with your Halo user before running it.
`visudo -cf` must answer `parsed OK`. If it does not, remove that file with
`sudo rm` and repeat the step. Check that it works without a password prompt:

```bash
sudo -n /usr/bin/snapper -c root list | head -3
```

## 3. Notifications (ntfy)

| When | Title | Priority |
| --- | --- | --- |
| The weekly maintenance starts | Mantenimiento semanal (Weekly maintenance) | normal |
| Inference is in progress for 30 min | Mantenimiento omitido (Maintenance skipped) | high |
| The pre-update snapshot cannot be created | Mantenimiento cancelado (Maintenance cancelled) | urgent |
| pacman fails (no reboot) | Actualización fallida (Update failed) | urgent |
| Update completed, reboot in progress | Actualización completada (Update completed) | normal |
| The reboot fails | Reinicio fallido (Reboot failed) | urgent |
| Shutdown or reboot starts | Halo apagándose (Halo shutting down) | high (best effort) |
| Machine powered on, with llama-swap and collector status | Halo encendido (Halo powered on) | normal |
| Saturday at 12:00: packages pending for Sunday (or system up to date) | Actualizaciones pendientes / Sistema al día (Updates pending / System up to date) | normal |

The shutdown notice is a system unit (`halo-shutdown-notify.service`, section 3.1)
and was verified during a test reboot. A manual reboot also sends a notice.
The power-on notice retries for five minutes while the gateway starts.

The titles are kept in Spanish because they are the strings the service sends.

Units (in `~/.config/systemd/user`): `halo-weekly-update.timer`,
`halo-weekly-update.service`, `halo-boot-notify.service`, `halo-update-check.timer`
(Saturdays at 12:00) and `halo-update-check.service`. The shutdown notice is a
system unit (`halo-shutdown-notify.service`), installed with sudo (section 3.1).

Topic: file `workspaces/inference/data/ntfy-topic` (mode 600, git-ignored).
To change it, edit that file; do not put it in the repository.
Gateway address for the power-on notice: `workspaces/inference/data/gateway-url`
(same rule; if missing, it uses `127.0.0.1:18080`).

### 3.1. Shutdown notice (system unit)

Unit: `/etc/systemd/system/halo-shutdown-notify.service`. It runs at boot, does
nothing, and sends the notice when the system stops. It is ordered before
`shutdown.target` and after `network-online.target`, so the notice leaves before
the network goes down.

Installation (once, with sudo):

```bash
! sudo install -m 644 ~/halo-shutdown-notify.service /etc/systemd/system/halo-shutdown-notify.service && sudo systemctl daemon-reload && sudo systemctl enable halo-shutdown-notify.service && systemctl --user disable --now halo-shutdown-notify.service
```

The last step disables the user copy, which never got to send the notice.
The unit template is in this repository, in section 3.2 below, with replaceable paths.

### 3.2. Shutdown unit template

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

Replace `__USER__` with the Halo user and `__REPO__` with the clone path before
copying it to `/etc/systemd/system/`.

### 3.3. Pending-updates notice

User timer `halo-update-check.timer`: on Saturdays at 12:00 it checks pending
packages with `checkupdates`, without applying anything, and reports the count and
the first names, or that the system is up to date.

## 4. Operation

```bash
systemctl --user list-timers halo-weekly-update.timer     # next run
systemctl --user start halo-weekly-update.service        # run the maintenance now
systemctl --user stop halo-weekly-update.timer           # disable temporarily
systemctl --user start halo-weekly-update.timer          # re-enable
python3 <REPO>/workspaces/halo-control/weekly_maintenance.py test   # ntfy test
```
