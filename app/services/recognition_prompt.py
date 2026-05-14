import json
from typing import Any, List

from sqlalchemy.orm import Session, joinedload

from app.models.box import Box
from app.models.box_template import BoxTemplate
from app.models.tag import Tag
from app.services.box_name_rules import BOX_NAME_MAX_DISPLAY_WIDTH


BOX_NAME_RULE_TEXT = (
    f"盒子名称的显示宽度必须不超过 {BOX_NAME_MAX_DISPLAY_WIDTH}（汉字按 2 计、英数字符按 1 计），"
    f"即最多 7 个汉字、或 6 个汉字加 2 个英数字符、或 14 个英数字符。"
    "不要包含“收纳盒”“盒子”“盒”等后缀；例如返回“电源芯片”而不是“电源芯片盒”。"
)

NOTES_RULE_TEXT = (
    "notes 只允许写器件本身的补充信息（用途、功能、关键参数解释等），"
    "禁止写拍摄角度、标签朝向、标签是否可见、标签包含几行字、竖放横放等图像或拍摄过程的旁白；"
    "看不到或不确定的，notes 留空。"
)


def build_component_recognition_prompt(
    db: Session,
    *,
    additional_prompt: str = "",
) -> str:
    tags = (
        db.query(Tag)
        .options(joinedload(Tag.attribute_definitions))
        .order_by(Tag.name)
        .all()
    )
    tag_lines: List[str] = []
    for tag in tags:
        attributes = [item.attribute_name for item in tag.attribute_definitions]
        attribute_text = ", ".join(attributes) if attributes else "无固定属性"
        tag_lines.append(f"- {tag.name}: {attribute_text}")

    tag_catalog = "\n".join(tag_lines) if tag_lines else "当前数据库还没有定义 Tag。"
    extra_instruction = f"\n补充要求：{additional_prompt}" if additional_prompt else ""
    return (
        "你是一个电子元器件视觉识别助手。请识别图片里的主体元器件或工具。\n"
        "如果图片为空格、空盒、无法判断或没有元器件，请把 is_empty 设为 true。\n"
        "如果能识别，请优先使用下面 Tag 库里的标签，并按标签定义抽取属性。\n\n"
        "display_attribute 必须是 attributes 中最适合在盒内缩略格子里显示的属性名。"
        "阻容感优先选择阻值、容值或电感值，例如名称为 0603 75pF 50V 10% 时，"
        "attributes 写入容值=75pF 且 display_attribute 写入容值。"
        "芯片、模块或传感器可以选择型号；长型号允许在前端被省略号截断，不要为了缩略显示改短 name。\n\n"
        f"{NOTES_RULE_TEXT}\n\n"
        f"Tag 与属性库：\n{tag_catalog}\n\n"
        "请只返回一个 JSON 对象，不要返回 Markdown，不要额外解释。格式必须是：\n"
        "{\n"
        '  "is_empty": false,\n'
        '  "name": "10K 0603 1%",\n'
        '  "tags": ["贴片", "电阻"],\n'
        '  "attributes": {"封装": "0603", "阻值": "10K", "精度": "1%"},\n'
        '  "display_attribute": "阻值",\n'
        '  "confidence": 0.82,\n'
        '  "notes": "可选说明"\n'
        "}\n"
        f"{extra_instruction}"
    )


def build_box_recognition_prompt(
    db: Session,
    *,
    box: Box,
    additional_prompt: str = "",
) -> str:
    base_prompt = build_component_recognition_prompt(
        db,
        additional_prompt=additional_prompt,
    )
    sub_box_positions = [
        item.position_identifier
        for item in sorted(
            box.sub_boxes,
            key=lambda sub_box: sub_box.position_identifier,
        )
    ]
    layout_payload: dict[str, Any] = {
        "box_readable_id": box.readable_id,
        "box_name": box.name,
        "template_name": box.template.name if box.template else None,
        "layout_type": box.template.layout_type if box.template else None,
        "layout_definition": box.template.layout_definition if box.template else None,
        "sub_box_positions": sub_box_positions,
    }
    return (
        f"{base_prompt}\n\n"
        "这是一张完整盒子的照片。请根据下面盒子布局，把每个子格分别识别出来。\n"
        f"盒子布局 JSON：{json.dumps(layout_payload, ensure_ascii=False)}\n"
        "请只返回一个 JSON 对象，格式必须是：\n"
        "{\n"
        '  "box_readable_id": "BOX-A01",\n'
        '  "cells": [\n'
        "    {\n"
        '      "position_identifier": "R1C1",\n'
        '      "is_empty": false,\n'
        '      "name": "10K 0603 1%",\n'
        '      "tags": ["贴片", "电阻"],\n'
        '      "attributes": {"封装": "0603", "阻值": "10K"},\n'
        '      "display_attribute": "阻值",\n'
        '      "confidence": 0.82,\n'
        '      "notes": "可选说明"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )


def build_new_box_recognition_prompt(
    db: Session,
    *,
    template: BoxTemplate,
    additional_prompt: str = "",
) -> str:
    base_prompt = build_component_recognition_prompt(
        db,
        additional_prompt=additional_prompt,
    )
    layout_payload: dict[str, Any] = {
        "template_name": template.name,
        "layout_type": template.layout_type,
        "layout_definition": template.layout_definition,
    }
    return (
        f"{base_prompt}\n\n"
        "这是一张准备新建入库盒子的完整照片。请根据下面盒子模板，把每个子格分别识别出来。\n"
        "请同时根据盒内主要元器件给这个盒子起一个简短、适合打印在标签上的中文名称。"
        f"{BOX_NAME_RULE_TEXT}\n"
        "规则网格的规格文字按“列x行”理解，例如 7 行 4 列写作 4x7。\n"
        f"盒子模板 JSON：{json.dumps(layout_payload, ensure_ascii=False)}\n"
        "请只返回一个 JSON 对象，格式必须是：\n"
        "{\n"
        '  "box_name": "电源芯片",\n'
        '  "cells": [\n'
        "    {\n"
        '      "position_identifier": "R1C1",\n'
        '      "is_empty": false,\n'
        '      "name": "BQ24195RGER",\n'
        '      "tags": ["IC", "IC/电源芯片"],\n'
        '      "attributes": {"型号": "BQ24195RGER", "封装": "VQFN-24"},\n'
        '      "display_attribute": "型号",\n'
        '      "confidence": 0.82,\n'
        '      "notes": "可选说明"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )


def build_box_template_recognition_prompt(
    db: Session,
    *,
    layout_type: str,
    additional_prompt: str = "",
) -> str:
    base_prompt = build_component_recognition_prompt(
        db,
        additional_prompt=additional_prompt,
    )
    grid_instruction = (
        "用户预期这是规则网格。请识别行数 rows、列数 cols，"
        "并使用 R1C1 这种 position_identifier 返回每个格子的结果。"
    )
    irregular_instruction = (
        "用户预期这是不规则网格。请为每个可用格子生成稳定的 id，"
        "例如 A1、A2、B1 或 CELL-01，并在 layout_definition 中返回 cells 列表。"
        "每个 cells 项必须包含 id、label、数字 row、数字 col；如果有旋转、跨格或特殊尺寸，"
        "继续增加 row_span、col_span、x、y、width、height。"
        "row、col 表示这个小格左上角所在的可视网格坐标，必须能让前端按真实摆放复原布局，"
        "不要只在 notes 或 label 中写“左上、右下、竖放”等文字描述。"
        "如果画面中是若干尺寸一致的小收纳盒，只是摆放方向或分组不同，"
        "请把每一个小收纳盒识别为一个 cell，不要把外层大盒误判为单一规则网格。"
        "同款小盒横放和竖放都应视为同一规格的小格子，并在 cell 中写入 orientation，"
        "例如 landscape、portrait 或 rotated_90。"
        "常见样式包括左侧 2 列 x 5 排，右侧同款小盒旋转后按 2 x 2 摆放；"
        "这种情况应返回 14 个 cell，并把右侧 4 个竖放小盒排成 2 x 2，"
        "用 group、row、col、row_span、col_span 描述它们的相对位置。"
        "右侧竖放列必须按连续实际顺序排布；例如左侧五排横放每格 row_span=2 时，"
        "右侧上下两个竖放格应为 row=1,row_span=5 和 row=6,row_span=5，"
        "不要因为编号是 C1、C3 就把第二个竖放格放到 row=11。"
        "不规则小格编号请按列优先，从左到右分列，每列从上到下编号，"
        "例如第一列 A1、A2、A3，第二列 B1、B2、B3；不要按行优先编号。"
        "layout_definition 可以包含 cols、rows、cell_size、cells，cells 顺序按从左到右、"
        "从上到下排列。"
    )
    layout_instruction = (
        grid_instruction if layout_type == "grid" else irregular_instruction
    )
    return (
        f"{base_prompt}\n\n"
        "这是一张收纳盒或元器件盒的完整照片。请先识别盒子的模板布局，"
        "再尽量识别每个格子里的元器件。\n"
        f"布局偏好：{layout_type}\n"
        f"{layout_instruction}\n"
        "template_name 只能按盒子结构特征命名，不能包含识别到的盒内物品类别。"
        "规则网格命名按“列x行格”，例如 4 列 7 行写作 4x7格。"
        "不规则网格命名按“不规则N格”，例如 14 个小格写作“不规则14格”。"
        f"box_name 才根据盒内主要元器件命名。{BOX_NAME_RULE_TEXT}\n"
        f"再次强调：{NOTES_RULE_TEXT}\n"
        "请只返回一个 JSON 对象，不要返回 Markdown，不要额外解释。格式必须是：\n"
        "{\n"
        '  "template_name": "4x7格",\n'
        '  "layout_type": "grid",\n'
        '  "layout_definition": {"rows": 7, "cols": 4},\n'
        '  "box_name": "电源芯片",\n'
        '  "cells": [\n'
        "    {\n"
        '      "position_identifier": "R1C1",\n'
        '      "is_empty": false,\n'
        '      "name": "BQ24195RGER",\n'
        '      "tags": ["IC", "IC/电源芯片"],\n'
        '      "attributes": {"型号": "BQ24195RGER", "封装": "VQFN-24"},\n'
        '      "display_attribute": "型号",\n'
        '      "confidence": 0.82,\n'
        '      "notes": "可选说明"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )

