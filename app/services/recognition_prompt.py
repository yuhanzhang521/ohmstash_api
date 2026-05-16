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
    "不要包含“收纳盒”“盒子”“盒”等后缀；只返回能概括盒内主要物品类别的简短名称。"
)

NOTES_RULE_TEXT = (
    "notes 只允许写器件本身的补充信息（用途、功能、关键参数解释等），"
    "禁止写拍摄角度、标签朝向、标签是否可见、标签包含几行字、竖放横放等图像或拍摄过程的旁白；"
    "看不到或不确定的，notes 留空。"
)

COMPONENT_TYPE_RULE_TEXT = (
    "component_type 必须由你结合标签文字与图片实物判断，只能返回 PASSIVE、IC、MODULE、OTHER 之一，不能省略。"
    "PASSIVE 仅用于普通两端基础阻容感（电阻、电容、电感）；"
    "水泥电阻、保险电阻、热敏电阻、压敏电阻、磁珠、变压器、扼流圈等带功能/类别词的特种被动元件不归 PASSIVE，归 OTHER。"
    "IC 是有完整丝印型号的芯片、集成电路或裸芯片。"
    "MODULE 是模块、模组、开发板、传感器模块、电源模块、带功能电路的板卡（多为 PCB 加多元件的形态）。"
    "OTHER 涵盖一切非阻容感、非芯片、非模块的实体：传感器探头、舵机、风扇、喇叭、按键、显示屏、连接器、端子/线鼻子、五金件、特种电阻、电池、工具等。"
)

COMPONENT_NAME_RULE_TEXT = (
    "name 必须能让人一眼看出器件是什么；除 IC 用纯型号外，name 中必须出现器件类别词或功能词。"
    "必须读取整张标签的所有文字行，不能默认只用第一行、最大字号行或最醒目的单个字段。"
    "标签中可见的型号、类别词、数量、通道数、接口、隔离/耦合方式、输入输出、供电、量程、"
    "封装、规格、版本等信息都必须尽量保留到 name_parts、attributes 或 notes 中。"
    "供电电压、电流、阻值、量程、尺寸、封装、版本号等参数不能单独作为 name 的全部，"
    "也不能误填到 name_parts.model；它们应进入 attributes，必要时作为 name 的辅助参数。"
    "\n"
    "如果标签上存在多个并列型号、料号或兼容型号，必须全部保留，按标签原有顺序合并到 name_parts.model；"
    "多个型号之间使用 / 分隔，不要只选择其中一个，也不要把并列型号误认为批号或备注。"
    "\n"
    "功能修饰词不能丢弃：数量、路数/通道数、隔离方式、触发方式、接口类型、输入输出类型、"
    "保护特性、调节方式、封装形态等都属于可识别信息。"
    "这类信息应写入 attributes 的明确字段；如果它们是区分器件的关键信息，也应进入 name_parts.spec 或 name。"
    "\n"
    "PASSIVE 命名规则：name_parts 必须含 value；贴片件还要含 package，插件件 package 留空。"
    "最终 name 使用 package 与 value 组合，或只使用 value；精度、耐压、温漂等次要参数写入 attributes。"
    "\n"
    "IC 命名规则：name_parts.model 必须填完整丝印型号或标签型号；name 直接等于该型号。"
    "不要把封装、丝印位置、批号、日期码或功能描述当作 model。"
    "\n"
    "MODULE 命名规则：从所有标签文字中识别真正的型号；供电电压、电流、接口数量等不是型号。"
    "name_parts 必须含 function，表示中文功能/类别词。"
    "若识别到型号则填 name_parts.model，并把 function 对应的功能后缀填入 name_parts.suffix；"
    "最终 name 使用 model 与 suffix 组合。若没有可靠型号，model 留空，name 使用 function，"
    "并把关键修饰词通过 name_parts.spec、attributes 或 notes 保留下来。"
    "\n"
    "OTHER 命名规则：name_parts 必须含 function，表示器件类别词。"
    "如果标签还有规格、参数或关键修饰词，另填 name_parts.spec；若有可识别型号字符串，填 name_parts.model。"
    "最终 name 必须包含 function，不能只用纯参数当 name。"
    "\n"
    "name 和 attributes 不互斥：name_parts 中的型号、功能名词和关键参数，attributes 中仍必须保留对应字段。"
    "tags 必须忠实于实际器件形态，不要给不符合形态的器件添加无关标签。"
)

SEARCH_RECOMMENDATION_RULE_TEXT = (
    "search_recommended 由 component_type 和 name_parts 决定。"
    "component_type=PASSIVE 时一律返回 false。"
    "component_type=IC 时一律返回 true。"
    "component_type=MODULE 时，name_parts.model 非空才返回 true，否则 false。"
    "component_type=OTHER 时，name_parts.model 非空才返回 true，否则 false（除非用户补充要求明确需要联网核对）。"
)


GRID_COUNT_RULE_TEXT = (
    "规则网格必须按可见分隔线、格子边界和重复格子数量来数 rows 与 cols，"
    "不要根据整盒外轮廓长宽比、格子形状比例或已有模板猜测行列数。"
    "rows 表示从上到下可见的格子排数，cols 表示从左到右可见的格子列数；"
    "必须逐行、逐列计数，并让 layout_definition 的 rows * cols 与返回的 cells 数量一致。"
    "如果图中某些格子为空，也必须计入布局；空格只影响 cell.is_empty，不影响 rows 或 cols。"
    "不要为了让结果更常见、更整齐或更接近经验值而合并、截断、省略任何可见行列。"
)

GRID_CELL_COVERAGE_RULE_TEXT = (
    "规则网格内容识别必须覆盖模板中的所有格子：按 rows x cols 返回完整 cells，"
    "每个格子都要有对应 position_identifier；空格或看不清的格子也要返回，"
    "并把 is_empty 设为 true。不要省略任何可见格子或模板中定义的格子。"
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
        "display_attribute 必须是 attributes 中适合作为辅助缩略信息的属性名，不是主标题。"
        "主标题必须写在 name 中，并优先表达器件是什么；display_attribute 不能让 name 丢失器件类别。"
        "阻容感优先选择阻值、容值或电感值，attributes 写入对应参数与封装，"
        "display_attribute 写入最适合缩略展示的参数名。"
        "芯片可以选择型号；模块模组可以选择型号或功能；不要为了缩略显示改短 name。"
        "长型号允许在前端被省略号截断，不要为了缩略显示改短 name。\n\n"
        f"{COMPONENT_TYPE_RULE_TEXT}\n\n"
        f"{COMPONENT_NAME_RULE_TEXT}\n\n"
        f"{SEARCH_RECOMMENDATION_RULE_TEXT}\n\n"
        f"{NOTES_RULE_TEXT}\n\n"
        f"Tag 与属性库：\n{tag_catalog}\n\n"
        "请只返回一个 JSON 对象，不要返回 Markdown，不要额外解释。格式必须是：\n"
        "{\n"
        '  "is_empty": false,\n'
        '  "component_type": "PASSIVE",\n'
        '  "name_parts": {"package": "PACKAGE", "value": "VALUE"},\n'
        '  "name": "PACKAGE VALUE",\n'
        '  "tags": ["TAG_NAME"],\n'
        '  "attributes": {"封装": "PACKAGE", "参数": "VALUE"},\n'
        '  "display_attribute": "参数",\n'
        '  "search_recommended": false,\n'
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
        f"{GRID_CELL_COVERAGE_RULE_TEXT}\n"
        "请只返回一个 JSON 对象，格式必须是：\n"
        "{\n"
        '  "box_readable_id": "BOX-A01",\n'
        '  "cells": [\n'
        "    {\n"
        '      "position_identifier": "R1C1",\n'
        '      "is_empty": false,\n'
        '      "component_type": "PASSIVE",\n'
        '      "name_parts": {"package": "PACKAGE", "value": "VALUE"},\n'
        '      "name": "PACKAGE VALUE",\n'
        '      "tags": ["TAG_NAME"],\n'
        '      "attributes": {"封装": "PACKAGE", "参数": "VALUE"},\n'
        '      "display_attribute": "参数",\n'
        '      "search_recommended": false,\n'
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
        f"{GRID_CELL_COVERAGE_RULE_TEXT}\n"
        "请只返回一个 JSON 对象，格式必须是：\n"
        "{\n"
        '  "box_name": "简短盒名",\n'
        '  "cells": [\n'
        "    {\n"
        '      "position_identifier": "R1C1",\n'
        '      "is_empty": false,\n'
        '      "component_type": "IC",\n'
        '      "name_parts": {"model": "MODEL"},\n'
        '      "name": "MODEL",\n'
        '      "tags": ["TAG_NAME"],\n'
        '      "attributes": {"型号": "MODEL", "封装": "PACKAGE"},\n'
        '      "display_attribute": "型号",\n'
        '      "search_recommended": true,\n'
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
        f"{GRID_COUNT_RULE_TEXT}"
        "layout_definition 中 rows 与 cols 必须和 cells 数量一致，"
        "即 grid 模式下 cells 数量必须等于 rows * cols。"
    )
    irregular_instruction = (
        "用户预期这是不规则网格。请为每个可用格子生成稳定的 id，"
        "例如 A1、A2、B1 或 CELL-01，并在 layout_definition 中返回 cells 列表。"
        "每个 cells 项必须包含 id、label、数字 row、数字 col；如果有旋转、跨格或特殊尺寸，"
        "继续增加 row_span、col_span、x、y、width、height。"
        "如果格子、小盒或贴纸上有可见编号或文字标签，必须把原文写入 label；"
        "id 用于稳定定位，label 用于展示原始标签，两者不能互相替代或丢失。"
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
        '  "box_name": "简短盒名",\n'
        '  "cells": [\n'
        "    {\n"
        '      "position_identifier": "R1C1",\n'
        '      "is_empty": false,\n'
        '      "component_type": "IC",\n'
        '      "name_parts": {"model": "MODEL"},\n'
        '      "name": "MODEL",\n'
        '      "tags": ["TAG_NAME"],\n'
        '      "attributes": {"型号": "MODEL", "封装": "PACKAGE"},\n'
        '      "display_attribute": "型号",\n'
        '      "search_recommended": true,\n'
        '      "confidence": 0.82,\n'
        '      "notes": "可选说明"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )
