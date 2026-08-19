from __future__ import annotations

import json

from app.api.dependencies import get_webhook_service
from app.api.exceptions import raise_http_from_webhook_error
from app.config import settings
from app.integrations.calle import CalleWebhookSignatureError, unwrap_webhook
from app.models.schemas import CalleWebhookEvent
from app.services.webhook_service import WebhookService, WebhookServiceError
from fastapi import APIRouter, Depends, HTTPException, Request, status

router = APIRouter()


@router.post("/calle", status_code=status.HTTP_200_OK)
async def calle_webhook(
    request: Request,
    service: WebhookService = Depends(get_webhook_service),
):
    raw_body = await request.body()

    if not settings.calle_webhook_secret:
        try:
            event_dict = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON webhook body",
            ) from exc
    else:
        try:
            event_dict = unwrap_webhook(
                raw_body=raw_body,
                headers=dict(request.headers),
                secret=settings.calle_webhook_secret,
            )
        except CalleWebhookSignatureError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc

    event = CalleWebhookEvent.model_validate(event_dict)

    try:
        return service.process_calle_event(
            event_id=event.id,
            event_type=event.type,
            data=event.data.model_dump(),
        )
    except WebhookServiceError as exc:
        raise_http_from_webhook_error(exc)
