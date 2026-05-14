from datetime import datetime, timezone
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app import crud, models, schemas
from app.api import deps
from app.services.box_labeling import (
    build_box_label_summary_lines,
    compute_box_category_summary,
    generate_next_box_readable_id,
)
from app.services.component_display import build_component_display_name
from app.services.label_generator import generate_box_label_svg
from app.services.wdfx_label import generate_box_label_wdfx

router = APIRouter()


def _get_component_display_name(
    component: Optional[models.Component],
) -> Optional[str]:
    if not component:
        return None
    return build_component_display_name(
        component.attributes,
        component.display_attribute,
    )


@router.post("/", response_model=schemas.Box)
def create_box(
    *,
    db: Session = Depends(deps.get_db),
    box_in: schemas.BoxCreate,
) -> Any:
    template = crud.box_template.get(db=db, id=box_in.template_id)
    if not template:
        raise HTTPException(status_code=404, detail="Box template not found")

    if not box_in.readable_id:
        box_in = schemas.BoxCreate(
            readable_id=generate_next_box_readable_id(db),
            name=box_in.name,
            template_id=box_in.template_id,
        )

    existing_box = (
        db.query(models.Box)
        .filter(models.Box.readable_id == box_in.readable_id)
        .first()
    )
    if existing_box:
        raise HTTPException(status_code=400, detail="Box readable_id already exists")

    box = crud.box.create(db=db, obj_in=box_in)
    return box


@router.get("/", response_model=List[schemas.Box])
def read_boxes(
    db: Session = Depends(deps.get_db),
    skip: int = 0,
    limit: int = 100,
) -> Any:
    boxes = crud.box.get_multi(db, skip=skip, limit=limit)
    return boxes


@router.get("/{box_id}/overview", response_model=schemas.BoxOverview)
def read_box_overview(
    *,
    db: Session = Depends(deps.get_db),
    box_id: int,
) -> Any:
    box = crud.box.get(db=db, id=box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")

    template = box.template
    sub_box_overviews = []
    for sub_box in sorted(box.sub_boxes, key=lambda item: item.position_identifier):
        inventory_items = []
        for inventory_item in sub_box.inventory:
            component = inventory_item.component
            inventory_items.append(
                {
                    "inventory_id": inventory_item.id,
                    "component_id": component.id if component else None,
                    "component_name": component.name if component else None,
                    "display_attribute": (
                        component.display_attribute if component else None
                    ),
                    "display_name": _get_component_display_name(component),
                    "tags": [tag.name for tag in component.tags] if component else [],
                    "attributes": component.attributes if component else {},
                    "stock_mode": inventory_item.stock_mode,
                    "quantity_exact": inventory_item.quantity_exact,
                    "quantity_fuzzy": inventory_item.quantity_fuzzy,
                    "notes": inventory_item.notes,
                }
            )
        sub_box_overviews.append(
            schemas.SubBoxOverview(
                id=sub_box.id,
                readable_id=sub_box.readable_id,
                position_identifier=sub_box.position_identifier,
                inventory=inventory_items,
            )
        )

    return schemas.BoxOverview(
        id=box.id,
        readable_id=box.readable_id,
        name=box.name,
        template={
            "id": template.id,
            "name": template.name,
            "layout_type": template.layout_type,
            "layout_definition": template.layout_definition,
            "physical_dimensions": template.physical_dimensions,
        },
        sub_boxes=sub_box_overviews,
        category_summary=compute_box_category_summary(box),
        label_needs_reprint=box.label_needs_reprint,
        printed_label_at=box.printed_label_at,
    )


@router.get("/{box_id}/label.svg")
def read_box_label(
    *,
    db: Session = Depends(deps.get_db),
    box_id: int,
) -> Response:
    box = crud.box.get(db=db, id=box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")

    svg = generate_box_label_svg(
        readable_id=box.readable_id,
        template_name=box.template.name if box.template else "Unknown Template",
        layout_type=box.template.layout_type if box.template else None,
        layout_definition=box.template.layout_definition if box.template else None,
        box_name=box.name,
        summary_lines=build_box_label_summary_lines(box),
    )
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={
            "Content-Disposition": f'inline; filename="{box.readable_id}-label.svg"',
        },
    )


@router.get("/{box_id}/label.wdfx")
def read_box_label_wdfx(
    *,
    db: Session = Depends(deps.get_db),
    box_id: int,
) -> Response:
    box = crud.box.get(db=db, id=box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")

    wdfx = generate_box_label_wdfx(box)
    box.printed_label_signature = box.current_label_signature
    box.printed_label_at = datetime.now(timezone.utc)
    db.add(box)
    db.commit()
    return Response(
        content=wdfx,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": (
                f'attachment; filename="{box.readable_id}-label.wdfx"'
            ),
        },
    )


@router.get("/{box_id}", response_model=schemas.Box)
def read_box(
    *,
    db: Session = Depends(deps.get_db),
    box_id: int,
) -> Any:
    box = crud.box.get(db=db, id=box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    return box


@router.put("/{box_id}", response_model=schemas.Box)
def update_box(
    *,
    db: Session = Depends(deps.get_db),
    box_id: int,
    box_in: schemas.BoxUpdate,
) -> Any:
    box = crud.box.get(db=db, id=box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")

    if box_in.template_id is not None:
        template = crud.box_template.get(db=db, id=box_in.template_id)
        if not template:
            raise HTTPException(status_code=404, detail="Box template not found")

    box = crud.box.update(db=db, db_obj=box, obj_in=box_in)
    return box


@router.delete("/{box_id}", response_model=schemas.Box)
def delete_box(
    *,
    db: Session = Depends(deps.get_db),
    box_id: int,
    delete_components: bool = False,
) -> Any:
    box = crud.box.get(db=db, id=box_id)
    if not box:
        raise HTTPException(status_code=404, detail="Box not found")
    deleted_box = schemas.Box.model_validate(box)
    component_ids = []
    if delete_components:
        component_ids = [
            row[0]
            for row in db.query(models.Inventory.component_id)
            .join(models.SubBox)
            .filter(models.SubBox.box_id == box_id)
            .distinct()
            .all()
        ]

    db.delete(box)
    db.flush()
    if component_ids:
        components = (
            db.query(models.Component)
            .filter(models.Component.id.in_(component_ids))
            .all()
        )
        for component in components:
            if not component.inventory:
                db.delete(component)
    db.commit()
    return deleted_box
