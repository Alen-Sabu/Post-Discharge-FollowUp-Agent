from fastapi import APIRouter, Depends

from app.api.dependencies import get_protocol_service
from app.api.exceptions import raise_http_from_protocol_error
from app.models.schemas import DiseaseProtocolDetail, DiseaseProtocolListItem
from app.services.protocol_service import ProtocolService, ProtocolServiceError

router = APIRouter()


@router.get("", response_model=list[DiseaseProtocolListItem])
def list_protocols(service: ProtocolService = Depends(get_protocol_service)):
    return service.list_active()


@router.get("/{protocol_id}", response_model=DiseaseProtocolDetail)
def get_protocol(
    protocol_id: int,
    service: ProtocolService = Depends(get_protocol_service),
): 
    try:
        return service.get_detail_response(protocol_id)
    except ProtocolServiceError as exc:
        raise_http_from_protocol_error(exc)