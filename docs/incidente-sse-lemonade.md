# Lemonade: timeout de streaming del 10 de septiembre de 2026

[English: full incident and maintenance guide](en/lemonade-sse-timeout.md) |
[Diccionario de parámetros](referencia-parametros-lemonade.md) |
[Estado documental](estado-proyecto.md) |
[Indice del proyecto](../README.md)

**Resultado:** servicio actualizado a **Lemonade 11.9.0-1**, Vulkan
**b10723-010be9683**, con `global_timeout = 1200` persistido. Se conservaron
Coder (3 slots, contexto total 196608) y Qwen3.8-27B (1 slot, contexto 65536),
ambos fijados y con sus perfiles originales.

> **Advertencia de procedencia:** el historial de sesion disponible contiene
> un checkpoint anterior en el que 11.9.0 estaba preparado, pero no instalado.
> Esta tarea documental no realizo una auditoria independiente. El informe
> conserva el supuesto resultado posterior, sin que ello pruebe el estado
> actual del host.

Cuatro peticiones del Qwen3.8-27B terminaron a unos 126 segundos mientras
llama-server seguia procesando la entrada. Todavia no generaban tokens.
El error era `CURL error: Timeout was reached`, seguido de cancelacion y
liberacion del slot, sin agotar la ventana de 64k ni descargar el modelo.

Lemonade 11.8.1 imponia al streaming un limite fijo de baja transferencia de
1 byte/s durante 120 segundos. El progreso de GPU no reiniciaba ese reloj.
El `global_timeout` de 1200 segundos no controlaba esa rama.

**La correccion oficial esta en Lemonade 11.9.0**: el intervalo de baja
transferencia del streaming pasa a respetar el timeout configurado. No es un
limite total para una respuesta que sigue enviando datos, ni implementa
timeouts separados para prefill y generacion.

La [guia completa en ingles](en/lemonade-sse-timeout.md) recoge la evidencia,
el paquete instalado desde fuentes oficiales, sus limites, el rollback y
las precauciones sobre Vulkan b10723, origenes web y descubrimiento de modelos.
La [prueba SSE](../scripts/README.md#synthetic-streaming-regression-probe)
exige una respuesta real posterior a 130 segundos, no solo HTTP 200 o pings.

Dos ejecuciones largas completaron una entrada sintetica de unos 44.5k
tokens, con primer contenido a los **214.735 y 214.866 segundos**.
La segunda se ejecuto independientemente desde Windows. Ambas terminaron
con `READY`, `stop` y `[DONE]`, sin truncamiento. El override que desactiva
el razonamiento se aplica solo a la prueba, no al perfil guardado del thinker.

El timeout interno queda corregido; el prefill sigue teniendo su coste y
los timeouts de clientes o proxies no cambian con esta actualizacion.

Esta incidencia es distinta del corte anterior por contexto de 32k y no
resuelve retrospectivamente el HTTP 403 de septiembre 4, cuyo origen sigue
sin determinarse. La referencia historica Coder + Thinking-2507 permanece
fechada por separado; no debe confundirse con una lectura en vivo.
