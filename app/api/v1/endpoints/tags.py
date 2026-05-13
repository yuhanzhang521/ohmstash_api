from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud, schemas
from app.api import deps

router = APIRouter()

DEFAULT_TAGS = [
    schemas.TagCreate(name="电阻", attribute_definitions=["阻值", "封装", "精度", "功率"]),
    schemas.TagCreate(name="电阻/贴片电阻", attribute_definitions=["阻值", "封装", "精度", "功率"]),
    schemas.TagCreate(name="电阻/插件电阻", attribute_definitions=["阻值", "精度", "功率"]),
    schemas.TagCreate(name="电容", attribute_definitions=["容值", "封装", "耐压", "介质"]),
    schemas.TagCreate(name="电容/陶瓷电容", attribute_definitions=["容值", "封装", "耐压", "温度特性"]),
    schemas.TagCreate(name="电容/电解电容", attribute_definitions=["容值", "耐压", "尺寸", "极性"]),
    schemas.TagCreate(name="电感", attribute_definitions=["感值", "封装", "额定电流", "直流电阻"]),
    schemas.TagCreate(name="二极管", attribute_definitions=["型号", "封装", "耐压", "电流"]),
    schemas.TagCreate(name="二极管/稳压二极管", attribute_definitions=["稳压值", "封装", "功率"]),
    schemas.TagCreate(name="二极管/发光二极管", attribute_definitions=["颜色", "封装", "正向电压"]),
    schemas.TagCreate(name="晶体管", attribute_definitions=["型号", "封装", "极性", "电流"]),
    schemas.TagCreate(name="MOSFET", attribute_definitions=["型号", "封装", "沟道", "耐压", "导通电阻"]),
    schemas.TagCreate(name="IC", attribute_definitions=["型号", "封装", "功能", "供电电压"]),
    schemas.TagCreate(name="IC/MCU", attribute_definitions=["型号", "封装", "内核", "Flash", "RAM"]),
    schemas.TagCreate(name="IC/电源芯片", attribute_definitions=["型号", "封装", "输入电压", "输出电压", "电流"]),
    schemas.TagCreate(name="IC/运放", attribute_definitions=["型号", "封装", "通道数", "供电电压"]),
    schemas.TagCreate(name="连接器", attribute_definitions=["类型", "间距", "针数", "封装"]),
    schemas.TagCreate(name="模块", attribute_definitions=["型号", "功能", "接口", "供电电压"]),
    schemas.TagCreate(name="模块/开发板", attribute_definitions=["型号", "主控", "接口", "供电电压"]),
    schemas.TagCreate(name="传感器", attribute_definitions=["型号", "测量类型", "接口", "供电电压"]),
    schemas.TagCreate(name="工具", attribute_definitions=["用途", "规格"]),
    schemas.TagCreate(name="线材", attribute_definitions=["类型", "长度", "接口"]),
]


@router.get("/", response_model=List[schemas.Tag])
def read_tags(
        db: Session = Depends(deps.get_db),
        skip: int = 0,
        limit: int = 100,
) -> Any:
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
) -> Any:
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
def read_default_tag_catalog() -> Any:
    return DEFAULT_TAGS


@router.post("/defaults/seed", response_model=schemas.BulkCreateResponse)
def seed_default_tags(
    *,
    db: Session = Depends(deps.get_db),
) -> Any:
    result = crud.tag.create_multiple(db=db, tags_in=DEFAULT_TAGS)
    return result


@router.post("/bulk", response_model=schemas.BulkCreateResponse, status_code=status.HTTP_200_OK)
def create_multiple_tags(
    *,
    db: Session = Depends(deps.get_db),
    tags_in: List[schemas.TagCreate],
) -> Any:
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
) -> Any:
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
) -> Any:
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
) -> Any:
    """
    Delete a tag.
    """
    tag = crud.tag.get(db, id=tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    tag = crud.tag.remove(db, id=tag_id)
    return tag
