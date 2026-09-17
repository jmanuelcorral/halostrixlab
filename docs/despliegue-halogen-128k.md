# Despliegue en el Halo: Halogen 128K y llama-swap

[English](en/halogen-128k-deployment.md) |
[Workspace](../workspaces/inference/README.md) |
[Continuación inicial](continuacion-en-halo.md) |
[Estado documental](estado-proyecto.md)

**Registro de intervención: 2026-09-17.** Resume el trabajo iniciado con el
checkout `a9a6e3f`, el preflight y las actuaciones autorizadas de septiembre
16-17. Las fechas de archivos privados y relojes de distintas sesiones no se
usan para construir una cronología de segundos común. Son observaciones
fechadas, no monitorización permanente ni una receta universal.

No sustituye el baseline histórico de Lemonade del 4 de septiembre ni cierra
el 403 histórico, el incidente SSE o los ensayos anteriores. No se publican
logs crudos, direcciones privadas, usuarios, credenciales, configuraciones de
agentes ni el contenido de `data/`. Los ejemplos siguientes son sanitizados.

## 1. Resultado y alcance

| Capa | Estado al cierre de la intervención |
| --- | --- |
| Hardware | Halo real confirmado, Linux nativo y GPU `gfx1151` |
| llama-swap | v255, servicio de usuario habilitado y activo |
| Modelo servido | Solo `flash-halogen`, Halogen W4B Quality, contexto 131072 |
| Salida | Máximo configurado 8192, compartiendo contexto con la entrada |
| Paralelismo | Un slot, pool KV 131072, concurrencia global y por modelo 1 |
| Lemonade | 11.9.0 conservado; servicio de usuario deshabilitado e inactivo |
| Coder Vulkan | Probado a 32K y 128K; retirado del catálogo activo, no borrado del disco |
| Cockpit | TUI instalada y utilizada; no controla el contenedor gestionado final |
| Red final | HTTP en una dirección LAN autorizada, TCP/18080, sin API key por petición expresa |
| TLS | Probado localmente con certificado de ensayo y luego retirado; no desplegado en LAN |
| Arranque | `linger` ya activo; servicio configurado para iniciar sin login, sin reinicio del host probado |

**Implementado**: control de runtimes, adaptador Cockpit, perfiles, publicación
de límites, pruebas y ejemplos. **Probado offline**: validaciones y gateway
real con backend sintético. **Validado en el Halo**: carga GPU, chat/SSE,
herramientas, alternancia y pruebas largas descritas abajo. La configuración
privada del servicio no se instala automáticamente al clonar el repositorio.

## 2. Preflight observado, no supuesto

- GMKtec EVO-X2, Ryzen AI Max+ 395, Radeon 8060S, `gfx1151`.
- BIOS EVO-X2S 1.13; kernel `7.2.5-1-cachyos`; RADV Mesa `26.2.2-arch3.2`.
  `vulkaninfo --summary` y `rocminfo` reconocieron la GPU.
- Aproximadamente 123,5 GiB de RAM visible, 2 GiB de VRAM y 61,73 GiB de GTT.
  Al inicio había unos 121 GiB disponibles y 1,28 TiB de disco libre.
- `/dev/kfd` y el nodo render eran accesibles; se observaron permisos amplios
  existentes. No se crearon reglas de dispositivos ni cambios UMA/GTT/IOMMU.
- Docker/Compose 29.8.0/5.5.1. Primero faltaban GitHub CLI y acceso al socket;
  después se instaló/autenticó `gh` y se añadió el operador al grupo Docker.
  Una nueva sesión o `newgrp docker` fue necesaria para renovar los grupos.
- Lemonade 11.9.0 devolvía HTTP 200, sin residentes ni pins. Había conexiones
  de clientes: servicio sin modelos no equivale a ventana reservada.
- La configuración real estaba bajo `$HOME/.config/lemonade/`, incluidos
  `config.json`, `recipe_options.json` y `user_models.json`, no en la ruta
  histórica de caché. Se respaldaron configuración, unidades y respuestas de
  catálogo/salud/configuración efectiva en privado, verificando hashes.

Ejecutar el workspace con `sudo` cambia la identidad y hace fallar la exigencia
de propietario y modo 0700. No resolverlo con `chmod 777` ni cambiando el dueño
de `data/`. El grupo Docker da autoridad equivalente a root sobre el host.

## 3. Artefactos y correcciones de compatibilidad

| Artefacto | Referencia comprobada |
| --- | --- |
| llama-swap | v255, commit informado `7761aa1`; archivo y binario contrastados con el SHA256 fijado por el instalador |
| Cockpit | `6959d068c020f3f33bfb8ef743e7ba44a6390dda`, versión 2026.9.16.1218 |
| Toolbox Vulkan | `docker.io/kyuz0/amd-strix-halo-toolboxes@sha256:c96266e8b29164f37e82b6b8a31f1ca4a044dc0b0c77c7ea5fefc861c9b541ef` |
| llama.cpp de esa imagen | build 11011, commit `aa39d7a3e`, versión informada 0.4.1-dev |
| Halogen | `ghcr.io/peonist-ai/halogen-flash-server@sha256:760691880fecbf07f25e6b067cb5cc70e6a9ae11f280ca4725d3878e68821bd2`, versión 0.11.3 |

La revisión `8215baa74dab` anunciada por la imagen Halogen no pudo resolverse
por la API de GitHub. Se extrajo e inspeccionó su entrypoint sin arrancar GPU;
la documentación upstream consultada por separado no se presenta como fuente
exactamente emparejada con ese commit. No se recompiló el motor cerrado.

Correcciones incorporadas al workspace:

1. La imagen Vulkan rechaza `--no-mmap`. `load_mode: "none"` selecciona
   `--load-mode none`; omitirlo conserva el contrato de builds anteriores.
2. Cockpit pasaba los nombres `video` y `render` a Docker. La imagen Halogen
   no define `render`: se reprodujo el fallo con `/bin/true`, sin GPU ni pesos.
   El adaptador del launcher sustituye esos nombres por los GID de los
   dispositivos del host, sin modificar el código instalado de Cockpit.
   La adaptación está limitada a la topología inicial de GPU única.
3. Reducir Context a 32768 y Slots a 1 dejaba **KV Pool en 524288** en la TUI.
   Se configuró el pool explícitamente antes del primer arranque correcto.
4. Los perfiles admiten `halogen_overlay`, `halogen_tokenizer` y
   `halogen_max_tok`, con validación de rutas relativas, contención de symlinks,
   existencia de `tokenizer.json` y límites de la arena de prefill.
5. El generador publica contexto y presupuesto de salida en el catálogo.

La instalación de Cockpit resolvió dependencias en un venv y conservó su
manifiesto privado. `pip check` pasó; el aviso de que `huggingface_hub` ya no
ofrece el extra `cli` no impidió instalación ni descarga. No se promete una
resolución transitiva reproducible byte a byte.

## 4. Modelos, memoria y pruebas reales

Coder reutilizó el GGUF Q4_K_M existente, 18556689568 bytes, con cabecera GGUF
válida y SHA256 local guardado; ese hash no se contrastó independientemente
con un checksum upstream. Se probó inferencia directa, luego gateway, auth,
UI, SSE, herramientas con argumentos y respuesta posterior, cancelación del
cliente, descarga y recuperación de memoria. Reiniciar Lemonade recuperó su
estado observado sin residentes; después se retomó Docker. Su configuración
original se conservó byte a byte durante ese rollback.

Cockpit descargó el bundle **W4B Quality**: ocho archivos, 117,88 GiB, HGN,
overlay y tokenizer. Se verificaron tamaños y completitud según su catálogo,
no hashes integrales de los 118 GiB. El sidecar de visión no estaba descargado;
no se anuncia soporte visual validado. Descargar la imagen no descarga pesos.

Primera carga Halogen: contexto/pool 32768, un slot, arena 32768. El motor
informó unos 68 GiB de pesos registrados, 0,9 GiB KV y 21 GiB de trabajo,
89,9 GiB en conjunto. Chat directo respondió en aproximadamente 1,8 s.
Después se migraron los artefactos explícitos al control exclusivo de
llama-swap y se verificó Halogen → Coder → Halogen, SSE y herramientas reales.

**Corrección de la estimación inicial:** comparar directamente 68 GiB de pesos
registrados con 61,73 GiB de GTT no bastaba para declarar imposible la carga.
Halogen registra mappings de pesos; se observó arranque correcto sin ampliar
GTT. A la inversa, `MemAvailable` sobreestima el margen cuando contabiliza
pesos registrados como caché recuperable. Se usan diagnósticos del motor,
memoria del driver, presión y comportamiento real, no una sola cifra.

### Ampliación a 128K

Se conservaron salida 8192 y concurrencia 1. Halogen pasó a contexto/pool
131072 y arena de prefill **16384**: aproximadamente 68 GiB de pesos,
3,6 GiB KV y 12,2 GiB de trabajo, **83,7 GiB totales** y unos 30,2 GiB restantes
según el diagnóstico de arranque. Menor arena reduce memoria de trabajo;
no reduce la ventana de conversación ni el presupuesto de salida.

| Ensayo sintético SSE | Entrada real | Salida real | Primer contenido | Total |
| --- | ---: | ---: | ---: | ---: |
| Halogen | 105074 tokens | 34 tokens, 27 de razonamiento | 77,63 s | 77,73 s |
| Coder Vulkan | 120033 tokens | 6 tokens | 1452,46 s | 1452,81 s |

Ambos devolvieron la clave de control del comienzo y `[DONE]`. Se usó el mismo
texto repetitivo; los tokenizadores produjeron cantidades distintas. No es
benchmark causal de motores equivalentes, ni calidad de recuperación general,
ni validación de la ventana completa 131072, ni soak. Coder resultó demasiado
lento en ese caso largo y se retiró por decisión del operador, conservando
pesos, imagen y backups. Solo Halogen permanece en el catálogo final.

## 5. Contexto publicado y clientes

`/v1/models` devuelve para Halogen:

```json
{
  "id": "flash-halogen",
  "context_length": 131072,
  "context_window": 131072,
  "meta": {
    "n_ctx": 131072,
    "llamaswap": {"max_output_tokens": 8192, "type": "model"}
  }
}
```

Llama-swap v255 transforma `capabilities.context` y `metadata` en esos campos.
Los tests comprueban la respuesta del binario real, no solo el JSON generado.
Publicarlos no recorta `max_tokens`. A 32K se rechazaron entradas de 24732 y
25188 tokens con salida solicitada 8192: entrada, herramientas, historial,
razonamiento y respuesta comparten la ventana.

Publicar límites no eliminó el problema en el cliente del operador. Se revisó
código upstream de OpenCode, no su versión/configuración remota efectiva.
Se prepararon fragmentos privados, sin sustituir archivos del equipo cliente:

- OpenCode: modelo `halo/flash-halogen`, contexto 131072, límite de entrada
  122880, salida 8192, compactación automática y poda activadas.
- Crush: ventana de cliente conservadora 122880, salida principal 8192,
  resumen 4096, auto-resumen activo. Modelo principal y de resumen Halogen,
  evitando cambiar de motor durante compactación. Discovery desactivado en
  ese fragmento para fijar el margen explícito.

La sintaxis del fragmento Crush fue comprobada; ni esto ni el catálogo prueban
compactación automática end-to-end en un equipo remoto. Resultados de
herramientas muy grandes aún pueden desbordar la ventana. Incorporar estos
ajustes privadamente y no reemplazar configuraciones enteras.

## 6. Red y excepción de laboratorio

El diseño público continúa siendo loopback con claves y frontal TLS filtrado.
Durante la intervención se probaron un certificado temporal para localhost,
validación de confianza/nombre, inferencia HTTPS y rechazo de claves erróneas
y rutas administrativas; el frontal de ensayo fue retirado. No se desplegó
TLS LAN ni se instaló una CA en clientes remotos.

Después el operador pidió acceso HTTP directo a la UI desde la LAN y quitar
la API key. La configuración privada final escucha en `<HALO_LAN_IP>:18080`,
con regla UFW TCP limitada a `<LAN_CIDR>` hacia esa dirección. UFW no se
desactivó; el operador aplicó la regla desde su terminal cuando la herramienta
no permitía ese comando. Se confirmó acceso desde otro equipo.

**Es una excepción aceptada para este laboratorio, no un default seguro:**
HTTP no cifra prompts ni respuestas; todo equipo admitido por la regla puede
inferir y administrar el gateway sin contraseña. No se realizó una auditoría
de NAT/router ni se garantiza ausencia de exposición externa a partir de una
regla local. Las claves anteriores se conservaron en privado para rollback.
El generador público sigue creando configuración autenticada y `start.sh`
sigue seleccionando la configuración estándar loopback; el servicio real
utiliza un launcher privado distinto. No ejecutar ambos simultáneamente.

## 7. Persistencia, operación y rollback

Los primeros gateways dependían de una sesión: sus logs mostraron señal de
interrupción y cierre limpio cuando la UI dejó de responder. Se sustituyó ese
arranque por **`llama-swap.service` de usuario**, enlazado a una unidad privada
bajo `data/` y habilitado en `default.target`. `linger` ya estaba activo.

Propiedades aplicadas: `Restart=always`, `RestartSec=10`,
`StartLimitIntervalSec=0`, `TimeoutStartSec=30`, `TimeoutStopSec=120`,
`KillMode=control-group`, `UMask=0077`, directorio de trabajo privado.
`ExecStartPre` comprueba Docker; `ExecStopPost` detiene únicamente el contenedor
Halogen con etiqueta de propietario mediante `runtime.py stop`. El launcher
preserva 128K, la dirección LAN y la excepción sin clave. No incluye secretos
en argumentos de procesos.

El gestor de usuario conservaba grupos anteriores a la autorización Docker.
`sg` no estaba instalado; se verificó `/usr/bin/newgrp docker -c` y se usó
para los comandos del servicio. No se ejecuta el gateway como root ni se
relajan permisos del socket. Docker de sistema estaba habilitado; si Docker
o la IP aún no están disponibles durante arranque, el servicio reintenta.
Revisar el journal si persiste ese bucle.

`lemond.service` de usuario quedó **disabled/inactive**; la unidad de sistema
ya estaba deshabilitada. No se desinstaló ni se enmascaró Lemonade: todavía
puede iniciarse manualmente. Antes de hacerlo, parar llama-swap y comprobar
que sus contenedores han salido y liberado memoria.

Comandos de operación desde una terminal del operador, sin sudo:

```bash
systemctl --user status llama-swap.service
journalctl --user -u llama-swap.service -n 100 --no-pager
systemctl --user stop llama-swap.service
systemctl --user start llama-swap.service
```

Para una prueba manual en Cockpit, cerrar admisión/parar el servicio, esperar
la descarga y abrir `manage.py cockpit` desde la raíz del repositorio. Cerrar
servidores y TUI antes de volver a iniciar el servicio. El lock es cooperativo;
no protege frente a Docker manual, otros usuarios o entrenamiento ajeno.
`manage.py unload` usa el endpoint loopback estándar y no debe suponerse
operativo para el bind LAN privado: usar la UI o parar el servicio.

Rollback a Lemonade: parar/deshabilitar llama-swap, verificar contenedores y
memoria, comparar archivos originales con el snapshot privado, restaurar solo
si fueron alterados y volver a habilitar/iniciar la unidad Lemonade observada.
No cargar a ciegas el par del baseline histórico. No usar `prune`, borrar pesos
ni sobreescribir archivos privados. Clonar este repositorio no reproduce la
unidad privada, los enlaces systemd, claves, perfiles activos ni firewall.

Al revalidar para este informe: Lemonade disabled/inactive; llama-swap
enabled/active, cero reinicios registrados, catálogo exclusivo Halogen
131072/8192 y 21 chats HTTP 200 en una muestra reciente de 200 líneas del
journal. Durante la prueba inicial del servicio hubo 429 por concurrencia 1;
no se interrumpieron las peticiones del operador para forzar el smoke.
**No se reinició el host:** arranque automático configurado, cold boot y
recuperación tras caída real aún pendientes. Halogen carga bajo demanda.

## 8. Logs, optimizaciones propuestas y límites

En una muestra previa de una hora: backend con 61 peticiones, sin HTTP 4xx/5xx,
OOM ni reinicios; journal de kernel sin fallos GPU/OOM coincidentes. Otra
muestra del gateway tuvo 72 chats, mediana 9,3 s y máximo 58,2 s; son tiempos
totales heterogéneos, no TTFT ni benchmark. Hubo cinco expulsiones de caché KV
por falta de espacio, recuperables pero con posible coste de nuevo prefill.
PSI de memoria instantáneo nulo no prueba ausencia de presión durante cargas.
Tctl observado 77-84 °C y sensor GPU 37 °C: no son medidas equivalentes ni
prueba de throttling; registrar temperaturas bajo carga antes de aumentar N.

Plan **no aplicado**:

| Paso | Propuesta | Validación necesaria |
| --- | --- | --- |
| N=2 | Pool 262144, dos slots, contexto 131072 | Aproximadamente +3,6 GiB KV respecto al pool actual, más estado; medir TTFT y velocidad individual/agregada |
| N=4 moderado | Pool 262144, presupuestos aproximados 64K por petición | No prometer cuatro peticiones de 128K simultáneas; medir expulsiones/cancelación |
| N=4 largo | Pool 524288 | Validar margen de RAM, caché de archivos y latencia antes de promover |
| Caché persistente | Directorio privado separado | Beneficio tras reinicios, escritura, privacidad y limpieza |
| Servicio | Reinicio del host y recuperación controlada | API tras boot, nueva carga, Docker/grupos/red, fallos de motor |

El controlador actual fija un slot, pool igual al contexto y concurrencia 1
en gateway/modelo. Para ensayar N=2 hay que extender esos contratos y sus tests,
no editar solo el campo Slots de Cockpit ni incrementar el contexto anunciado.
No se propone ampliar GTT o desactivar IOMMU para obtener más concurrencia.

## 9. Pruebas de repositorio y publicación

```bash
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -v
.venv-site/bin/python -m unittest discover -s scripts/tests -p test_build_site.py -v
.venv-site/bin/python scripts/build_site.py
git diff --check
```

Al preparar la entrega: 28 tests de inferencia/control y 14 documentales pasan,
incluyendo pruebas opcionales con llama-swap instalado. Se verificó la unidad
privada con `systemd-analyze --user verify`. El build completo del sitio sigue
fallando por el enlace EngramHalo a `.dockerignore`, no permitido. No se amplió
el allowlist ni se presenta el éxito de fixtures como éxito de publicación.

Pendientes: cold boot, soak, concurrencia N=2/N=4, calidad de tareas largas,
compactación del cliente real, TLS LAN si cambia el alcance, otros runtimes,
visión y entrenamiento. No hay inferencia ROCm Coder/vLLM promovida ni prueba
visual Halogen. Los archivos locales antiguos y backups conservan sus nombres
históricos aunque solo Halogen sea servido al cierre.
