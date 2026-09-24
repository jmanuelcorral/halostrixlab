# Halo Control

[English](README.en.md) | [Proyecto](../../README.md) |
[Consolidación del 24 de septiembre](../../docs/halo-control-operacion.md)

Panel privado de operación para Strix Halo, como extensión de **Cockpit Linux**.
No es AI Toolbox Cockpit de kyuz0 ni la web pública estática del repositorio.

## Estado y límites

Implementación iniciada el 2026-09-22, consolidada el 2026-09-23:
interfaz React/TypeScript y PatternFly, ECharts,
terminal xterm.js, controlador de operaciones, telemetría y helper administrativo.
El panel se compiló y se probó con navegador real y fixtures autenticados.
Prometheus, node_exporter y el colector AMD se desplegaron en loopback;
Halogen no se detuvo durante la instalación inicial del panel. No se presupone
que esas unidades estén activas después de un reinicio.

La instalación inicial no tenía Cockpit ni agente de autenticación pkexec.
Posteriormente el operador instaló Cockpit y tmux, instaló el helper root y
confirmó el login PAM por HTTPS. Se comprobó el puente Cockpit con el controlador.
El operador reinició después y se observó un nuevo arranque. Cockpit necesitó
la reparación de FreeBind descrita en Recuperación, cuya eficacia confirmó el
operador. Eso no valida entrenamiento ni todas las rutas de mantenimiento.
Desplegar la interfaz no reinicia motores; sus acciones explícitas sí pueden hacerlo.

La consulta real de `checkupdates` sí completó como trabajo supervisado. Su
resultado es temporal, no una afirmación permanente sobre paquetes pendientes.

## Integración visual con Cockpit

Halo Control usa los colores y tipografía de PatternFly 6, sin paleta azul propia,
degradados ni selector de tema independiente. Sigue la preferencia `shell:style`
de Cockpit (`light`, `dark`, `auto`), los eventos `storage`/`cockpit-style` y la
preferencia del sistema cuando está en automático. No modifica esa preferencia.
Gráficas, logs, formularios y terminal se adaptan en vivo; cambiar tema no cierra
la consola. Las pruebas cubren ambos temas, cambios en vivo, anchura móvil y
contraste mínimo 3:1 de las series frente al fondo de las gráficas.

## Imágenes y estados de los motores

Las seis tarjetas usan arte original de los repositorios oficiales: mascota de
llama-swap, imagen de Halogen, logotipo Laya, símbolo de ComfyUI, logotipo de
Unsloth Studio y cabecera de LLaMA-Factory para LlamaBoard. Se sirven desde `public/engine-art/`,
sin CDN ni peticiones externas, con proporciones intactas y variantes oficiales
clara/oscura de Studio y Laya. Un fallo de imagen conserva el nombre y los controles.
`public/engine-art/ATTRIBUTION.txt` recoge procedencia, revisiones y condiciones,
con los avisos originales; las revisiones del arte no actualizan los motores.
También es accesible desde el enlace de atribuciones bajo las tarjetas.
Halogen mantiene sus condiciones propias y marcas de Peonist, no una licencia
MIT/Apache. La identificación de las integraciones no implica patrocinio.

Cada estado combina icono, texto y color con contraste mínimo 4.5:1:

- **Verde:** activo y HTTP disponible. Halogen muestra **Cargado** cuando su
  contenedor está presente y el gateway responde; no verifica carga completa
  del modelo, inferencia ni entrenamiento.
- **Rojo:** parado/descargado o fallo, diferenciados por texto e icono.
  Parado y detenido son sinónimos; una parada normal no se presenta como fallo.
- **Naranja:** pausado, iniciando/deteniendo, instancia anterior activa o HTTP
  sin confirmar. Un proceso en ejecución no garantiza disponibilidad.
- **Gris:** desconocido, no instalado o sin configurar, sin inferir una parada.

Las transiciones/fallos de las unidades Studio y LlamaBoard tienen prioridad
sobre el estado del contenedor. Las etiquetas explican su alcance y se actualizan
con el sondeo existente; las acciones y protecciones operativas no cambian.
Pruebas de navegador cubren carga local, imágenes fallidas, cambios de tema y
estado, contraste y anchuras 390/768/1024/1440.

## Laya en el gateway compartido

La tarjeta Laya muestra estado CPU, logotipo, **Arrancar Laya**, **Detener Laya**
y logs compartidos. Es la sexta tarjeta, no una sexta ficha editable.
Usa el llama-swap original de Halogen; no crea otro proxy ni arranca el gateway
implícitamente. El gateway debe estar activo. La parada rechaza peticiones en
curso y solo descarga Laya; el sondeo nunca autocarga un contenedor parado.
Una nueva petición externa sí puede recargarlo. Detener el gateway descarga ambos.
[Arquitectura](../inference/LAYA.md) y [pruebas paso a paso](../../docs/pruebas-laya.md).

## Avisos temporales

Los avisos generales y los resultados del editor usan toast de PatternFly, sin
librería Toastr adicional: 8 segundos, 12 para errores, cierre manual y hasta
cuatro visibles. Se deduplican por mensaje/tipo y respetan el tema de Cockpit.
No desplazan widgets. Los estados críticos, bloqueos de servicio y progreso de
actualización/reinicio siguen visibles en su sección; el historial de operaciones
permanece en Actividad aunque desaparezca el toast. No se guardan avisos en el navegador.

## Red y disposición de widgets

Resumen y Métricas incluyen gráficas de recepción y envío en Mbit/s, con selector
de interfaz y el mismo intervalo histórico que las demás gráficas. Usan las tasas
existentes de `/proc/net/dev`, sin pruebas activas de velocidad ni captura de
paquetes. No suman interfaces físicas, puentes y veth; las muestras ausentes
aparecen como huecos, no como cero. La selección inicial prioriza nombres que
no correspondan a loopback o puentes Docker habituales.

Los widgets tienen separación entre rejillas, tarjetas adaptables y cabeceras
que pueden ocupar varias líneas. Las leyendas quedan arriba, separadas del
control de zoom inferior. Pruebas de navegador comprueban colisiones y desbordes
a 390, 768, 1024 y 1440 píxeles de ancho.

## Disco: actividad, temperatura y ocupación

Resumen y Métricas incluyen histórico de espacio ocupado/disponible (GiB),
actividad de E/S (% de tiempo activo), lectura/escritura (MiB/s) y sensores de
disco NVMe/drivetemp accesibles en hwmon. Cada sensor se muestra por separado;
no se confunde la temperatura del controlador con todos los sensores internos.
La capacidad corresponde al sistema de archivos del workspace, no a la suma de
todos los discos. Las tasas se muestran por dispositivo físico sin duplicar
particiones, zram o device mapper. Tiempo activo no equivale a saturación NVMe.

**Analizar ocupación** ejecuta un trabajo manual de solo lectura con prioridad
CPU/E/S baja, hasta 120 segundos por raíz y profundidad de salida 3. Recorre
metadatos del usuario, workspaces IA, cachés, `/usr`, `/var` y `/opt` cuando
existen, sin seguir enlaces ni cruzar sistemas de archivos dentro de cada raíz.
No lee contenidos ni realiza limpieza. Muestra 25 carpetas principales con
barras y categorías orientativas por ruta, además de `docker system df`.
Los resultados quedan en la caché privada; no se recorre el disco cada 5 segundos.

Las carpetas incluyen sus descendientes y algunas raíces se solapan: no sumar
filas ni añadir los tamaños Docker (capas compartidas). Reflinks, snapshots,
metadatos y archivos borrados aún abiertos explican diferencias con el espacio
ocupado. Los permisos insuficientes o límites de tiempo se marcan como parciales,
nunca como cero. El primer análisis real encontró rutas parcialmente legibles;
no se elevó a root para inspeccionarlas. Los nombres de rutas también son privados.

## Fichas de motores, edición y secretos

Cada tarjeta abre **Ficha y logs** con configuración guardada, entorno observado
y registros. El entorno Docker corresponde al contenedor existente; un servicio
sin contenedor no tiene entorno efectivo disponible. LlamaBoard puede mostrar
logs del contenedor histórico, identificados como tales. Halogen comparte journal
con llama-swap y añade logs de su contenedor actual.

| Motor | Campos permitidos, solo detenido |
| --- | --- |
| llama-swap | Esperas de arranque/descarga y concurrencia global |
| Halogen | Contexto, salida, slots, pool KV y arena de prefill |
| ComfyUI | Reserva GPU, caché, VAE BF16, smart memory, hipBLASLt y AOTriton |
| LLaMA-Factory | Memoria compartida, modo HF offline y paralelismo de tokenizadores |
| Unsloth Studio | Memoria compartida, HF/Transformers offline y paralelismo de tokenizadores; recrea el contenedor detenido |

Para Halogen también debe estar detenido llama-swap, pues una petición puede
volver a cargar el modelo. Guardar valida tipos, rangos, estado de unidad y
contenedor, operaciones pendientes, bloqueo del launcher y revisión de origen.
No detiene ni arranca servicios. Los cambios se aplican en el próximo arranque
manual. No hay editor libre de comandos, rutas, imágenes, red o credenciales.
Los máximos permitidos no garantizan que una combinación quepa en memoria.

Studio se recrea mediante la API Docker local, sin secretos en argumentos ni
logs. Conserva la imagen por ID inmutable, configuración Docker, UID/GID, grupos,
dispositivos GPU, puertos, montajes, entorno, credenciales y configuración de red.
Solo cambia los campos permitidos solicitados. No actualiza imágenes ni borra
los datos persistentes; las contraseñas de la base de Studio no se restablecen.
Rechaza cambios no revisados en la capa escribible en vez de descartarlos.

El reemplazo se crea y verifica detenido antes de renombrar el original como
respaldo. Si falla el cambio de nombres, intenta restaurar el nombre original;
una transacción interrumpida bloquea nuevos arranques/ediciones para revisión.
Los registros privados 0600 están en `data/studio-recreation/`; los respaldos no
se eliminan automáticamente, tampoco después del primer arranque correcto.
Los dos contenedores comparten montajes: conservar el anterior **no equivale a
una copia de los datos**, ni revierte cambios de una futura ejecución. No arrancar
el respaldo simultáneamente. Compose puede sobrescribir las opciones del panel;
reconciliar su fuente antes de usarlo para recrear Studio.

Se detuvo y recreó Studio con sus valores existentes y se comprobó la igualdad
de imagen, entorno, montajes, permisos, dispositivos y red. Quedó detenido con
el original conservado. No se arrancó durante esa recreación porque Halogen
seguía cargado. Posteriormente se observaron operaciones `switch-studio`
completadas, cuyo criterio incluye `/api/health`; no validan entrenamiento ni
constituyen una garantía permanente de salud del contenedor.

ComfyUI y LlamaBoard leen opciones privadas de `inference/data/` en cada arranque.
El adaptador de llama-swap está limitado al launcher revisado
`start-coder-halogen.py` y su configuración JSON `gateway-coder-halogen-noauth.yaml`.
Descubre el perfil desde el comando activo, no desde una referencia histórica.
El launcher privado debe mantener `service_options.lease('gateway')` y heredar
su descriptor al ejecutar llama-swap; si no coincide, rechaza el adaptador.
Se añadió ese guard al launcher local, con copia privada, sin reiniciar el gateway.
En otro despliegue hay que revisar el adaptador y el guard, no adivinar la fuente.
Al editar Halogen se crea un perfil inmutable nuevo y se cambia atómicamente
el puntero de configuración del gateway junto con metadatos y concurrencia,
tras `llama-swap -validate`. Los perfiles anteriores se conservan.
Hay copias privadas antes de reemplazar archivos (0600); no se purgan automáticamente.
El historial registra nombres de campos, nunca sus valores.

**Mostrar secretos y valores privados** revela bajo demanda los valores
configurados disponibles dentro de la sesión Cockpit. Incluye el entorno del
proceso llama-swap cuando PID, ejecutable y propietario coinciden; no consulta
bases de contraseñas de Studio ni archivos `.env` ajenos. Al cambiar de pestaña
o salir de la ficha se ocultan, sin localStorage ni historial de valores.
Los logs se refrescan cada 3 segundos, admiten pausa y filtro y están limitados
a 250 líneas por fuente y 80 KB de respuesta. La redacción es orientativa:
pueden contener prompts u otros datos privados, no compartirlos sin revisar.

Pruebas: guardado y conflictos con archivos sintéticos privados, comandos de
arranque y navegador con puente simulado. Las consultas de las cinco fichas y
logs se verificaron en el host sin imprimir secretos. No se cambió la
configuración activa de Halogen ni se validó un nuevo arranque GPU.

## Componentes

| Pieza | Función |
| --- | --- |
| `frontend/` | Resumen, servicios, gráficas, logs, terminal, actualizaciones y actividad |
| `control.py` | Acciones cerradas, estado, SSE de llama-swap, operaciones systemd y auditoría SQLite |
| `engine_details.py` | Fuentes fijas, validación, revisión optimista, secretos bajo demanda y logs |
| `studio_recreate.py` | Recreación de Studio detenido y registros privados de recuperación |
| `llamafactory.py` / `unsloth.py` | Launchers manuales y verificación de ownership/lease GPU |
| `reboot.py` | Parada supervisada, reserva temporal y verificación previa al helper root |
| `storage.py` | Análisis de metadatos de disco e inventario Docker bajo demanda |
| `metrics.py` | CPU, memoria, hwmon, GTT/VRAM, red, disco y PSI; endpoint Prometheus |
| `install.py` | Paquete Cockpit, unidades manuales de ComfyUI/Studio/LlamaBoard y métricas |
| `install_metrics.py` | Binarios Prometheus/node_exporter con SHA256 verificado, unidades loopback |
| `maintenance.py` | Helper root limitado a actualización completa, informe y reinicio |
| `install-system.sh` | Helper root y socket Cockpit, loopback por defecto o LAN privada explícita |
| `repair-cockpit.sh` | Recuperación idempotente del socket mediante FreeBind, sin tocar el firewall |

Cockpit autentica con cuentas del sistema. La aplicación usa su API documentada
para ejecutar el controlador como usuario; no abre un servidor REST privilegiado
ni monta el socket Docker en un servidor web. El controlador del operador sí
puede gestionar Docker: ese usuario ya tiene autoridad equivalente a root.
No hay RBAC independiente ni aislamiento adicional respecto a esa cuenta.

## Preparación

Requisitos del host: Linux Strix Halo, Python 3.12+, Docker, systemd de usuario,
`checkupdates`, `journalctl`. Para el frontend: Node 22.12+ y npm; el lockfile
fija las dependencias. Se usó npm 11.6.0 para evitar un fallo del resolver 10.9.

Desde este directorio:

```bash
npm ci --ignore-scripts
npm test
npm run build
python3 install.py --start-metrics
```

El instalador no sobrescribe unidades con contenido diferente, no cambia
llama-swap y no habilita arranque automático de ComfyUI. El paquete se instala
en `~/.local/share/cockpit/halo_control`. `dist/` y dependencias no se publican.
La advertencia de Vite sobre `../base1/cockpit.js` es esperada: lo proporciona
Cockpit en tiempo de ejecución. ECharts se empaqueta por separado.

Editar **privadamente** `data/config.json`, modo 0600:

```json
{
  "gateway_url": "http://127.0.0.1:18080",
  "comfyui_bind": "127.0.0.1",
  "model": "flash-halogen",
  "admin_key_file": "",
  "drain_timeout": 120,
  "ssh_hosts": []
}
```

Usar el origen real del gateway en la configuración privada; solo se aceptan
IPs privadas/loopback, no URLs con credenciales o rutas. Si requiere clave,
`admin_key_file` apunta a un fichero privado del operador; no se envía al
navegador. Para cambiar el bind de ComfyUI, revisar también su unidad generada;
el instalador rechaza reemplazar silenciosamente una unidad diferente.
Para operar desde otro ordenador, poner la misma `<IP_LAN_PRIVADA>` en
`comfyui_bind` y en `--bind` de `halo-comfyui.service`, recargar systemd de
usuario y reiniciar ComfyUI solo con la cola vacía. El enlace del panel deriva
de esa configuración: no se debe publicar un enlace loopback a clientes remotos.
ComfyUI queda accesible en `http://<IP_LAN_PRIVADA>:8188`, sin autenticación
propia ni TLS; el login de Cockpit no protege ese puerto independiente.
Solo LAN de confianza, sin redirección en el router. El default público sigue
siendo loopback; la dirección real se conserva únicamente en archivos privados.

## Activación del login web en un host nuevo

Desde una terminal administrativa local, revisar primero los avisos de CachyOS,
el estado de trabajos y las condiciones de una actualización completa. No hacer
una actualización parcial de Arch. Instalar Cockpit y tmux con el gestor de la
distribución en esa ventana, por ejemplo:

```bash
sudo pacman -Syu --needed cockpit tmux
sudo bash workspaces/halo-control/install-system.sh
```

El segundo comando se ejecuta desde la raíz del repositorio. Revisar el script
antes de darle privilegios. Instala una copia root-owned del helper; nunca se
invoca código editable del repositorio como root desde la web.

La autenticación usa **usuario y contraseña locales de Linux mediante PAM de
Cockpit**, no una base de contraseñas propia. El instalador verifica que exista
`/etc/pam.d/cockpit`; no lee shadow ni reemplaza políticas PAM. Entrar como el
operador que tiene instalado el paquete web y las unidades de inferencia.
La contraseña se introduce solo en el login HTTPS de Cockpit, nunca en el chat.

Para acceso LAN explícito, el instalador admite una IPv4 privada como argumento:

```bash
sudo bash workspaces/halo-control/install-system.sh <IP_LAN_PRIVADA>
```

No acepta `0.0.0.0` ni direcciones públicas. UFW no se modifica: autorizar el
puerto TCP 9090 únicamente desde la subred de confianza mediante administración
local. Verificar/confiar en el certificado antes de introducir credenciales.
El instalador rechaza overrides previos para no sobrescribir configuración.
El socket usa `FreeBind=yes` para poder arrancar antes de que Wi-Fi/DHCP asigne
la IP privada configurada, sin escuchar en todas las interfaces. En instalaciones
anteriores, si el journal indica `Cannot assign requested address`, añadir desde
una terminal administrativa un drop-in independiente `[Socket]` con
`FreeBind=yes`, recargar systemd y reiniciar `cockpit.socket`. Esto no fija la IP
por DHCP: mantener una reserva de dirección para el host.

El socket predeterminado queda en `127.0.0.1:9090`. Usar un túnel SSH aprobado
para acceder por HTTPS, o configurar explícitamente una dirección LAN autorizada
y un certificado confiable. No exponerlo a Internet ni desactivar comprobaciones
TLS. No se cambia firewall, router, contraseña de usuario ni política polkit.
Un usuario con login sin contraseña local puede necesitar configurar una
credencial válida para Cockpit; eso es un paso administrativo, no automático.

Tras autenticarse, abrir **Tools → Halo Control**. No servir este panel como una
carpeta pública: fuera de Cockpit muestra una vista previa con acciones bloqueadas.
Las acciones se ejecutan con un clic, sin diálogo ni texto de confirmación,
por preferencia del operador del laboratorio. Se bloquean dobles envíos y se
mantienen las comprobaciones de cola, exclusión GPU y permisos en backend.
La actualización abre la consola de inmediato. El reinicio es una excepción:
requiere confirmación explícita y advierte que interrumpirá trabajos IA activos.
Los permisos administrativos siguen solicitándose a Cockpit; no se elimina PAM,
polkit ni las preguntas interactivas de pacman. El aviso de pegado multilínea en
terminal se mantiene separado de las confirmaciones de operaciones.

## Métricas e histórico

El colector consulta cada 5 segundos sin GPU de cómputo ni comandos root. Conserva
hasta 15 días/259200 muestras en SQLite como caché del panel, con consultas
acotadas a unas 900 muestras. Prometheus almacena además series estándar con
retención de 15 días y límite 2 GB. No sumar RAM, GTT y VRAM como memorias
independientes. Valores ausentes son desconocidos, no cero; sensores se muestran
con nombre y unidad. La potencia puede corresponder al paquete/APU.

Para reproducir las descargas, desde la raíz del repositorio:

```bash
gh release download v1.12.1 -R prometheus/node_exporter -p node_exporter-1.12.1.linux-amd64.tar.gz -p sha256sums.txt --dir workspaces/halo-control/data/node-release
gh release download v3.14.0 -R prometheus/prometheus -p prometheus-3.14.0.linux-amd64.tar.gz -p sha256sums.txt --dir workspaces/halo-control/data/prometheus-release
python3 workspaces/halo-control/install_metrics.py
```

Los checksums se verifican antes de extraer solo binarios regulares. No se instala
software global. Endpoints locales: colector `19100`, node_exporter `19101`,
Prometheus `19090`. Ninguno se publica en LAN. Las unidades se arrancan pero no
se habilitan al boot automáticamente. Si se desea persistencia, revisar y habilitar
las tres unidades de métricas como usuario; no habilitar ComfyUI por defecto.

## Servicios IA y limitación de drenaje

Las acciones se serializan y ejecutan mediante `systemd-run --user`: sobreviven
al cierre del navegador. Se conserva actor UID, estado, tiempo y error; no hay
endpoint shell genérico. Jobs pendientes/running bloquean nuevos cambios.

- Halogen se carga con una petición corta por llama-swap, no arrancando otro motor.
- Descargar Halogen no evita que una petición posterior lo vuelva a cargar.
- ComfyUI conserva el lock de GPU del workspace y offload de memoria corregido.
- Se comprueba cola ComfyUI y se rechaza parada con trabajos activos/pendientes.
- Se comprueban solicitudes llama-swap mediante su snapshot SSE antes de parar.
- **No hay bloqueo global de admisiones del endpoint existente.** Una petición
  puede entrar entre comprobar actividad y parar. v255 drena como máximo 30 s
  tras SIGTERM: reservar los clientes antes de cambiar. No prometer ausencia de
  cancelación frente a clientes externos o carreras de último instante.
- La exclusión es cooperativa; contenedores/procesos externos pueden ignorarla.
- Una transición fallida no reinicia automáticamente otro motor a ciegas.

Si un job queda antiguo se muestra `unknown`; comprobar journal y procesos antes
de repetir. Los logs de unidades nuevas sobreviven al contenedor `--rm` según
la política de journald del host. El visor muestra hasta 250 líneas con filtro,
pausa y descarga; no es búsqueda ilimitada ni retención garantizada entre boots.
No se registra una terminal íntegra; logs IA pueden contener prompts privados.

## Unsloth Studio existente

La tarjeta Unsloth Studio adopta el contenedor local
`halostrix-unsloth-studio-studio-1`, no una instalación nueva. `unsloth.py`
verifica labels de proyecto/servicio, revisión upstream, imagen y UID no-root
antes de operar. El adaptador de estado limita su inspección a identidad, estado
y binding. La ficha y la recreación sí consultan el entorno del contenedor, lo
ocultan por defecto y preservan credenciales sin publicarlas. Si falta o es ajeno,
el arranque falla sin crear datos, reconstruir imágenes ni detener otros motores.

La unidad manual `halo-unsloth.service` ejecuta `docker start --attach` y conserva
la reserva `inference/data/gpu.lock` durante toda la sesión. La parada usa el ID
verificado y conserva el contenedor, volúmenes, base de autenticación y proyectos.
El enlace se deriva de la dirección LAN/loopback ya configurada en el contenedor,
puerto interno 8888. Se comprueba `/api/health`; logs nuevos van a journald y
aparecen en el selector de logs del panel. No se modifica el firewall ni la
contraseña: Studio mantiene su propio login, independiente del de Cockpit.

- **Arrancar Studio** requiere gateway y motores GPU parados.
- **Cambiar a Studio** revisa primero que Studio exista; después comprueba/detiene
  ComfyUI y drena/detiene el gateway antes de arrancarlo.
- **Detener Studio** es una parada explícita que puede interrumpir entrenamiento,
  exportaciones o inferencia: finalizarlos dentro de Studio primero. No existe
  todavía un contrato autenticado de detección de todos sus trabajos activos.
- Mientras Studio esté activo, texto/imágenes siguen bloqueados hasta detenerlo.
  **Cambiar a LlamaBoard** es una parada explícita de Studio y puede interrumpir
  entrenamiento; es la excepción deliberada a ese bloqueo.
- Los scripts originales fuera del panel no adquieren el lock y pueden saltarse
  la exclusión cooperativa; no usarlos en paralelo. Detener Studio antes de
  actualizar; el reinicio confirmado lo detiene automáticamente. No confiar en
  detección genérica de procesos para proteger entrenamiento arbitrario.

Inventario observado: imagen local de aproximadamente 51 GB, PyTorch 2.11/ROCm
7.14, revisión `e18a069c15cde98c7af77ccdb952254db8b0315d`, contenedor detenido
con datos persistentes existentes. No se leyó el `.env` real ni se migraron datos.
La evidencia histórica valida UI y GPU, no entrenamiento; `bitsandbytes` no estaba
instalado, por lo que no se promete QLoRA 4-bit. Integración cubierta con pruebas
de ownership, bloqueo GPU, orden de cambio y tarjeta/enlace en navegador.
No se arrancó Studio ni se interrumpió Halogen para añadir la tarjeta.

## LLaMA-Factory / LlamaBoard

La tarjeta LLaMA-Factory incluye arranque, parada explícita, cambio desde
inferencia/imágenes, estado, logs y enlace LAN. `llamafactory.py prepare --bind
<IP_LAN_PRIVADA>` inspecciona el contenedor histórico y guarda un pin privado
del ID de imagen y su raíz de datos. Nunca lee el `.env` ni reconstruye imágenes.
Verifica revisión `7af909522a951e3ad9f022ea6f88b6755257eaa5`, origen upstream y
labels Compose del contenedor original, que carece de los labels nuevos del
workspace. Solo acepta los siete bind mounts del layout revisado y directorios
escribibles por el operador, sin cambiar ownership. Al arrancar también monta
cache/config en `/workspace/llamaboard_cache` y `/workspace/llamaboard_config`,
las rutas relativas que utiliza la aplicación, sin hacer escribible todo `/workspace`.

El contenedor histórico permanece parado e intacto. El launcher crea un
contenedor distinto `halostrix-llamaboard-panel`, no-root, con capabilities
retiradas, no-new-privileges, dispositivos GPU explícitos y bind a una IPv4
privada concreta en 7860; no hereda el antiguo bind `0.0.0.0` ni usuario root.
Reutiliza exactamente la imagen de unos 50,4 GB y datos existentes. La unidad
manual `halo-llamafactory.service` conserva el lock GPU y registra salida en
journald; parar elimina solo el nuevo contenedor efímero, nunca pesos/datasets.

No tiene autenticación propia: solo LAN de confianza y sin exposición Internet.
El login de Cockpit no protege el puerto 7860. La UI no arranca entrenamientos
por sí sola. Finalizar entrenamiento/exportaciones antes de pulsar detener;
no se conoce automáticamente su cola. Si LlamaBoard (nuevo o antiguo) está
activo, el panel bloquea cambios hacia Halogen, ComfyUI y Unsloth hasta parada
explícita. No usar los launchers antiguos en paralelo al panel.

Cambiar a LlamaBoard detiene ComfyUI y gateway tras sus comprobaciones de
actividad, y detiene explícitamente Studio antes de arrancar LlamaBoard. Esta
acción puede interrumpir entrenamiento en Studio; finalizarlo antes de cambiar.
Arrancar LlamaBoard (sin cambiar) sigue rechazando otros motores activos.
El enlace configurado permanece visible y se distingue de la salud HTTP.

El arranque real no-root fallaba por permisos en `llamaboard_cache`; corregidos
sus montajes persistentes, se verificó el arranque y HTTP 200 sin detener otros
motores (ya estaban parados). El entrenamiento sigue sin validación. Las pruebas
simuladas cubren orden de parada, fallos y enlace antes de disponibilidad HTTP.

## Terminal y mantenimiento

Terminal xterm.js conectada a PTY Cockpit del usuario. Destinos SSH proceden de
aliases en `ssh_hosts`, con clave del host estricta y sin agent forwarding.
Registrar previamente el host de forma confiable; no aceptar automáticamente
claves desconocidas. No guardar claves SSH en JavaScript. Abrir terminal es
acceso real a todos los permisos de esa cuenta. Cerrar sesión desmonta el PTY;
las actualizaciones usan tmux root separado para poder reconectar.

**Aplicar actualización completa** abre y desplaza la vista a una consola dentro
de Actualizaciones, no a la terminal SSH genérica. Muestra estado de conexión,
salida estándar/error, preguntas de pacman y códigos de cierre. Si Cockpit
rechaza permisos, activar su acceso administrativo y reconectar; si IA está
activa, detenerla explícitamente antes de reintentar. La ausencia de salida no
se presenta como éxito ni como actualización iniciada.

La consola conserva su conexión al navegar por el panel y no se cierra por
inactividad durante mantenimiento. Cerrar el visor no cancela tmux. Reconectar
se une a la sesión si existe, pero puede iniciar otra actualización si terminó;
no es una consulta de estado. Las pruebas de salida, rechazo y entrada interactiva
usan un puente simulado; no se ejecutó pacman para validar la interfaz.

El reinicio confirmado comprueba acceso administrativo antes de detener nada,
comprueba primero si la sesión tmux de actualización sigue abierta, consulta el
informe de actualización y prepara la parada como trabajo supervisado. Una sesión
terminada puede estar esperando Enter y seguir bloqueando el reinicio. El botón
**Ver sesión de actualización existente** solo conecta a esa sesión, sin iniciar
pacman; si muestra el final y pide Enter, pulsarlo cierra la sesión. Si sigue
trabajando, esperar. No se mata tmux ni se envía Enter automáticamente.
Detiene las cuatro unidades IA, contenedores de inferencia gestionados y los
contenedores Studio/LlamaBoard verificados, incluido LlamaBoard histórico si está
activo. Esta parada puede interrumpir generaciones y entrenamientos; no espera a
vaciar colas. No borra contenedores persistentes ni datos. Si falla una parada o
queda un estado desconocido, no solicita reiniciar. Las operaciones del panel
quedan bloqueadas temporalmente durante la preparación y verificación final.

No detiene gestores de paquetes ni procesos ajenos arbitrarios. El helper root
mantiene sus comprobaciones finales de procesos, locks y sesión tmux; un rechazo
se muestra sin declarar éxito. Sin acceso administrativo Cockpit, no se paran
servicios. La orden aceptada se distingue de un reinicio confirmado: solo un
nuevo identificador de arranque confirma el resultado al reconectar.
Tras solicitarlo aparece una cuenta atrás con reintentos cada 5 segundos y
límite de 10 minutos. Sigue visible por encima del iframe aunque Cockpit oculte
el panel al desconectarse. Consulta el identificador de arranque sin permisos
administrativos; si el puente cae, comprueba la web del mismo origen sin caché.
Cuando la web vuelve tras una caída (o responde pasados 30 segundos), recarga
Cockpit una sola vez para restablecer el puente; una respuesta web por sí sola
no confirma un reinicio. Si el arranque cambia con el puente conectado, recarga
tras 2 segundos. Nunca reenvía la orden ni arranca motores automáticamente.
El recibo se conserva en sessionStorage, sin credenciales, y permite comprobar
el nuevo arranque después del refresco. Cockpit puede pedir iniciar sesión de
nuevo; no se elude su autenticación. Al vencer el plazo se muestra un aviso,
sin bucles de recarga. Cerrar seguimiento no cancela el reinicio solicitado.
Si se pierde la sesión del navegador, puede perderse la verificación automática.
Las pruebas de reinicio son simuladas: no se reinició el host al desplegar.

El helper instalado exige root y copia root-owned no escribible por terceros.
Solo permite cuatro acciones fijas. Actualizar:

1. Drenar y detener IA antes de solicitarlo; el helper rechaza procesos conocidos.
2. Pulsar la acción y obtener autorización administrativa Cockpit si se requiere.
3. Verificar disco (mínimo 10 GiB) y ausencia del lock de pacman.
4. Abrir/reconectar tmux con `pacman -Syu`, interactivo y sin `--noconfirm`.
5. Conservar resultado en `/var/log/halo-control/last-update.json`.

Nunca elimina locks, ejecuta AUR como root ni promete rollback. No hay snapshot
Btrfs automático: validar recuperación y `/boot` por separado. El reinicio rechaza
IA y sesión de actualización abiertas. No se ejecutó en la validación local.
La detección de procesos es una precaución, no una barrera contra otros usuarios.

Consultar imágenes solo inspecciona manifiestos y referencias locales; muestra
la evidencia para comparar plataformas, sin afirmar igualdad entre manifest-list
y digest de una arquitectura. No descarga ni cambia imágenes o pins.

## Pruebas y seguridad

```bash
python3 -m unittest discover -s workspaces/halo-control/tests -v
python3 -m unittest discover -s scripts/tests -p 'test_inference*.py' -v
```

Desde el workspace:

```bash
npm test
npm run build
npx playwright install chromium
npm run test:browser
npm audit
```

Revisión 2026-09-24: 101 tests Python del panel, 57 de inferencia, 50 unitarios
frontend, 40 Playwright y 14 fixtures del sitio. Incluyen editor/recreación,
transiciones, enlaces, avisos, temas, móvil y reinicio confirmado simulado.
La auditoría npm consultada no encontró vulnerabilidades; no equivale a pentest,
prueba de autenticación real ni validación de seguridad de updates/reinicio.

Sin Node global, desde el workspace se puede usar el binario privado ya instalado:

```bash
data/node node_modules/typescript/bin/tsc --noEmit
data/node node_modules/vitest/vitest.mjs run frontend
data/node node_modules/vite/bin/vite.js build
PATH="$PWD/data:$PATH" PLAYWRIGHT_BROWSERS_PATH="$PWD/data/browsers" data/node node_modules/@playwright/test/cli.js test
python3 install.py
```

No descargar herramientas nuevas ni reiniciar servicios de IA solo para documentar
resultados. El instalador copia el frontend; cambios del colector requieren un
reinicio explícito de su unidad de telemetría, no de los motores.

La web pública sigue fallando por un enlace EngramHalo previo fuera de allowlist;
no se amplió esa frontera para publicar paneles, datos o instalaciones privadas.

## Recuperación

### Web inaccesible después de reiniciar

En el reinicio observado el 2026-09-23, Cockpit intentó escuchar antes de que
Wi-Fi tuviera su IP y quedó `failed`, con `Cannot assign requested address`.
La IP llegó después, pero no había listener 9090. La regla UFW guardada permitía
la LAN y no se registraron bloqueos recientes; no se pudo leer el ruleset activo
sin root. El operador confirmó la recuperación al ejecutar, desde la raíz:

```bash
sudo bash workspaces/halo-control/repair-cockpit.sh
```

El script crea `halo-freebind.conf` con `FreeBind=yes`, conservando IP/puerto y
otros overrides. Rechaza enlaces simbólicos, permisos inseguros o un archivo
existente diferente; recarga systemd, habilita/reinicia `cockpit.socket` y
consulta UFW. No cambia reglas, certificados ni credenciales y no reinicia el
host. En caso de fallo muestra estado y journal. Mantener una reserva DHCP;
FreeBind no asigna una IP. No se comprobó otro reboot tras esta reparación.

### Telemetría después del arranque

El colector se recuperó manualmente después del reinicio. Para habilitar la
telemetría ya instalada, como operador y tras revisar sus unidades:

```bash
systemctl --user enable --now halo-metrics.service halo-node-exporter.service halo-prometheus.service
```

Esto no habilita los motores GPU. Para arranque sin sesión de usuario también
hay que verificar la política de linger del operador; no se cambia automáticamente.
No afirmar que Prometheus está activo solo porque el panel conserva muestras.

### Retirar el panel sin perder datos

Detener las unidades `halo-metrics`, `halo-node-exporter` y `halo-prometheus`
para retirar telemetría. Quitar el paquete de usuario solo después de respaldar
su configuración. No borrar `data/`, modelos ni unidades de inferencia existentes.
No detener Cockpit desde su propia terminal durante una operación de mantenimiento.
Una actualización en tmux puede seguir aunque el navegador se desconecte.

Fuentes: [Cockpit](https://cockpit-project.org/),
[ECharts](https://echarts.apache.org/), [xterm.js](https://github.com/xtermjs/xterm.js),
[Prometheus](https://github.com/prometheus/prometheus),
[node_exporter](https://github.com/prometheus/node_exporter).
