# Retrato profesional con una foto propia

[English](PORTRAIT.en.md) | [Inferencia](README.md)

Workflow: **Halo-Retrato-Profesional-Qwen-Edit-4steps.json**.
Se instala en los workflows del usuario de ComfyUI, sin modificar las plantillas
existentes. Usa Qwen Image **Edit 2511**, no el modelo de generación Image 2512.

## Variantes con dos o tres fotos

También se instalan, sin sobrescribir el workflow original:

- `Halo-Retrato-Profesional-2Fotos-Qwen-Edit-4steps.json`
- `Halo-Retrato-Profesional-3Fotos-Qwen-Edit-4steps.json`

Refresca ComfyUI y busca estos nombres en **Workflows**, no en Plantillas.
En cada variante debes cargar todas las fotos indicadas: la principal define
encuadre, pose y expresión; las otras muestran a la misma persona con buena luz,
sin filtros y con los ojos visibles. Usa la variante de dos si solo tienes dos;
no dejes un selector vacío. No se examinan ni seleccionan fotos automáticamente.

Ambas ramas de conditioning reciben todas las referencias, pero solo la primera
foto alimenta el latente inicial. El prompt multifoto pide explícitamente ojos
azul-gris claros y evita oscurecerlos; adapta ese color si retratas a otra persona.
No incorpora máscara ni conserva píxeles originales del rostro: sigue siendo
regeneración y no garantiza identidad exacta. Varias fotos aumentan el trabajo
visual y pueden consumir más memoria/tiempo. Mantén batch 1 y prueba primero dos.
Los grafos de dos y tres fotos pasaron la validación nativa con entrada sintética,
sin encolar una generación; no se ha evaluado fidelidad con tus fotografías.

```bash
python3 workspaces/inference/portrait_workflow.py --references 2
python3 workspaces/inference/portrait_workflow.py --references 3
```

## Uso del workflow original de una foto

1. Con ComfyUI activo, refresca la página y abre Workflows. Busca
   `Halo-Retrato-Profesional-Qwen-Edit-4steps`. Si no aparece, importa el JSON de
   `data/comfyui/user/default/workflows/` bajo este workspace.
2. En **1. SUBE TU FOTO**, carga un JPG/PNG tuyo, nítido, bien iluminado, de
   cabeza y hombros. Recorta antes a cuadrado si necesitas avatar cuadrado.
   El workflow conserva la proporción y ajusta a aproximadamente un megapíxel,
   con dimensiones múltiplos de 32; no fuerza ni deforma el rostro a 1024².
3. El prompt en **2. ESTILO PROFESIONAL** pide conservar identidad y textura,
   cambiando ropa a americana azul marino/camisa clara, fondo gris e iluminación.
   Puedes cambiar ropa y fondo. Está escrito en inglés y es editable.
4. Pulsa **Run / Queue Prompt**. Una imagen por ejecución, cuatro pasos,
   CFG 1, Euler/simple, shift 3.1, LoRA Edit Lightning a fuerza 1.
5. Revisa el resultado y descárgalo. Se guarda en `output/retratos/` con prefijo
   `profesional`. La semilla inicial es 42 fija; cámbiala para otra variante.

No se incluye una foto personal ni se busca una entre los archivos del equipo.
El selector queda vacío deliberadamente: debes elegir tu foto antes de ejecutar.
Conservar identidad es una instrucción, no una garantía: compara ojos, nariz,
boca, edad y pelo con el original. No uses una edición que cambie tu parecido.

La imagen alimenta tanto el encoder visual de Edit como el latente inicial.
`denoise=1` corresponde a la receta Lightning de cuatro pasos; no significa
preservación píxel a píxel. No bajar denoise indiscriminadamente, porque reduce
el recorrido efectivo de esta receta. El negativo queda vacío con CFG 1.
No se necesitan nodos comunitarios, face swap, entrenamiento ni LoRAs personales.

## Incidencia de fidelidad y alcance de la corrección

El operador probó la versión de una foto y comunicó que unos ojos azul-gris
aparecían negros/marrones. Es una observación del operador, no una comparación
biométrica ni una inspección independiente de las fotos. Demuestra que el prompt
original no basta para garantizar el parecido; no debe presentarse ese ensayo
como validación de identidad.

La respuesta implementada añade variantes de dos y tres fotos y una instrucción
explícita sobre el iris. Conserva la versión original y sus modificaciones.
No se ha confirmado todavía que las variantes corrijan el caso comunicado.
Añadir más fotos, más pasos o reducir denoise no garantiza la corrección.
La LoRA instalada está preparada para cuatro pasos: aumentar ese número no
equivale a evaluar una receta sin Lightning de mayor calidad.

Para preservar con más rigor el rostro se recomendó una máscara y composición
final con los píxeles de la foto original. **No está implementado en estos grafos**.
Conservaría también la iluminación de la cara y exigiría adaptar el fondo y
los bordes; no debe confundirse con el conditioning multifoto ya disponible.

## Localización, archivos y problemas habituales

Todos los paths siguientes son relativos a `workspaces/inference/` en el Halo:

| Elemento | Ubicación |
| --- | --- |
| JSON de las tres variantes | `data/comfyui/user/default/workflows/` |
| Fotos cargadas por el usuario | `data/comfyui/input/` |
| Resultados | `data/comfyui/output/retratos/` |
| Generador público, sin fotos | `portrait_workflow.py` |
| Descargador con revisiones y hashes | `download_portrait_models.py` |

Los prefijos de salida son `profesional`, `profesional-2fotos` y
`profesional-3fotos`. Los JSON instalados y los resultados son privados;
el repositorio conserva el generador reproducible, no las fotos del operador.

- **No aparece en Workflows:** refresca con Ctrl+F5 y busca el nombre completo,
  no en Plantillas. Usa Abrir/Importar o arrastra el JSON al lienzo. Si el
  navegador está en otro ordenador, primero transfiere solo el JSON desde el
  Halo por un canal autorizado; el selector de archivos muestra tu equipo local.
- **Selector de foto vacío:** sube todas las fotos que pide la variante. Si tienes
  dos, abre `2Fotos`, no `3Fotos` con un campo vacío.
- **Modelo o LoRA ausente:** termina el descargador y refresca la interfaz;
  selecciona Edit 2511 y Lightning Edit 2511, nunca Image 2512.
- **La reinstalación rechaza un archivo distinto:** protege cambios del usuario.
  Guarda/exporta una copia con otro nombre; no sobreescribas a ciegas el original.
- **Rostro o iris todavía incorrectos:** rechaza el resultado; prueba referencias
  con luz neutra, mismo aspecto y ojos visibles. No confundir más referencias con
  preservación exacta del rostro.
- **Presión de memoria:** comprueba batch 1, un megapíxel y offload a CPU;
  vuelve a dos referencias antes de aumentar resolución. No ejecutes motores GPU
  externos simultáneamente ni cambies BIOS/GTT como primera solución.

## Preparación reproducible

Desde la raíz del repositorio, después de preparar ComfyUI:

```bash
workspaces/inference/data/cockpit-venv/bin/python workspaces/inference/download_portrait_models.py
python3 workspaces/inference/portrait_workflow.py
python3 -m unittest discover -s scripts/tests -p test_inference_portrait.py -v
```

El descargador requiere huggingface_hub en el entorno aislado existente. Añade
unos **41,71 GB** (38,85 GiB), reutiliza encoder y VAE ya descargados y no sustituye
Image 2512. Descarga a staging privado, verifica tamaño y SHA256, y publica cada
archivo completo con un hard link sin sobrescribir destinos. Staging y destino
comparten los datos, no son dos copias independientes. Reejecutar verifica los
archivos existentes. No descarga con GPU ni reinicia servicios.

| Archivo | Repositorio | Revisión |
| --- | --- | --- |
| `diffusion_models/qwen_image_edit_2511_bf16.safetensors` | `Comfy-Org/Qwen-Image-Edit_ComfyUI` | `f68ace85e60b4a02a323e394253731947657b7d2` |
| `loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors` | `lightx2v/Qwen-Image-Edit-2511-Lightning` | `d74eba145674fd7e31b949324e148e21e7118abd` |

SHA256 respectivos:

```text
ae42d927b5fac4f278b9a894554c727e619727a63622976f2d95625be4bce08c
22226e8d05d354bb356627d428809f5afd7819399b077238a2b70a82883a904f
```

Encoder: `qwen_2.5_vl_7b_fp8_scaled.safetensors`; VAE:
`qwen_image_vae.safetensors`. No usar la LoRA **Image-2512** con este workflow.
Los nodos y ajustes se contrastaron con la plantilla Edit de la imagen ComfyUI
ya fijada y con `/object_info` del servicio instalado. La receta usa los pesos
Comfy-Org, por lo que omite los nodos opcionales de método de referencia para
repack alternativos. Las pruebas verifican enlaces, tipos, entrada de referencia,
selección de pesos, integridad e instalación que no pisa cambios del usuario.
Los dos pesos Edit se descargaron y verificaron; el servicio activo los reconoce
sin reinicio. La validación nativa de ComfyUI aceptó el grafo completo con una
imagen sintética temporal, sin cargar modelos ni encolar generación. El validador
CPU aislado avisó de un nodo auxiliar no usado (`nodes_replacements`); ninguno
de los nodos del workflow faltó. Eso no demuestra calidad del retrato ni
generación GPU con tu fotografía.

## Memoria, servicios y privacidad

Mantener el offload a CPU y la reserva de 4 GiB del launcher; no activar
`--gpu-only`. El tiempo de unos 45 segundos observado para Image 2512 no es una
medición de Edit. Empezar con batch 1 y un megapíxel.

Si ComfyUI está parado, usa **ON graceful** en su tarjeta de Halo Control para
liberar la GPU del gateway. Se interrumpe disponibilidad de Halogen, Gufo y Laya
servidos por ese gateway. Si ComfyUI ya está activo, no hace falta reiniciarlo
para instalar un workflow; refresca la interfaz tras completar los modelos.
Volver a Halogen con su **ON graceful** exige que la cola de imágenes esté vacía.

Fotos, PNGs y workflows usados quedan bajo `data/comfyui/`, privado e ignorado.
La generación usa modelos locales, sin servicio externo de retratos. ComfyUI
no es una caja aislada sin red y su interfaz LAN no tiene autenticación propia:
no exponerla a Internet. Los PNG pueden incluir prompt/workflow y nombre del
archivo de entrada en metadatos; elimina metadatos en una copia antes de publicar.
Conserva siempre el original y no publiques el directorio privado.
