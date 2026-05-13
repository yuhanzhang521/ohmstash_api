from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps

router = APIRouter()


@router.delete("/{attribute_definition_id}", response_model=schemas.AttributeDefinition)
def delete_attribute_definition(
    *,
    db: Session = Depends(deps.get_db),
    attribute_definition_id: int,
) -> Any:
    """
    Delete an attribute definition.
    """
    attribute_definition = crud.attribute_definition.get(db=db, id=attribute_definition_id)
    if not attribute_definition:
        raise HTTPException(status_code=404, detail="Attribute definition not found")
    attribute_definition = crud.attribute_definition.remove(db=db, id=attribute_definition_id)
    return attribute_definition
