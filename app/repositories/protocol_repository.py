from sqlalchemy.orm import Session, selectinload

from app.models.orm import DiseaseProtocol, ProtocolResultField


class ProtocolRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_active(self) -> list[DiseaseProtocol]:
        return (
            self.db.query(DiseaseProtocol)
            .filter(DiseaseProtocol.is_active.is_(True))
            .order_by(DiseaseProtocol.name.asc())
            .all()
        )

    def get_by_id(self, protocol_id: int) -> DiseaseProtocol | None:
        return (
            self.db.query(DiseaseProtocol)
            .options(
                selectinload(DiseaseProtocol.questions),
                selectinload(DiseaseProtocol.emergency_keywords),
                selectinload(DiseaseProtocol.result_fields).selectinload(
                    ProtocolResultField.enums
                ),
            )
            .filter(DiseaseProtocol.id == protocol_id)
            .first()
        )

    def get_active_by_id(self, protocol_id: int) -> DiseaseProtocol | None:
        protocol = self.get_by_id(protocol_id)
        if protocol is None or not protocol.is_active:
            return None
        return protocol
        
