from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps

router = APIRouter()


@router.get("/", response_model=List[schemas.SubBox])
def read_sub_boxes_for_box(
    box_id: int,
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> Any:
    """
    Retrieve sub-boxes for a specific box.
    """
    sub_boxes = crud.sub_box.get_multi_by_box(
        db=db,
        box_id=box_id,
        skip=skip,
        limit=limit,
    )
    return sub_boxes


@router.get("/by_readable_id/{readable_id}", response_model=schemas.SubBox)
def read_sub_box_by_readable_id(
    *,
    db: Session = Depends(deps.get_db),
    readable_id: str,
) -> Any:
    sub_box = (
        db.query(models.SubBox)
        .filter(models.SubBox.readable_id == readable_id)
        .first()
    )
    if not sub_box:
        raise HTTPException(status_code=404, detail="Sub-box not found")
    return sub_box


@router.post("/move_inventory", response_model=schemas.InventoryMoveResult)
def move_sub_box_inventory(
    *,
    db: Session = Depends(deps.get_db),
    move_in: schemas.MoveInventoryRequest,
) -> Any:
    source_sub_box = crud.sub_box.get(db=db, id=move_in.source_sub_box_id)
    target_sub_box = crud.sub_box.get(db=db, id=move_in.target_sub_box_id)
    if not source_sub_box or not target_sub_box:
        raise HTTPException(status_code=404, detail="Source or target sub-box not found")

    source_items = list(source_sub_box.inventory)
    target_items = list(target_sub_box.inventory)
    if target_items and not move_in.allow_merge:
        raise HTTPException(status_code=400, detail="Target sub-box is not empty")

    target_component_ids = {item.component_id for item in target_items}
    duplicate_component_ids = [
        item.component_id
        for item in source_items
        if item.component_id in target_component_ids
    ]
    if duplicate_component_ids:
        raise HTTPException(
            status_code=400,
            detail="Target sub-box already contains one or more moved components",
        )

    for item in source_items:
        item.sub_box_id = target_sub_box.id
        db.add(item)
    db.commit()
    for item in source_items:
        db.refresh(item)

    return schemas.InventoryMoveResult(
        source_sub_box_id=source_sub_box.id,
        target_sub_box_id=target_sub_box.id,
        moved_items=source_items,
    )


@router.post("/swap_inventory", response_model=List[schemas.Inventory])
def swap_sub_box_inventory(
    *,
    db: Session = Depends(deps.get_db),
    swap_in: schemas.SwapInventoryRequest,
) -> Any:
    first_sub_box = crud.sub_box.get(db=db, id=swap_in.first_sub_box_id)
    second_sub_box = crud.sub_box.get(db=db, id=swap_in.second_sub_box_id)
    if not first_sub_box or not second_sub_box:
        raise HTTPException(status_code=404, detail="First or second sub-box not found")

    first_items = list(first_sub_box.inventory)
    second_items = list(second_sub_box.inventory)
    first_component_ids = {item.component_id for item in first_items}
    second_component_ids = {item.component_id for item in second_items}
    if first_component_ids.intersection(second_component_ids):
        raise HTTPException(
            status_code=400,
            detail="Cannot swap sub-boxes containing the same component",
        )

    for item in first_items:
        item.sub_box_id = second_sub_box.id
        db.add(item)
    db.flush()
    for item in second_items:
        item.sub_box_id = first_sub_box.id
        db.add(item)
    db.commit()

    moved_items = first_items + second_items
    for item in moved_items:
        db.refresh(item)
    return moved_items


@router.get("/{sub_box_id}", response_model=schemas.SubBox)
def read_sub_box(
    *,
    db: Session = Depends(deps.get_db),
    sub_box_id: int,
) -> Any:
    """
    Get a specific sub-box by ID.
    """
    sub_box = crud.sub_box.get(db, id=sub_box_id)
    if not sub_box:
        raise HTTPException(status_code=404, detail="Sub-box not found")
    return sub_box
