# Winnow-12B con Ollaya CPU y el llama-swap existente

[English](OLLAYA.en.md) | [Workspace](README.md) |
[Investigación previa](../../docs/investigacion-winnow-ollaya.md)

## Despliegue del 28 de septiembre de 2026

Se desplegó **Ollaya 0.7.5 CPU con Winnow-12B Q8_0**, no E4B. El único llama-swap
existente administra el contenedor; no se instaló otro gateway ni daemon de
Ollaya en el host. La prueba terminó con **Halogen, Laya y Winnow residentes**.
Esto es evidencia fechada, no garantía de salud permanente.

La imagen derivada combina Ollaya y Python estándar para un adaptador HTTP
restringido. No modifica pesos ni bibliotecas llama.cpp, no usa GPU ni instala
paquetes Python adicionales para el adaptador. Sus bases están fijadas por digest
en `ollaya.Dockerfile`; el build envía solo ese archivo y `ollaya_server.py`.

- Modelo: `EldanRing/Winnow-12B`, revisión
  `b6ac22b0d51b69b18200acacb3fbdd98073fffe8`.
- Q8: 12.669.646.592 bytes, SHA-256
  `b710efc4c0d048ee61eed92c5fef5ce323a4d17e7c51f9f0533cc72ae50818ea`.
- Ollaya: `32acb6d2ea13f616b1e11d9dfb8260b305106847`, release 0.7.5.
- Manifiesto de modelo fijado: SHA-256
  `8d72fee0e5f92a625cdb85ae4f6abdc024c9e6f124a0ca67e64522c3f24c47ce`.
- Imagen local probada:
  `sha256:a0de95d83b48204809102cb6ee581a79f0d0dfccf98f20a1695b262ebfa25383`.
  Docker informa 299.258.921 bytes; no incluye pesos. El ID de reconstrucción
  puede diferir. `deployment.json` conserva la imagen inmutable y hash del adaptador.
- Pesos, metadatos, licencias, caché y evidencia permanecen en `data/winnow/`
  ignorado. El archivo de staging y el blob final son hard links, no dos copias
  físicas del GGUF. No publicar ese directorio.

## Contrato y límites

| Propiedad | Valor |
| --- | --- |
| Alias llama-swap | `winnow-12b-cpu` |
| Modelo backend | `winnow:12b` |
| Decisiones | `POST /upstream/winnow-12b-cpu/v1/systemone` |
| Readiness | `GET /upstream/winnow-12b-cpu/ready` |
| Backend host | `127.0.0.1:18182`, solo adaptador |
| Ollaya | `127.0.0.1:11435` dentro del contenedor, no publicado |
| CPU / memoria | Cuota 8 CPU, límite RAM 32 GiB, sin swap adicional |
| Contexto | 8192 tokens totales, estado hasta 6144; no todos disponibles para texto de estado |
| Peticiones | Una activa; exceso simultáneo puede devolver 429, sin cola garantizada |
| Cuerpo / preguntas | 64 KiB, 1-8 preguntas, hasta 64 alternativas |
| Tipos | `noul`, `choice`, `score`; no chat ni imágenes |
| Salida | Decisiones con `output_tokens=0`, no generación de respuesta |
| Grupo | CPU no exclusivo y persistente, separado de Laya |
| Concurrencia global tras integración | 8, preservando límites anteriores |

Se admite `model` ausente, `winnow:12b` o el alias, pero el adaptador siempre envía
`winnow:12b` al backend. Otros modelos, campos administrativos, extensiones de
visión y rutas como `/api/pull` no se exponen. Confidence tiene semántica Ollaya;
no interpretar probabilidades como calibración universal.

Readiness solo pasa después de una decisión sintética y de comprobar un único
runner CPU. No se confunde la respuesta del daemon con inferencia lista. Un error
o timeout de backend deja el adaptador no disponible y termina el contenedor:
se requiere recarga, no fallback a otro modelo/dispositivo.

Las desconexiones no garantizan cancelar inmediatamente una evaluación CPU ya
iniciada. El adaptador conserva su lock hasta que termina o falla la llamada
acotada a 300 segundos, evitando admitir otra decisión concurrente. Drenar antes
de descargar. Al detener llama-swap se descargan también sus otros modelos.

## Aislamiento

Contenedor no root, pesos y raíz de solo lectura, capabilities eliminadas,
`no-new-privileges`, sin Docker socket, sin KFD/render y sin IPC host. Tmpfs
acotados, 256 procesos, logs Docker rotados y sin registrar prompts/respuestas.
El backend nativo no queda publicado ni accesible por passthrough.

La red Docker propia desactiva masquerading saliente; la prueba HTTPS externa
falló por timeout. **No equivale a una política universal de firewall:** cambios
de rutas del host pueden cambiar conectividad. Una red `--internal` impidió
publicar el puerto en este Docker; se descartó esa variante tras comprobarlo.
La prevención de pulls se apoya además en rutas denegadas, modelo fijo y almacén RO.

La API mantiene la política existente del gateway; no se cambió autenticación
ni dirección LAN. La plantilla Caddy pública continúa restringida a texto y
no publica este endpoint. Para consumirlo, usar el origen existente autorizado
o un túnel aprobado; no abrir `/upstream/*` al exterior.

## Operación

Desde la raíz del repositorio:

```bash
python3 workspaces/inference/ollaya_runtime.py status
python3 workspaces/inference/ollaya_runtime.py load
python3 workspaces/inference/ollaya_runtime.py unload
```

`unload` conserva alias y pesos; una petición posterior puede volver a cargar.
`load`/`unload` adquieren el lock operativo y rechazan gateway ocupado. El control
se ofrece mediante CLI y la UI original de llama-swap; **no se añadió ficha de
Winnow ni editor a Halo Control**. Su catálogo anterior sigue disponible.

Ejemplo de cuerpo, enviado al endpoint de decisiones del gateway autorizado:

```json
{
  "model": "winnow:12b",
  "state": {"pagado": true, "prioridad": "alta"},
  "questions": {
    "pagado": {"type": "noul", "instructions": "¿Está pagado?"},
    "ruta": {
      "type": "choice",
      "instructions": "¿Cuál es la prioridad?",
      "criteria": {"baja": null, "alta": null}
    },
    "urgencia": {
      "type": "score",
      "instructions": "Valora la urgencia de la prioridad registrada.",
      "criteria": ["baja", "media", "alta"]
    }
  }
}
```

### Preparación reproducible, no repetir el corte innecesariamente

```bash
workspaces/inference/data/cockpit-venv/bin/python workspaces/inference/ollaya_runtime.py download
python3 workspaces/inference/ollaya_runtime.py build
python3 workspaces/inference/ollaya_runtime.py configure
python3 workspaces/inference/ollaya_runtime.py verify
```

Download requiere el venv existente con huggingface_hub. Se verifican hashes
completos de todos los blobs y manifiesto; configure no sustituye una imagen
privada distinta. Arranque comprueba identidad y tamaños, no recalcula 12,67 GB
en cada petición. No editar pesos ni manifiestos bajo un servicio activo.

Para añadir al gateway durante mantenimiento autorizado:

```bash
python3 workspaces/inference/ollaya_runtime.py install --restart
```

El instalador verifica el launcher/configuración activos, valida el candidato,
rechaza peticiones inflight, para el gateway, adquiere lease de ajustes, crea
backup y reemplaza atómicamente. Reinicia y restaura los modelos anteriormente
residentes. **Es un corte temporal**, no hot reload ni reserva de admisión frente
a clientes directos nuevos: coordinar pausa de clientes durante mantenimiento.
Sin `--restart` exige gateway parado. Una instalación ya idéntica no reinicia.
El corte real restauró Halogen y Laya antes de cargar Winnow.

Ante fallo, inspeccionar evidencia privada y estado antes de reintentar. Para
retirar la integración: drenar y parar el gateway en mantenimiento, restaurar
el backup validado bajo el lease y arrancar el gateway anterior. No borrar pesos,
staging ni configuraciones antiguas como parte del rollback.

## Pruebas realizadas y pendientes

- 82 pruebas Python de inferencia, incluidas 8 específicas del adaptador/runtime;
  108 pruebas Python de Halo Control. Fixtures no prueban GPU ni login Cockpit.
- Carga real CPU confirmada por `/api/ps`: Winnow-12B Q8_0, contexto 8192,
  `device=cpu`, `size_vram=0`.
- Tres preguntas españolas: pago verdadero, prioridad alta, score próximo a 2.
  Primera prueba directa 7,602 s; tres ejecuciones calientes vía gateway:
  **5,283 / 5,262 / 5,271 s**. Son muestras cortas, no p95 ni benchmark de calidad.
- Una pregunta simultánea a Laya: Winnow **1,683 s**, Laya **0,061 s**.
  Misma tarea sintética, no evaluación representativa de ambos modelos.
- Rutas administrativas 404, modelo ajeno 400, cuerpo excesivo 413; dos solicitudes
  simultáneas dieron 200 y 429. Recuperación después de desconexión comprobada.
- Descarga/recarga selectiva dejó Halogen y Laya residentes; sin segundo gateway.
- Pico cgroup observado en una tanda corta: unos 2,85 GiB. **No es memoria total
  del modelo:** páginas mmap/page cache compartidas pueden contabilizarse fuera
  de este cgroup. No usarlo para dimensionar una instalación sin caché.
- Pendientes: calidad española retenida, contexto límite, p50/p95 representativos,
  carga prolongada, reboot y GPU AMD. No se afirma mejora de calidad sobre Laya.

Evidencia privada: `direct-smoke.json`, `gateway-smoke.json`, `lifecycle-smoke.json`.

```bash
python3 -m unittest discover -s scripts/tests -p test_inference_ollaya.py -v
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -q
python3 -m unittest discover -s workspaces/halo-control/tests -q
```
