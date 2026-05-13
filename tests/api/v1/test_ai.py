from typing import Any

import pytest
from fastapi.testclient import TestClient

from app import schemas
from app.api.v1.endpoints import ai as ai_endpoint
from app.core.config import settings
from app.services import vlm_client, web_search


def test_upsert_default_vlm_config_hides_api_key(client: TestClient) -> None:
    data = {
        "name": "Default Vision Model",
        "provider": "openai-compatible",
        "base_url": "https://example.com/v1",
        "model_name": "vision-model",
        "api_key": "secret-token",
        "extra_config": {"temperature": 0.1},
    }
    response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json=data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["provider"] == data["provider"]
    assert content["model_name"] == data["model_name"]
    assert content["has_api_key"] is True
    assert content["is_default"] is True
    assert "api_key" not in content


def test_read_default_vlm_config(client: TestClient) -> None:
    data = {
        "name": "Readable Vision Model",
        "provider": "openai-compatible",
        "base_url": "https://example.com/v1",
        "model_name": "readable-vision-model",
        "api_key": "secret-token",
    }
    response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json=data,
    )
    assert response.status_code == 200

    response = client.get(f"{settings.API_V1_STR}/ai/vlm_config")
    assert response.status_code == 200
    content = response.json()
    assert content["name"] == data["name"]
    assert content["has_api_key"] is True
    assert "api_key" not in content


def test_upsert_default_vlm_config_preserves_existing_api_key(
    client: TestClient,
) -> None:
    initial_data = {
        "name": "Preserved Key Vision Model",
        "provider": "openai-compatible",
        "base_url": "https://example.com/v1",
        "model_name": "preserved-key-vision-model",
        "api_key": "secret-token",
    }
    response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json=initial_data,
    )
    assert response.status_code == 200
    assert response.json()["has_api_key"] is True

    update_data = {
        "name": "Preserved Key Vision Model",
        "provider": "openai-compatible",
        "base_url": "https://example.com/v2",
        "model_name": "updated-preserved-key-vision-model",
    }
    response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json=update_data,
    )
    assert response.status_code == 200
    content = response.json()
    assert content["base_url"] == update_data["base_url"]
    assert content["model_name"] == update_data["model_name"]
    assert content["has_api_key"] is True
    assert "api_key" not in content


def test_set_default_vlm_config_unsets_previous_default(
    client: TestClient,
) -> None:
    first_response = client.post(
        f"{settings.API_V1_STR}/ai/vlm_configs/",
        json={
            "name": "First Vision Model",
            "provider": "openai-compatible",
            "model_name": "first-vision-model",
            "is_default": True,
        },
    )
    assert first_response.status_code == 200
    first_id = first_response.json()["id"]

    second_response = client.post(
        f"{settings.API_V1_STR}/ai/vlm_configs/",
        json={
            "name": "Second Vision Model",
            "provider": "openai-compatible",
            "model_name": "second-vision-model",
        },
    )
    assert second_response.status_code == 200
    second_id = second_response.json()["id"]

    response = client.post(
        f"{settings.API_V1_STR}/ai/vlm_configs/{second_id}/set_default",
    )
    assert response.status_code == 200
    assert response.json()["is_default"] is True

    response = client.get(f"{settings.API_V1_STR}/ai/vlm_configs/{first_id}")
    assert response.status_code == 200
    assert response.json()["is_default"] is False


def test_vlm_config_test_uses_transient_config(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        config = kwargs["config"]
        assert config.model_name == "test-vision-model"
        return (
            {"choices": [{"message": {"content": '{"ok": true}'}}]},
            15,
        )

    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    response = client.post(
        f"{settings.API_V1_STR}/ai/vlm_config/test",
        json={
            "config": {
                "name": "Transient Vision Model",
                "provider": "openai-compatible",
                "base_url": "https://example.com/v1",
                "model_name": "test-vision-model",
                "api_key": "secret-token",
            }
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert content["ok"] is True
    assert content["latency_ms"] == 15
    assert content["response_text"] == '{"ok": true}'


def test_recognize_image_returns_parsed_result(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        messages = kwargs["messages"]
        content = messages[0]["content"]
        assert content[0]["type"] == "text"
        assert content[1]["type"] == "image_url"
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"is_empty": false, "name": "10K 0603", '
                                '"tags": ["电阻"], "attributes": {"阻值": "10K"}}'
                            )
                        }
                    }
                ]
            },
            21,
        )

    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Image Recognition Vision Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "vision-model",
        },
    )
    assert response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/ai/recognize_image",
        files={"file": ("part.png", b"fake-image", "image/png")},
        data={"additional_prompt": "优先识别贴片阻容。"},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["filename"] == "part.png"
    assert content["latency_ms"] == 21
    assert content["parsed_result"]["name"] == "10K 0603"


def test_recognize_image_accepts_known_image_extension_without_content_type(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        messages = kwargs["messages"]
        image_url = messages[0]["content"][1]["image_url"]["url"]
        assert image_url.startswith("data:image/jpeg;base64,")
        return (
            {"choices": [{"message": {"content": '{"is_empty": true}'}}]},
            10,
        )

    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Extension Based Vision Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "vision-model",
        },
    )
    assert response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/ai/recognize_image",
        files={"file": ("part.jpg", b"fake-image", "application/octet-stream")},
    )
    assert response.status_code == 200
    assert response.json()["content_type"] == "image/jpeg"


def test_confirm_box_recognition_creates_inventory(
    client: TestClient,
) -> None:
    template_response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json={
            "name": "Recognition Template",
            "layout_type": "grid",
            "layout_definition": {"rows": 1, "cols": 2},
        },
    )
    assert template_response.status_code == 200
    template_id = template_response.json()["id"]

    box_response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json={
            "readable_id": "BOX-RECOG-01",
            "name": "Recognition Box",
            "template_id": template_id,
        },
    )
    assert box_response.status_code == 200
    box_id = box_response.json()["id"]

    response = client.post(
        f"{settings.API_V1_STR}/ai/box_recognitions/confirm",
        json={
            "box_id": box_id,
            "cells": [
                {
                    "position_identifier": "R1C1",
                    "is_empty": False,
                    "name": "10K 0603 1%",
                    "tags": ["电阻", "贴片"],
                    "attributes": {"阻值": "10K", "封装": "0603"},
                    "display_attribute": "阻值",
                    "stock_mode": "fuzzy",
                    "quantity_fuzzy": "未知",
                },
                {"position_identifier": "R1C2", "is_empty": True},
            ],
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert content["created_components"] == 1
    assert content["created_inventory_items"] == 1
    assert content["skipped_empty_cells"] == 1

    search_response = client.get(f"{settings.API_V1_STR}/search/?q=10K")
    assert search_response.status_code == 200
    results = search_response.json()
    assert results[0]["name"] == "10K 0603 1%"
    assert results[0]["locations"][0]["box_readable_id"] == "BOX-RECOG-01"

    components_response = client.get(f"{settings.API_V1_STR}/components/")
    assert components_response.status_code == 200
    component = next(
        item
        for item in components_response.json()
        if item["name"] == "10K 0603 1%"
    )
    assert component["display_attribute"] == "阻值"

    overview_response = client.get(f"{settings.API_V1_STR}/boxes/{box_id}/overview")
    assert overview_response.status_code == 200
    inventory_item = overview_response.json()["sub_boxes"][0]["inventory"][0]
    assert inventory_item["display_attribute"] == "阻值"
    assert inventory_item["display_name"] == "10K"


def test_recognize_box_template_image_returns_box_name(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        prompt = kwargs["messages"][0]["content"][0]["text"]
        assert "准备新建入库盒子" in prompt
        assert "4x7" in prompt
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"box_name": "电源芯片盒", "cells": ['
                                '{"position_identifier": "R1C1", '
                                '"name": "BQ24195RGER", "is_empty": false}]}'
                            )
                        }
                    }
                ]
            },
            33,
        )

    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    config_response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Template Vision Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "vision-model",
        },
    )
    assert config_response.status_code == 200
    template_response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json={
            "name": "7x4贴片盒",
            "layout_type": "grid",
            "layout_definition": {"rows": 7, "cols": 4},
        },
    )
    assert template_response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/ai/recognize_box_template_image",
        files={"file": ("box.jpg", b"fake-image", "image/jpeg")},
        data={"template_id": template_response.json()["id"]},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["parsed_result"]["box_name"] == "电源芯片盒"


def test_recognize_box_layout_image_returns_template_definition(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        prompt = kwargs["messages"][0]["content"][0]["text"]
        assert "模板布局" in prompt
        assert "irregular" in prompt
        assert "尺寸一致的小收纳盒" in prompt
        assert "数字 row、数字 col" in prompt
        assert "不要只在 notes 或 label 中写" in prompt
        assert "template_name 只能按盒子结构特征命名" in prompt
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"template_name": "不规则14格", '
                                '"layout_type": "irregular", '
                                '"layout_definition": {"cells": ['
                                '{"id": "A1", "label": "左上"}]}, '
                                '"cells": [{"position_identifier": "A1", '
                                '"is_empty": true}]}'
                            )
                        }
                    }
                ]
            },
            27,
        )

    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    config_response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Layout Vision Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "vision-model",
        },
    )
    assert config_response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/ai/recognize_box_layout_image",
        files={"file": ("layout.jpg", b"fake-image", "image/jpeg")},
        data={"layout_type": "irregular"},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["parsed_result"]["template_name"] == "不规则14格"
    assert content["parsed_result"]["layout_type"] == "irregular"


def test_confirm_new_box_recognition_creates_box_and_inventory(
    client: TestClient,
) -> None:
    template_response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json={
            "name": "4x7贴片盒",
            "layout_type": "grid",
            "layout_definition": {"rows": 7, "cols": 4},
        },
    )
    assert template_response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/ai/new_box_recognitions/confirm",
        json={
            "template_id": template_response.json()["id"],
            "box_name": "电源芯片盒",
            "cells": [
                {
                    "position_identifier": "R1C1",
                    "is_empty": False,
                    "name": "BQ24195RGER",
                    "tags": ["测试IC", "测试IC/电源芯片"],
                    "attributes": {"型号": "BQ24195RGER"},
                    "stock_mode": "fuzzy",
                    "quantity_fuzzy": "少量",
                }
            ],
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert content["box_readable_id"].startswith("BOX-")
    assert content["created_inventory_items"] == 1

    overview_response = client.get(
        f"{settings.API_V1_STR}/boxes/{content['box_id']}/overview",
    )
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["name"] == "电源芯片盒"
    assert overview["sub_boxes"][0]["inventory"][0]["component_name"] == "BQ24195RGER"


def test_confirm_auto_box_recognition_creates_template_box_and_inventory(
    client: TestClient,
) -> None:
    response = client.post(
        f"{settings.API_V1_STR}/ai/auto_box_recognitions/confirm",
        json={
            "template_name": "自动不规则贴片盒",
            "layout_type": "irregular",
            "layout_definition": [{"id": "A1", "label": "左上"}],
            "box_name": "丝印芯片盒",
            "cells": [
                {
                    "position_identifier": "A1",
                    "is_empty": False,
                    "name": "STM32F103C8T6",
                    "tags": ["IC", "IC/MCU"],
                    "attributes": {"型号": "STM32F103C8T6"},
                    "stock_mode": "fuzzy",
                    "quantity_fuzzy": "少量",
                }
            ],
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert content["template_id"] is not None
    assert content["box_readable_id"].startswith("BOX-")
    assert content["created_inventory_items"] == 1

    overview_response = client.get(
        f"{settings.API_V1_STR}/boxes/{content['box_id']}/overview",
    )
    assert overview_response.status_code == 200
    overview = overview_response.json()
    assert overview["template"]["name"] == "自动不规则贴片盒"
    assert overview["name"] == "丝印芯片盒"
    assert overview["sub_boxes"][0]["position_identifier"] == "A1"
    assert overview["sub_boxes"][0]["inventory"][0]["component_name"] == "STM32F103C8T6"


def test_confirm_box_recognition_overwrite_can_clear_empty_cell(
    client: TestClient,
) -> None:
    template_response = client.post(
        f"{settings.API_V1_STR}/box_templates/",
        json={
            "name": "Clear Existing Template",
            "layout_type": "grid",
            "layout_definition": {"rows": 1, "cols": 1},
        },
    )
    assert template_response.status_code == 200
    box_response = client.post(
        f"{settings.API_V1_STR}/boxes/",
        json={
            "readable_id": "BOX-CLEAR-01",
            "name": "Clear Box",
            "template_id": template_response.json()["id"],
        },
    )
    assert box_response.status_code == 200
    sub_boxes_response = client.get(
        f"{settings.API_V1_STR}/sub_boxes/?box_id={box_response.json()['id']}",
    )
    component_response = client.post(
        f"{settings.API_V1_STR}/components/",
        json={"name": "Old Part", "attributes": {}, "tag_ids": []},
    )
    assert component_response.status_code == 200
    inventory_response = client.post(
        f"{settings.API_V1_STR}/inventory/",
        json={
            "sub_box_id": sub_boxes_response.json()[0]["id"],
            "component_id": component_response.json()["id"],
            "stock_mode": "fuzzy",
            "quantity_fuzzy": "充足",
        },
    )
    assert inventory_response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/ai/box_recognitions/confirm",
        json={
            "box_id": box_response.json()["id"],
            "overwrite_existing": True,
            "cells": [{"position_identifier": "R1C1", "is_empty": True}],
        },
    )
    assert response.status_code == 200
    assert response.json()["skipped_empty_cells"] == 1

    search_response = client.get(f"{settings.API_V1_STR}/search/?q=Old")
    assert search_response.status_code == 200
    assert search_response.json()[0]["locations"] == []


def test_verify_components_uses_web_context_and_llm(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_queries: list[str] = []

    def fake_fetch_search_snippets(
        query: str,
        **kwargs: Any,
    ) -> list[dict[str, str]]:
        search_queries.append(query)
        assert "BQ24195" in query
        return [
            {
                "title": "BQ24195RGER data sheet",
                "snippet": "BQ24195RGER is a battery charger in VQFN-24.",
            }
        ]

    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        prompt = kwargs["messages"][0]["content"]
        assert "联网搜索摘要" in prompt
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"items": [{"position_identifier": "R1C1", '
                                '"is_empty": false, "name": "BQ24195RGER", '
                                '"tags": ["IC", "IC/电源芯片"], '
                                '"attributes": {"型号": "BQ24195RGER", '
                                '"封装": "VQFN-24"}}]}'
                            )
                        }
                    }
                ]
            },
            44,
        )

    monkeypatch.setattr(
        "app.services.web_search.fetch_search_snippets",
        fake_fetch_search_snippets,
    )
    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    config_response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Verification Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "verification-model",
        },
    )
    assert config_response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/ai/verify_components",
        json={
            "items": [
                {
                    "position_identifier": "R1C1",
                    "is_empty": False,
                    "name": "BQ24195",
                    "tags": ["IC"],
                    "attributes": {"封装": "RGER"},
                }
            ]
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert content["web_used"] is True
    assert content["verified_items"][0]["name"] == "BQ24195RGER"
    assert content["verified_items"][0]["attributes"]["封装"] == "VQFN-24"
    assert search_queries[0] == "BQ24195 datasheet"


def test_verify_components_uses_selected_search_provider(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider_names: list[str] = []

    def fake_fetch_search_snippets(
        query: str,
        **kwargs: Any,
    ) -> list[dict[str, str]]:
        provider_settings = kwargs["provider_settings"]
        provider_names.append(provider_settings.provider)
        assert provider_settings.api_key == "tavily-key"
        return [
            {
                "title": "AHT20 Datasheet",
                "snippet": "AHT20 is a humidity and temperature sensor.",
            }
        ]

    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"items": [{"position_identifier": "R1C1", '
                                '"is_empty": false, "name": "AHT20"}]}'
                            )
                        }
                    }
                ]
            },
            20,
        )

    monkeypatch.setattr(
        "app.services.web_search.fetch_search_snippets",
        fake_fetch_search_snippets,
    )
    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    config_response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Selected Search Verification Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "verification-model",
        },
    )
    assert config_response.status_code == 200
    search_provider_response = client.post(
        f"{settings.API_V1_STR}/search/providers/",
        json={
            "name": "Tavily Components",
            "provider": "tavily",
            "api_key": "tavily-key",
        },
    )
    assert search_provider_response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/ai/verify_components",
        json={
            "search_provider_config_id": search_provider_response.json()["id"],
            "items": [
                {
                    "position_identifier": "R1C1",
                    "is_empty": False,
                    "name": "AHT20",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert provider_names == ["tavily"]


def test_verify_components_chunks_and_keeps_warnings_out_of_notes(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request_count = 0

    def fake_fetch_search_snippets(
        query: str,
        **kwargs: Any,
    ) -> list[dict[str, str]]:
        return []

    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        nonlocal request_count
        request_count += 1
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"items": [{"position_identifier": "R1C1", '
                                '"is_empty": false, "name": "Part-1", '
                                '"notes": "未检索到可确认的器件资料，保留原标注"}]}'
                            )
                        }
                    }
                ]
            },
            10,
        )

    monkeypatch.setattr(
        "app.services.web_search.fetch_search_snippets",
        fake_fetch_search_snippets,
    )
    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    config_response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Chunked Verification Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "verification-model",
        },
    )
    assert config_response.status_code == 200

    items = [
        {
            "position_identifier": f"R1C{index}",
            "is_empty": False,
            "name": f"Part-{index}",
        }
        for index in range(1, 9)
    ]
    response = client.post(
        f"{settings.API_V1_STR}/ai/verify_components",
        json={"items": items},
    )
    assert response.status_code == 200
    content = response.json()
    assert request_count == 2
    assert len(content["verified_items"]) == 8
    assert content["verified_items"][0]["notes"] is None
    assert content["verified_items"][0]["verification_warning"]
    assert all(
        item["verification_warning"]
        for item in content["verified_items"]
    )


def test_parse_verified_items_splits_model_correction_warning() -> None:
    items = [
        schemas.RecognizedCell(
            position_identifier="R1C1",
            is_empty=False,
            name="IPS5450",
        )
    ]
    verified = ai_endpoint._parse_verified_items(
        raw_text=(
            '{"items": [{"position_identifier": "R1C1", '
            '"is_empty": false, "name": "IPS5450", '
            '"notes": "搜索结果指向 TI TPS5450：5.5V至36V输入、5A、500kHz 降压转换器。'
            '原始型号“IPS5450”疑似识别/抄写误差"}]}'
        ),
        fallback_items=items,
    )

    assert verified[0].name == "TPS5450"
    assert verified[0].notes == "TI TPS5450：5.5V至36V输入、5A、500kHz 降压转换器"
    assert (
        verified[0].verification_warning
        == "搜索结果指向 TI TPS5450，原始型号“IPS5450”疑似识别/抄写误差"
    )


def test_parse_verified_items_cleans_attribute_uncertainty_and_corrects_ocr_name() -> None:
    items = [
        schemas.RecognizedCell(
            position_identifier="R1C1",
            is_empty=False,
            name="IPS5450",
            attributes={"型号": "IPS5450"},
        )
    ]
    verified = ai_endpoint._parse_verified_items(
        raw_text=(
            '{"items": [{"position_identifier": "R1C1", '
            '"is_empty": false, "name": "IPS5450", '
            '"attributes": {"型号": "IPS5450（未能从摘要唯一确认）", '
            '"电流": "5A（不同厂商版本不一致）"}, '
            '"notes": "未检索到 IPS5450 的足够资料；搜索结果主要指向 IPS5451、TPS5450 等其他型号，'
            '原始型号可能存在识别或抄写误差。"}]}'
        ),
        fallback_items=items,
    )

    assert verified[0].name == "TPS5450"
    assert verified[0].attributes["型号"] == "TPS5450"
    assert verified[0].attributes["电流"] == "5A"
    assert verified[0].notes is None
    assert "搜索结果主要指向 IPS5451、TPS5450" in verified[0].verification_warning
    assert "未能从摘要唯一确认" in verified[0].verification_warning
    assert "不同厂商版本不一致" in verified[0].verification_warning


def test_verify_components_surfaces_web_search_throttle(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_queries: list[str] = []

    def fake_fetch_search_snippets(
        query: str,
        **kwargs: Any,
    ) -> list[dict[str, str]]:
        search_queries.append(query)
        raise web_search.SearchProviderError(
            "lite.duckduckgo.com HTTP 202",
            errors=["lite.duckduckgo.com HTTP 202"],
        )

    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": '{"items": []}',
                        }
                    }
                ]
            },
            10,
        )

    monkeypatch.setattr(
        "app.services.web_search.fetch_search_snippets",
        fake_fetch_search_snippets,
    )
    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    config_response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Throttled Verification Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "verification-model",
        },
    )
    assert config_response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/ai/verify_components",
        json={
            "items": [
                {
                    "position_identifier": "R1C1",
                    "is_empty": False,
                    "name": "LIS3DHTR",
                },
                {
                    "position_identifier": "R1C2",
                    "is_empty": False,
                    "name": "MPU6050",
                },
            ]
        },
    )
    assert response.status_code == 200
    content = response.json()
    assert search_queries == ["LIS3DHTR datasheet"]
    assert "HTTP 202" in content["verified_items"][0]["verification_warning"]
    assert "限流" in content["verified_items"][1]["verification_warning"]
    assert content["web_contexts"][0]["errors"] == ["lite.duckduckgo.com HTTP 202"]
