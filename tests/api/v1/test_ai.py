import json
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app import models, schemas
from app.api.v1.endpoints import ai as ai_endpoint
from app.core.config import settings
from app.models.auth_user import AuthUser
from app.services import recognition_prompt, vlm_client, web_search
from app.services.component_naming import normalize_component_names_in_parsed_result

TEST_DATA_DIR = Path(__file__).resolve().parents[2]


def _grid_cells(rows: int, cols: int) -> list[dict[str, Any]]:
    return [
        {"position_identifier": f"R{row}C{col}", "is_empty": True}
        for row in range(1, rows + 1)
        for col in range(1, cols + 1)
    ]


def _admin_user_id(db: Session) -> int:
    user = db.query(AuthUser).filter(AuthUser.username == "admin").one()
    return int(user.id)


def _copy_real_default_vlm_config_to_test_db(db: Session) -> int | None:
    database_url = str(settings.DATABASE_URL)
    if not database_url.endswith("_test"):
        return None

    prod_url = database_url.removesuffix("_test")
    prod_session_factory = sessionmaker(
        bind=create_engine(prod_url, pool_pre_ping=True),
    )
    prod_db = prod_session_factory()
    try:
        source = (
            prod_db.query(models.VlmProviderConfig)
            .filter(models.VlmProviderConfig.is_default.is_(True))
            .order_by(models.VlmProviderConfig.id)
            .first()
        )
        if source is None:
            return None
        db.query(models.VlmProviderConfig).update(
            {models.VlmProviderConfig.is_default: False},
        )
        db.query(models.VlmProviderConfig).filter(
            models.VlmProviderConfig.name == source.name,
        ).delete()
        copied_config = models.VlmProviderConfig(
            name=source.name,
            provider=source.provider,
            base_url=source.base_url,
            model_name=source.model_name,
            api_key=source.api_key,
            is_active=source.is_active,
            is_default=True,
            extra_config=source.extra_config or {},
        )
        db.add(copied_config)
        db.commit()
        db.refresh(copied_config)
        return int(copied_config.id)
    finally:
        prod_db.close()


def _assert_3x13_result_preserves_recognition_content(parsed_result: dict[str, Any]) -> None:
    assert parsed_result["template_name"] == "3x13格"
    assert parsed_result["layout_definition"] == {"rows": 13, "cols": 3}
    cells = parsed_result["cells"]
    assert len(cells) == 39
    assert cells[0]["position_identifier"] == "R1C1"
    assert cells[-1]["position_identifier"] == "R13C3"

    content_cells = [cell for cell in cells if cell.get("name")]
    assert content_cells
    for cell in content_cells:
        assert cell.get("component_type") in {"PASSIVE", "IC", "MODULE", "OTHER"}
        assert isinstance(cell.get("name_parts"), dict)
        assert cell.get("tags")
        assert cell.get("attributes")
        assert cell.get("search_recommended") in {True, False}
        if cell["component_type"] == "PASSIVE":
            assert cell["search_recommended"] is False
        if cell["component_type"] == "IC":
            assert cell["search_recommended"] is True
        if cell["component_type"] == "MODULE":
            has_model = bool(cell["name_parts"].get("model"))
            assert cell["search_recommended"] is has_model


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


def test_recognition_and_verification_prompts_include_name_rules(
    client: TestClient,
) -> None:
    response = client.get(f"{settings.API_V1_STR}/ai/recognition_prompt")
    assert response.status_code == 200
    prompt = response.json()["prompt"]

    assert recognition_prompt.COMPONENT_TYPE_RULE_TEXT in prompt
    assert "只能返回 PASSIVE、IC、MODULE、OTHER" in prompt
    assert "PASSIVE 命名规则" in prompt
    assert "IC 命名规则" in prompt
    assert "MODULE 命名规则" in prompt
    assert "OTHER 命名规则" in prompt
    assert "name_parts" in prompt

    verification_prompt = ai_endpoint._build_verification_prompt(
        items=[
            schemas.RecognizedCell(
                position_identifier="R1C1",
                name="12V 5015",
                tags=["风扇"],
            )
        ],
        web_contexts=[],
    )
    assert recognition_prompt.COMPONENT_NAME_RULE_TEXT in verification_prompt


def test_component_name_normalization_keeps_ai_provided_name() -> None:
    normalized = normalize_component_names_in_parsed_result(
        {
            "cells": [
                {
                    "position_identifier": "R1C1",
                    "is_empty": False,
                    "component_type": "MODULE",
                    "name": "SG90舵机",
                    "name_parts": {
                        "model": "SG90",
                        "suffix": "舵机",
                        "function": "舵机",
                    },
                    "tags": [],
                    "attributes": {},
                },
                {
                    "position_identifier": "R1C2",
                    "is_empty": False,
                    "component_type": "OTHER",
                    "name": "水泥电阻 10W 5Ω",
                    "name_parts": {"function": "水泥电阻", "spec": "10W 5Ω"},
                    "tags": ["电阻"],
                    "attributes": {"功率": "10W", "阻值": "5Ω"},
                },
            ]
        }
    )

    assert normalized
    names = [cell["name"] for cell in normalized["cells"]]
    assert names == ["SG90舵机", "水泥电阻 10W 5Ω"]
    assert normalized["cells"][0]["attributes"]["型号"] == "SG90"
    assert normalized["cells"][0]["attributes"]["功能"] == "舵机"
    assert normalized["cells"][0]["search_recommended"] is True
    assert normalized["cells"][1]["search_recommended"] is False


def test_component_name_normalization_falls_back_when_name_missing() -> None:
    normalized = normalize_component_names_in_parsed_result(
        {
            "cells": [
                {
                    "position_identifier": "R1C1",
                    "is_empty": False,
                    "component_type": "MODULE",
                    "name": "",
                    "name_parts": {
                        "model": "ESP32S3",
                        "suffix": "开发板",
                        "function": "开发板",
                    },
                    "tags": [],
                    "attributes": {},
                },
                {
                    "position_identifier": "R1C2",
                    "is_empty": False,
                    "component_type": "MODULE",
                    "name": "",
                    "name_parts": {"function": "红外感应模块"},
                    "tags": [],
                    "attributes": {},
                },
                {
                    "position_identifier": "R1C3",
                    "is_empty": False,
                    "component_type": "PASSIVE",
                    "name": "",
                    "name_parts": {"package": "0603", "value": "10k"},
                    "tags": [],
                    "attributes": {"精度": "1%"},
                },
                {
                    "position_identifier": "R1C4",
                    "is_empty": False,
                    "component_type": "IC",
                    "name": "",
                    "name_parts": {"model": "STM32F103C8T6"},
                    "tags": [],
                    "attributes": {"封装": "LQFP-48"},
                },
                {
                    "position_identifier": "R1C5",
                    "is_empty": False,
                    "component_type": "OTHER",
                    "name": "",
                    "name_parts": {"function": "线鼻子", "spec": "0.5-3"},
                    "tags": [],
                    "attributes": {},
                },
            ]
        }
    )

    assert normalized
    names = [cell["name"] for cell in normalized["cells"]]
    assert names == [
        "ESP32S3开发板",
        "红外感应模块",
        "0603 10k",
        "STM32F103C8T6",
        "线鼻子 0.5-3",
    ]
    assert normalized["cells"][0]["search_recommended"] is True
    assert normalized["cells"][1]["search_recommended"] is False
    assert normalized["cells"][2]["search_recommended"] is False
    assert normalized["cells"][3]["search_recommended"] is True
    assert normalized["cells"][4]["search_recommended"] is False


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
        assert kwargs["max_tokens"] == ai_endpoint.SINGLE_IMAGE_RECOGNITION_MAX_TOKENS
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"is_empty": false, "name": "0603 10K", '
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
    assert content["parsed_result"]["name"] == "0603 10K"


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


def test_create_recognition_session_returns_queued_session(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_endpoint, "_run_recognition_session", lambda **kwargs: None)
    response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Session Vision Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "vision-model",
        },
    )
    assert response.status_code == 200

    response = client.post(
        f"{settings.API_V1_STR}/ai/recognition_sessions",
        files={"file": ("session.png", b"fake-image", "image/png")},
        data={"mode": "single_image", "additional_prompt": "优先使用功能名词。"},
    )
    assert response.status_code == 200
    content = response.json()
    assert content["status"] == "queued"
    assert content["verification_status"] == "idle"
    assert content["filename"] == "session.png"
    assert content["additional_prompt"] == "优先使用功能名词。"

    response = client.get(f"{settings.API_V1_STR}/ai/recognition_sessions")
    assert response.status_code == 200
    assert response.json()[0]["id"] == content["id"]


def test_delete_finished_recognition_session(
    client: TestClient,
    db: Session,
) -> None:
    recognition_session = models.RecognitionSession(
        owner_kind="user",
        owner_id=_admin_user_id(db),
        owner_name="admin",
        mode="single_image",
        status="succeeded",
        verification_status="skipped",
        filename="old-session.png",
        content_type="image/png",
        additional_prompt="",
        overwrite_existing=False,
    )
    db.add(recognition_session)
    db.commit()
    db.refresh(recognition_session)

    response = client.delete(
        f"{settings.API_V1_STR}/ai/recognition_sessions/{recognition_session.id}",
    )

    assert response.status_code == 204
    assert db.get(models.RecognitionSession, recognition_session.id) is None


def test_recognition_session_background_stores_verified_result(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Background Session Vision Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "vision-model",
        },
    )
    assert response.status_code == 200
    config_id = response.json()["id"]

    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        messages = kwargs["messages"]
        content = messages[0]["content"]
        if isinstance(content, list):
            return (
                {
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"is_empty": false, '
                                    '"position_identifier": "单图", '
                                    '"component_type": "MODULE", '
                                    '"name_parts": {"model": "223B", "suffix": "触摸开关模块", "function": "触摸开关模块"}, '
                                    '"name": "223B触摸开关模块", '
                                    '"tags": ["模块"], '
                                    '"attributes": {"型号": "223B", "功能": "触摸开关模块"}}'
                                )
                            }
                        }
                    ]
                },
                11,
            )
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": (
                                '{"items": [{"position_identifier": "单图", '
                                '"is_empty": false, '
                                '"component_type": "MODULE", '
                                '"name_parts": {"model": "223B", "suffix": "触摸开关模块", "function": "触摸开关模块"}, '
                                '"name": "223B触摸开关模块", '
                                '"tags": ["模块"], '
                                '"attributes": {"型号": "223B", "功能": "触摸开关模块"}, '
                                '"display_attribute": "功能"}]}'
                            )
                        }
                    }
                ]
            },
            13,
        )

    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    monkeypatch.setattr(
        web_search,
        "fetch_search_snippets",
        lambda *args, **kwargs: [{"title": "触摸开关模块", "snippet": "触摸开关模块资料"}],
    )

    recognition_session = models.RecognitionSession(
        owner_kind="user",
        owner_id=_admin_user_id(db),
        owner_name="admin",
        mode="single_image",
        status="queued",
        verification_status="idle",
        filename="switch.png",
        content_type="image/png",
        config_id=config_id,
        additional_prompt="",
        overwrite_existing=False,
    )
    db.add(recognition_session)
    db.commit()
    db.refresh(recognition_session)

    ai_endpoint._run_recognition_session_with_db(
        db=db,
        session_id=recognition_session.id,
        content=b"fake-image",
        content_type="image/png",
    )
    db.refresh(recognition_session)

    assert recognition_session.status == "succeeded"
    assert recognition_session.verification_status == "succeeded"
    assert recognition_session.result["parsed_result"]["name"] == "223B触摸开关模块"
    assert recognition_session.verification_result["web_used"] is True


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
            "name": "Recog Box",
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
                    "name": "0603 10K 1%",
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
    assert results[0]["name"] == "0603 10K 1%"
    assert results[0]["locations"][0]["box_readable_id"] == "BOX-RECOG-01"

    components_response = client.get(f"{settings.API_V1_STR}/components/")
    assert components_response.status_code == 200
    component = next(
        item
        for item in components_response.json()
        if item["name"] == "0603 10K 1%"
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
        assert "按 rows x cols 返回完整 cells" in prompt
        assert kwargs["max_tokens"] == 28 * ai_endpoint.BOX_RECOGNITION_TOKENS_PER_CELL
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
        assert kwargs["max_tokens"] == ai_endpoint.BOX_LAYOUT_RECOGNITION_MAX_TOKENS
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


def test_recognize_grid_layout_prompt_counts_flat_3x13_grid(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = TEST_DATA_DIR / "recognition_3x13_grid.jpg"
    cells = _grid_cells(rows=13, cols=3)

    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        prompt = kwargs["messages"][0]["content"][0]["text"]
        image_url = kwargs["messages"][0]["content"][1]["image_url"]["url"]
        assert "count physical compartments only" in prompt
        assert "rows * cols" in prompt
        assert "four inner borders" in prompt
        assert "本地图像分析提示" in prompt
        assert "rows=13, cols=3" in prompt
        assert "horizontal_lines=14, vertical_lines=4" in prompt
        assert "3 列 13 行" not in prompt
        assert image_url.startswith("data:image/jpeg;base64,")
        assert kwargs["max_tokens"] == ai_endpoint.BOX_LAYOUT_RECOGNITION_MAX_TOKENS
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "template_name": "3x13格",
                                    "layout_type": "grid",
                                    "layout_definition": {"rows": 13, "cols": 3},
                                    "cells": cells,
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            31,
        )

    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    config_response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Grid Layout Vision Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "vision-model",
        },
    )
    assert config_response.status_code == 200

    with image_path.open("rb") as image_file:
        response = client.post(
            f"{settings.API_V1_STR}/ai/recognize_box_layout_image",
            files={"file": (image_path.name, image_file, "image/jpeg")},
            data={"layout_type": "grid"},
        )

    assert response.status_code == 200
    content = response.json()
    layout_definition = content["parsed_result"]["layout_definition"]
    assert layout_definition["rows"] == 13
    assert layout_definition["cols"] == 3
    assert len(content["parsed_result"]["cells"]) == 39


def test_auto_template_session_applies_3x13_grid_hint_and_completes_cells(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = TEST_DATA_DIR / "recognition_3x13_grid.jpg"
    prompts: list[str] = []

    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        prompt = kwargs["messages"][0]["content"][0]["text"]
        prompts.append(prompt)
        assert "本地图像分析提示" in prompt
        assert "rows=13, cols=3" in prompt
        assert "完整数出 rows、cols" in prompt
        assert "name_parts" in prompt
        assert "search_recommended" in prompt
        assert "所有 OCR text" not in prompt
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "template_name": "3x12格",
                                    "layout_type": "grid",
                                    "layout_definition": {"rows": 12, "cols": 3},
                                    "box_name": "模块",
                                    "cells": [
                                        {
                                            "position_identifier": "R1C1",
                                            "is_empty": False,
                                            "component_type": "MODULE",
                                            "name_parts": {
                                                "model": "TTP223B",
                                                "function": "触摸模块",
                                                "suffix": "触摸模块",
                                            },
                                            "name": "TTP223B触摸模块",
                                            "tags": ["模块"],
                                            "attributes": {
                                                "型号": "TTP223B",
                                                "功能": "触摸模块",
                                            },
                                            "display_attribute": "型号",
                                            "search_recommended": True,
                                        }
                                    ],
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            31,
        )

    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    monkeypatch.setattr(
        web_search,
        "fetch_search_snippets",
        lambda *args, **kwargs: [],
    )
    config_response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Auto Template Session Vision Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "vision-model",
        },
    )
    assert config_response.status_code == 200

    recognition_session = models.RecognitionSession(
        owner_kind="user",
        owner_id=_admin_user_id(db),
        owner_name="admin",
        mode="auto_template_box",
        status="queued",
        verification_status="idle",
        filename=image_path.name,
        content_type="image/jpeg",
        config_id=config_response.json()["id"],
        layout_type="grid",
        additional_prompt="",
        overwrite_existing=False,
    )
    db.add(recognition_session)
    db.commit()
    db.refresh(recognition_session)

    ai_endpoint._run_recognition_session_with_db(
        db=db,
        session_id=recognition_session.id,
        content=image_path.read_bytes(),
        content_type="image/jpeg",
    )
    db.refresh(recognition_session)

    assert prompts
    assert recognition_session.status == "succeeded"
    parsed_result = recognition_session.result["parsed_result"]
    assert parsed_result["template_name"] == "3x13格"
    assert parsed_result["layout_definition"] == {"rows": 13, "cols": 3}
    assert len(parsed_result["cells"]) == 39
    assert parsed_result["cells"][0]["name"] == "TTP223B触摸模块"
    assert parsed_result["cells"][0]["search_recommended"] is True
    assert parsed_result["cells"][-1]["position_identifier"] == "R13C3"


def test_auto_template_session_clears_empty_cell_payload(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = TEST_DATA_DIR / "recognition_3x13_grid.jpg"

    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "template_name": "3x13格",
                                    "layout_type": "grid",
                                    "layout_definition": {"rows": 13, "cols": 3},
                                    "box_name": "模块",
                                    "cells": [
                                        {
                                            "position_identifier": "R1C2",
                                            "is_empty": True,
                                            "component_type": "OTHER",
                                            "name_parts": {"function": "工具"},
                                            "name": "工具",
                                            "tags": ["工具"],
                                            "attributes": {"功能": "工具"},
                                            "search_recommended": True,
                                        }
                                    ],
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            31,
        )

    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    config_response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Empty Cell Cleanup Vision Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "vision-model",
        },
    )
    assert config_response.status_code == 200

    recognition_session = models.RecognitionSession(
        owner_kind="user",
        owner_id=_admin_user_id(db),
        owner_name="admin",
        mode="auto_template_box",
        status="queued",
        verification_status="idle",
        filename=image_path.name,
        content_type="image/jpeg",
        config_id=config_response.json()["id"],
        layout_type="grid",
        additional_prompt="",
        overwrite_existing=False,
    )
    db.add(recognition_session)
    db.commit()
    db.refresh(recognition_session)

    ai_endpoint._run_recognition_session_with_db(
        db=db,
        session_id=recognition_session.id,
        content=image_path.read_bytes(),
        content_type="image/jpeg",
    )
    db.refresh(recognition_session)

    parsed_result = recognition_session.result["parsed_result"]
    assert parsed_result["cells"][1] == {
        "position_identifier": "R1C2",
        "is_empty": True,
    }


def test_auto_template_session_keeps_3x13_grid_stable_for_five_runs(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image_path = TEST_DATA_DIR / "recognition_3x13_grid.jpg"

    def fake_request_chat_completion(**kwargs: Any) -> tuple[dict[str, Any], int]:
        return (
            {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "template_name": "3x12格",
                                    "layout_type": "grid",
                                    "layout_definition": {"rows": 12, "cols": 3},
                                    "box_name": "模块",
                                    "cells": _grid_cells(rows=12, cols=3),
                                },
                                ensure_ascii=False,
                            )
                        }
                    }
                ]
            },
            31,
        )

    monkeypatch.setattr(
        vlm_client,
        "request_chat_completion",
        fake_request_chat_completion,
    )
    config_response = client.put(
        f"{settings.API_V1_STR}/ai/vlm_config",
        json={
            "name": "Stable Auto Template Session Vision Model",
            "provider": "openai-compatible",
            "base_url": "https://example.com/v1",
            "model_name": "vision-model",
        },
    )
    assert config_response.status_code == 200

    for index in range(5):
        recognition_session = models.RecognitionSession(
            owner_kind="user",
            owner_id=_admin_user_id(db),
            owner_name="admin",
            mode="auto_template_box",
            status="queued",
            verification_status="idle",
            filename=f"{index}-{image_path.name}",
            content_type="image/jpeg",
            config_id=config_response.json()["id"],
            layout_type="grid",
            additional_prompt="",
            overwrite_existing=False,
        )
        db.add(recognition_session)
        db.commit()
        db.refresh(recognition_session)

        ai_endpoint._run_recognition_session_with_db(
            db=db,
            session_id=recognition_session.id,
            content=image_path.read_bytes(),
            content_type="image/jpeg",
        )
        db.refresh(recognition_session)

        parsed_result = recognition_session.result["parsed_result"]
        assert parsed_result["template_name"] == "3x13格"
        assert parsed_result["layout_definition"] == {"rows": 13, "cols": 3}
        assert len(parsed_result["cells"]) == 39
        assert parsed_result["cells"][-1]["position_identifier"] == "R13C3"


def test_real_vlm_auto_template_session_keeps_3x13_stable_for_five_runs(
    db: Session,
) -> None:
    api_key = os.environ.get("REAL_VLM_API_KEY")
    model_name = os.environ.get("REAL_VLM_MODEL_NAME")
    base_url = os.environ.get("REAL_VLM_BASE_URL")
    provider = os.environ.get("REAL_VLM_PROVIDER", "openai-compatible")

    image_path = TEST_DATA_DIR / "recognition_3x13_grid.jpg"
    config_id: int | None = None
    if api_key and model_name and base_url:
        config = models.VlmProviderConfig(
            name="Real Stable Auto Template Session Vision Model",
            provider=provider,
            base_url=base_url,
            model_name=model_name,
            api_key=api_key,
            is_active=True,
            is_default=True,
            extra_config={},
        )
        db.add(config)
        db.commit()
        db.refresh(config)
        config_id = int(config.id)
    else:
        config_id = _copy_real_default_vlm_config_to_test_db(db)

    if config_id is None:
        pytest.skip(
            "Set REAL_VLM_API_KEY, REAL_VLM_MODEL_NAME, and REAL_VLM_BASE_URL, "
            "or keep a default VLM config in the matching non-test database."
        )

    for index in range(5):
        recognition_session = models.RecognitionSession(
            owner_kind="user",
            owner_id=1,
            owner_name="admin",
            mode="auto_template_box",
            status="queued",
            verification_status="idle",
            filename=f"real-{index}-{image_path.name}",
            content_type="image/jpeg",
            config_id=config_id,
            layout_type="grid",
            additional_prompt="",
            overwrite_existing=False,
        )
        db.add(recognition_session)
        db.commit()
        db.refresh(recognition_session)

        ai_endpoint._run_recognition_session_with_db(
            db=db,
            session_id=recognition_session.id,
            content=image_path.read_bytes(),
            content_type="image/jpeg",
        )
        db.refresh(recognition_session)

        assert recognition_session.status == "succeeded", recognition_session.error_message
        parsed_result = recognition_session.result["parsed_result"]
        _assert_3x13_result_preserves_recognition_content(parsed_result)


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
