from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.schemas.box_template import BoxTemplateCreate
from app.schemas.box import BoxCreate


def create_test_box_template(client: TestClient) -> dict:
    template_data = {
        "name": "Test Box Template for Box Test",
        "layout_type": "grid",
        "layout_definition": {"rows": 2, "cols": 2}
    }
    response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json=template_data,
    )
    assert response.status_code == 200
    return response.json()


def test_delete_box_can_delete_exclusive_components(client: TestClient) -> None:
    suffix = uuid4().hex[:8]
    template_response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json={
            "name": f"Delete Components Template {suffix}",
            "layout_type": "grid",
            "layout_definition": {"rows": 1, "cols": 1},
        },
    )
    assert template_response.status_code == 200
    box_response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json={
            "readable_id": f"BOX-DEL-{suffix}",
            "name": "Delete Components Box",
            "template_id": template_response.json()["id"],
        },
    )
    assert box_response.status_code == 200
    sub_boxes_response = client.get(
        f"{settings.API_V1_STR}/sub_boxes/?box_id={box_response.json()['id']}"
    )
    assert sub_boxes_response.status_code == 200
    component_response = client.post(
        f"{settings.API_V1_STR}/components/",
        json={"name": f"Delete Component {suffix}", "tag_ids": []},
    )
    assert component_response.status_code == 200
    inventory_response = client.post(
        f"{settings.API_V1_STR}/inventory/",
        json={
            "sub_box_id": sub_boxes_response.json()[0]["id"],
            "component_id": component_response.json()["id"],
            "stock_mode": "fuzzy",
            "quantity_fuzzy": "未知",
        },
    )
    assert inventory_response.status_code == 200

    delete_response = client.delete(
        f"{settings.API_V1_STR}/boxes/{box_response.json()['id']}?delete_components=true"
    )
    assert delete_response.status_code == 200
    component_lookup = client.get(
        f"{settings.API_V1_STR}/components/{component_response.json()['id']}"
    )
    assert component_lookup.status_code == 404


def test_create_box(client: TestClient, db: Session) -> None:
    template = create_test_box_template(client)
    box_data = {
        "readable_id": "BOX-TEST-01",
        "name": "My Test Box",
        "template_id": template["id"]
    }
    response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json=box_data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == box_data["name"]
    assert content["readable_id"] == box_data["readable_id"]
    assert "id" in content

    # Verify that sub-boxes were created
    box_id = content["id"]
    response = client.get(f"{settings.API_V1_STR}/sub_boxes/?box_id={box_id}")
    assert response.status_code == 200
    sub_boxes = response.json()
    assert len(sub_boxes) == 4  # 2x2 grid
    assert sub_boxes[0]["position_identifier"] == "R1C1"
    assert f"SUB-BOX-TEST-01-R1C1" in sub_boxes[0]["readable_id"]

    response = client.get(f"{settings.API_V1_STR}/boxes/{box_id}/overview")
    assert response.status_code == 200
    overview = response.json()
    assert overview["readable_id"] == box_data["readable_id"]
    assert len(overview["sub_boxes"]) == 4


def test_create_box_can_generate_readable_id(client: TestClient) -> None:
    template = create_test_box_template(client)
    response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json={
            "name": "Generated ID Box",
            "template_id": template["id"],
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert content["readable_id"].startswith("BOX-")

    label_response = client.get(
        f"{settings.API_V1_STR}/boxes/{content['id']}/label.svg",
    )
    assert label_response.status_code == 200
    assert "image/svg+xml" in label_response.headers["content-type"]
    assert content["readable_id"] in label_response.text


def test_create_bulk_box_uses_single_contents_slot(client: TestClient) -> None:
    template_response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json={
            "name": "整理箱",
            "layout_type": "irregular",
            "layout_definition": [{"id": "CONTENTS", "label": "内容"}],
            "physical_dimensions": {"container_type": "bulk"},
        },
    )
    assert template_response.status_code == 200
    box_response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json={
            "readable_id": "BULK-TEST-01",
            "name": "工具整理箱",
            "template_id": template_response.json()["id"],
        },
    )
    assert box_response.status_code == 200
    sub_boxes_response = client.get(
        f"{settings.API_V1_STR}/sub_boxes/?box_id={box_response.json()['id']}",
    )
    assert sub_boxes_response.status_code == 200
    sub_boxes = sub_boxes_response.json()
    assert len(sub_boxes) == 1
    assert sub_boxes[0]["position_identifier"] == "CONTENTS"

    first_component_response = client.post(
        f"{settings.API_V1_STR}/components/",
        json={"name": "USB Cable", "attributes": {}, "tag_ids": []},
    )
    assert first_component_response.status_code == 200
    second_component_response = client.post(
        f"{settings.API_V1_STR}/components/",
        json={"name": "Spare Screw", "attributes": {}, "tag_ids": []},
    )
    assert second_component_response.status_code == 200
    for component_response in [first_component_response, second_component_response]:
        inventory_response = client.post(
            f"{settings.API_V1_STR}/inventory/",
            json={
                "sub_box_id": sub_boxes[0]["id"],
                "component_id": component_response.json()["id"],
                "stock_mode": "fuzzy",
                "quantity_fuzzy": "未知",
            },
        )
        assert inventory_response.status_code == 200

    overview_response = client.get(
        f"{settings.API_V1_STR}/boxes/{box_response.json()['id']}/overview",
    )
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert len(overview["sub_boxes"][0]["inventory"]) == 2


def test_box_label_wdfx_uses_columns_by_rows_and_summary(
    client: TestClient,
) -> None:
    template_response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json={
            "name": "7x4贴片盒",
            "layout_type": "grid",
            "layout_definition": {"rows": 7, "cols": 4},
        },
    )
    assert template_response.status_code == 200
    box_response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json={
            "readable_id": "BOX-WDFX-01",
            "name": "盒1",
            "template_id": template_response.json()["id"],
        },
    )
    assert box_response.status_code == 200
    box_id = box_response.json()["id"]
    sub_boxes_response = client.get(f"{settings.API_V1_STR}/sub_boxes/?box_id={box_id}")
    assert sub_boxes_response.status_code == 200
    tag_response = client.post(
        f"{settings.API_V1_STR}/tags/",
        json={"name": "测试IC/电源芯片", "attribute_definitions": ["型号"]},
    )
    assert tag_response.status_code == 201
    component_response = client.post(
        f"{settings.API_V1_STR}/components/",
        json={
            "name": "BQ24195RGER",
            "attributes": {"型号": "BQ24195RGER"},
            "tag_ids": [tag_response.json()["id"]],
        },
    )
    assert component_response.status_code == 200
    inventory_response = client.post(
        f"{settings.API_V1_STR}/inventory/",
        json={
            "sub_box_id": sub_boxes_response.json()[0]["id"],
            "component_id": component_response.json()["id"],
            "stock_mode": "fuzzy",
            "quantity_fuzzy": "少量",
        },
    )
    assert inventory_response.status_code == 200

    response = client.get(f"{settings.API_V1_STR}/boxes/{box_id}/label.wdfx")
    assert response.status_code == 200
    assert "application/octet-stream" in response.headers["content-type"]
    assert (
        'filename="BOX-WDFX-01-label.wdfx"'
        in response.headers["content-disposition"]
    )
    assert ".xml" not in response.headers["content-disposition"].lower()
    assert "BOX-WDFX-01" in response.text
    assert "盒1" in response.text
    assert "7x4贴片盒" in response.text
    assert "<type>2</type>" in response.text
    assert "<dmCodeShape>2</dmCodeShape>" in response.text
    assert "测试IC" in response.text


def test_move_inventory_between_sub_boxes(client: TestClient, db: Session) -> None:
    template = create_test_box_template(client)
    box_response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json={
            "readable_id": "BOX-MOVE-01",
            "name": "Move Test Box",
            "template_id": template["id"],
        },
    )
    assert box_response.status_code == 200
    box_id = box_response.json()["id"]

    sub_box_response = client.get(f"{settings.API_V1_STR}/sub_boxes/?box_id={box_id}")
    assert sub_box_response.status_code == 200
    sub_boxes = sub_box_response.json()

    component_response = client.post(
        f"{settings.API_V1_STR}/components/",
        json={
            "name": "Move Test Resistor",
            "description": None,
            "attributes": {"阻值": "1K"},
            "tag_ids": [],
        },
    )
    assert component_response.status_code == 200
    component_id = component_response.json()["id"]

    inventory_response = client.post(
        f"{settings.API_V1_STR}/inventory/",
        json={
            "sub_box_id": sub_boxes[0]["id"],
            "component_id": component_id,
            "stock_mode": "exact",
            "quantity_exact": 10,
        },
    )
    assert inventory_response.status_code == 200

    move_response = client.post(
        f"{settings.API_V1_STR}/sub_boxes/move_inventory",
        json={
            "source_sub_box_id": sub_boxes[0]["id"],
            "target_sub_box_id": sub_boxes[1]["id"],
        },
    )
    assert move_response.status_code == 200
    moved_items = move_response.json()["moved_items"]
    assert moved_items[0]["sub_box_id"] == sub_boxes[1]["id"]
