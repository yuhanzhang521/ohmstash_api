from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps

router = APIRouter()


@router.post("/", response_model=schemas.Inventory)
def create_inventory_item(
    *,
    db: Session = Depends(deps.get_db),
    inventory_in: schemas.InventoryCreate,
) -> Any:
    """
    Create a new inventory item, linking a component to a sub-box.
    A component can only exist once in a sub-box.
    """
    existing_item = crud.inventory.get_by_sub_box_and_component(
        db,
        sub_box_id=inventory_in.sub_box_id,
        component_id=inventory_in.component_id,
    )
    if existing_item:
        raise HTTPException(
            status_code=400,
            detail=(
                "This component already exists in this sub-box. "
                "Update the existing entry instead."
            ),
        )
    inventory_item = crud.inventory.create(db=db, obj_in=inventory_in)
    return inventory_item


@router.get("/{inventory_id}", response_model=schemas.Inventory)
def read_inventory_item(
    *,
    db: Session = Depends(deps.get_db),
    inventory_id: int,
) -> Any:
    """
    Get a specific inventory item by its ID.
    """
    inventory_item = crud.inventory.get(db=db, id=inventory_id)
    if not inventory_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return inventory_item


@router.get("/", response_model=List[schemas.Inventory])
def read_inventory_items(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve inventory items.
    """
    inventory_items = crud.inventory.get_multi(db, skip=skip, limit=limit)
    return inventory_items


@router.put("/{inventory_id}", response_model=schemas.Inventory)
def update_inventory_item(
    *,
    db: Session = Depends(deps.get_db),
    inventory_id: int,
    inventory_in: schemas.InventoryUpdate,
) -> Any:
    """
    Update an inventory item.
    """
    inventory_item = crud.inventory.get(db=db, id=inventory_id)
    if not inventory_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    target_sub_box_id = inventory_in.sub_box_id or inventory_item.sub_box_id
    target_component_id = inventory_in.component_id or inventory_item.component_id
    existing_item = crud.inventory.get_by_sub_box_and_component(
        db,
        sub_box_id=target_sub_box_id,
        component_id=target_component_id,
    )
    if existing_item and existing_item.id != inventory_item.id:
        raise HTTPException(
            status_code=400,
            detail="This component already exists in this sub-box.",
        )

    inventory_item = crud.inventory.update(
        db=db,
        db_obj=inventory_item,
        obj_in=inventory_in,
    )
    return inventory_item


@router.delete("/{inventory_id}", response_model=schemas.Inventory)
def delete_inventory_item(
    *,
    db: Session = Depends(deps.get_db),
    inventory_id: int,
) -> Any:
    """
    Delete an inventory item.
    """
    inventory_item = crud.inventory.get(db=db, id=inventory_id)
    if not inventory_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    inventory_item = crud.inventory.remove(db=db, id=inventory_id)
    return inventory_item
