# Estado documental del proyecto

[Diccionario de parámetros Lemonade](referencia-parametros-lemonade.md) |
[English equivalent](en/project-status.md) |
[Índice principal](../README.md)

**Corte documental: 2026-09-10. No es monitorización ni auditoría live.**
Este resumen separa resultados históricos, configuración documentada,
recomendaciones y trabajo pendiente. El baseline reutilizable sigue fechado el
2026-09-04; los eventos posteriores no lo sobrescriben.

## Inventario público disponible

- README bilingüe, documentos técnicos en español y guías operativas en inglés.
- Perfil documental JSON, no importable por Lemonade.
- Smoke OpenAI/PowerShell y probe SSE/Python, ambos con objetivos y efectos
  secundarios acotados.
- Sitio estático bilingüe autocontenido con lector, generador y tests.
- Dos workspaces Docker/ROCm: LLaMA-Factory/LlamaBoard y Unsloth Studio.

El generador del sitio descubre recursivamente los Markdown bajo `docs/` y
`workspaces/`; por tanto, estas nuevas guías se incorporan sin una lista manual.

## Cronología de inferencia

| Fecha | Tipo | Registro |
| --- | --- | --- |
| 2026-09-04 | **Baseline histórico positivo** | Lemonade 11.8.1, llama.cpp Vulkan b10375. Coder 196608/3 y Thinking-2507 98304/1; dos residentes, ambos sin pin; GTT conjunto ~48.02 GiB. |
| 2026-09-04, posterior | **Incidencia abierta** | HTTP 403 reportado sin endpoint, cliente, causa ni cierre confirmados. |
| 2026-09-08 | **Observación live fechada** | Una petición Phi-4-mini provocó autocarga y expulsión LRU de Thinking al alcanzar `max_loaded_models=2`. Quedaron Coder+Phi, `pinned=false`. Cliente causante desconocido. |
| 2026-09-10 | **Observación live fechada** | Seguía 11.8.1. Coder+Thinking residentes, ready y `pinned=true`; máximo LLM 2. Qwen3.8-27B descargado, sin pin, con opciones guardadas de contexto 262144 y otros defaults. |
| 2026-09-10 | **Recomendación no validada** | Prueba transitoria Qwen3.8 a 32768 falló al cargar según el usuario. Causa y restauración posterior no se cerraron; no promover la receta. |
| Registro posterior del repo | **Evidencia documental incompatible con un checkpoint anterior** | Los informes SSE afirman upgrade a 11.9.0/b10723, `global_timeout=1200`, perfiles restaurados y dos PASS largos. El checkpoint disponible anterior decía “preparado, no instalado”. Esta tarea no hizo una auditoría independiente: se conservan ambos registros sin negar ni confirmar el estado actual. |
| 2026-09-15 | **Ensayo real, restaurado (no promovido)** | Matriz completa Qwen3.8-Flash-Next N1-N4 (64K/slot, `--no-kv-unified`) cargó, sirvió inferencia y restauró Coder+Qwen3.8-27B con verificación byte a byte. Soporte de arquitectura `qwen4exp` confirmado por código fuente en el build vivo `b10723@010be9683` (PR upstream #27742), pero sin las correcciones del PR #27941. Ver [ensayos Qwen3.8-Flash-Next](ensayos-qwen38-flash-next.md). No cierra el 403 ni el incidente SSE; no es salud permanente ni promoción a modelo residente. |
| 2026-09-15 | **Ensayo largo aprobado, no ejecutado** | El ensayo de contexto largo "sweet spot" (8K/16K/32K/~60K, N1 control vs N2/N3) quedó aprobado ese mismo día pero **no corrió**: 0 peticiones, bloqueado por transporte SSH/ControlMaster hacia el runner remoto, no por el modelo. Ver [ensayos Qwen3.8-Flash-Next](ensayos-qwen38-flash-next.md), sección 7, punto 6. |
| 2026-09-16 | **Ensayo fechado, confundido (no causal, no promovido)** | Comparación de offload Q4_K_M (base `--cpu-moe` todo-CPU vs `--n-cpu-moe 40`, una ronda barrera válida de N=2 solicitudes concurrentes por perfil, ctx 131072/parallel 2): `n-cpu-moe 40` mostró -16,1% de media en latencia wall de cliente y +1,85% de media en decode tok/s, pero una descarga gestionada `UD-IQ4_XS` activa concurrentemente (iniciada, no completada) y conteos de tokens de completion no emparejados confunden la muestra; no es una afirmación de speedup causal. 4 solicitudes previas del mismo día toparon con un límite de 32 tokens (inconcluso, no un hallazgo de modelo no soportado); un perfil candidato `--n-cpu-moe 32` (4 solicitudes planificadas adicionales) quedó sin ensayar tras un fallo de transporte SSH, no "32 solicitudes no ejecutadas" (ese 32 era el valor del flag `--n-cpu-moe`, no un conteo de solicitudes). Modelo: Bartowski `Qwen3.8-Flash-Next-GGUF-Q4_K_M` (catálogo público: [bartowski/Qwen3.8-Flash-Next-GGUF](https://huggingface.co/bartowski/Qwen3.8-Flash-Next-GGUF)). Ver [ensayos Qwen3.8-Flash-Next](ensayos-qwen38-flash-next.md), sección 8. |
| 2026-09-16T12:42:05Z–12:44:03Z (~118s) | **Ensayo fechado, ejecutado con éxito (sin ganador estadísticamente robusto, no promovido)** | Intento posterior y separado del barrido baseline/`--n-cpu-moe 32`/`24` señalado arriba como "no ejecutado" ese mismo día: este segundo intento se completó, 6/6 solicitudes reales (2 por perfil), con restauración verificada byte a byte. El throughput agregado (~12,1–12,7 tok/s entre perfiles) quedó dentro de un margen de ruido similar; sin perfil ganador estadísticamente robusto. No entra en conflicto con la fila anterior del mismo día ("no ejecutado"), que documenta un intento previo y separado, bloqueado. Ver [ensayos Qwen3.8-Flash-Next](ensayos-qwen38-flash-next.md), sección 8, subsección fechada. |

## Entrenamiento y workspaces

| Área | Resultado documentado | Lo que no demuestra |
| --- | --- | --- |
| Smoke tensorial ROCm | Operaciones y backward finitos FP16/BF16, histórico. | Fine-tuning de un LLM, estabilidad larga o calidad. |
| LLaMA-Factory | Workspace y plantilla BF16 LoRA configurados. | Entrenamiento/LlamaBoard GPU end-to-end validado. |
| Unsloth Studio | Build, imports, GPU, health y SPA validados el 2026-09-01. | Entrenamiento LLM. QLoRA 4-bit no estaba disponible en el stack documentado. |
| vLLM | Intento histórico e investigación conservados. | Backend promovido o validación reutilizable. |

Los `.env.example` son las únicas plantillas públicas para variables de entorno.
No se consultaron `.env` reales, datos, modelos, credenciales ni bases de
autenticación para producir este resumen.

## Contrato de las pruebas

- `scripts/test-lemonade.ps1`: exige `-BaseUrl` y `-Model`; hace discovery y
  una petición chat no streaming. No es read-only y puede activar autocarga/LRU.
- `scripts/test-lemonade-sse.py`: exige origen sin `/v1`, ID exacto ya residente,
  backend ready e inactividad. El modo largo valida primer contenido después de
  130 s, `READY`, `stop` y `[DONE]`; no acredita calidad ni aislamiento GPU.
- Los tests offline usan loopback/fixtures y no contactan el Halo ni requieren
  GPU, modelos o secretos.

## Pendientes explícitos

1. Causa y resolución del 403 histórico.
2. Resolver la contradicción “Qwen3.8 cargado” frente a “nunca cargado” en
   fuentes antiguas; las observaciones del 10 de septiembre prueban al menos
   descarga/opciones, no una historia completa de cargas.
3. Precedencia global/modelo/request, flags duplicados y archivo exacto de
   persistencia por modelo.
4. Cold boot y precarga automática de residentes.
5. TLS, autenticación/proxy y política de exposición.
6. Concurrencia N=1/N=2/N=4, soak, cancelación y presión de memoria.
7. Fine-tuning LLM real en ambos workspaces y convivencia con inferencia.
8. Validación actual y reproducible de vLLM.
9. Contexto largo real (~60K) y TTFT en streaming para Flash-Next; solape
   real de backend (no solo despacho concurrente de cliente); soak
   sostenido; tool calling/visión; reevaluación tras el PR upstream #27941.
   Ver [ensayos Qwen3.8-Flash-Next](ensayos-qwen38-flash-next.md), sección 7.

## Criterio de reutilización

Usar el baseline solo como comparación. Antes de operar, medir versión, health,
catálogo, residentes/pins, opciones efectivas, argumentos del proceso, memoria,
listeners y actividad. No cargar candidatos ni restaurar recetas por diferencia
documental. Guardar backups privados y aplicar cambios únicamente en una ventana
autorizada.
