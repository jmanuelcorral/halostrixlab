# Halo Strix Lab

**Espanol** | [English](README.en.md)

Laboratorio de inferencia local y experimentacion con entrenamiento de LLM
sobre **AMD Strix Halo**: un GMKtec EVO-X2 con 128 GiB de memoria,
Radeon 8060S y CachyOS.

Este repositorio recoge configuraciones, mediciones, incidencias y workspaces
para aprender a aprovechar una APU de memoria unificada con **Lemonade Server,
llama.cpp, Vulkan y ROCm**. El objetivo es conservar lo que se ha probado,
explicar sus limites y facilitar que otras personas adapten el trabajo a su
equipo, sin empezar de cero.

**[Configuracion reutilizable](docs/configuracion-reutilizable-halo-strix.md)**
| **[Diccionario Lemonade](docs/referencia-parametros-lemonade.md)**
| **[Estado documental](docs/estado-proyecto.md)**
| **[Perfil de parametros](config/halo-strix.reference.json)**
| **[Setup completo](docs/setup-completo-halo-strix.md)**
| **[English documentation](docs/en/README.md)**
| **[Web estatica / GitHub Pages](site/README.md)**

> **Estado: laboratorio experimental.** La configuracion historica de referencia
> documentada corresponde al **4 de septiembre de 2026**, consolidada el
> 7 de septiembre. No es una auditoria en vivo ni una garantia de soporte
> para otras versiones, equipos o cargas de trabajo.

Las actuaciones posteriores se registran por separado en el
[informe del timeout SSE del 10 de septiembre](docs/incidente-sse-lemonade.md),
con la correccion oficial de Lemonade y una prueba de streaming reproducible.
Los [ensayos Qwen3.8-Flash-Next del 15 de septiembre](docs/ensayos-qwen38-flash-next.md)
registran, por separado, una matriz real de carga/inferencia/restauracion
64K para un candidato experimental antes bloqueado; no cierra el 403 ni el
incidente SSE, y no es una comprobacion de salud permanente.

## Que encontraras aqui

- Preparacion de CachyOS, inventario de hardware y ajuste de memoria UMA.
- Comparacion de llama.cpp con Vulkan frente a HIP/ROCm.
- Operacion de Lemonade: API compatible con OpenAI, modelos residentes,
  contexto, concurrencia y KV cache.
- Workspaces Docker para LLaMA-Factory/LlamaBoard y Unsloth Studio, con
  persistencia de datos y scripts de operacion.
- Procedimientos de diagnostico, recuperacion y rollback, junto con
  resultados medidos y cuestiones todavia pendientes.

No es un instalador automatico del servidor ni una distribucion de modelos.
Los pesos, las imagenes construidas y los datos de entrenamiento se obtienen
o generan por separado.

## Web visual y GitHub Pages

La web incluye una portada bilingue, perfiles de modelos, memoria, workspaces
y un lector con las guias completas y busqueda local. Funciona sin backend,
CDN ni conexion al servidor Halo; el resultado es un HTML autocontenido.

Sigue la [guia de generacion y despliegue](site/README.md) para construir
`site/dist/index.html` y activar **Settings > Pages > Source: GitHub Actions**.
El workflow publica exclusivamente la carpeta generada, no el repositorio
completo ni sus archivos locales privados.

## Equipo de referencia

| Componente | Configuracion documentada |
| --- | --- |
| Equipo | GMKtec EVO-X2 |
| APU | AMD Ryzen AI Max+ 395, 32 CPU logicas |
| GPU integrada | Radeon 8060S, arquitectura `gfx1151` |
| Memoria fisica | 128 GiB |
| Almacenamiento | NVMe de 2 TB nominales, raiz Btrfs |
| Sistema operativo | CachyOS |
| Reserva UMA en BIOS | `UMA_SPECIFIED`, 2 GiB |
| RAM visible tras el ajuste | Aproximadamente 123.5 GiB |
| GTT disponible para GPU | Aproximadamente 61.73 GiB |

Los 128 GiB fisicos **no equivalen a 128 GiB disponibles para cargar modelos
en la GPU**. La reserva de firmware, los limites GTT, los pesos, la KV cache y
los buffers del backend determinan la capacidad real.

Consulta el [inventario y ajuste de UMA](docs/auditoria-ssh-inicial.md)
antes de trasladar esta configuracion a otro equipo o firmware.

## Inferencia: Lemonade + llama.cpp

La ruta seleccionada en las pruebas del laboratorio es **llama.cpp con
Vulkan/RADV**, gestionado por Lemonade Server. HIP/ROCm se evaluo como
alternativa, pero no sustituyo a Vulkan para inferencia: en el benchmark
corto registrado mejoro el procesamiento del prompt y empeoro la generacion.
Las [mediciones y sus condiciones](docs/validacion-llamacpp-hip.md)
no deben extrapolarse a todos los modelos.

Lemonade se documento como servicio de usuario `lemond.service`, con
`linger` habilitado y **`max_loaded_models=2`**. Este parametro controla
modelos residentes, no peticiones concurrentes.

### Perfil Coder + Thinking

| Parametro | Coding | Razonamiento |
| --- | --- | --- |
| Modelo | Qwen3-Coder-30B-A3B-Instruct | Qwen3-30B-A3B-Thinking-2507 |
| Cuantizacion de pesos | `Q4_K_M` | `Q4_K_M` |
| Contexto total | 196608 tokens | 98304 tokens |
| Slots (`--parallel`) | 3 | 1 |
| KV cache K/V | `q8_0` / `q8_0` | `q8_0` / `q8_0` |
| Flash Attention | Activada | Activada |
| Presupuesto de razonamiento | No aplica: modelo non-thinking | 16384 tokens |

Con `--kv-unified`, el contexto del Coder es un **pool compartido**:
196608 tokens totales, unos 65536 por peticion si los tres slots reparten
la capacidad por igual; no 196608 por slot. Tener cuatro slots entre ambos
modelos tampoco garantiza cuatro generaciones eficientes simultaneas.

Los argumentos exactos, IDs de catalogo, revisiones de los GGUF y medidas de
memoria estan en la [referencia reutilizable](docs/configuracion-reutilizable-halo-strix.md)
y la [comparativa de modelos](docs/comparativa-qwen38-halo-strix.md).
El [JSON de referencia](config/halo-strix.reference.json) sirve para consulta
y comparacion: **no es un archivo de configuracion importable en Lemonade**.

### Conexion desde clientes

Para un cliente compatible con OpenAI, incluido un proveedor configurado en
OpenCode, la URL base de referencia es:

```text
http://<HALO_HOST>:13305/v1
```

Sustituye `<HALO_HOST>` por una direccion de tu entorno y selecciona un ID
exacto del catalogo. `GET /api/v1/health` permite consultar la salud y los
modelos cargados; `GET /v1/models` lista el catalogo, pero no demuestra
que todos sus modelos esten residentes.

La configuracion historica utilizaba HTTP en una LAN de confianza.
**Publicar este repositorio no implica exponer sus servicios a Internet.**
Antes de habilitar acceso externo, configura autenticacion, TLS y controles
de red adecuados.

## Nueva ruta: Cockpit + llama-swap + Docker

Para continuar desde el servidor, sigue la [guia de continuacion en el Halo](docs/continuacion-en-halo.md),
sin credenciales publicadas y sin necesidad de instalar Crush.

El [workspace de inferencia](workspaces/inference/README.md) implementa
instalacion aislada, perfiles Docker, web administrativa local y un frontal
TLS restringido para OpenCode. Probado con backend sintetico; **pendiente de
activar y validar en el Halo**. No sustituye automaticamente Lemonade ni
modifica el baseline historico.

## Entrenamiento: workspaces Docker/ROCm

Los entornos de entrenamiento estan separados de la inferencia. Sus scripts
no paran ni reconfiguran Lemonade; ejecutar cargas simultaneas sigue
compitiendo por GPU, GTT y RAM.

| Workspace | Uso | Estado documentado | Bind por defecto |
| --- | --- | --- | --- |
| [LLaMA-Factory / LlamaBoard](workspaces/llama-factory/README.md) | Interfaz web y plantilla de POC LoRA BF16 | Configurado; sin fine-tuning LLM validado | `127.0.0.1:7860` |
| [Unsloth Studio](workspaces/unsloth-studio/README.md) | Interfaz web para experimentar con modelos | UI, imports y deteccion GPU validados; entrenamiento pendiente | `127.0.0.1:8888` |

Cada workspace incluye `Dockerfile`, `compose.yaml`, `.env.example`,
scripts de build/arranque/parada/estado/logs y limpieza. Los datos persisten
mediante bind mounts bajo `data/`. Consulta su README antes de construir o
arrancar: las bases ROCm/PyTorch y las restricciones de cada entorno difieren.

El smoke de PyTorch comprobo operaciones y gradientes FP16/BF16, **no un
entrenamiento LLM completo**. QLoRA de 4 bits no esta disponible en el stack
de Unsloth documentado. Los builds fijan bases por digest y fuentes por
commit, pero no son reproducibles byte a byte; conserva las imagenes por
ID si necesitas volver exactamente al mismo artefacto.

## Por donde empezar

1. Lee la [configuracion reutilizable](docs/configuracion-reutilizable-halo-strix.md)
   para distinguir resultados observados, propuestas e incidencias.
2. Compara tu hardware, firmware, memoria y versiones con el inventario.
   Los scripts de los workspaces se ejecutan en Linux con Bash, Docker
   y Compose v2; el host debe ofrecer acceso a los dispositivos AMD indicados.
3. Elige la ruta de inferencia o uno de los workspaces de entrenamiento.
   Sigue su guia y revisa los requisitos antes de cambiar el sistema.
4. Adapta las plantillas a tu entorno. Los placeholders no son valores
   ejecutables; Lemonade necesita rutas de modelos absolutas.
5. Comprueba primero salud, memoria y modelos residentes. Programa las
   cargas, reinicios y pruebas de generacion para no interrumpir otras tareas.

Para comprobar un Lemonade **ya instalado** desde Windows existe
[`scripts\test-lemonade.ps1`](scripts/test-lemonade.ps1).
Tras confirmar que el modelo indicado esta residente, puedes ejecutar
desde la raiz del repositorio:

```powershell
powershell -File .\scripts\test-lemonade.ps1 -BaseUrl 'http://<HALO_HOST>:13305/v1' -Model 'Qwen3-Coder-30B-A3B-Instruct-GGUF-Q4_K_M'
```

Sustituye el host y, si procede, el ID por los de tu despliegue.
**Esta prueba genera una respuesta: no es de solo lectura.** Pasa siempre
`-BaseUrl` y `-Model`, ambos obligatorios; no se incluye un host ni modelo
por defecto. Elegir un modelo no residente puede expulsar otro.
No instala Lemonade ni mide la calidad o el rendimiento del modelo.
Consulta tambien la [guia del script en ingles](scripts/README.md).

## Mapa de documentacion

| Documento | Contenido |
| --- | --- |
| [Configuracion reutilizable](docs/configuracion-reutilizable-halo-strix.md) | Punto de entrada, parametros y pendientes |
| [Diccionario de parametros Lemonade](docs/referencia-parametros-lemonade.md) | Funcion, alcance, valores, interacciones, riesgos y evidencia de cada parametro |
| [Estado documental del proyecto](docs/estado-proyecto.md) | Cronologia 4/8/10 de septiembre, entrenamiento, pruebas y pendientes |
| [Investigacion Docker, toolboxes y Halogen](docs/investigacion-docker-toolboxes-halogen.md) | APIs existentes, papel de Lemonade, gateway y migracion propuesta; sin despliegue |
| [Perfil JSON](config/halo-strix.reference.json) | Valores estructurados y procedencia |
| [Setup completo](docs/setup-completo-halo-strix.md) | Recorrido de configuracion y operacion |
| [Plan inicial](docs/plan-configuracion-halo-strix.md) | Propuesta original; no equivale al estado final |
| [Auditoria inicial](docs/auditoria-ssh-inicial.md) | Hardware, memoria, UMA y comprobaciones del host |
| [llama.cpp Vulkan](docs/validacion-llamacpp-vulkan.md) | Build, offload y benchmark inicial |
| [llama.cpp HIP](docs/validacion-llamacpp-hip.md) | Alternativa ROCm y comparacion con Vulkan |
| [Lemonade](docs/validacion-lemonade-vulkan.md) | API, modelos e historial de incidencias |
| [Comparativa de modelos](docs/comparativa-qwen38-halo-strix.md) | Coder + Thinking y candidatos Qwen3.8 |
| [Entrenamiento ROCm](docs/validacion-entrenamiento-rocm.md) | Alcance del smoke PyTorch en contenedor |

Los documentos historicos conservan decisiones superadas y resultados
negativos. Prioriza la evidencia fechada de cada tema y la referencia
reutilizable; un PASS antiguo no acredita el estado actual del servidor.

## Limites y trabajo pendiente

- El ultimo reporte de HTTP 403, del 4 de septiembre de 2026, no tiene
  causa ni resolucion confirmadas en la evidencia disponible.
- Falta validar fine-tuning LLM de extremo a extremo, estabilidad sostenida
  y comportamiento con cargas reales de inferencia y entrenamiento.
- vLLM, HIP para inferencia y los candidatos Qwen3.8 no forman parte del
  perfil seleccionado. Su estado refleja las versiones probadas, no el
  soporte upstream actual.
- Guardar opciones de Lemonade y habilitar `linger` no demuestra precarga
  automatica de modelos tras un arranque en frio.

## Compartir y contribuir

Las comparativas son mas utiles si incluyen hardware, versiones, modelo y
cuantizacion, contexto total, slots, argumentos efectivos, memoria y
condiciones de medicion. Distingue una propuesta de un cambio aplicado y un
smoke corto de una prueba sostenida.

No incluyas contrasenas, tokens, claves SSH, archivos `.env` reales,
bases de datos de autenticacion ni datasets privados en contribuciones.
Usa placeholders y `.env.example`; revisa tambien logs y capturas.
Los ejemplos publicables sustituyen los datos de acceso por placeholders.
La configuracion local de agentes y editores, archivos de entorno privados,
credenciales, datos de trabajo y pesos de modelos estan excluidos mediante
`.gitignore`; permanecen en el equipo y no forman parte de la distribucion.
Los workflows locales de Squad que dependen de ese estado tambien se excluyen.

Publica solo los archivos revisados por Git, no un ZIP de toda la carpeta
de trabajo, y no uses `git add -f` para saltarte las exclusiones. Antes de
cada publicacion revisa `git status --short` y `git diff --cached`.
`.gitignore` no elimina secretos ya incluidos en el historial ni impide
que aparezcan nuevos datos privados dentro de un archivo publicable.

Los modelos y proyectos de terceros mantienen sus propias licencias.
Consulta sus condiciones antes de descargar o redistribuir pesos,
imagenes y modificaciones.
