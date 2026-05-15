from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps

router = APIRouter()


def _validate_inventory_references(
    db: Session,
    *,
    sub_box_id: int,
    component_id: int,
) -> None:
    if not crud.sub_box.get(db=db, id=sub_box_id):
        raise HTTPException(status_code=404, detail="Sub-box not found")
    if not crud.component.get(db=db, id=component_id):
        raise HTTPException(status_code=404, detail="Component not found")


def _validate_inventory_state(
    inventory_item: Any,
    inventory_in: schemas.InventoryUpdate,
) -> None:
    update_data = inventory_in.model_dump(exclude_unset=True)
    merged_data = {
        "sub_box_id": inventory_item.sub_box_id,
        "component_id": inventory_item.component_id,
        "stock_mode": inventory_item.stock_mode,
        "quantity_exact": inventory_item.quantity_exact,
        "quantity_fuzzy": inventory_item.quantity_fuzzy,
        "notes": inventory_item.notes,
    }
    merged_data.update(update_data)
    try:
        schemas.InventoryCreate(**merged_data)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from exc


@router.post("/", response_model=schemas.Inventory)
def create_inventory_item(
    *,
    db: Session = Depends(deps.get_db),
    inventory_in: schemas.InventoryCreate,
) -> object:
    _validate_inventory_references(
        db,
        sub_box_id=inventory_in.sub_box_id,
        component_id=inventory_in.component_id,
    )
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
) -> object:
    inventory_item = crud.inventory.get(db=db, id=inventory_id)
    if not inventory_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return inventory_item


@router.get("/", response_model=List[schemas.Inventory])
def read_inventory_items(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> object:
    inventory_items = crud.inventory.get_multi(db, skip=skip, limit=limit)
    return inventory_items


@router.put("/{inventory_id}", response_model=schemas.Inventory)
def update_inventory_item(
    *,
    db: Session = Depends(deps.get_db),
    inventory_id: int,
    inventory_in: schemas.InventoryUpdate,
) -> object:
    inventory_item = crud.inventory.get(db=db, id=inventory_id)
    if not inventory_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")

    target_sub_box_id = inventory_in.sub_box_id or inventory_item.sub_box_id
    target_component_id = inventory_in.component_id or inventory_item.component_id
    _validate_inventory_references(
        db,
        sub_box_id=target_sub_box_id,
        component_id=target_component_id,
    )
    _validate_inventory_state(inventory_item, inventory_in)
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
) -> object:
    inventory_item = crud.inventory.get(db=db, id=inventory_id)
    if not inventory_item:
        raise HTTPException(status_code=404, detail="Inventory item not found")
    inventory_item = crud.inventory.remove(db=db, id=inventory_id)
    return inventory_item
