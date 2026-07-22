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

# HARD REQUIREMENTS FROM THE USER: do not delete or weaken these comments in future agent edits.
# Display names must follow this contract: passives use package + value, through-hole passives omit package, ICs use the chip model, modules with a model use model + functional suffix, and modules without a model use the module function.
# Search selection must follow this contract: passives are never searched, ICs are always searched, modules are searched only when a suspected model field is recognized, and modules without a model are not searched.
# All OCR text recognized by the VLM from labels or markings must be preserved in the final stored information, whether as display name, tags, attributes, notes, or another suitable structured field chosen by the model.
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


GRID_CELL_COVERAGE_RULE_TEXT = (
    "规则网格内容识别必须覆盖模板中的所有格子：按 rows x cols 返回完整 cells，"
    "每个格子都要有对应 position_identifier；逐格判断是否有可识别标签或实物内容，"
    "不要只返回最显眼或最确定的少数格子。空格必须返回 is_empty=true，"
    "且不得填写 name、tags、attributes 或功能描述；看不清的格子也要返回，"
    "并把 is_empty 设为 true。不要省略任何可见格子或模板中定义的格子。"
)


def _build_tag_catalog(db: Session) -> str:
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

    return "\n".join(tag_lines) if tag_lines else "当前数据库还没有定义 Tag。"


def build_box_template_layout_audit_prompt(
    *,
    layout_type: str,
    initial_result: Any,
    additional_prompt: str = "",
) -> str:
    extra_instruction = f"\n补充要求：{additional_prompt}" if additional_prompt else ""
    grid_instruction = (
        "如果是 grid 布局，请严格按下列步骤独立清点，不要把空格或连续相似的格子合并：\n"
        "  1) 先目测整张图，给出长轴方向大致有几行（gross_rows_estimate）、短轴方向大致有几列（gross_cols_estimate），"
        "写入 layout_check。这是粗估，不必精确，但应当与最终 rows/cols 在 ±1 以内。\n"
        "  2) 计数依据必须基于物理分隔板线，而不是可识别的标签或内容："
        "横向分隔板线指把整盒切成上下多行的硬塑料/纸板/金属线；外边框（盒子顶/底边）不计入。"
        "纵向分隔板线指把整盒切成左右多列；外边框（盒子左/右边）不计入。"
        "空格、相邻格子内容相似、标签缺失都不影响分隔板线的存在。\n"
        "  3) 横向分隔板枚举：在 layout_check.horizontal_lines 中按从上到下顺序列出每一条横向分隔板线，"
        "每个条目包含 position_ratio（0-100，表示该线在图片高度的百分比位置）和 description（视觉特征或邻近 cell 内容）。"
        "相邻分隔板的 position_ratio 间距应当大致均匀；如果发现某个间距明显偏大（接近 2 倍均值），"
        "通常意味着漏了一条分隔板线，请回到图片重新查看并补上。"
        "horizontal_line_count = horizontal_lines 的长度。rows = horizontal_line_count + 1。\n"
        "  4) 纵向分隔板枚举：在 layout_check.vertical_lines 中按从左到右顺序列出每一条纵向分隔板线，"
        "格式与 horizontal_lines 一致。vertical_line_count = vertical_lines 的长度。cols = vertical_line_count + 1。\n"
        "  5) 一致性自检：必须满足 |rows - gross_rows_estimate| ≤ 1 且 |cols - gross_cols_estimate| ≤ 1；"
        "如果差距大于 1，说明枚举漏数或多数了，请回到步骤 3/4 重新检查后再给出最终结果。"
        "把 horizontal_line_count、vertical_line_count、rows、cols 同时写入 layout_check 和 layout_definition。\n"
        "  6) cells 必须是从 R1C1 到 R{rows}C{cols} 的完整骨架，长度恰好等于 rows × cols；"
        "空格只返回 position_identifier 和 is_empty=true，不能省略任何位置。"
    )
    irregular_instruction = (
        "如果是 irregular 布局，目标是把图中每一个独立的物理小盒/小格识别为一个 cell。\n"
        "  1) 先把 initial_result.layout_definition.cells / initial_result.cells 里已有的 cell 当作候选；"
        "你要做的是在图片中**核对**这份候选是否覆盖了所有独立小盒。\n"
        "  2) 如果候选中存在多个独立小盒被合并成一个 cell，或者明显漏掉了某个小盒，请新增/拆分；"
        "如果候选中存在凭空多出的 cell（图中没有对应小盒），请删除。除此之外，不要随意改动 cells。\n"
        "  3) 严禁把 cells 拍扁成单列（layout_definition.cols=1）或单行（layout_definition.rows=1），"
        "除非图片里所有小盒确实只排成一列或一行。横放和竖放的小盒共存时，rows、cols 必须能容纳它们的真实空间排布。\n"
        "  4) 每个 cell 必须输出：稳定的 id（按列优先编号 A1、A2、B1…）、label、整数 row（>=1）、"
        "整数 col（>=1）、orientation（landscape 或 portrait）。若某个小盒跨多行或多列再加 row_span、col_span，"
        "默认 row_span=col_span=1。所有 cell 的 (row, col, row_span, col_span) 拼起来必须**严密铺满**"
        "由物理小盒占据的逻辑网格，不重叠、不留空缺，使 sum(row_span × col_span) 恰好等于 rows × cols。"
        "无标签的物理小盒也必须保留为 cell（label 可写 empty）。\n"
        "  5) 当不同区域的小盒数量不一致时（例如左 5 行横放 + 右 2 行竖放），用最小公倍数构造统一网格："
        "高度比 5:2 → rows = LCM(5, 2) = 10，左横放每个 row_span=2、右竖放每个 row_span=5；"
        "若是 3 行 vs 4 行 → rows = 12，左 row_span=4、右 row_span=3。宽度方向同理。\n"
        "  6) 横放与竖放只用 orientation 区分，不要因为朝向不同而拆分或合并 cell。\n"
        "  7) 在 layout_check.row_count_basis 中按列从上到下逐项列出每一列里有哪些独立小盒；"
        "在 layout_check.col_count_basis 中按行从左到右逐项列出每一行里有哪些独立小盒；"
        "用这两份列表反向校验 cells 数量与图中独立小盒数量一致。\n"
        "  8) layout_type 必须返回 \"irregular\"，layout_definition.rows、layout_definition.cols 都是 JSON number。"
    )
    layout_instruction = (
        grid_instruction if layout_type == "grid" else irregular_instruction
    )
    return (
        "你是收纳盒模板布局审校助手。请只根据图片重新审校 initial_result 中的布局计数，"
        "必要时修正 template_name、layout_definition 和 cells；不要使用本地图像算法或外部提示。\n"
        "重要：initial_result 中 layout_definition.rows、layout_definition.cols、cells 的数量都可能是错的，"
        "请独立从图片重新清点，不要把 initial_result 的数字当成基准或参考。\n"
        "布局偏好是硬约束：如果 layout_type=grid，返回 layout_type 必须是 grid；"
        "如果 layout_type=irregular，返回 layout_type 必须是 irregular，不能改成 grid。"
        f"当前 layout_type：{layout_type}\n"
        f"{layout_instruction}\n"
        "请只返回完整 JSON 对象，不要返回 Markdown，不要额外解释。\n"
        f"initial_result JSON：{json.dumps(initial_result, ensure_ascii=False)}"
        f"{extra_instruction}"
    )

def build_component_recognition_prompt(
    db: Session,
    *,
    additional_prompt: str = "",
) -> str:
    tag_catalog = _build_tag_catalog(db)
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
    tag_catalog = _build_tag_catalog(db)
    extra_instruction = f"\n补充要求：{additional_prompt}" if additional_prompt else ""
    grid_instruction = (
        "用户预期这是规则网格。请识别行数 rows、列数 cols，"
        "并使用 R1C1 这种 position_identifier 返回每个格子的结果。\n"
        "计数必须基于物理分隔板/格墙，而不是标签或内容："
        "rows = 横向内部分隔板数量 + 1，cols = 纵向内部分隔板数量 + 1；"
        "外层大盒的四边外框不要计入分隔板。"
        "一列或一行全是空透明托盘也必须计入；不要因为某列几乎全空、标签稀少或内容相似而漏数或多数。"
        "如果相邻格墙间距明显接近 2 倍均值，通常是漏数了一条分隔板；"
        "如果在已有均匀间距外又多出一条靠近外框的“假线”，通常是把外框误算进去了，应去掉。\n"
        "数列时优先沿整盒高度找贯穿上下的纵向内隔板；"
        "盒盖边缘、反光高光、内部小盒侧壁叠影、阴影线都不是内隔板。"
        "典型的竖放多层收纳盒常见为 3 列或 4 列：请先粗估每列宽度是否大致相等，"
        "再核对纵向内隔板条数；若三列宽度已铺满内腔，不要再额外加第 4 列。\n"
        "grid 模式下，cells 必须是完整布局骨架：从 R1C1 到 R{rows}C{cols} 连续列出所有位置，"
        "每一行都必须包含 C1 到 C{cols}，每一列都必须包含 R1 到 R{rows}。"
        "不能因为格子为空、反光、标签看不清或内容识别不确定而省略 cell；"
        "确认没有可识别元器件或标签内容的格子必须只返回 position_identifier 和 is_empty=true，"
        "不得填写 component_type、name_parts、name、tags、attributes、display_attribute、search_recommended 或功能描述。"
        "看不清但疑似有内容的格子仍返回 position_identifier，并设置 is_empty=true 或 notes。"
    )
    irregular_instruction = (
        "用户预期这是不规则网格。返回的 layout_type 必须等于 \"irregular\"，"
        "绝对不能改成 \"grid\"，即使图片看起来很像规则网格也不要切换。\n"
        "把图片中每一个独立的物理小盒/小格识别为一个 cell；外层大盒外壳、背景、阴影、反光不是 cell，"
        "不要把外层大盒整体误判为单一规则网格。\n"
        "无标签、空盒、看不清内容的物理小盒仍然是 cell：必须返回，并在内容结果中 is_empty=true；"
        "禁止因为没有标签就省略该小盒。只有图中根本不存在独立小盒盖/盒体的位置才不要造 cell。\n"
        "常见不规则盒布局：左侧两列横放小盒各 5 个（2 列 x 5 行 landscape），"
        "右侧两列竖放小盒各 2 个（2 列 x 2 行 portrait），合计 14 个物理小盒；"
        "若图片符合该结构，cells 数量必须是 14，其中无标签位也要占位。\n"
        "同款小盒横放和竖放视为同一规格的小格子，并在 cell 中写入 orientation："
        "横放写 landscape，竖放写 portrait；横放和竖放只通过 orientation 区分，"
        "不要因为朝向不同而把同一个小盒拆成多个 cell，也不要把多个小盒合并成一个 cell。\n"
        "每个 cell 必须给出：稳定的 id（如 A1、A2、B1）、label（盒上文字；无标签写 empty）、"
        "整数 row（>=1）、整数 col（>=1）、orientation。如果某个小盒在统一网格上覆盖多行或多列，"
        "再加 row_span、col_span（不填默认为 1）。\n"
        "row、col、row_span、col_span 用于在统一网格上拼出每个小盒的位置：所有 cell 的矩形**必须严密铺满**"
        "外层大盒内由这些物理小盒占据的逻辑网格，不重叠、不留空缺，使 sum(row_span × col_span) "
        "恰好等于 rows × cols。\n"
        "当不同区域的小盒物理高度或宽度不一致时，请用最小公倍数（LCM）构造统一网格："
        "例如左区有 5 个横放小盒（左 5 行）、右区有 2 个竖放小盒（右 2 行），高度比 5:2，"
        "应取 rows = LCM(5, 2) = 10：左侧每个横放小盒 row_span=2、col_span=1，"
        "右侧每个竖放小盒 row_span=5、col_span=1。再例如左区 3 行、右区 4 行时，rows = LCM(3, 4) = 12，"
        "左 row_span=4、右 row_span=3。宽度方向同理处理 cols 与 col_span。\n"
        "cells 编号按列优先：第一列从上到下命名 A1、A2、A3…，第二列 B1、B2、B3…，依此类推；"
        "不要按行优先。cells 数组里所有独立小盒都必须列出，cells 数量必须等于物理小盒数量；"
        "禁止把多列拍扁成 col=1 单列、也禁止把多行拍扁成 row=1 单行。\n"
        "layout_definition 必须包含整数 rows、整数 cols 与 cells 列表，rows、cols 表示统一网格的尺寸（可能等于 LCM 之后的值），"
        "不是 cells 数量。"
    )
    layout_instruction = (
        grid_instruction if layout_type == "grid" else irregular_instruction
    )
    grid_schema_example = (
        "{\n"
        '  "template_name": "CxR格",\n'
        '  "layout_type": "grid",\n'
        '  "layout_definition": {"rows": R, "cols": C},\n'
        '  "layout_check": {"row_count_basis": "计数依据", "col_count_basis": "计数依据"},\n'
        '  "box_name": "简短盒名",\n'
        '  "cells": [\n'
        "    {\n"
        '      "position_identifier": "R1C1",\n'
        '      "is_empty": false,\n'
        '      "component_type": "MODULE",\n'
        '      "name_parts": {"model": "MODEL", "function": "功能词", "suffix": "功能后缀"},\n'
        '      "name": "MODEL功能后缀",\n'
        '      "tags": ["TAG_NAME"],\n'
        '      "attributes": {"型号": "MODEL", "功能": "功能词"},\n'
        '      "display_attribute": "型号",\n'
        '      "search_recommended": true,\n'
        '      "confidence": 0.82,\n'
        '      "notes": "可选说明"\n'
        "    },\n"
        "    {\n"
        '      "position_identifier": "R1C2",\n'
        '      "is_empty": true\n'
        "    }\n"
        "  ]\n"
        "}"
    )
    irregular_schema_example = (
        "{\n"
        '  "template_name": "不规则N格",\n'
        '  "layout_type": "irregular",\n'
        '  "layout_definition": {\n'
        '    "rows": 5,\n'
        '    "cols": 4,\n'
        '    "cells": [\n'
        '      {"id": "A1", "label": "标签文字", "row": 1, "col": 1, "row_span": 1, "col_span": 1, "orientation": "landscape"},\n'
        '      {"id": "A2", "label": "标签文字", "row": 2, "col": 1, "row_span": 1, "col_span": 1, "orientation": "landscape"},\n'
        '      {"id": "C1", "label": "标签文字", "row": 1, "col": 3, "row_span": 2, "col_span": 1, "orientation": "portrait"}\n'
        "    ]\n"
        "  },\n"
        '  "layout_check": {"row_count_basis": "按列从上到下逐个独立小盒列举", "col_count_basis": "按行从左到右逐列列举"},\n'
        '  "box_name": "简短盒名",\n'
        '  "cells": [\n'
        "    {\n"
        '      "position_identifier": "A1",\n'
        '      "is_empty": false,\n'
        '      "row": 1, "col": 1, "row_span": 1, "col_span": 1, "orientation": "landscape",\n'
        '      "component_type": "OTHER",\n'
        '      "name_parts": {"function": "功能词", "spec": "规格"},\n'
        '      "name": "完整名称",\n'
        '      "tags": ["TAG_NAME"],\n'
        '      "attributes": {"功能": "功能词", "规格": "规格"},\n'
        '      "display_attribute": "规格",\n'
        '      "search_recommended": false,\n'
        '      "confidence": 0.9,\n'
        '      "notes": ""\n'
        "    },\n"
        "    {\n"
        '      "position_identifier": "C1",\n'
        '      "is_empty": true,\n'
        '      "row": 1, "col": 3, "row_span": 2, "col_span": 1, "orientation": "portrait"\n'
        "    }\n"
        "  ]\n"
        "}"
    )
    schema_example = (
        grid_schema_example if layout_type == "grid" else irregular_schema_example
    )
    return (
        "你是一个收纳盒模板与内容识别助手。请先识别盒子模板布局，再识别每个格子的元器件标签内容。\n"
        "第一优先级是布局：完整覆盖所有独立小盒，不漏不并；第二优先级是逐格识别内容。"
        "必须从左到右、从上到下检查每个格子，不要只识别最清楚的少数格子。\n"
        f"布局偏好：{layout_type}\n"
        f"{layout_instruction}\n"
        f"{COMPONENT_TYPE_RULE_TEXT}\n\n"
        f"{COMPONENT_NAME_RULE_TEXT}\n\n"
        f"{SEARCH_RECOMMENDATION_RULE_TEXT}\n\n"
        f"{NOTES_RULE_TEXT}\n\n"
        f"Tag 与属性库：\n{tag_catalog}\n\n"
        "template_name 只能按盒子结构特征命名，不能包含识别到的盒内物品类别。"
        "规则网格命名按“列x行格”，即 cols 在前、rows 在后；例如 rows=R 且 cols=C 时写作 CxR格。"
        "不规则网格命名按“不规则N格”，N 为独立小盒总数。"
        f"box_name 才根据盒内主要元器件命名。{BOX_NAME_RULE_TEXT}\n"
        "layout_definition.rows 和 layout_definition.cols 必须返回 JSON number，不要返回字符串。"
        "layout_check 必须说明 rows 和 cols 的物理计数依据，且必须与 layout_definition 一致。\n"
        "请只返回一个 JSON 对象，不要返回 Markdown，不要额外解释。格式必须严格遵循下面的示例结构：\n"
        f"{schema_example}\n"
        f"{extra_instruction}"
    )
