from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_call_service
from app.api.exceptions import raise_http_from_trigger_error
from app.models.schemas import CallRead, CallTriggerRequest
from app.services.call_service import CallService, TriggerError

router = APIRouter()


@router.post(
    "/trigger",
    response_model=CallRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_call(
    payload: CallTriggerRequest,
    service: CallService = Depends(get_call_service),
):
    try:
        return service.trigger(
            patient_id=payload.patient_id,
            followup_id=payload.followup_id,
            dry_run=payload.dry_run,
        )
    except TriggerError as exc:
        raise_http_from_trigger_error(exc)


@router.get("", response_model=list[CallRead])
def list_calls(service: CallService = Depends(get_call_service)):
    return service.list()


@router.get("/{call_id}", response_model=CallRead)
def get_call(call_id: int, service: CallService = Depends(get_call_service)):
    try:
        return service.get(call_id)
    except TriggerError as exc:
        raise_http_from_trigger_error(exc)
