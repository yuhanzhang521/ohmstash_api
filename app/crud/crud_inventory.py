from sqlalchemy.orm import Session
from app.crud.base import CRUDBase
from app.models import Inventory
from app.schemas.inventory import InventoryCreate, InventoryUpdate


class CRUDInventory(CRUDBase[Inventory, InventoryCreate, InventoryUpdate]):
    def get_by_sub_box_and_component(self, db: Session, *, sub_box_id: int, component_id: int) -> Inventory | None:
        return db.query(Inventory).filter(
            Inventory.sub_box_id == sub_box_id,
            Inventory.component_id == component_id
        ).first()


inventory = CRUDInventory(Inventory)

