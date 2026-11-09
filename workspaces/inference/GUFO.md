# Gufo: Qwen3.8-27B en el gateway existente

[English](GUFO.en.md) | [Inferencia](README.md)

## Configuración actual: 128K y máximo dos slots

El catálogo mantiene el alias `gufo-qwen38-27b`, ahora con **131072 tokens por
sesión y dos slots**. El runtime rechaza más de dos slots; llama-swap admite
hasta dos peticiones Gufo simultáneas. El límite global queda en 7 para conservar
el contrato de Laya (Halogen 4 + Gufo 2 + Laya 1), aunque los motores GPU se alternan.
Imagen, pesos, DFlash2 y salida por defecto 2048 no cambian.

En Halo Control, abre **Servicios IA → Catálogo de modelos · llama-swap**:
**Activar Gufo** carga el modelo comprobando `/ready`; **Desactivar Gufo** descarga
solo Gufo y conserva la entrada del catálogo. Se bloquean operaciones con trabajos
en curso, gateway detenido o configuración incompatible. Activar alterna la GPU
con Halogen; Laya sigue en CPU. Descargar no bloquea futuras peticiones: estas
pueden cargarlo otra vez. No es una deshabilitación permanente del alias.

Alternativa desde la raíz del repositorio:

```bash
python3 workspaces/inference/gufo.py load
python3 workspaces/inference/gufo.py unload
```

El botón Load de la interfaz nativa v255 consulta `/upstream/MODELO/`, pero Gufo
responde 404 en `/` aunque haya arrancado. Por eso los botones del catálogo de
Halo Control usan `/ready`; no se presenta ese 404 como fallo de inferencia.
Los botones son trabajos supervisados; consultar Actividad y logs compartidos.
No se añadió un editor de parámetros ni una séptima tarjeta de motor.

Validación real del perfil ampliado, 2026-09-25 UTC:

- Loader: `sessions=2 context_tokens=131072`, 3,450 s; carga por `/ready` 4,385 s
  desde gateway sin motor GPU residente, no desde Halogen cargado.
- Dos peticiones concurrentes de 128 tokens respondieron en 5,616 y 5,417 s;
  el servidor confirmó `batched-w2`, ancho físico 2 y hasta dos residentes.
- Decode por petición: 25,82 y 25,90 tokens/s. No es throughput extremo a extremo
  ni comparación de calidad. Ambos textos finalizaron por límite de prueba.
- Contador HIP del loader: 23160 MiB; no sumar a RSS o memoria Docker en UMA.
- Descarga explícita: 60,41 s; alias conservado y Laya sin cambio de contenedor.
- Halogen quedó restaurado, Laya saludable y Gufo disponible bajo demanda.

Esto verifica reserva de contexto, arranque y dos peticiones cortas concurrentes,
**no dos prompts completos de 128K**, soak ni estabilidad en todos los tamaños.
El ensayo siguiente se conserva como evidencia histórica de 32K/un slot.

## Prueba inicial de 32K / un slot

Observación del host fechada **2026-09-25 UTC**, no garantía de salud futura.
Se descargó la imagen oficial, se verificaron ambos GGUF por SHA256 y se sirvió
`gufo-qwen38-27b` mediante el mismo llama-swap v255 que Halogen y Laya.
No se instaló otro proxy ni se cambió la política de autenticación existente.

- Qwen3.8-27B UD-Q4_K_XL con DFlash2 Q4_K_M, contexto configurado 32768,
  una sesión y razonamiento desactivado por defecto.
- Chat Completions: respuesta correcta `42` para `17 + 25`, HTTP 200.
- Streaming: contenido correcto y terminador SSE `[DONE]`.
- Herramientas: llamada declarada `add` con argumentos enteros 17 y 25;
  no se ejecutó código generado ni una herramienta real.
- `/ready` confirmó modelo disponible. `/health` solo indica proceso vivo.
- La primera petición, incluyendo arranque del contenedor/modelo, tardó 3,63 s.
  El loader registró 2,876 s; esto no es un arranque del host con cachés frías.
- Tres peticiones idénticas de explicación de programación, 128 tokens cada
  una: 4,329 / 4,120 / 4,136 s de extremo a extremo; decode del servidor
  31,06 / 31,14 / 31,02 tokens/s. Las dos últimas reutilizaron 29 tokens.
  TTFT del servidor: 196,5 / 3,4 / 3,4 ms, no latencia hasta el cliente.
  Las respuestas se truncaron por el presupuesto de prueba (`length`).
- `docker stats`: 16,79 GiB; RSS del proceso cerca de 18 GiB y contador HIP
  del loader 6268 MiB. Son contadores distintos sobre UMA, no se suman ni
  representan por sí solos el consumo total o máximo del sistema.
- Laya conservó el mismo contenedor y salud CPU durante Gufo y la vuelta a
  Halogen. El reinicio inicial del gateway sí descargó ambos servicios.
- Restaurar Halogen mediante una petición llevó 76,27 s, incluyendo descarga
  de Gufo y carga de Halogen. No se promete alternancia instantánea.
- Estado final verificado: Halogen cargado, Laya saludable; Gufo descargado
  pero disponible en el catálogo para la siguiente petición.

En la prueba inicial no se probaron visión, contexto lleno de 32K, concurrencia Gufo, soak, reinicio,
paridad AR/DFlash2 ni calidad de programación sistemática. Es otro modelo y otra
cuantización: estos números **no demuestran superioridad sobre Halogen**.

## Identidades fijadas

Imagen oficial de `gufo-org/toolboxes`:

```text
ghcr.io/gufo-org/toolboxes/gufo-runtime@sha256:989ab52a190244f08511a3ad0fd46546f2144220c37e6c808ad8008a934ebab5
```

El ejecutable informa `gufo version 9cad139`, coincidente con el prefijo del
commit revisado `9cad13974cf6da0cd3674b4e0a88b14b7e4a2908`.
No se afirma una reconstrucción reproducible de la imagen.

| Artefacto | Repositorio y revisión | Bytes |
| --- | --- | --- |
| `Qwen3.8-27B-UD-Q4_K_XL.gguf` | `unsloth/Qwen3.8-27B-GGUF` @ `4ca720788d1e01f1bff70c033e0d0028fd02e502` | 17559178144 |
| `Qwen3.8-27B-DFlash2-Q4_K_M.gguf` | `z-lab/Qwen3.8-27B-DFlash2-GGUF` @ `2d9571f8ce46e151f61c6499c99dee6079e1d610` | 1143006816 |

SHA256, respectivamente:

```text
3f227079003add2511437e5b1e94812e363385225bf6a9b47b0054a72bc8b01e
1a25c56858e1ebe93f2718ac1d49d1151f9323325c1bbfd6209370f4db131ebd
```

## Preparación y operación

Desde la raíz del repositorio, sin detener los motores durante la descarga:

```bash
docker pull ghcr.io/gufo-org/toolboxes/gufo-runtime@sha256:989ab52a190244f08511a3ad0fd46546f2144220c37e6c808ad8008a934ebab5
workspaces/inference/data/cockpit-venv/bin/python workspaces/inference/gufo.py download
python3 workspaces/inference/gufo.py prepare
```

La descarga requiere `huggingface_hub` en el entorno aislado ya instalado por
`manage.py install`; no instala paquetes globales. Descarga solo target/drafter,
reanuda mediante HF y verifica los hashes fijados en código, no un manifiesto
local confiado ciegamente. Todo queda en `data/gufo/`, privado e ignorado.
La prueba inicial utilizó el cliente HF de la imagen CPU local de Laya.

`gufo.py install` es un adaptador para el despliegue existente de Halo Control:
exige su launcher revisado y gateway **detenido**, toma los locks de operación
y ajustes, valida el candidato con llama-swap y reemplaza atómicamente la
configuración real con copia privada. No detiene ni arranca servicios por sí
solo. Antes de ejecutarlo, reservar tráfico de clientes, comprobar trabajos,
drenar y detener el gateway desde el panel; después arrancar el mismo gateway.
Una lectura de inflight aislada no bloquea clientes directos nuevos.

```bash
python3 workspaces/inference/gufo.py install
```

Para actualizar una instalación anterior de 32K, ejecutar `prepare` antes de
parar servicios y, con gateway drenado/detenido, ejecutar:

```bash
python3 workspaces/inference/gufo.py upgrade
```

`upgrade` verifica los comandos/perfil de la entrada anterior antes de cambiar
solo Gufo. Conserva el perfil previo; el nuevo es `data/gufo/profiles-128k-2slots.json`.
Valida el candidato y cambia atómicamente el puntero del gateway con copia privada.
Reinicia después el mismo gateway; no crea un proxy paralelo.

No usar `manage.py generate` sobre el despliegue existente: perdería entradas
ajenas al perfil, como Laya. En una instalación diferente se puede usar el tipo
`gufo` de `runtime.py`, con un perfil privado validado y routing revisado.
El instalador falla ante colisiones de alias/puerto o routing incompatible.

Gufo comparte el grupo GPU exclusivo con Halogen; Laya permanece en su grupo
CPU persistente. Backend Gufo `127.0.0.1:18102`, modelos RO, usuario no root,
capabilities eliminadas, sin IPC host ni socket Docker, KFD y render exactos,
memlock ilimitado y GPU lock cooperativo heredado por el cliente Docker.
El guard de procesos detecta también `gufo`; no es un aislamiento frente a
operadores que lancen otros motores por fuera del sistema gestionado.

La concurrencia global queda al menos en la suma de límites configurados
(7 en el perfil actual), respetando el contrato actual de Laya. Gufo usa dos sesiones.
`output=2048` es el default del servidor y metadato del catálogo, **no un techo
inmutable** frente a `max_tokens` explícito del cliente; siempre usar presupuestos
acotados. El contexto 131072 limita cada sesión, incluyendo entrada y salida.

Ejemplo sobre el gateway ya operativo; esta petición descarga Halogen si está
residente, por lo que debe coordinarse con otros usuarios:

```python
import sys
sys.path.insert(0, 'workspaces/halo-control')
import control
response = control.http('/v1/chat/completions', {
    'model': 'gufo-qwen38-27b',
    'messages': [{'role': 'user', 'content': 'Responde solo con el resultado de 17 + 25.'}],
    'max_tokens': 32, 'temperature': 0,
    'chat_template_kwargs': {'enable_thinking': False},
}, timeout=1200)
print(response['choices'][0]['message']['content'])
```

Usar el mismo endpoint/base del cliente actual y seleccionar `gufo-qwen38-27b`.
Chat Completions es la ruta probada; Responses solo soporta un subconjunto
síncrono textual sin streaming/herramientas/imágenes/estado. No es sustitución
transparente de todos los clientes Responses de Halogen. El catálogo de Halo
Control permite cargar/descargar; no se añadió editor de parámetros.

## Recuperación y verificaciones

Una petición a `flash-halogen` por el mismo gateway descarga Gufo y restaura
Halogen. Para retirar la entrada: drenar, detener gateway, tomar settings lease,
restaurar la copia privada anterior con validación y sustitución atómica,
arrancar el mismo gateway y recargar los modelos deseados. No borrar pesos ni
copias históricas. No parar contenedores ajenos por nombre sin validar propiedad.

```bash
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -q
python3 -m unittest discover -s workspaces/halo-control/tests -q
git diff --check
```

68 pruebas de inferencia y 102 de panel pasaron. Las pruebas de navegador del
catálogo comprueban botones, bloqueo y envío de acciones sin ejecutar motores. El ensayo sintético con v255
comprueba las dos órdenes CPU/GPU y Gufo→Halogen sin descargar Laya; no prueba
GPU por sí solo. La evidencia de inferencia real queda privada en `data/gufo/`.
El sitio completo conserva un fallo previo de publicación de
`scripts/engramhalo/.dockerignore`; no se amplió la lista pública para ocultarlo.

Fuentes: [Gufo](https://github.com/gufo-org/gufo),
[guía Qwen27B](https://github.com/gufo-org/gufo/blob/main/docs/models/qwen3.8-27b/README.md),
[API](https://github.com/gufo-org/gufo/blob/main/docs/SERVER.md).
