from typing import Any
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.services import vlm_client


def test_recommend_locations_prefers_boxes_with_matching_components(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        raise vlm_client.VlmClientError("VLM disabled for fallback test")

    monkeypatch.setattr(
        "app.services.vlm_client.request_chat_completion",
        fake_request_chat_completion,
    )

    suffix = uuid4().hex[:8]
    template_response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json={
            "name": f"Recommendation Grid {suffix}",
            "layout_type": "grid",
            "layout_definition": {"rows": 1, "cols": 2},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["id"]

    sensor_box_response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json={
            "readable_id": f"BOX-REC-SENSOR-{suffix}",
            "name": "Sensor Box",
            "template_id": template_id,
        },
    )
    power_box_response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json={
            "readable_id": f"BOX-REC-POWER-{suffix}",
            "name": "Power Box",
            "template_id": template_id,
        },
    )
    assert sensor_box_response.status_code == 200
    assert power_box_response.status_code == 200

    sensor_sub_boxes_response = client.get(
        f"{settings.API_V1_STR}/sub_boxes/?box_id={sensor_box_response.json()['id']}"
    )
    assert sensor_sub_boxes_response.status_code == 200
    sensor_sub_boxes = sensor_sub_boxes_response.json()

    tag_response = client.post(
        f"{settings.API_V1_STR}/tags/",
        json={"name": f"传感器-{suffix}", "attribute_definitions": ["型号"]},
    )
    assert tag_response.status_code == 201

    component_response = client.post(
        f"{settings.API_V1_STR}/components/",
        json={
            "name": f"AHT20-{suffix}",
            "description": f"温湿度传感器 {suffix}",
            "attributes": {"型号": f"AHT20-{suffix}"},
            "tag_ids": [tag_response.json()["id"]],
        },
    )
    assert component_response.status_code == 200

    inventory_response = client.post(
        f"{settings.API_V1_STR}/inventory/",
        json={
            "sub_box_id": sensor_sub_boxes[0]["id"],
            "component_id": component_response.json()["id"],
            "stock_mode": "fuzzy",
            "quantity_fuzzy": "少量",
        },
    )
    assert inventory_response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/search/recommend_locations",
        json={
            "text": f"数字温湿度传感器 {suffix}",
            "tag_names": [f"传感器-{suffix}"],
            "limit": 2,
        },
    )
    assert response.status_code == 200
    recommendations = response.json()["recommendations"]
    assert recommendations[0]["box_readable_id"] == f"BOX-REC-SENSOR-{suffix}"
    assert recommendations[0]["position_identifier"] == "R1C2"
    assert "相近器件" in recommendations[0]["reason"]


def test_recommend_locations_uses_ai_analysis_when_available(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:8]
    config_response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": f"Recommendation AI {suffix}",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "recommendation-model",
        },
    )
    assert config_response.status_code == 200
    template_response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json={
            "name": f"AI Recommendation Grid {suffix}",
            "layout_type": "grid",
            "layout_definition": {"rows": 1, "cols": 2},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["id"]

    sensor_box_response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json={
            "readable_id": f"BOX-AI-SENSOR-{suffix}",
            "name": "Sensor Box",
            "template_id": template_id,
        },
    )
    power_box_response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json={
            "readable_id": f"BOX-AI-POWER-{suffix}",
            "name": "Power Box",
            "template_id": template_id,
        },
    )
    assert sensor_box_response.status_code == 200
    assert power_box_response.status_code == 200

    power_sub_boxes_response = client.get(
        f"{settings.API_V1_STR}/sub_boxes/?box_id={power_box_response.json()['id']}"
    )
    assert power_sub_boxes_response.status_code == 200
    power_sub_boxes = power_sub_boxes_response.json()

    component_response = client.post(
        f"{settings.API_V1_STR}/components/",
        json={
            "name": f"TPS5430-{suffix}",
            "description": "DC-DC power chip",
            "attributes": {"型号": f"TPS5430-{suffix}"},
            "tag_ids": [],
        },
    )
    assert component_response.status_code == 200
    inventory_response = client.post(
        f"{settings.API_V1_STR}/inventory/",
        json={
            "sub_box_id": power_sub_boxes[0]["id"],
            "component_id": component_response.json()["id"],
            "stock_mode": "fuzzy",
            "quantity_fuzzy": "少量",
        },
    )
    assert inventory_response.status_code == 200

    target_sub_box_id = power_sub_boxes[1]["id"]

    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        prompt = kwargs["messages"][0]["content"]
        assert "同类别元件旁边" in prompt
        assert str(target_sub_box_id) in prompt
        return (
            {
                "choices": [
                    {
                        "message": {
                                "content": (
                                    '{"keywords": ["电源芯片"], '
                                    '"recommendations": ['
                                    f'{{"sub_box_id": {target_sub_box_id}, '
                                    '"reason": "同盒已有 DC-DC 电源芯片"}], '
                                    '"analysis_note": "优先靠近电源芯片"}'
                                )
                        }
                    }
                ]
            },
            15,
        )

    monkeypatch.setattr(
        "app.services.vlm_client.request_chat_completion",
        fake_request_chat_completion,
    )

    response = client.post(
        f"{settings.API_V1_STR}/search/recommend_locations",
        json={
            "text": f"新的传感器模块 {suffix}",
            "tag_names": ["传感器"],
            "limit": 3,
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert content["analysis_used"] is True
    assert content["recommendations"][0]["sub_box_id"] == target_sub_box_id
    assert "AI 分析" in content["recommendations"][0]["reason"]


def test_search_provider_config_crud_and_test(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    suffix = uuid4().hex[:8]

    def fake_fetch_search_snippets(
        query: str,
        **kwargs: Any,
    ) -> list[dict[str, str]]:
        assert query == "LIS3DHTR datasheet"
        provider_settings = kwargs["provider_settings"]
        assert provider_settings.provider == "brave"
        assert provider_settings.api_key == "brave-key"
        return [
            {
                "title": "LIS3DHTR Datasheet",
                "url": "https://example.com/lis3dhtr",
                "snippet": "Three-axis accelerometer.",
            }
        ]

    monkeypatch.setattr(
        "app.services.web_search.fetch_search_snippets",
        fake_fetch_search_snippets,
    )

    create_response = client.post(
        f"{settings.API_V1_STR}/search/providers/",
        json={
            "name": f"Brave Components {suffix}",
            "provider": "brave",
            "api_key": "brave-key",
            "is_default": True,
            "extra_config": {"country": "US"},
        },
    )
    assert create_response.status_code == 200
    content = create_response.json()
    assert content["has_api_key"] is True
    assert "api_key" not in content

    config_id = content["id"]
    test_response = client.post(
        f"{settings.API_V1_STR}/search/providers/{config_id}/test",
        json={"query": "LIS3DHTR datasheet"},
    )
    assert test_response.status_code == 200
    assert test_response.json()["ok"] is True

    update_response = client.put(
        f"{settings.API_V1_STR}/search/providers/{config_id}",
        json={"name": f"Brave Components Updated {suffix}"},
    )
    assert update_response.status_code == 200
    assert update_response.json()["has_api_key"] is True

    list_response = client.get(f"{settings.API_V1_STR}/search/providers/")
    assert list_response.status_code == 200
    updated_config = next(
        item for item in list_response.json() if item["id"] == config_id
    )
    assert updated_config["name"] == f"Brave Components Updated {suffix}"
