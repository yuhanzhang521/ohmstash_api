from fastapi import APIRouter
from fastapi import Depends

from app.api import deps
from app.api.v1.endpoints import (
    ai,
    auth,
    attribute_definitions,
    box_templates,
    boxes,
    components,
    inventory,
    search,
    sub_boxes,
    system,
    tags,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
protected_dependencies = [Depends(deps.get_current_principal)]
api_router.include_router(
    ai.router,
    prefix="/ai",
    tags=["ai"],
    dependencies=protected_dependencies,
)
api_router.include_router(
    attribute_definitions.router,
    prefix="/attribute_definitions",
    tags=["attribute_definitions"],
    dependencies=protected_dependencies,
)
api_router.include_router(
    tags.router,
    prefix="/tags",
    tags=["tags"],
    dependencies=protected_dependencies,
)
api_router.include_router(
    box_templates.router,
    prefix="/box_templates",
    tags=["box_templates"],
    dependencies=protected_dependencies,
)
api_router.include_router(
    boxes.router,
    prefix="/boxes",
    tags=["boxes"],
    dependencies=protected_dependencies,
)
api_router.include_router(
    sub_boxes.router,
    prefix="/sub_boxes",
    tags=["sub_boxes"],
    dependencies=protected_dependencies,
)
api_router.include_router(
    components.router,
    prefix="/components",
    tags=["components"],
    dependencies=protected_dependencies,
)
api_router.include_router(
    inventory.router,
    prefix="/inventory",
    tags=["inventory"],
    dependencies=protected_dependencies,
)
api_router.include_router(
    search.router,
    prefix="/search",
    tags=["search"],
    dependencies=protected_dependencies,
)
api_router.include_router(
    system.router,
    prefix="/system",
    tags=["system"],
    dependencies=protected_dependencies,
)
