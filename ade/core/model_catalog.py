"""Live text model catalogue; never equate catalogue membership with account access."""
import asyncio
import time

import httpx

_cache: list[str] = []
_updated = 0.0
_lock = asyncio.Lock()


def model_ids(payload: dict) -> list[str]:
    models = []
    for row in payload.get('data', []):
        architecture = row.get('architecture') or {}
        model = row.get('id', '')
        if (isinstance(model, str) and '/' in model and len(model) < 200
                and 'text' in architecture.get('input_modalities', [])
                and 'text' in architecture.get('output_modalities', [])):
            models.append((row.get('created') or 0, 'openrouter/' + model))
    return list(dict.fromkeys(model for _, model in sorted(models, reverse=True)))


async def catalogue() -> dict:
    global _cache, _updated
    async with _lock:
        error = False
        if not _cache or time.time() - _updated > 3600:
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get('https://openrouter.ai/api/v1/models')
                    response.raise_for_status()
                    models = model_ids(response.json())
                    if not models:
                        raise ValueError('Empty catalogue')
                    _cache, _updated = models, time.time()
            except (httpx.HTTPError, ValueError, TypeError, AttributeError):
                error = True
        return {'models': _cache, 'stale': error, 'updated_at': _updated or None,
                'message': ('Каталог недоступен. Показан сохранённый список; выбранные модели сохранены.'
                            if error else 'Каталог OpenRouter: новые модели сверху. Доступ аккаунта не проверен.')}
