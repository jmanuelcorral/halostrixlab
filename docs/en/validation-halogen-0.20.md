# Halogen 0.20.0 validation on the Halo

[Spanish report](../validacion-halogen-0.20.md) |
[Docker, toolboxes and Halogen investigation](../investigacion-docker-toolboxes-halogen.md) |
[Documentation index](README.md)

**Test dates: 2026-11-09. Status: in service on the Halo with the code of branch
`halogen-0.20-upgrade` (commit `a9f2c17`), validated with synthetic load.**

Addresses, usernames and private paths are replaced with placeholders. The numbers
are measurements from that session, not a published benchmark or a performance
commitment. The full report, with commands and log lines, is in the
[Spanish report](../validacion-halogen-0.20.md).

## Summary

| Item | Result |
| --- | --- |
| Version | Halogen 0.20.0 (API and engine match in `/health`). Previously 0.11.3 |
| Checkpoint | `qwen38-flash-next-v2.hgn` (62.11 GiB) with ngram and MTP. The previous `w4b` is kept on disk |
| Vision | **Enabled**: sidecar `qwen38-flash-next-vision.hgn` (857 MiB). Checked with synthetic blue and red images |
| NPU | Enabled: `decider-0.8b`, `qwen3-embedding-0.6b`, `qwen3-reranker-0.6b` on `/dev/accel/accel0`, with the GPU fabric clock held at 2000 MHz |
| Cold start | Engine listening after 34 s; first text request answered after 17 s following a restart |
| Concurrency | 8 slots over a 1,048,576-position KV pool. Eight simultaneous requests succeeded |
| 128k context | Eight requests of 128,949 prompt tokens completed; prefill is serialized at about 68 s each |
| Decode | 57 tok/s for one 128k stream alone; about 16 tok/s per stream with eight short streams |
| Gateway | llama-swap **v271** (previously v255), without `apiKeys` because the network is a LAN for exclusive use |
| Endpoints | All Halogen endpoints reachable, through the gateway and through `/upstream/flash-halogen/…` |
| Control panel | Gufo and Laya removed; the catalog lists Halogen and the NPU peers |
| GTT | Unchanged at 61.73 GiB. Not required for this version |

## Gateway routes

llama-swap v255 routed by a fixed table, so Halogen's `/tokenize`, `/detokenize`,
`/slots`, `/cache`, `/halogen/handles` and `/v1/systemone` returned 404 through the
gateway. llama-swap v271 exposes `/upstream/<model>/<path>`, which forwards any path
to the model's server and loads the model if needed. All of them were checked this way.

The NPU models are configured as a **peer** pointing at the Halogen backend. Peer
models are addressed as `halogen-npu/<model>`, and also without the prefix while
there is no ambiguity. Peers need no auxiliary process and do not unload Flash.

Retired from the gateway on 2026-11-09: `laya`, `winnow-12b-cpu` and
`gufo-qwen38-27b`, with their groups.

## Open items

1. Cold start with the cleaned code (`a9f2c17`) is verified once; repeat after profile changes.
2. The control panel's browser test (Playwright) was rewritten for Halogen but has not run.
3. Ollaya and Winnow stay in the repository; their tests still use laya and gufo group names.
4. The gateway listens on the LAN without authentication. Accepted for exclusive use.
5. `qwen3guard-gen-0.6b` (moderation) is not enabled.
6. Quality under concurrency, long context, vision and NPU load has not been measured.
7. Vision was only checked with synthetic single-colour images.
