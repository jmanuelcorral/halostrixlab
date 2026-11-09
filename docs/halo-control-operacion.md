# Halo Control, ComfyUI y Laya: consolidación del 24 de septiembre de 2026

[English](en/halo-control-operations.md) | [Proyecto](../README.md) |
[Manual de Halo Control](../workspaces/halo-control/README.md) |
[Inferencia y ComfyUI](../workspaces/inference/README.md)

Este informe reúne lo implementado, observado y corregido durante el trabajo de
los días 22 a 24. No sustituye el [despliegue Halogen del 17 de septiembre](despliegue-halogen-128k.md)
ni el baseline histórico de Lemonade. No es una auditoría permanente: consultar
el panel y los logs para conocer el estado actual. No contiene configuración
privada ni autoriza cambios sobre otro host.

## 1. Arquitectura y superficies de acceso

- **Halo Control** es una extensión de Cockpit Linux: React/TypeScript,
  PatternFly 6, ECharts y xterm.js. Cockpit autentica al usuario Linux mediante
  PAM y ejecuta operaciones fijas del controlador Python como ese usuario.
- **AI Toolbox Cockpit de kyuz0** es otra herramienta, una TUI de gestión de
  modelos/runtimes. No es el servidor web Cockpit Linux.
- **llama-swap** gestiona un único gateway para Halogen GPU y Laya CPU. ComfyUI, Studio y
  LlamaBoard usan launchers y unidades manuales con reserva GPU cooperativa.
- Las operaciones se serializan, se ejecutan como trabajos systemd de usuario
  y quedan registradas en SQLite. Los cambios de configuración usan adaptadores
  fijos y payloads por stdin, no un editor libre de comandos.
- Las actualizaciones y el reinicio usan una copia root-owned del helper
  administrativo. El código mutable del repositorio no se eleva desde el panel.
- El sitio público es documentación estática, no el panel operativo. No lleva
  credenciales, inventarios privados, telemetría, screenshots ni archivos `data/`.

| Servicio | Acceso documentado | Límite de seguridad |
| --- | --- | --- |
| Cockpit Linux | `https://<IP_LAN_PRIVADA>:9090` | PAM/TLS; verificar certificado |
| llama-swap | `http://<IP_LAN_PRIVADA>:18080/ui/` | Excepción privada LAN; no default público |
| Laya | Mismo origen 18080, `/upstream/laya/v1/systemone` | Hereda la política de acceso de Halogen; backend 18181 solo loopback |
| ComfyUI | `http://<IP_LAN_PRIVADA>:8188` | Sin autenticación propia ni TLS |
| Unsloth Studio | Puerto publicado del contenedor, normalmente 8888 | Login propio de Studio |
| LlamaBoard | `http://<IP_LAN_PRIVADA>:7860` | Sin autenticación propia ni TLS |
| Métricas | Loopback 19100, 19101 y 19090 | Colector, node_exporter y Prometheus |

El login de Cockpit no protege los puertos directos de las interfaces IA. No
exponerlos a Internet. Un operador con acceso Docker ya tiene autoridad
equivalente a root; el panel no añade aislamiento frente a esa cuenta.

## 2. Imágenes con ComfyUI

Se preparó una imagen kyuz0 fijada por digest, ComfyUI 0.31.0, PyTorch
`2.14.0a0+rocm7.15.0a20260721`, con 30 workflows. La imagen observada ocupaba
21,8 GB; el tag `latest` no garantiza repetir esas versiones. El pin y todos
los datos persisten privadamente bajo `workspaces/inference/data/comfyui/`.

Se añadió el descargador aislado de Qwen Image 2512 BF16: no usa GPU, ejecuta los
helpers de la imagen fijada, tiene lock propio y no monta el HOME real.

| Archivo de modelo | Tamaño observado aproximado |
| --- | --- |
| `diffusion_models/qwen_image_2512_bf16.safetensors` | 40,86 GB |
| `text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors` | 9,38 GB |
| `vae/qwen_image_vae.safetensors` | 0,25 GB |
| `loras/Qwen-Image-2512-Lightning-4steps-V1.0-bf16.safetensors` | 0,85 GB |

Total: 51,35 GB decimales, aproximadamente 47,82 GiB. Se revisaron cabeceras y
longitudes safetensors, no hashes criptográficos independientes. El workflow
privado tenía una LoRA Edit-2511 incorrecta; se sustituyó por Image-2512 y se
revisaron los enlaces del grafo. Los workflows upstream no se modifican al copiarlos.

La primera generación con `--gpu-only` agotó GTT durante el parcheado LoRA y
terminó con salida 139. Se permitió offload a CPU y se dejó reserva de 4 GiB,
sin cambiar BIOS, kernel ni GTT. Una generación real de 1024², batch 1 y cuatro
pasos produjo un PNG válido en unos 45 s de servidor. Después se restauró Halogen
y se verificó una respuesta HTTP 200. No demuestra estabilidad prolongada,
entrenamiento, cancelación GPU ni capacidad concurrente de ambos motores.

## 3. Operación de motores y editor

| Botón / operación | Comportamiento |
| --- | --- |
| `ON graceful` en Halogen | Rechaza ComfyUI ocupado, lo detiene, arranca gateway y carga Halogen con una petición breve |
| `ON graceful` en ComfyUI | Drena solicitudes del gateway, lo detiene y arranca ComfyUI |
| Cambiar a Studio | Prevalida Studio, comprueba/detiene ComfyUI y gateway; LlamaBoard activo bloquea |
| Cambiar a LlamaBoard | Prevalida destino, comprueba/detiene ComfyUI y gateway, detiene Studio y verifica antes de arrancar |
| Arrancar Laya | Carga CPU mediante el gateway existente, que debe estar activo; no cambia motores GPU |
| Detener Laya | Rechaza peticiones activas del gateway y descarga solo Laya; una petición posterior puede recargarlo |
| Arrancar sin cambiar | No debe interpretarse como autorización para detener otro motor |
| Detener entrenamiento | Puede interrumpir trabajo; no hay detección autenticada completa de todos los jobs |

`ON graceful` solo cambió el texto de los botones. No significa que siempre espere
cualquier cola: ComfyUI ocupado bloquea el cambio, y el gateway tiene carreras
con clientes externos y un drenaje final limitado por llama-swap. Studio activo
bloquea cambios a texto/imágenes; la excepción explícita es cambiar a LlamaBoard,
que puede interrumpir entrenamiento en Studio. No usar launchers externos en paralelo.

Hay seis tarjetas. Las cinco fichas originales muestran configuración, entorno
disponible y logs; Laya añade estado, arranque/parada y logs compartidos, sin
editor propio de parámetros. Los secretos
se revelan solo bajo demanda en Cockpit, sin persistencia en el navegador ni
valores en auditoría. Logs: journal y contenedor verificado, 250 líneas por fuente,
80 KB de respuesta, pausa/filtro. La redacción no garantiza eliminar prompts o
secretos arbitrarios de los logs.

El editor solo permite campos validados con el servicio detenido. Halogen exige
gateway detenido y sigue el perfil del comando activo, no una referencia histórica.
Crea un perfil nuevo, valida el gateway candidato y cambia su puntero atómicamente,
con copias privadas. ComfyUI/LlamaBoard leen opciones privadas al arrancar.

Studio se recrea detenido para aplicar variables permitidas, conservando imagen
inmutable, UID/GID, dispositivos, montajes, credenciales, entorno y red. Se conserva
el contenedor anterior y un registro de transacción privado. Una transacción
pendiente bloquea nuevos arranques/ediciones. Ambos contenedores comparten datos:
**no es un backup de datos**. La recreación no prueba salud ni entrenamiento.

LlamaBoard fallaba al crear `llamaboard_cache` bajo `/workspace` no escribible.
Se añadieron montajes de sus directorios persistentes en las rutas relativas de
caché/configuración, sin hacerlo root ni abrir todo el workspace. Se verificó
arranque no-root y HTTP 200. El enlace configurado ahora siempre se muestra,
indicando por separado detenido, HTTP pendiente o disponible. Entrenamiento pendiente.

## 4. Laya CPU concurrente con Halogen

Se desplegó Laya 0.3.9 multilingual (322M) en Docker, PyTorch 2.8.0 CPU y
Transformers 4.57.6, código/pesos fijados por revisión e imagen por ID inmutable.
Usa 4 CPU de cuota, 8 GiB de límite, no-root, sin dispositivos GPU ni socket
Docker, pesos de solo lectura y configuración/tokenizador temporal para compatibilidad.
La inferencia no descarga archivos; modo offline no equivale a firewall de salida.

La primera instalación creó un proxy separado. **Se corrigió:** Laya pertenece
ahora al llama-swap original, grupo CPU no exclusivo y persistente; la unidad
`halo-laya.service` quedó archivada y el puerto 18081 cerrado. Se preservaron
comandos/perfil de Halogen y la política privada de acceso. Aplicar la migración
requirió parar el gateway tras comprobar actividad y recargar Halogen. El límite
global permite sus cuatro slots más una petición CPU; captura de cuerpos desactivada.

Se comprobaron respuestas reales simultáneas, catálogo con ambos motores y
parada/arranque de Laya sin cambiar ID/arranque de Halogen. Parar el gateway
compartido sí descarga ambos, también al cambiar a ComfyUI/Studio/LlamaBoard.
Los botones de Laya no arrancan implícitamente el gateway. El sondeo del panel
no autocarga un Laya parado; salud HTTP verde no acredita precisión de decisiones.

Mediciones iniciales: unos 1,62 GiB de contenedor, 4,3-5,4 s de primera carga y
56-80 ms en peticiones calientes sintéticas. Son muestras históricas, no un SLA.
No hay pipeline Laya → Halogen, selección automática de motor, fine-tuning ni
calibración de negocio; ese flujo se implementará fuera de este proyecto.

[Guía completa de pruebas Laya](pruebas-laya.md): tests sintéticos, HTTP real con
`choice`/`score`/`noul`, errores 422/413, coexistencia opcional, controles del panel
y diagnóstico. [Manual de despliegue](../workspaces/inference/LAYA.md).

## 5. Interfaz y telemetría

- Tema claro/oscuro/automático de Cockpit, colores y tipografía PatternFly, sin
  selector independiente. Gráficas y terminal se repintan sin reconectar la consola.
- Seis tarjetas con arte oficial local, revisiones y avisos de licencia/marca.
  Sin CDN, recortes ni filtros; Laya/Studio usan variantes claras y oscuras.
- Estados con icono y texto: verde activo/cargado, rojo parado/fallo, naranja
  pausa/transición/sin disponibilidad y gris desconocido; contraste de texto 4.5:1.
  Parado y detenido son sinónimos, no una distinción inventada del backend.
- Espaciado corregido en tarjetas, rejillas, cabeceras, leyendas y zoom; pruebas
  de colisiones a 390, 768, 1024 y 1440 píxeles. Series con contraste mínimo 3:1.
- Avisos toast PatternFly, no librería Toastr adicional: 8 segundos, 12 para
  errores, cierre manual, hasta cuatro visibles y deduplicación por texto/tipo.
  Estados críticos y progreso de mantenimiento/reinicio permanecen visibles.
- CPU, GPU, RAM, GTT, temperaturas, carga, PSI y disco; histórico de 15 días,
  muestreo cada 5 s y consultas acotadas. No sumar GTT y RAM como memorias distintas.
- Disco: capacidad ocupada/disponible, actividad, MiB/s y sensores NVMe/drivetemp.
  Análisis manual de carpetas mediante `du` a baja prioridad, con límites y
  permisos parciales visibles; Docker se presenta aparte. No sumar padres,
  descendientes, reflinks o capas compartidas como si fueran datos independientes.
- Red: recepción/envío por interfaz en Mbit/s, sin capturar paquetes ni hacer
  tests de Internet. No sumar interfaces virtuales y físicas. Ausencias son huecos.

## 6. Actualizaciones, reinicio y recuperación web

Consultar paquetes no actualiza el equipo. Aplicar actualización abre una consola
administrativa visible en Actualizaciones, con stdout/stderr, prompts y errores;
no se cierra al navegar. `access-denied` requiere activar **Acceso administrativo**
en Cockpit: no se solicita o elude automáticamente esa autorización.

El reinicio sí pide confirmación. Comprueba permisos y mantenimiento, detiene
motores gestionados, verifica parada y llama al helper. Puede interrumpir trabajos
IA, pero no mata gestores de paquetes. Una orden aceptada no equivale a un reboot;
se confirma por cambio de identificador de arranque al reconectar.

La reconexión añadida muestra cuenta atrás con intentos cada 5 s, máximo 10 min,
y permanece visible por encima del iframe aunque Cockpit lo oculte al desconectar.
Consulta boot ID sin privilegios y, si cae el puente, comprueba la web del mismo
origen sin caché. Cuando vuelve (o responde tras 30 s), recarga una sola vez para
restablecer el puente; web accesible no confirma reboot. Con boot ID nuevo, refresca
tras 2 s. Conserva recibo sin credenciales en sessionStorage, admite nuevo login
Cockpit, no repite reinicios ni arranca motores. Cerrar seguimiento no cancela
el reinicio. Estas rutas se probaron con fixtures, no con otro reboot real.

Un intento registrado terminó la parada pero no reinició. Se observó el servidor
tmux de mantenimiento vivo, compatible con un bloqueo por sesión aún abierta;
no se pudo inspeccionar esa sesión root desde la CLI. Ahora se comprueba antes
de parar motores y se ofrece **Ver sesión de actualización existente**, sin
iniciar otra actualización. Pulsar Enter solo si la sesión terminó y lo pide.

Posteriormente el operador reinició y se observó un nuevo arranque. Cockpit falló
con `Cannot assign requested address`: su socket intentó escuchar antes de que
Wi-Fi tuviera la IP. La regla UFW guardada permitía 9090 desde la LAN y no había
bloqueos recientes registrados; eso no equivalía a una lectura completa del
ruleset activo sin root. No había listener en 9090.

El operador ejecutó la reparación y confirmó que recuperó la web:

```bash
sudo bash workspaces/halo-control/repair-cockpit.sh
```

El script añade `FreeBind=yes` en un drop-in separado, conserva IP/puerto y
archivos ajenos, recarga systemd, habilita/reinicia el socket y consulta UFW sin
cambiar reglas. No reinicia el host ni actualiza paquetes. El instalador nuevo
también usa FreeBind. Mantener una reserva DHCP: FreeBind no fija la IP.
No se ensayó otro reinicio después de la reparación para certificar su persistencia.

Tras el reinicio el colector estaba inactivo; se arrancó manualmente. Los tres
servicios de telemetría no se habilitan automáticamente al boot. La receta para
habilitarlos, si se desea, está en el manual; no confundirlos con motores GPU manuales.

## 7. Verificación y pendientes

Los comandos reproducibles están en los manuales enlazados. En la revisión del
24 de septiembre: 101 tests Python de Halo Control, 57 de inferencia, 50 unitarios
frontend, 40 Playwright y 14 fixtures del sitio. Son evidencias de pruebas, no
promesas de salud permanente. Playwright simula el puente autenticado; no ejecuta
actualizaciones, entrenamiento ni reinicios reales. La auditoría npm consultada
no encontró vulnerabilidades; no equivale a pentest.

El sitio completo sigue rechazando el enlace previo a
`scripts/engramhalo/.dockerignore`, fuera de su allowlist. Se añadieron exclusiones
de `node_modules`, `test-results` y `playwright-report`, no permisos de publicación
más amplios. Los archivos privados siguen ignorados y no deben forzarse a Git.

Pendientes: entrenamiento real Studio/Factory, estabilidad repetida de generación,
validación TLS LAN y certificado con identidad adecuada, concurrencia/soak de
inferencia sostenida (la coexistencia puntual Laya/Halogen sí se verificó), calidad
y calibración de Laya en datos propios, verificación de servicios tras otro reboot y recuperación de datos
independiente de contenedores retenidos. No se aplican updates ni reinicios para
cerrar esos pendientes como simple prueba de instalación.
