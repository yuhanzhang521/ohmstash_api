from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps

router = APIRouter()


@router.post("/", response_model=schemas.Component)
def create_component(
    *,
    db: Session = Depends(deps.get_db),
    component_in: schemas.ComponentCreate,
) -> models.Component:
    component = crud.component.create(db=db, obj_in=component_in)
    return component


@router.get("/", response_model=List[schemas.Component])
def read_components(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    tag_ids: Optional[List[int]] = Query(None),
) -> List[models.Component]:
    if tag_ids:
        components = crud.component.get_multi_by_tags(
            db=db,
            tag_ids=tag_ids,
            skip=skip,
            limit=limit,
        )
        return components

    components = crud.component.get_multi(db=db, skip=skip, limit=limit)
    return components


@router.get("/{component_id}", response_model=schemas.Component)
def read_component(
    *,
    db: Session = Depends(deps.get_db),
    component_id: int,
) -> models.Component:
    component = crud.component.get(db=db, id=component_id)
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")
    return component


@router.put("/{component_id}", response_model=schemas.Component)
def update_component(
    *,
    db: Session = Depends(deps.get_db),
    component_id: int,
    component_in: schemas.ComponentUpdate,
) -> models.Component:
    component = crud.component.get(db=db, id=component_id)
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")
    component = crud.component.update(db=db, db_obj=component, obj_in=component_in)
    return component


@router.delete("/{component_id}", response_model=schemas.Component)
def delete_component(
    *,
    db: Session = Depends(deps.get_db),
    component_id: int,
) -> models.Component:
    component = crud.component.get(db=db, id=component_id)
    if not component:
        raise HTTPException(status_code=404, detail="Component not found")
    component = crud.component.remove(db=db, id=component_id)
    return component

