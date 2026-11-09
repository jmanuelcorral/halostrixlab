import json
from pathlib import Path

import comfyui
import runtime


NAME = 'Halo-Retrato-Profesional-Qwen-Edit-4steps.json'
MODEL = 'qwen_image_edit_2511_bf16.safetensors'
LORA = 'Qwen-Image-Edit-2511-Lightning-4steps-V1.0-bf16.safetensors'
PROMPT = ('Edit this photo into a realistic professional headshot of the same person. '
          'Preserve their identity, facial proportions, apparent age, skin tone, hairstyle and natural skin texture. '
          'Keep the original expression and a head-and-shoulders composition. '
          'Change only the clothing to a well-fitted navy blazer and plain light shirt, '
          'the background to a clean light gray studio backdrop, and the lighting to soft flattering studio light. '
          'Keep a natural photographic appearance. Do not reshape the face, change the person, '
          'smooth away skin texture, add text, logos or watermarks.')


def build(reference_count=1):
    if type(reference_count) is not int or reference_count not in (1, 2, 3):
        raise ValueError('Use one, two or three reference photos')
    nodes = []
    links = []

    def node(identifier, kind, title, position, widgets, inputs=(), outputs=()):
        value = {'id': identifier, 'type': kind, 'title': title, 'pos': position,
                 'size': [340, 170], 'flags': {}, 'order': len(nodes), 'mode': 0,
                 'inputs': [{'name': name, 'type': datatype, 'link': None} for name, datatype in inputs],
                 'outputs': [{'name': name, 'type': datatype, 'links': []} for name, datatype in outputs],
                 'properties': {'Node name for S&R': kind}, 'widgets_values': widgets}
        nodes.append(value)
        return value

    model = node(1, 'UNETLoader', 'Modelo Qwen Image Edit 2511', [0, 0], [MODEL, 'default'], outputs=[('MODEL', 'MODEL')])
    lora = node(2, 'LoraLoaderModelOnly', 'Lightning EDIT: 4 pasos', [0, 230], [LORA, 1.0], [('model', 'MODEL')], [('MODEL', 'MODEL')])
    sampling = node(3, 'ModelSamplingAuraFlow', 'Shift de la receta Edit', [390, 0], [3.1], [('model', 'MODEL')], [('MODEL', 'MODEL')])
    norm = node(4, 'CFGNorm', 'Normalización', [390, 220], [1.0, False], [('model', 'MODEL')], [('MODEL', 'MODEL')])
    clip = node(5, 'CLIPLoader', 'Encoder existente', [0, 460], ['qwen_2.5_vl_7b_fp8_scaled.safetensors', 'qwen_image', 'default'], outputs=[('CLIP', 'CLIP')])
    vae = node(6, 'VAELoader', 'VAE existente', [0, 680], ['qwen_image_vae.safetensors'], outputs=[('VAE', 'VAE')])
    photo = node(7, 'LoadImage', '1. SUBE TU FOTO (cabeza y hombros)', [0, 930], ['', 'image'], outputs=[('IMAGE', 'IMAGE'), ('MASK', 'MASK')])
    photo['size'] = [340, 330]
    scale = node(8, 'ImageScaleToTotalPixels', '1 megapíxel, conserva proporción', [390, 930], ['lanczos', 1.0, 32], [('image', 'IMAGE')], [('IMAGE', 'IMAGE')])
    encode_inputs = [('clip', 'CLIP'), ('vae', 'VAE'), ('image1', 'IMAGE')]
    positive = node(9, 'TextEncodeQwenImageEditPlus', '2. ESTILO PROFESIONAL (editable)', [800, 0], [PROMPT], encode_inputs, [('CONDITIONING', 'CONDITIONING')])
    positive['size'] = [480, 360]
    negative = node(10, 'TextEncodeQwenImageEditPlus', 'Negativo vacío para CFG 1', [800, 460], [''], encode_inputs, [('CONDITIONING', 'CONDITIONING')])
    latent = node(11, 'VAEEncode', 'Foto como imagen inicial', [800, 930], [], [('pixels', 'IMAGE'), ('vae', 'VAE')], [('LATENT', 'LATENT')])
    sampler = node(12, 'KSampler', '3. GENERAR: 4 pasos, CFG 1', [1350, 0], [42, 'fixed', 4, 1.0, 'euler', 'simple', 1.0], [('model', 'MODEL'), ('positive', 'CONDITIONING'), ('negative', 'CONDITIONING'), ('latent_image', 'LATENT')], [('LATENT', 'LATENT')])
    sampler['size'] = [340, 350]
    decode = node(13, 'VAEDecode', 'Decodificar', [1350, 490], [], [('samples', 'LATENT'), ('vae', 'VAE')], [('IMAGE', 'IMAGE')])
    save = node(14, 'SaveImage', '4. RESULTADO', [1770, 0], ['retratos/profesional'], [('images', 'IMAGE')], [('images', 'IMAGE')])
    save['size'] = [500, 650]

    def connect(source, output, target, input_slot):
        identifier = len(links) + 1
        datatype = source['outputs'][output]['type']
        assert datatype == target['inputs'][input_slot]['type']
        links.append([identifier, source['id'], output, target['id'], input_slot, datatype])
        source['outputs'][output]['links'].append(identifier)
        target['inputs'][input_slot]['link'] = identifier

    for source, output, target, input_slot in [
        (model, 0, lora, 0), (lora, 0, sampling, 0), (sampling, 0, norm, 0),
        (photo, 0, scale, 0), (clip, 0, positive, 0), (vae, 0, positive, 1),
        (scale, 0, positive, 2), (clip, 0, negative, 0), (vae, 0, negative, 1),
        (scale, 0, negative, 2), (scale, 0, latent, 0), (vae, 0, latent, 1),
        (norm, 0, sampler, 0), (positive, 0, sampler, 1), (negative, 0, sampler, 2),
        (latent, 0, sampler, 3), (sampler, 0, decode, 0), (vae, 0, decode, 1),
        (decode, 0, save, 0),
    ]:
        connect(source, output, target, input_slot)
    if reference_count > 1:
        photo['title'] = '1. FOTO PRINCIPAL: encuadre y expresión'
        positive['widgets_values'] = [
            'All input images show the same person. Edit image 1 only; preserve its framing, pose and expression. '
            'Use the other images only as identity references, not as extra people or a collage. '
            'Preserve the original light blue-gray iris color exactly, without turning eyes brown, black or darker. '
            + PROMPT
        ]
        positive['size'] = [480, 410]
        save['widgets_values'] = [f'retratos/profesional-{reference_count}fotos']
        for reference in range(2, reference_count + 1):
            loader = node(15 + (reference - 2) * 2, 'LoadImage',
                          f'REFERENCIA {reference}: misma persona, ojos visibles',
                          [0, 930 + (reference - 1) * 430], ['', 'image'],
                          outputs=[('IMAGE', 'IMAGE'), ('MASK', 'MASK')])
            loader['size'] = [340, 330]
            resized = node(16 + (reference - 2) * 2, 'ImageScaleToTotalPixels',
                           f'Referencia {reference}: 1 megapíxel',
                           [390, 930 + (reference - 1) * 430], ['lanczos', 1.0, 32],
                           [('image', 'IMAGE')], [('IMAGE', 'IMAGE')])
            connect(loader, 0, resized, 0)
            for conditioning in (positive, negative):
                conditioning['inputs'].append({'name': f'image{reference}', 'type': 'IMAGE', 'link': None})
                connect(resized, 0, conditioning, len(conditioning['inputs']) - 1)
        ordered = []
        remaining = list(nodes)
        while remaining:
            ready = next(value for value in remaining if all(
                link[1] in ordered for link in links if link[3] == value['id']))
            ready['order'] = len(ordered)
            ordered.append(ready['id'])
            remaining.remove(ready)
    return {'last_node_id': max(value['id'] for value in nodes), 'last_link_id': len(links), 'nodes': nodes, 'links': links,
            'groups': [], 'config': {}, 'extra': {'ds': {'scale': 0.65, 'offset': [60, 80]}}, 'version': 0.4}


def install(reference_count=1):
    import os
    root = runtime.private_directory(comfyui.STORAGE / 'user')
    directory = root / 'default' / 'workflows'
    for path in (root / 'default', directory):
        if path.is_symlink() or not path.is_dir() or path.stat().st_uid != os.getuid():
            raise ValueError('Workflow directory must be owned by the operator without symlinks')
    workflow = build(reference_count)
    name = NAME if reference_count == 1 else f'Halo-Retrato-Profesional-{reference_count}Fotos-Qwen-Edit-4steps.json'
    destination = directory / name
    text = json.dumps(workflow, ensure_ascii=False, indent=2) + '\n'
    if destination.exists():
        if runtime.private_file(destination).read_text() != text:
            raise ValueError('Existing portrait workflow differs; refusing to overwrite edits')
    else:
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, 'w') as stream:
            stream.write(text)
    print('Installed workflow: ' + name)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--references', type=int, choices=(1, 2, 3), default=1)
    install(parser.parse_args().references)
