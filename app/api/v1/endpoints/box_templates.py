from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps

router = APIRouter()


@router.post("/", response_model=schemas.BoxTemplate)
def create_box_template(
    *,
    db: Session = Depends(deps.get_db),
    box_template_in: schemas.BoxTemplateCreate,
) -> Any:
    box_template = crud.box_template.create(db=db, obj_in=box_template_in)
    return box_template


@router.get("/", response_model=List[schemas.BoxTemplate])
def read_box_templates(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    box_templates = crud.box_template.get_multi(db, skip=skip, limit=limit)
    return box_templates


@router.get("/{box_template_id}", response_model=schemas.BoxTemplate)
def read_box_template(
    *,
    db: Session = Depends(deps.get_db),
    box_template_id: int,
) -> Any:
    box_template = crud.box_template.get(db=db, id=box_template_id)
    if not box_template:
        raise HTTPException(status_code=404, detail="Box template not found")
    return box_template


@router.put("/{box_template_id}", response_model=schemas.BoxTemplate)
def update_box_template(
    *,
    db: Session = Depends(deps.get_db),
    box_template_id: int,
    box_template_in: schemas.BoxTemplateUpdate,
) -> Any:
    box_template = crud.box_template.get(db=db, id=box_template_id)
    if not box_template:
        raise HTTPException(status_code=404, detail="Box template not found")
    box_template = crud.box_template.update(
        db=db,
        db_obj=box_template,
        obj_in=box_template_in,
    )
    return box_template


@router.delete("/{box_template_id}", response_model=schemas.BoxTemplate)
def delete_box_template(
    *,
    db: Session = Depends(deps.get_db),
    box_template_id: int,
) -> Any:
    box_template = crud.box_template.get(db=db, id=box_template_id)
    if not box_template:
        raise HTTPException(status_code=404, detail="Box template not found")
    box_template = crud.box_template.remove(db=db, id=box_template_id)
    return box_template

