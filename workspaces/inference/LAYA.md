# Laya CPU junto a Halogen

[English](LAYA.en.md) | [Inferencia](README.md)

## Arquitectura

Laya 0.3.9 multilingual está aislado en Docker y servido por el mismo llama-swap
v255 que Halogen. No hay proxy paralelo. El grupo CPU es no exclusivo y
persistente: cargar Laya no descarga Halogen y cargar Halogen no descarga Laya.
El límite global admite los slots GPU más una petición CPU. No añade un pipeline,
no selecciona motores automáticamente y no pasa respuestas a Halogen.

- Gateway: el origen existente de Halogen, puerto 18080; mismas políticas de acceso.
- Decisiones: `POST /upstream/laya/v1/systemone`.
- Salud del modelo (lo carga si está parado): `GET /upstream/laya/health`.
- Salud del gateway: `GET /health`, no prueba inferencia.
- Backend: `127.0.0.1:18181`, solo acceso local, sin autenticación adicional.
- Unidad de usuario compartida: `llama-swap.service`. Carga a demanda y `ttl: 0`.
  El antiguo `halo-laya.service` fue retirado y el puerto 18081 está cerrado.
- Contenedor: `halostrix-laya-cpu`, sin dispositivos GPU ni socket Docker,
  usuario no-root, capacidades eliminadas, filesystem de solo lectura, límite
  de 4 CPU, 8 GiB RAM sin swap adicional y 256 procesos/hilos.

El límite de CPU no reserva núcleos físicos: ambos procesos comparten el host.
No se usa el lease GPU ni la etiqueta de contenedores GPU. Detener el gateway
compartido (incluido cambiar a otro motor desde el panel) también detiene Laya.
Descargar solo Halogen no descarga Laya. El autoinicio depende del gateway existente.
Halo Control incluye la tarjeta Laya en Resumen y Servicios IA, con logotipo
oficial, estado, Arrancar Laya, Detener Laya y acceso a logs compartidos.
Requiere que el gateway esté activo; no inicia proxies ni detiene motores GPU.
La parada se rechaza si hay peticiones en curso en el gateway. El sondeo de
estado consulta el backend solo cuando el contenedor existe: no autocarga Laya.

## Preparación reproducible

Desde la raíz, con Docker, gh, Python con extracción segura de tar y llama-swap
v255 ya instalado:

```bash
python3 workspaces/inference/prepare_laya.py
python3 workspaces/inference/install_laya.py --config /ruta/privada/gateway-activo.yaml
systemctl --user start llama-swap.service
```

Antes de instalar: reservar clientes, esperar peticiones y detener el gateway
existente. El instalador exige parada y lease de configuración; valida el candidato,
conserva copia privada y reemplaza atómicamente. Usar el archivo del launcher
activo, no uno histórico. No modifica comandos, perfiles ni credenciales de Halogen.
Desactiva la captura de cuerpos del gateway compartido (`captureBuffer: 0`).

`prepare_laya.py` descarga el código oficial fijado, construye CPU y descarga
solamente multilingual. Reejecutarlo conserva un despliegue existente; una
actualización exige revisión explícita, no sustituye una imagen en uso.
La base Docker está fijada por digest; las dependencias principales por versión.
Las transitivas quedan registradas en `data/laya/packages.txt`, no totalmente
bloqueadas para futuras reconstrucciones. El runtime usa el ID inmutable local.

- Código: `NandhaKishorM/laya`, revisión
  `d120d4ba220711b93c171973118753460310e16b`.
- Pesos: `convaiinnovations/laya-multilingual`, revisión
  `b4a904d1a2a54c822b829e24291d4b8f280fe43e`.
- PyTorch 2.8.0 CPU, Transformers 4.57.6; sin TileLang ni compilación.
- Pesos originales de solo lectura. Se copian configuración/tokenizador a tmpfs
  para que la reparación de compatibilidad de Laya no modifique los originales.
- Inferencia sin descargas: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`.
  Eso no es un firewall de salida; la red bridge no se presenta como air gap.

Código, modelos, caché, claves, inventario y evidencias permanecen en el directorio
ignorado `data/laya/`. No publicar esos archivos ni leer claves en la terminal.

## Cliente local

Ejemplo sin imprimir ni introducir la clave en argumentos de procesos:

```python
import json
from pathlib import Path
from urllib.request import Request, urlopen

key = Path('workspaces/inference/data/client.key').read_text().strip()
payload = {
    'state': 'Necesito corregir un error en un programa Python.',
    'questions': {
        'category': {
            'type': 'choice',
            'instructions': 'Clasifica la tarea solicitada.',
            'criteria': {
                'programming': 'Escribir o corregir código informático',
                'writing': 'Redactar o resumir texto',
                'images': 'Crear o editar imágenes',
            },
        },
    },
}
request = Request(
    'http://127.0.0.1:18080/upstream/laya/v1/systemone',
    data=json.dumps(payload).encode(),
    headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'},
)
with urlopen(request, timeout=180) as response:
    print(json.load(response))
```

El ejemplo usa los defaults públicos de loopback y Bearer. Adaptar origen y
credenciales al gateway existente. La excepción privada LAN HTTP sin clave que
ya usaba Halogen se conserva y ahora también cubre Laya; la clave del proxy
retirado no se usa. No publicar ese origen ni abrir el backend en LAN. Para
acceso remoto seguro, usar un túnel aprobado o la protección del gateway.
Es una API de decisiones, no chat OpenAI.
Solo sirve multilingual; `model` puede omitirse o ser `multilingual`, `laya` o
el ID completo del checkpoint. Rechaza rutas a otros modelos. Máximo 64 KiB por
petición, 1-8 preguntas y 20 criterios por pregunta. Una inferencia a la vez;
la saturación puede devolver 429/503. No se registran cuerpos de peticiones.

## Observación del 23 de septiembre de 2026

- Modelo cargado offline y respuesta real HTTP 200 en CPU.
- Petición sintética española: `programming`, probabilidad 0.9778.
- Primera carga observada: 4.3-5.4 s; petición caliente: 56 ms y 80 ms durante
  una prueba concurrente con Halogen. No son percentiles ni garantía de SLA.
- Memoria de contenedor observada: aproximadamente 1.62 GiB.
- La instalación inicial usó temporalmente un proxy separado; esas mediciones
  son históricas. Se migró posteriormente al gateway original tras comprobar
  ausencia de peticiones; esa migración sí reinició gateway y recargó Halogen.
- Ambos modelos respondieron simultáneamente desde el gateway único y aparecen
  en `/v1/models`. Pruebas con v255 verifican convivencia en ambos órdenes.
- Esquema/modelo inválido: 422; cuerpo excesivo: 413. La autenticación depende
  ahora exclusivamente del gateway existente.

Esto no mide precisión en producción, calidad del enrutamiento ni calibración.
No usar `action.act_probability` para automatizar: el propio proyecto reconoce
que todavía no aporta una señal útil. Validar probabilidades y umbrales con datos
propios antes de conectar el flujo de decisión en otro proyecto.

## Pruebas y operación

[Guía reproducible de pruebas](../../docs/pruebas-laya.md): tests sin modelos,
peticiones reales `choice`/`score`/`noul`, validación de probabilidades, rechazos
422/413, latencias, coexistencia opcional y arranque/parada desde Halo Control.
Incluye cliente que utiliza el origen y autenticación activos sin imprimirlos.
Verificación del 24 de septiembre: 8 tests runtime y 8 del adaptador del panel;
57 tests de inferencia y 101 del panel en las suites completas. El frontend pasó
50 unitarios y 40 Playwright. No confundir fixtures con inferencia real.

```bash
python3 -m unittest discover -s scripts/tests -p test_inference_laya.py -v
python3 workspaces/inference/laya_runtime.py status
systemctl --user status llama-swap.service
```

Para descargar únicamente Laya: `POST /api/models/unload/laya` en el gateway
existente con su autenticación configurada. Detener `llama-swap.service` descarga
ambos; pesos y caché se conservan. Los archivos del proxy retirado y su unidad
archivada permanecen en `data/laya/` solo como evidencia, no como configuración activa.

Fuentes: [Laya](https://github.com/NandhaKishorM/laya),
[pesos](https://huggingface.co/convaiinnovations/laya-multilingual).
Código y pesos publicados con Apache-2.0; conservar los avisos upstream.
