from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps

router = APIRouter()


def _validate_template_update(
    box_template: schemas.BoxTemplate,
    box_template_in: schemas.BoxTemplateUpdate,
) -> None:
    update_data = box_template_in.model_dump(exclude_unset=True)
    merged_data = {
        "name": box_template.name,
        "physical_dimensions": box_template.physical_dimensions,
        "layout_type": box_template.layout_type,
        "layout_definition": box_template.layout_definition,
    }
    merged_data.update(update_data)
    try:
        schemas.BoxTemplateCreate(**merged_data)
    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.errors()) from exc


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
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
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
    _validate_template_update(
        schemas.BoxTemplate.model_validate(box_template, from_attributes=True),
        box_template_in,
    )
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
