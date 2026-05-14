from typing import List
from xml.etree import ElementTree

from app.models.box import Box
from app.services.box_labeling import (
    build_box_label_summary_lines,
    format_template_label,
)

WDFX_TEMPLATE = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<LPAPI>
    <backgroundPhotoFrame>false</backgroundPhotoFrame>
    <tailDirection>3</tailDirection>
    <gapLength>3.000</gapLength>
    <printHorOffset>0.000</printHorOffset>
    <printVerOffset>0.000</printVerOffset>
    <mirrorMode>0</mirrorMode>
    <isFlagLabel>false</isFlagLabel>
    <antiColor>false</antiColor>
    <currPageNo>1</currPageNo>
    <mirrorColGap>0.000</mirrorColGap>
    <version>1.4</version>
    <borderScale>1.000</borderScale>
    <gapType>2</gapType>
    <templateID>2C75B62D-B821-4D1C-96C2-2D923AD31D38</templateID>
    <labelType>0</labelType>
    <mirrorRowGap>0.000</mirrorRowGap>
    <printOrientation>0</printOrientation>
    <printSpeed>255</printSpeed>
    <dataSheet>0</dataSheet>
    <labelHeight>15.000</labelHeight>
    <internationalName>zh=OhmStash</internationalName>
    <multirowPrint>false</multirowPrint>
    <mirrorRowCount>0</mirrorRowCount>
    <labelWidth>30.000</labelWidth>
    <tailLength>0.000</tailLength>
    <mirrorColCount>0</mirrorColCount>
    <labelName>OhmStash</labelName>
    <horFlip>false</horFlip>
    <printDarkness>255</printDarkness>
    <Page>
        <Qrcode>
            <printing>true</printing>
            <dataColumn>1</dataColumn>
            <zoneSize>0</zoneSize>
            <degreeOffset>1</degreeOffset>
            <waterMarkSeed>0</waterMarkSeed>
            <antiColor>false</antiColor>
            <mask>-1</mask>
            <version>0</version>
            <contentInputType>16777216</contentInputType>
            <encoding>1</encoding>
            <eccLevel>0</eccLevel>
            <type>2</type>
            <x>1.000</x>
            <mirrorIndex>0</mirrorIndex>
            <orientation>0</orientation>
            <lockMovement>false</lockMovement>
            <contentType>0</contentType>
            <height>5.233</height>
            <dmCodeShape>2</dmCodeShape>
            <y>9.000</y>
            <waterMarkMode>-1</waterMarkMode>
            <width>11.979</width>
            <mode>0</mode>
            <degreeLength>0</degreeLength>
            <content>BOX-0148</content>
        </Qrcode>
        <Text>
            <printing>true</printing>
            <dataColumn>1</dataColumn>
            <verDisplay>false</verDisplay>
            <degreeOffset>1</degreeOffset>
            <fontName>HarmonyOS Sans</fontName>
            <verAlignment>0</verAlignment>
            <charSpace>0.000</charSpace>
            <autoHeight>true</autoHeight>
            <autoReturn>0</autoReturn>
            <antiColor>false</antiColor>
            <contentInputType>16777216</contentInputType>
            <x>1.000</x>
            <lockMovement>false</lockMovement>
            <orientation>0</orientation>
            <y>1.000</y>
            <contentType>0</contentType>
            <mirrorIndex>0</mirrorIndex>
            <width>15.288</width>
            <height>3.307</height>
            <fontHeight>2.822</fontHeight>
            <fontStyle>0x0</fontStyle>
            <horAlignment>0</horAlignment>
            <lineSpace>1_0</lineSpace>
            <degreeLength>0</degreeLength>
            <content>BOX-0148</content>
        </Text>
        <Text>
            <printing>true</printing>
            <dataColumn>1</dataColumn>
            <verDisplay>false</verDisplay>
            <degreeOffset>1</degreeOffset>
            <fontName>HarmonyOS Sans</fontName>
            <verAlignment>0</verAlignment>
            <charSpace>0.000</charSpace>
            <autoHeight>true</autoHeight>
            <autoReturn>0</autoReturn>
            <antiColor>false</antiColor>
            <contentInputType>16777216</contentInputType>
            <x>1.000</x>
            <lockMovement>false</lockMovement>
            <orientation>0</orientation>
            <y>6.860</y>
            <contentType>0</contentType>
            <mirrorIndex>0</mirrorIndex>
            <width>15.150</width>
            <height>2.481</height>
            <fontHeight>2.117</fontHeight>
            <fontStyle>0x0</fontStyle>
            <horAlignment>0</horAlignment>
            <lineSpace>1_0</lineSpace>
            <degreeLength>0</degreeLength>
            <content>盒子类型</content>
        </Text>
        <Text>
            <printing>true</printing>
            <dataColumn>1</dataColumn>
            <verDisplay>false</verDisplay>
            <degreeOffset>1</degreeOffset>
            <fontName>HarmonyOS Sans</fontName>
            <verAlignment>0</verAlignment>
            <charSpace>0.000</charSpace>
            <autoHeight>true</autoHeight>
            <autoReturn>0</autoReturn>
            <antiColor>false</antiColor>
            <contentInputType>16777216</contentInputType>
            <x>1.000</x>
            <lockMovement>false</lockMovement>
            <orientation>0</orientation>
            <y>4.222</y>
            <contentType>0</contentType>
            <mirrorIndex>0</mirrorIndex>
            <width>14.900</width>
            <height>2.481</height>
            <fontHeight>2.117</fontHeight>
            <fontStyle>0x0</fontStyle>
            <horAlignment>0</horAlignment>
            <lineSpace>1_0</lineSpace>
            <degreeLength>0</degreeLength>
            <content>盒子名称</content>
        </Text>
        <Text>
            <printing>true</printing>
            <dataColumn>1</dataColumn>
            <verDisplay>false</verDisplay>
            <degreeOffset>1</degreeOffset>
            <fontName>HarmonyOS Sans</fontName>
            <verAlignment>0</verAlignment>
            <charSpace>0.000</charSpace>
            <autoHeight>true</autoHeight>
            <autoReturn>0</autoReturn>
            <antiColor>false</antiColor>
            <contentInputType>16777216</contentInputType>
            <x>16.000</x>
            <lockMovement>false</lockMovement>
            <orientation>0</orientation>
            <y>0.679</y>
            <contentType>0</contentType>
            <mirrorIndex>0</mirrorIndex>
            <width>13.601</width>
            <height>13.642</height>
            <fontHeight>1.940</fontHeight>
            <fontStyle>0x0</fontStyle>
            <horAlignment>1</horAlignment>
            <lineSpace>1_0</lineSpace>
            <degreeLength>0</degreeLength>
            <content>稳压器
LDO
DC-DC
电源芯片
电源管理芯片
充电芯片</content>
        </Text>
    </Page>
</LPAPI>
"""


def generate_box_label_wdfx(box: Box) -> str:
    root = ElementTree.fromstring(WDFX_TEMPLATE)
    template_name = box.template.name if box.template else "未知模板"
    template_label = format_template_label(
        template_name=template_name,
        layout_type=box.template.layout_type if box.template else None,
        layout_definition=box.template.layout_definition if box.template else None,
    )
    summary_lines = build_box_label_summary_lines(box)

    qrcode = root.find("./Page/Qrcode")
    if qrcode is not None:
        content = qrcode.find("content")
        if content is not None:
            content.text = box.readable_id

    text_nodes = root.findall("./Page/Text")
    _set_text_content(text_nodes, y_value="1.000", content=box.readable_id)
    _set_text_content(text_nodes, y_value="4.222", content=box.name or "未命名")
    _set_text_content(text_nodes, y_value="6.860", content=template_label)
    _set_text_content(
        text_nodes,
        x_value="16.000",
        content="\n".join(summary_lines),
    )
    ElementTree.indent(root, space="    ")
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        + ElementTree.tostring(root, encoding="unicode")
        + "\n"
    )


def _set_text_content(
    text_nodes: List[ElementTree.Element],
    *,
    content: str,
    x_value: str | None = None,
    y_value: str | None = None,
) -> None:
    for text_node in text_nodes:
        x_node = text_node.find("x")
        y_node = text_node.find("y")
        x_matches = x_value is None or x_node is not None and x_node.text == x_value
        y_matches = y_value is None or y_node is not None and y_node.text == y_value
        if x_matches and y_matches:
            content_node = text_node.find("content")
            if content_node is not None:
                content_node.text = content
            return

