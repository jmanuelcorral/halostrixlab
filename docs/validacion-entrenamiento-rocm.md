# Validación entrenamiento ROCm — 2026-08-25

> **English:** [operational guide](en/setup-guide.md#rocm-container-smoke) (equivalente operativo, no traduccion literal de logs).
> **Edicion publica:** topologia e identificadores anonimizados; registros privados excluidos.
> Los bloques `text` con placeholders son ilustrativos, no comandos para pegar. El baseline
> es historico (hasta 2026-09-04), con un 403 posterior sin causa ni cierre confirmados.

## Docker Engine

**Gate: PASS básico.** Tras preflight limpio se instaló únicamente `docker` y
se habilitó/inició `docker.service` con `sudo`; no se añadió el usuario al
grupo Docker ni se relajaron permisos del socket. `sudo docker version`
confirmó cliente y servidor Docker Engine 29.7.2. No se descargaron ni
ejecutaron imágenes, incluidos contenedores GPU.

El baseline pre de paquetes quedó bajo el fallback existente. Rollback
documentado, no ejecutado: `sudo systemctl disable --now docker.service`,
revisar dependencias/huérfanos y considerar `sudo pacman -Rns docker`;
preservar `/var/lib/docker` salvo autorización explícita para eliminar datos.

## Smoke de entrenamiento ROCm en contenedor — 2026-08-25

**Gate: PASS.** La validación se ejecutó con el runtime ROCm aislado en
contenedor, sin cambios a ROCm del host, sin `--privileged`, sin
`--ipc=host`, sin override de seccomp y sin mounts ROCm adicionales.

### PRE y artefacto retenido

- Ambos puntos de montaje (`/` y `/var/lib/docker`) residen en
  `/dev/nvme0n1p2`: **1,9 T**, **16 G usados (1 %)** antes del pull y
  **54 G (3 %)** antes del smoke.
- Docker Engine **29.7.2**, CachyOS, kernel **7.2.0-1-cachyos**, 32 CPU,
  123,5 GiB de RAM; el preflight y el postflight reportaron **0**
  contenedores. El usuario no pertenece al grupo `docker`.
- Se hizo pull exclusivamente de
  `rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad`.
  `RepoDigests` coincide exactamente, `Architecture=amd64`,
  `ImageID=sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad`
  y `SizeBytes=19373531366` (≈18,04 GiB). La imagen queda retenida.
- Estaban disponibles `/dev/kfd` (carácter, modo `666`, grupo `render`) y
  `/dev/dri`. La GTT era 18.681.856 / 66.281.017.344 bytes antes y después.

### Comando reproducible

El siguiente bloque usa una sola ejecución efímera y el digest inmutable:

```bash
cat <<'SMOKE' | sudo docker run --rm \
  --device=/dev/kfd --device=/dev/dri --shm-size=8g \
  rocm/pytorch@sha256:c38eeda81d85f00fbe35d3d50ce42ce59c524e87d810624f4eb5c52fddb3b9ad bash
set -euo pipefail
rocminfo | grep -m1 gfx1151
python3 - <<'PY'
import torch
assert torch.version.hip and torch.cuda.is_available() and torch.cuda.device_count() >= 1
print(torch.__version__, torch.version.hip, torch.cuda.get_device_name(0))
for dtype in (torch.float16, torch.bfloat16):
    a = torch.randn((2048, 2048), device="cuda", dtype=dtype, requires_grad=True)
    b = torch.randn((2048, 2048), device="cuda", dtype=dtype, requires_grad=True)
    loss = (a @ b).float().square().mean()
    loss.backward()
    torch.cuda.synchronize()
    assert torch.isfinite(loss) and torch.isfinite(a.grad).all() and torch.isfinite(b.grad).all()
    print(dtype, loss.item(), torch.cuda.memory_allocated(), torch.cuda.memory_reserved())
PY
SMOKE
```

### Resultado GPU

- `rocminfo` detectó **gfx1151**.
- PyTorch informó `2.12.0+rocm7.14.0`, HIP `7.14.60850`, disponibilidad
  `True`, un dispositivo y `AMD Radeon 8060S Graphics`. Es coherente con el
  contexto esperado ROCm 7.14 / Ubuntu 24.04 / Python 3.12 del artefacto.
- FP16: pérdida `2047.4448`; salida y gradientes de ambas matrices finitos.
  BF16: pérdida `2047.9354`; salida y gradientes finitos. Cada operación
  realizó multiplicación 2048×2048, `backward()` y sincronización.
- Tras cada dtype: `allocated=201327104` y `reserved=287309824` bytes.
  No quedaron contenedores al finalizar.

### POST, temperatura y Lemonade

- El sensor `<GPU_SENSOR>` marcó borde **32,0 °C** después del smoke
  (32,0 °C antes), con 6,68 W y SCLK 600 MHz. El journal de kernel desde
  `2026-08-25T18:00:38.604509563+02:00`, filtrado por
  `amdgpu|kfd|OOM|reset|thermal`, no devolvió eventos.
- `lemond.service` se detuvo temporalmente sin deshabilitarse; su `MainPID`
  terminó y el estado fue `inactive/dead` antes del contenedor. Se inició en
  el bloque `finally`.
- La comprobación final controlada de restauración confirmó `active/running`,
  bind exclusivo en `127.0.0.1:13305` y respuesta de `/v1/models` a los
  **5 s** (dentro de 60 s). El catálogo ya publicado fue consultado, sin
  cargar ningún modelo. El puerto correcto es 13305; las primeras sondas a
  8001 no eran el endpoint de Lemonade y se conservaron como evidencia
  diagnóstica redactada.

Los resultados necesarios se resumen en este documento; los registros privados no se publican ni son una dependencia de lectura.

### Pausa explícita posterior al gate

Por directiva de operador, este alcance termina tras el pull/smoke PyTorch ROCm y
la restauración/verificación de Lemonade. **No se iniciaron, instalaron ni
evaluaron Unsloth, QLoRA, datasets ni pasos posteriores de entrenamiento.**
Todo trabajo posterior queda fuera de esta validación y requiere una
instrucción independiente.
