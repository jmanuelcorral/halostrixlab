import os
import threading


MODEL = 'convaiinnovations/laya-multilingual'
MAX_BODY = 65536


def validate_request(body):
    if not isinstance(body, dict) or set(body) - {'model', 'state', 'questions'}:
        raise ValueError('Expected state, questions and optional model')
    if body.get('model', 'multilingual') not in ('multilingual', 'laya', MODEL):
        raise ValueError('Only the installed multilingual checkpoint is available')
    if not isinstance(body.get('state'), (str, dict, list)):
        raise ValueError('state must be text, an object or a list')
    questions = body.get('questions')
    if not isinstance(questions, dict) or not 1 <= len(questions) <= 8:
        raise ValueError('Provide between 1 and 8 questions')
    for question in questions.values():
        if not isinstance(question, dict) or question.get('type') not in ('choice', 'score', 'noul'):
            raise ValueError('Unsupported question type')
        criteria = question.get('criteria', {})
        if not isinstance(criteria, (dict, list)) or len(criteria) > 20:
            raise ValueError('At most 20 criteria per question')
    return body['state'], questions


def create_app(agent):
    import asyncio
    from fastapi import FastAPI, Request
    from fastapi.responses import JSONResponse

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    gate = threading.Lock()

    @app.get('/health')
    def health():
        return {'status': 'ok', 'model': MODEL, 'device': str(agent.device), 'revision': os.environ.get('LAYA_MODEL_REVISION', '')}

    @app.post('/v1/systemone')
    async def decide(request: Request):
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) > MAX_BODY:
                return JSONResponse({'error': 'Request exceeds 64 KiB'}, status_code=413)
        try:
            import json
            state, questions = validate_request(json.loads(content))
        except (ValueError, TypeError):
            return JSONResponse({'error': 'Invalid decision request; use 1-8 typed questions and at most 20 criteria'}, status_code=422)
        if not gate.acquire(blocking=False):
            return JSONResponse({'error': 'Decision worker busy; retry later'}, status_code=429)
        def infer():
            try:
                result = agent.predict(state, questions)
                result['model'] = MODEL
                return result
            finally:
                gate.release()
        try:
            result = await asyncio.shield(asyncio.to_thread(infer))
            return result
        except (ValueError, TypeError, KeyError):
            return JSONResponse({'error': 'Invalid question schema'}, status_code=422)
        except Exception:
            return JSONResponse({'error': 'Inference failed'}, status_code=500)

    return app


def main():
    import laya
    import torch
    import uvicorn

    torch.set_num_threads(4)
    torch.set_num_interop_threads(1)
    import shutil
    from pathlib import Path
    model = Path('/tmp/laya-model')
    model.mkdir(exist_ok=True)
    for name in ('encoder', 'tokenizer'):
        shutil.copytree(Path('/models') / name, model / name, dirs_exist_ok=True)
    shutil.copyfile('/models/rl_agent_config.json', model / 'rl_agent_config.json')
    (model / 'model.safetensors').symlink_to('/models/model.safetensors')
    agent = laya.load(str(model), device='cpu', fast=False)
    if str(agent.device) != 'cpu':
        raise ValueError('This service must use CPU only')
    uvicorn.run(create_app(agent), host='0.0.0.0', port=8000, access_log=False, limit_concurrency=8)


if __name__ == '__main__':
    main()
