# Continuación del despliegue en el Halo

[Workspace y comandos](../workspaces/inference/README.md) |
[Investigación completa](investigacion-docker-toolboxes-halogen.md) |
[Índice](../README.md)

**Guía inicial conservada; despliegue ejecutado el 2026-09-17.** Consultar
primero el [informe de Halogen 128K y servicio persistente](despliegue-halogen-128k.md):
Lemonade quedó deshabilitado y solo Halogen se sirve mediante llama-swap.
Los pasos siguientes describen la preparación original, no instrucciones para
repetir el corte sobre el servicio ya instalado. La guía permite continuar
por una sesión autorizada, sin instalar un asistente en el servidor; instalar
Crush es opcional. No contiene direcciones privadas, usuarios, contraseñas,
claves ni configuración real del laboratorio.

## Objetivo acordado

- Cockpit para descargar modelos, explorar runtimes y probar configuraciones.
- llama-swap en el host como API estable y web administrativa.
- Servidores de inferencia en contenedores Docker independientes.
- OpenCode en otro equipo consumiendo la API mediante un frontal TLS restringido.
- Coder Vulkan como primera migración; ROCm, vLLM y Halogen después.
- Halogen como perfil exclusivo hasta demostrar capacidad y estabilidad.
- Un solo propietario del ciclo de vida, sin Cockpit y llama-swap compitiendo.

## Qué hay y qué no hay

El workspace incluye instalador aislado, perfiles deshabilitados, controlador
Docker, generador de configuración, frontal Caddy y ejemplo OpenCode. Se han
probado validaciones offline y la API/UI del binario real de llama-swap con un
backend sintético. Esto no equivale a una inferencia real ni a despliegue en el
Halo. No se ha detenido Lemonade ni cambiado firmware, kernel, memoria o red.

Las herramientas instaladas en la estación original y sus secretos están bajo
`workspaces/inference/data/`, ignorado por Git. **Clonar el repositorio no
transfiere esa instalación ni sus claves.** Se inicializa un entorno nuevo en
el Halo. Tampoco se transfieren imágenes, modelos ni certificados.

## 1. Obtener el repositorio

Usar la URL pública del remoto del proyecto, sin credenciales incrustadas.
No descargar un ZIP de la carpeta local completa. Si ya existe un checkout,
comprobar sus cambios antes de actualizar; no usar reset, limpieza forzada ni
sobrescribir archivos privados.

Leer antes de actuar:

1. `AGENTS.md`.
2. Este documento.
3. `workspaces/inference/README.md`.
4. `docs/investigacion-docker-toolboxes-halogen.md`.

## 2. Preflight de solo lectura

Desde la raíz del checkout, comprobar primero:

```bash
uname -r
python3 --version
docker version
docker compose version
git status --short
getent group render video
```

Revisar localmente hardware, dispositivos GPU, memoria/GTT, espacio, listener
de Lemonade, versiones, modelos residentes, pins y actividad de entrenamiento.
No pegar salidas con secretos o topología privada en documentación pública.
No inferir estado actual a partir del baseline histórico.

Guardar un snapshot privado recuperable de la configuración actual de Lemonade,
catálogo, rutas y argumentos. No usar `config/halo-strix.reference.json` como
archivo importable. Decidir cómo volver a ese estado antes de una parada.

## 3. Instalar herramientas sin iniciar inferencia

Requisitos y versiones fijadas: ver el workspace. Sus comandos no instalan
paquetes del sistema, no usan sudo y no arrancan servicios automáticamente.

```bash
python3 workspaces/inference/manage.py install
python3 workspaces/inference/manage.py init
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -v
```

`init` crea claves nuevas privadas y perfiles deshabilitados. No imprimirlas,
publicarlas ni transportarlas en argumentos de shell. Mantener los permisos
0700 del directorio privado y 0600 de sus archivos de configuración/credenciales.

## 4. Preparar Coder y validar el cambio

- Seleccionar una imagen Vulkan y comprobar su digest y binario.
- Localizar el GGUF real del Coder; no asumir el nombre de ejemplo.
- Configurar únicamente el archivo privado `data/profiles.json` y habilitar
  `coder-vulkan` con un contexto inicial conservador.
- Preparar una ventana sin cargas competidoras; drenar y detener Lemonade
  explícitamente, después del snapshot. No desinstalarlo ni borrar pesos.
- Generar configuración y arrancar el gateway:

```bash
python3 workspaces/inference/manage.py generate
bash workspaces/inference/start.sh
```

El controlador escucha solo en loopback, puerto 18080; web `/ui/`. No ocupa el
13305 histórico. La primera petición al perfil puede arrancar el modelo;
consultar catálogo no valida inferencia. Verificar offload GPU, contenido,
streaming, herramientas, errores, uso de memoria y parada.

## 5. Habilitar acceso desde OpenCode

Preparar DNS y certificado confiable, dirección autorizada LAN/VPN, UID/GID y
archivo privado basado en `.env.example`. La API externa propuesta usa puerto
18443 y solo rutas de inferencia. No publicar el 18080 administrativo.

Seguir los comandos Compose del workspace. Validar handshake TLS y comprobar
que una clave incorrecta y rutas administrativas reciben rechazo antes de
conectar clientes. No desactivar la validación de certificados.

Incorporar el fragmento `opencode.example.json` sin sobrescribir el archivo
actual del cliente. Configurar privadamente `HALO_BASE_URL` y `HALO_CLIENT_KEY`;
retirar de la lista modelos deshabilitados. Probar una tarea pequeña con lectura,
edición y tests en un repositorio desechable.

## 6. Uso de Cockpit y ampliaciones

Descargar los modelos gestionados antes de abrir Cockpit:

```bash
python3 workspaces/inference/manage.py unload
python3 workspaces/inference/manage.py cockpit
```

No arrancar Cockpit fuera del launcher mientras exista actividad del gateway.
El lock es cooperativo, no bloquea entrenamiento ni Docker manual. Cerrar sus
servidores y salir de la TUI antes de servir otra vez.

Evaluar Halogen después de comprobar memoria y formatos soportados. Su imagen
requiere `gfx1151` y su esquema de memoria no equivale al baseline Vulkan.
No aplicar ajustes IOMMU/GTT de terceros automáticamente. vLLM necesita una
receta de modelo y parsers verificada; un catálogo compatible no demuestra
calidad de herramientas ni capacidad local.

## 7. Criterios de finalización y rollback

No promover el despliegue hasta comprobar:

- API directa y por frontal, auth, TLS y bloqueo de administración remota.
- Chat/SSE, herramientas reales, presupuesto y contexto efectivo.
- Cancelación, salida de contenedores y recuperación de memoria.
- Exclusión Cockpit/llama-swap y ausencia de trabajos ajenos simultáneos.
- Reinicio y recuperación antes de instalar un servicio permanente.
- Snapshot de Lemonade restaurable, sin pérdida de pesos ni opciones.

Si falla una carga, detener solo el contenedor propio, cerrar la admisión y
restaurar el estado observado de Lemonade. No usar `prune`, borrado de volúmenes
ni restaurar a ciegas el perfil histórico. Publicar resultados sanitizados en
un informe fechado separado.

## Pendientes conocidos

El sitio estático completo tiene un fallo anterior por un enlace del README
EngramHalo a `.dockerignore`, fuera de su allowlist. No ampliar ese permiso
para publicar datos privados. Los tests del generador pueden pasar aunque el
build del repositorio completo falle por ese enlace.

El bloqueo SSH de la herramienta de la estación no se elude con scripts. La
continuación se realiza desde la terminal autorizada del operador o mediante
una sesión del asistente ejecutada directamente en el Halo. Nunca guardar
contraseñas SSH en este repositorio ni en ejemplos de comandos.
