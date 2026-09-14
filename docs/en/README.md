# Halo Strix: English documentation

[Project overview](../../README.en.md) |
[Spanish reference](../configuracion-reutilizable-halo-strix.md)

These guides cover the operational instructions and conclusions of the
Spanish historical documents. They are **English runbook equivalents, not
line-by-line translations of private logs**. No unpublished records, internal
coordination files, credentials or private network topology are required.

The historical dual-model baseline is dated **2026-09-04**, consolidated and
sanitized on **2026-09-07**. A later HTTP **403** was reported on September 4;
its endpoint, cause and resolution are unknown. Nothing here is a live audit,
an assertion of current service health or permission to execute changes.

The [September 10 streaming timeout report](lemonade-sse-timeout.md) records
a later incident and its official correction separately from that baseline.

## Reading order

1. [Configuration reference](configuration-reference.md): exact dual-model
   settings, persistence, endpoints, CORS, health checks and manual restoration.
2. [Lemonade parameter dictionary](lemonade-parameter-reference.md): meaning,
   scope, documented values, interactions, risk and evidence status for each
   Lemonade/llama.cpp parameter.
3. [Documentary project status](project-status.md): September 4/8/10
   chronology, training evidence, test contracts and unresolved work.
4. [Setup guide](setup-guide.md): preflight, backup, UMA, Vulkan/HIP,
   installation, systemd, networking, Docker/ROCm, workspaces and recovery.
5. [Model guide](model-guide.md): model identity, reasoning, cache/concurrency,
   experimental candidates and their proposed evaluation gates.
6. [Documentary JSON profile](../../config/halo-strix.reference.json):
   machine-readable parameters, **not a native Lemonade import or live dump**.
7. Workspace instructions:
   [LLaMA-Factory](../../workspaces/llama-factory/README.en.md) and
   [Unsloth Studio](../../workspaces/unsloth-studio/README.en.md).
8. [PowerShell smoke-test instructions](../../scripts/README.md): required
   `BaseUrl`/`Model` parameters, validation and side-effect boundaries.
9. [Streaming timeout correction](lemonade-sse-timeout.md): Lemonade 11.9.0,
   maintenance/rollback boundaries and the synthetic long-prefill probe.

## Coverage of the historical sources

| Spanish source | English operational coverage |
| --- | --- |
| [Initial audit](../auditoria-ssh-inicial.md) | Setup: SSH trust, hardware, backup restrictions, UMA, package/runtime inventory, post-power-cycle verification |
| [Original plan](../plan-configuracion-halo-strix.md) | Setup: staged gates, thermal/memory/storage limits, isolation, deferred work and approval boundaries |
| [Vulkan validation](../validacion-llamacpp-vulkan.md) | Setup: build provenance, offload, bounded smoke, benchmark, runaway logs and short/provisional PASS |
| [HIP validation](../validacion-llamacpp-hip.md) | Setup: compiler/dependency/linkage gates and final non-promotion decision |
| [Lemonade validation](../validacion-lemonade-vulkan.md) | Configuration + setup: service, LAN, CLI, UI, CORS, model options, pull/variants, path resolution, catalog collisions, recovery |
| [ROCm training validation](../validacion-entrenamiento-rocm.md) | Setup: Docker deployment boundary, exact base image, finite FP16/BF16 backward smoke and restoration |
| [Model comparison](../comparativa-qwen38-halo-strix.md) | Configuration + model guide: exact Coder/Thinking recipes, GTT, reasoning, candidate POCs and rollback |
| [Complete historical setup](../setup-completo-halo-strix.md) | All three guides: integrated operation, vLLM caveats, workspaces, authentication boundary, HTTP/TLS and incident checklist |
| [Reusable Spanish reference](../configuracion-reutilizable-halo-strix.md) | Configuration reference: complete functional equivalent, including unresolved 403 and contradictory Qwen3.8 history |

Read **observed**, **configured**, **recommendation** and **pending** as distinct
states. A successful download is not a successful load; a working UI is not
validated fine-tuning; an earlier PASS does not close a later incident.
