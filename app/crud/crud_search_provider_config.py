from typing import Optional

from sqlalchemy.orm import Session

from app.crud.base import CRUDBase
from app.models.search_provider_config import SearchProviderConfig
from app.schemas.search_provider_config import (
    SearchProviderConfigCreate,
    SearchProviderConfigUpdate,
)


class CRUDSearchProviderConfig(
    CRUDBase[
        SearchProviderConfig,
        SearchProviderConfigCreate,
        SearchProviderConfigUpdate,
    ]
):
    def get_by_name(
        self,
        db: Session,
        *,
        name: str,
    ) -> Optional[SearchProviderConfig]:
        return db.query(self.model).filter(self.model.name == name).first()

    def get_default(self, db: Session) -> Optional[SearchProviderConfig]:
        return db.query(self.model).filter(self.model.is_default.is_(True)).first()

    def create(
        self,
        db: Session,
        *,
        obj_in: SearchProviderConfigCreate,
    ) -> SearchProviderConfig:
        db_obj = super().create(db=db, obj_in=obj_in)
        if db_obj.is_default:
            self._clear_other_defaults(db=db, config_id=db_obj.id)
            db.refresh(db_obj)
        return db_obj

    def update(
        self,
        db: Session,
        *,
        db_obj: SearchProviderConfig,
        obj_in: SearchProviderConfigUpdate,
    ) -> SearchProviderConfig:
        db_obj = super().update(db=db, db_obj=db_obj, obj_in=obj_in)
        if db_obj.is_default:
            self._clear_other_defaults(db=db, config_id=db_obj.id)
            db.refresh(db_obj)
        return db_obj

    def set_default(
        self,
        db: Session,
        *,
        db_obj: SearchProviderConfig,
    ) -> SearchProviderConfig:
        self._clear_other_defaults(db=db, config_id=db_obj.id)
        db_obj.is_default = True
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def _clear_other_defaults(self, db: Session, *, config_id: int) -> None:
        db.query(self.model).filter(
            self.model.id != config_id,
            self.model.is_default.is_(True),
        ).update({"is_default": False}, synchronize_session=False)
        db.commit()


search_provider_config = CRUDSearchProviderConfig(SearchProviderConfig)
