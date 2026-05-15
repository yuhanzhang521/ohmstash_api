from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps
from app.services.default_tags import load_default_tags

router = APIRouter()


@router.get("/", response_model=List[schemas.Tag])
def read_tags(
        db: Session = Depends(deps.get_db),
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=500),
) -> object:
    """
    Retrieve tags.
    """
    tags = crud.tag.get_multi(db, skip=skip, limit=limit)
    return tags


@router.post("/", response_model=schemas.Tag, status_code=status.HTTP_201_CREATED)
def create_tag(
        *,
        db: Session = Depends(deps.get_db),
        tag_in: schemas.TagCreate,
) -> object:
    """
    Create new tag.
    """
    tag = crud.tag.get_by_name(db, name=tag_in.name)
    if tag:
        raise HTTPException(
            status_code=400,
            detail="A tag with this name already exists.",
        )
    tag = crud.tag.create(db, obj_in=tag_in)
    return tag


@router.get("/defaults/catalog", response_model=List[schemas.TagCreate])
def read_default_tag_catalog() -> object:
    return list(load_default_tags())


@router.post("/defaults/seed", response_model=schemas.BulkCreateResponse)
def seed_default_tags(
    *,
    db: Session = Depends(deps.get_db),
) -> object:
    result = crud.tag.create_multiple(db=db, tags_in=list(load_default_tags()))
    return result


@router.post("/bulk", response_model=schemas.BulkCreateResponse, status_code=status.HTTP_200_OK)
def create_multiple_tags(
    *,
    db: Session = Depends(deps.get_db),
    tags_in: List[schemas.TagCreate],
) -> object:
    """
    Create multiple tags at once.
    If a tag name already exists, it will be skipped.
    Returns a report of created and skipped tags.
    """
    submitted_names = [tag.name for tag in tags_in]
    if len(submitted_names) != len(set(submitted_names)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate tag names found in the submitted list. Please send unique names."
        )
    result = crud.tag.create_multiple(db=db, tags_in=tags_in)
    return result


@router.put("/{tag_id}", response_model=schemas.Tag)
def update_tag(
        *,
        db: Session = Depends(deps.get_db),
        tag_id: int,
        tag_in: schemas.TagUpdate,
) -> object:
    """
    Update a tag.
    """
    tag = crud.tag.get(db, id=tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    existing_tag_with_new_name = crud.tag.get_by_name(db, name=tag_in.name)
    if existing_tag_with_new_name and existing_tag_with_new_name.id != tag_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tag with name '{tag_in.name}' already exists."
        )

    tag = crud.tag.update(db, db_obj=tag, obj_in=tag_in)
    return tag


@router.get("/{tag_id}", response_model=schemas.TagWithAttributes)
def read_tag(
        *,
        db: Session = Depends(deps.get_db),
        tag_id: int,
) -> object:
    """
    Get tag by ID.
    """
    tag = crud.tag.get(db, id=tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return tag


@router.delete("/{tag_id}", response_model=schemas.Tag)
def delete_tag(
        *,
        db: Session = Depends(deps.get_db),
        tag_id: int,
) -> object:
    """
    Delete a tag.
    """
    tag = crud.tag.get(db, id=tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag = crud.tag.remove(db, id=tag_id)
    return tag
