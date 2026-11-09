# Professional headshot from your own photo

[Español](PORTRAIT.md) | [Inference](README.en.md)

Workflow: **Halo-Retrato-Profesional-Qwen-Edit-4steps.json**.
Installed in ComfyUI user workflows without replacing existing templates.
It uses Qwen Image **Edit 2511**, not the Image 2512 generation model.

## Two-photo and three-photo variants

Additional workflows are installed without overwriting the original:

- `Halo-Retrato-Profesional-2Fotos-Qwen-Edit-4steps.json`
- `Halo-Retrato-Profesional-3Fotos-Qwen-Edit-4steps.json`

Refresh ComfyUI and look in **Workflows**, not Templates. Fill every image
selector in the chosen variant. The primary photo controls framing, pose and
expression; references should show the same person in good light, without filters,
with visible eyes. Use the two-photo version if you only have two; do not leave
an input empty. Personal photos are not searched for or selected automatically.

Both conditioning branches receive every reference; only the first photo feeds
the initial latent. The multi-photo prompt explicitly requests light blue-gray
eyes without darkening; edit that color when depicting someone else. These
variants do not add a mask or preserve original face pixels: they still regenerate
the image and cannot guarantee identity. Extra photos may increase visual
processing, memory and latency. Keep batch 1 and try two references first.
Both graphs passed native validation with synthetic input, without queuing a
render. Likeness with your photographs has not been evaluated.

```bash
python3 workspaces/inference/portrait_workflow.py --references 2
python3 workspaces/inference/portrait_workflow.py --references 3
```

## Original single-photo workflow usage

1. With ComfyUI running, refresh the page and open Workflows. Select
   `Halo-Retrato-Profesional-Qwen-Edit-4steps`. If missing, import its JSON from
   this workspace's `data/comfyui/user/default/workflows/`.
2. Upload a clear, well-lit head-and-shoulders JPG/PNG in **1. SUBE TU FOTO**.
   Crop it square first if you need a square avatar. The workflow preserves
   aspect ratio and resizes to approximately one megapixel, with dimensions
   divisible by 32. It does not stretch the face into a forced 1024-square image.
3. **2. ESTILO PROFESIONAL** contains an editable English prompt preserving
   identity and texture, requesting a navy blazer/light shirt, gray studio
   backdrop and soft lighting. Change clothing/background as desired.
4. Press **Run / Queue Prompt**. One image per execution, four steps,
   CFG 1, Euler/simple, shift 3.1, Edit Lightning LoRA strength 1.
5. Review and download the result, saved under `output/retratos/` with prefix
   `profesional`. Initial seed 42 is fixed; change it for another variation.

No personal photo is bundled or searched for on disk. The image selector starts
empty intentionally; upload your own before running. Identity preservation is
an instruction, not a guarantee. Compare eyes, nose, mouth, age and hair with
the original, and reject edits that change your likeness.

The photo feeds both Edit's visual conditioning and the initial latent.
`denoise=1` follows the four-step Lightning recipe; it does not preserve pixels
exactly. Do not lower denoise indiscriminately: it reduces this recipe's effective
sampling schedule. Negative conditioning stays empty at CFG 1.
No community nodes, face swap, training or personal LoRA is required.

## Likeness incident and scope of the change

The operator tried the single-photo version and reported that blue-gray eyes
became black/brown. This is an operator observation, not a biometric comparison
or an independent inspection of the photos. It shows that the original prompt
cannot guarantee likeness; that trial must not be presented as identity validation.

The implemented response adds two-photo and three-photo variants with an explicit
iris-color instruction, preserving the original workflow and user edits.
It has not yet been confirmed that these variants fix the reported case.
More references, more steps or lower denoise cannot guarantee a fix. The installed
Lightning LoRA is designed for four steps; increasing that count is not equivalent
to evaluating a higher-quality non-Lightning recipe.

Masking and compositing original face pixels was recommended for stricter
preservation. **It is not implemented in these graphs.** It would also retain
original face lighting and require matching background and edge transitions;
it must not be confused with the available multi-reference conditioning.

## Locations, files and troubleshooting

Paths below are relative to `workspaces/inference/` on the Halo:

| Item | Location |
| --- | --- |
| Three installed workflow JSONs | `data/comfyui/user/default/workflows/` |
| User-uploaded photos | `data/comfyui/input/` |
| Results | `data/comfyui/output/retratos/` |
| Public generator, no photos | `portrait_workflow.py` |
| Revision/hash-pinned downloader | `download_portrait_models.py` |

Output prefixes are `profesional`, `profesional-2fotos` and `profesional-3fotos`.
Installed JSONs and outputs are private; the repository contains the reproducible
generator rather than operator photos.

- **Missing from Workflows:** refresh with Ctrl+F5 and search the full name,
  not Templates. Use Open/Import or drag the JSON onto the canvas. When browsing
  from another computer, transfer only the JSON from the Halo through an authorized
  channel first; your browser file picker shows your local machine.
- **Empty photo input:** fill every selector. If you have two photos, choose
  `2Fotos`, not `3Fotos` with an empty field.
- **Missing model/LoRA:** finish downloading and refresh; select Edit 2511 and
  Lightning Edit 2511, never Image 2512.
- **Reinstall refuses a different file:** this protects user edits. Save/export
  a copy under a different name instead of blindly overwriting the original.
- **Face/iris still wrong:** reject the result; try neutral lighting, a consistent
  appearance and clearly visible eyes. More references are not exact preservation.
- **Memory pressure:** check batch 1, one megapixel and CPU offload; return to two
  references before raising resolution. Do not launch unmanaged GPU engines
  concurrently or change BIOS/GTT as a first response.

## Reproducible preparation

From repository root after preparing ComfyUI:

```bash
workspaces/inference/data/cockpit-venv/bin/python workspaces/inference/download_portrait_models.py
python3 workspaces/inference/portrait_workflow.py
python3 -m unittest discover -s scripts/tests -p test_inference_portrait.py -v
```

The downloader requires huggingface_hub in the existing isolated environment.
It adds about **41.71 GB** (38.85 GiB), reuses the installed encoder/VAE and does
not replace Image 2512. Downloads use private staging; size and SHA256 are checked
before publishing complete files via a non-overwriting hard link. Staging and
destination share data, not two independent copies. Reruns verify existing files.
No GPU or service restart is used for preparation.

| File | Repository | Revision |
| --- | --- | --- |
| `diffusion_models/qwen_image_edit_2511_bf16.safetensors` | `Comfy-Org/Qwen-Image-Edit_ComfyUI` | `f68ace85e60b4a02a323e394253731947657b7d2` |
| `loras/Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors` | `lightx2v/Qwen-Image-Edit-2511-Lightning` | `d74eba145674fd7e31b949324e148e21e7118abd` |

Respective SHA256 values:

```text
ae42d927b5fac4f278b9a894554c727e619727a63622976f2d95625be4bce08c
22226e8d05d354bb356627d428809f5afd7819399b077238a2b70a82883a904f
```

Encoder: `qwen_2.5_vl_7b_fp8_scaled.safetensors`; VAE:
`qwen_image_vae.safetensors`. Do not use the **Image-2512** LoRA here.
Nodes/settings were checked against the pinned ComfyUI image's Edit template
and the installed server's `/object_info`. Comfy-Org weights do not require the
optional reference-method nodes used by alternative repacks. Tests verify links,
types, reference conditioning, model selection, integrity and non-overwriting
installation. Both Edit weights were downloaded and verified; the running server
recognizes them without restarting. Native ComfyUI validation accepted the entire
graph with a temporary synthetic input, without loading models or queuing a
render. The isolated CPU validator warned about an unused auxiliary module
(`nodes_replacements`); none of the workflow nodes was missing. This does not
establish portrait quality or GPU execution with your photo.

## Memory, services and privacy

Keep CPU offload and the launcher's 4 GiB reserve; do not enable `--gpu-only`.
The historical 45-second Image 2512 result is not an Edit measurement.
Start with batch 1 at one megapixel.

If ComfyUI is stopped, its Halo Control **ON graceful** action releases the GPU
from the gateway, making Halogen, Gufo and Laya unavailable through that gateway.
An already-running ComfyUI does not need restarting to install a workflow;
refresh its interface after model downloads complete. Returning to Halogen via
its **ON graceful** requires an empty image queue.

Photos, outputs and used workflows stay under private ignored `data/comfyui/`.
Generation uses local models, not an external portrait service. ComfyUI is not a
network-isolated sandbox and its LAN interface has no authentication of its own;
do not expose it to the Internet. PNG metadata may include prompts/workflows and
the input filename. Remove metadata from a copy before publishing. Preserve the
original and never publish the private data directory.
