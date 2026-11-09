# Halogen 0.20.0 validation on the Halo

[Spanish report](../validacion-halogen-0.20.md) |
[Docker, toolboxes and Halogen investigation](../investigacion-docker-toolboxes-halogen.md) |
[Documentation index](README.md)

**Test date: 2026-11-09. Status: validated on the Halo with synthetic load. The
service configuration is not promoted to reference documentation.**

Addresses, usernames and private paths are replaced with placeholders. The numbers
are measurements from that session, not a published benchmark or a performance
commitment. The full report, with the exact commands and log lines, is in the
[Spanish report](../validacion-halogen-0.20.md).

## Summary

| Item | Result |
| --- | --- |
| Version | Halogen 0.20.0 (API and engine match in `/health`). Previously 0.11.3 |
| Checkpoint | `qwen38-flash-next-v2.hgn` (62.11 GiB). The previous `w4b` is kept on disk |
| Startup | Engine listening after 34 s from a cold start |
| Concurrency | 8 slots over a 1,048,576-position KV pool. Eight simultaneous requests succeeded |
| 128k context | Eight requests of 128,949 prompt tokens completed; prefill is serialized at about 68 s each |
| Decode | 57 tok/s for one 128k stream alone; about 16 tok/s per stream with eight short streams |
| NPU | Enabled: `decider-0.8b`, `qwen3-embedding-0.6b`, `qwen3-reranker-0.6b` on `/dev/accel/accel0`, with the GPU fabric clock held at 2000 MHz |
| Gateway | llama-swap serves `flash-halogen` and the alias `halogen-qwen3.8-flash-next`. Concurrency limit raised from 4 to 8 |
| GTT | Unchanged at 61.73 GiB. Not required for this version |

## Gateway routes

Through the llama-swap gateway, these work: chat, completions, responses, messages,
embeddings, rerank, and the three NPU models by name. Halogen's `/v1/systemone`,
`/v1/moderations`, `/tokenize`, `/detokenize`, `/slots`, `/cache` and
`/halogen/handles` return 404, because llama-swap has a fixed route table. Exposing
them needs a reverse proxy in front (Caddy) or direct access to the backend.

The NPU models are reached through extra llama-swap entries that point to the same
backend. Each has a no-op auxiliary process, and they sit in a non-exclusive group,
so requesting an NPU model does not unload Flash.

## Open items

1. The runtime on the Halo has `npu_models`, `slots` and `kv_pool`. The repository
   branch does not yet. The two must be reconciled before merging.
2. The gateway listens on the LAN without authentication.
3. Caddy is not running, so `/v1/systemone` and `/v1/moderations` are not exposed.
4. `qwen3guard-gen-0.6b` (moderation) is not enabled.
5. Quality under concurrency and with long context has not been measured.
