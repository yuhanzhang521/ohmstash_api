import json
from pathlib import Path
import shutil
import subprocess
import textwrap
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_app_js_expression(expression: str) -> Any:
    node_path = shutil.which("node")
    if not node_path:
        pytest.skip("Node.js is not available")

    script = textwrap.dedent(
        f"""
        const fs = require("fs");
        const vm = require("vm");

        function createTestElement(tagName) {{
            const element = {{
                tagName,
                children: [],
                style: {{}},
                dataset: {{}},
                className: "",
                innerHTML: "",
                textContent: "",
                append(child) {{
                    this.children.push(child);
                }},
            }};
            element.classList = {{
                add(...names) {{
                    const classes = new Set(element.className.split(/\\s+/).filter(Boolean));
                    names.forEach((name) => classes.add(name));
                    element.className = Array.from(classes).join(" ");
                }},
                contains(name) {{
                    return element.className.split(/\\s+/).includes(name);
                }},
                remove(...names) {{
                    const blocked = new Set(names);
                    element.className = element.className
                        .split(/\\s+/)
                        .filter((name) => name && !blocked.has(name))
                        .join(" ");
                }},
                toggle(name, force) {{
                    const shouldAdd = force ?? !this.contains(name);
                    if (shouldAdd) {{
                        this.add(name);
                    }} else {{
                        this.remove(name);
                    }}
                    return shouldAdd;
                }},
            }};
            return element;
        }}

        const code = fs.readFileSync("app/static/app.js", "utf8").replace(/\\nboot\\(\\);\\s*$/, "\\n");
        const storage = new Map();
        const localStorage = {{
            getItem: (key) => storage.has(key) ? storage.get(key) : "",
            setItem: (key, value) => storage.set(key, String(value)),
            removeItem: (key) => storage.delete(key),
        }};
        const context = {{
            window: {{
                __storage: storage,
                localStorage,
                addEventListener: () => {{}},
                clearTimeout: () => {{}},
                setTimeout: (callback) => {{
                    callback();
                    return 0;
                }},
            }},
            document: {{
                createElement: createTestElement,
                querySelector: () => null,
                querySelectorAll: () => [],
            }},
            console,
        }};
        vm.createContext(context);
        vm.runInContext(code, context);
        const result = vm.runInContext({json.dumps(expression)}, context);
        Promise.resolve(result)
            .then((resolved) => {{
                console.log(JSON.stringify(resolved));
            }})
            .catch((error) => {{
                console.error(error && error.stack ? error.stack : error);
                process.exit(1);
            }});
        """
    )
    completed = subprocess.run(
        [node_path, "-e", script],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def test_irregular_layout_normalization_keeps_portrait_stack_continuous() -> None:
    result = run_app_js_expression(
        """
        (() => {
            const parsed = {
                layout_type: "irregular",
                layout_definition: {
                    rows: 5,
                    cols: 4,
                    cells: [
                        {id: "A1", row: 1, col: 1, row_span: 2, orientation: "landscape"},
                        {id: "A2", row: 3, col: 1, row_span: 2, orientation: "landscape"},
                        {id: "A3", row: 5, col: 1, row_span: 2, orientation: "landscape"},
                        {id: "A4", row: 7, col: 1, row_span: 2, orientation: "landscape"},
                        {id: "A5", row: 9, col: 1, row_span: 2, orientation: "landscape"},
                        {id: "B1", row: 1, col: 2, row_span: 2, orientation: "landscape"},
                        {id: "B2", row: 3, col: 2, row_span: 2, orientation: "landscape"},
                        {id: "B3", row: 5, col: 2, row_span: 2, orientation: "landscape"},
                        {id: "B4", row: 7, col: 2, row_span: 2, orientation: "landscape"},
                        {id: "B5", row: 9, col: 2, row_span: 2, orientation: "landscape"},
                        {id: "C1", row: 1, col: 3, row_span: 5, orientation: "portrait"},
                        {id: "D1", row: 1, col: 4, row_span: 5, orientation: "portrait"},
                        {id: "C3", row: 11, col: 3, row_span: 5, orientation: "portrait"},
                        {id: "D3", row: 11, col: 4, row_span: 5, orientation: "portrait"},
                    ],
                },
            };
            const template = normalizeRecognizedTemplate(parsed, "irregular");
            const cells = template.layout_definition.cells;
            return {
                rows: template.layout_definition.rows,
                cols: template.layout_definition.cols,
                c3: cells.find((cell) => cell.id === "C3"),
                d3: cells.find((cell) => cell.id === "D3"),
            };
        })()
        """
    )

    assert result["rows"] == 10
    assert result["cols"] == 4
    assert result["c3"]["row"] == 6
    assert result["c3"]["row_span"] == 5
    assert result["d3"]["row"] == 6
    assert result["d3"]["row_span"] == 5


def test_irregular_recognition_editing_keeps_layout_placement() -> None:
    result = run_app_js_expression(
        """
        (() => {
            const layoutDefinition = {
                rows: 10,
                cols: 4,
                cells: [
                    {id: "A1", row: 1, col: 1, row_span: 2, orientation: "landscape"},
                    {id: "A2", row: 3, col: 1, row_span: 2, orientation: "landscape"},
                    {id: "A3", row: 5, col: 1, row_span: 2, orientation: "landscape"},
                    {id: "A4", row: 7, col: 1, row_span: 2, orientation: "landscape"},
                    {id: "A5", row: 9, col: 1, row_span: 2, orientation: "landscape"},
                    {id: "B1", row: 1, col: 2, row_span: 2, orientation: "landscape"},
                    {id: "B2", row: 3, col: 2, row_span: 2, orientation: "landscape"},
                    {id: "B3", row: 5, col: 2, row_span: 2, orientation: "landscape"},
                    {id: "B4", row: 7, col: 2, row_span: 2, orientation: "landscape"},
                    {id: "B5", row: 9, col: 2, row_span: 2, orientation: "landscape"},
                    {id: "C1", row: 1, col: 3, row_span: 5, orientation: "portrait"},
                    {id: "D1", row: 1, col: 4, row_span: 5, orientation: "portrait"},
                    {id: "C3", row: 6, col: 3, row_span: 5, orientation: "portrait"},
                    {id: "D3", row: 6, col: 4, row_span: 5, orientation: "portrait"},
                ],
            };
            const viewer = document.createElement("div");
            document.querySelector = (selector) => {
                if (selector === "#ai-result-viewer") {
                    return viewer;
                }
                if (selector === "#recognition-box-id") {
                    return {value: "1"};
                }
                return null;
            };
            state.recognitionMode = "existing_box";
            state.recognitionEditing = true;
            state.boxes = [{id: 1, template_id: 1}];
            state.templates = [{id: 1, layout_type: "irregular", layout_definition: layoutDefinition}];
            state.recognitionCells = layoutDefinition.cells.map((cell) => ({
                position_identifier: cell.id,
                is_empty: true,
                name: "",
                tags: [],
                attributes: {},
            }));
            renderRecognitionCards();
            const grid = viewer.children[0];
            const c3Card = grid.children.find((card) => card.dataset.position === "C3");
            return {
                gridClassName: grid.className,
                gridTemplateColumns: grid.style.gridTemplateColumns,
                gridTemplateRows: grid.style.gridTemplateRows,
                cardCount: grid.children.length,
                c3GridRow: c3Card.style.gridRow,
                c3GridColumn: c3Card.style.gridColumn,
            };
        })()
        """
    )

    assert "irregular-map" in result["gridClassName"]
    assert result["gridTemplateColumns"] == "repeat(4, minmax(132px, 1fr))"
    assert result["gridTemplateRows"] == "repeat(10, minmax(130px, auto))"
    assert result["cardCount"] == 14
    assert result["c3GridRow"] == "6 / span 5"
    assert result["c3GridColumn"] == "3 / span 1"


def test_manage_grid_uses_scrollable_equal_width_columns() -> None:
    result = run_app_js_expression(
        """
        (() => {
            return {
                columns: getManageGridTemplateColumns(8),
                minWidth: getManageGridMinWidth(8),
                title: getInventoryDisplayTitle({
                    component_name: "0603 75pF 50V 10%",
                    display_attribute: "容值",
                    attributes: {"封装": "0603", "容值": "75pF", "耐压": "50V"},
                }),
                longModelTitle: getInventoryDisplayTitle({
                    component_name: "MSM261S4030H0R",
                    display_attribute: "型号",
                    attributes: {"型号": "MSM261S4030H0R"},
                }),
            };
        })()
        """
    )

    assert result["columns"] == "repeat(8, minmax(88px, 1fr))"
    assert result["minWidth"] == "max(100%, 746px)"
    assert result["title"] == "75pF"
    assert result["longModelTitle"] == "MSM261S4030H0R"


def test_manage_select_all_ignores_empty_cells() -> None:
    result = run_app_js_expression(
        """
        (() => {
            renderManageBoxDetail = () => {};
            state.selectedBoxOverview = {
                sub_boxes: [
                    {id: 1, inventory: [{inventory_id: 10}]},
                    {id: 2, inventory: []},
                    {id: 3, inventory: [{inventory_id: 30}]},
                ],
            };
            state.manageSelectionMode = true;
            toggleManageAllCellSelection();
            const selectedAfterSelect = Array.from(state.manageSelectedSubBoxIds).sort();
            toggleManageAllCellSelection();
            const selectedAfterClear = Array.from(state.manageSelectedSubBoxIds).sort();
            return {selectedAfterSelect, selectedAfterClear};
        })()
        """
    )

    assert result["selectedAfterSelect"] == [1, 3]
    assert result["selectedAfterClear"] == []


def test_frontend_index_is_served() -> None:
    response = client.get("/ui/")
    assert response.status_code == 200
    assert "OhmStash" in response.text
    assert "recognition-form" in response.text
    assert "view-search" in response.text
    assert "recognition-result" in response.text
    assert "按模板新建盒子" in response.text
    assert "识别样式并新建模板" in response.text
    assert "view-dashboard" in response.text
    assert "view-manage" in response.text
    assert "cell-editor-modal" in response.text
    assert "placement-modal" in response.text
    assert "AI 搜索" in response.text
    assert "search-mode" in response.text
    assert "log-viewer" in response.text
    assert "search-provider-form" in response.text
    assert "search-provider-model-line" in response.text
    assert "search-provider-test-result" in response.text
    assert "box-scanner-modal" in response.text
    assert "scanner-frame" in response.text
    assert "server-config-form" in response.text
    assert "restart-service" in response.text
    assert "server-https-options" in response.text
    assert 'data-certificate-source="acme"' in response.text
    assert 'data-certificate-source="path"' in response.text
    assert 'data-certificate-source="upload"' in response.text
    assert 'data-certificate-source="paste"' in response.text
    assert 'data-acme-challenge="http-01"' in response.text
    assert 'data-acme-challenge="dns-01"' in response.text
    assert "confirm-password" in response.text
    assert 'data-action="toggle-password-visibility"' in response.text
    assert 'data-theme-mode="system"' in response.text
    assert "recognition-file-preview" in response.text
    assert "recognition-session-list" in response.text
    assert "verification-search-provider-id" in response.text
    assert "cell-search-provider-id" in response.text
    assert "下载 WDFX" in response.text
    assert "recognized-info-panel" in response.text
    assert 'data-action="set-recognition-side-tab"' not in response.text
    assert 'data-recognition-side-panel="capture"' not in response.text
    assert "login-modal" not in response.text
    assert "view-inventory" not in response.text


def test_login_page_is_served() -> None:
    response = client.get("/ui/login.html")
    assert response.status_code == 200
    assert "登录 OhmStash" in response.text
    assert "login-form" in response.text
    assert "login.js" in response.text


def test_frontend_assets_are_served() -> None:
    response = client.get("/ui/app.js")
    assert response.status_code == 200
    assert "API_BASE" in response.text
    assert "apiFormRequest" in response.text
    assert "renderRecognitionCards" in response.text
    assert "verifySelectedComponents" in response.text
    assert "/ai/recognition_sessions" in response.text
    assert "openRecognitionSession" in response.text
    assert "recognizeTemplateLayout" in response.text
    assert "createComponentSummaryHtml" in response.text
    assert "runAiSearch" in response.text
    assert "saveLogSettings" in response.text
    assert "async function saveLogSettings" in response.text
    assert "saveServerConfig" in response.text
    assert "async function saveServerConfig" in response.text
    assert "buildServerConfigPayload" in response.text
    assert "updateServerHttpsVisibility" in response.text
    assert "setServerAcmeChallengeType" in response.text
    assert "togglePasswordVisibility" in response.text
    assert "setThemeMode" in response.text
    assert "restartService" in response.text
    assert "saveSearchProviderConfig" in response.text
    assert "updateSearchProviderFieldVisibility" in response.text
    assert "showSearchProviderTestResult" in response.text
    assert "openBoxScanner" in response.text
    assert "applyIrregularGridRows" in response.text
    assert "applyManageBulkStock" in response.text
    assert "deleteBoxWithOptions" in response.text
    assert "decodeBoxCodeFrameViaServer" in response.text
    assert "zoom: 2" in response.text
    assert "* 0.46" in response.text
    assert "setRecognitionSideTab" not in response.text
    assert "application/octet-stream" in response.text


def test_recognition_upload_helpers_target_mobile_large_images() -> None:
    result = run_app_js_expression(
        """
        (() => {
            return {
                jpeg: isRecognitionImageCompressible({
                    type: "image/jpeg",
                    name: "camera.jpg",
                }),
                pngByExtension: isRecognitionImageCompressible({
                    type: "",
                    name: "template.PNG",
                }),
                heic: isRecognitionImageCompressible({
                    type: "image/heic",
                    name: "camera.heic",
                }),
                filename: buildCompressedImageFilename("box.photo.png"),
                networkMessage: getNetworkErrorMessage(new Error("Load failed")),
                retryCount: RECOGNITION_NETWORK_RETRY_COUNT,
            };
        })()
        """
    )

    assert result["jpeg"] is True
    assert result["pngByExtension"] is True
    assert result["heic"] is False
    assert result["filename"] == "box.photo-compressed.jpg"
    assert "短暂中断" in result["networkMessage"]
    assert result["retryCount"] == 2


def test_recognition_upload_requests_retry_transient_network_errors() -> None:
    result = run_app_js_expression(
        """
        (async () => {
            let attempts = 0;
            const statuses = [];
            window.setTimeout = (callback) => {
                callback();
                return 0;
            };
            fetch = () => {
                attempts += 1;
                if (attempts < 3) {
                    return Promise.reject(new Error("Failed to fetch"));
                }
                return Promise.resolve({
                    ok: true,
                    status: 200,
                    statusText: "OK",
                    text: () => Promise.resolve('{"ok": true}'),
                });
            };

            const response = await apiRequest(
                "/retry-test",
                {},
                buildRecognitionNetworkRetryOptions((message) => statuses.push(message)),
            );
            return {attempts, statuses, response};
        })()
        """
    )

    assert result["attempts"] == 3
    assert len(result["statuses"]) == 2
    assert "自动重试 (2/3)" in result["statuses"][0]
    assert result["response"]["ok"] is True


def test_recognition_draft_restores_until_explicitly_cleared() -> None:
    result = run_app_js_expression(
        """
        (() => {
            const elements = {};
            function addElement(selector, value = "") {
                const element = document.createElement("div");
                element.value = value;
                element.checked = false;
                elements[selector] = element;
                return element;
            }

            [
                "#recognition-mode",
                "#recognition-box-id",
                "#recognition-template-id",
                "#recognition-layout-type",
                "#recognition-prompt",
                "#verification-search-provider-id",
                "#recognized-box-name",
                "#recognized-box-readable-id",
                "#recognized-template-name",
                "#recognized-template-rows",
                "#recognized-template-cols",
                "#recognized-template-layout-json",
                "#recognition-summary",
                "#recognition-box-line",
                "#recognition-template-line",
                "#recognition-layout-line",
                "#recognition-overwrite-line",
                "#recognized-info-panel",
                "#recognized-box-fields",
                "#recognized-template-fields",
                "#recognition-edit-toggle",
                "#ai-result-viewer",
            ].forEach((selector) => addElement(selector));
            addElement("#recognition-overwrite-existing").checked = true;

            document.querySelector = (selector) => elements[selector] || null;
            document.querySelectorAll = () => [];

            state.currentUser = {username: "admin"};
            state.boxes = [{id: 7, template_id: 3, readable_id: "BOX-7", name: "Fan"}];
            state.templates = [{id: 3, layout_type: "grid", layout_definition: {rows: 1, cols: 2}}];
            elements["#recognition-mode"].value = "existing_box";
            elements["#recognition-box-id"].value = "7";
            elements["#recognition-template-id"].value = "3";
            elements["#recognition-layout-type"].value = "grid";
            elements["#recognition-prompt"].value = "优先使用功能名词";
            elements["#verification-search-provider-id"].value = "5";
            state.recognitionMode = "existing_box";
            state.lastRecognition = {
                filename: "phone.jpg",
                latency_ms: 61000,
                config_id: 1,
                content_type: "image/jpeg",
            };
            state.recognitionCells = [
                {
                    position_identifier: "R1C1",
                    is_empty: false,
                    name: "12V 离心风扇",
                    tags: ["风扇"],
                    attributes: {"供电电压": "12V"},
                    display_attribute: "供电电压",
                    verify_selected: true,
                },
                {
                    position_identifier: "R1C2",
                    is_empty: true,
                    name: "",
                    tags: [],
                    attributes: {},
                },
            ];

            const saved = saveRecognitionDraftFromCurrentState();
            const stored = JSON.parse(window.__storage.get(RECOGNITION_DRAFT_STORAGE_KEY));
            state.recognitionCells = [];
            elements["#recognition-summary"].textContent = "";
            const restored = restoreRecognitionDraft();
            const restoredName = state.recognitionCells[0].name;
            const restoredPrompt = elements["#recognition-prompt"].value;
            const restoredSummary = elements["#recognition-summary"].textContent;
            clearRecognitionDraft();
            return {
                saved,
                storedName: stored.cells[0].name,
                restored,
                restoredName,
                restoredPrompt,
                restoredSummary,
                draftExistsAfterClear: window.__storage.has(RECOGNITION_DRAFT_STORAGE_KEY),
            };
        })()
        """
    )

    assert result["saved"] is True
    assert result["storedName"] == "12V 离心风扇"
    assert result["restored"] is True
    assert result["restoredName"] == "12V 离心风扇"
    assert result["restoredPrompt"] == "优先使用功能名词"
    assert "已恢复未入库结果" in result["restoredSummary"]
    assert result["draftExistsAfterClear"] is False


def test_recognition_uses_sessions_instead_of_unload_warning() -> None:
    response = client.get("/ui/app.js")
    assert response.status_code == 200
    assert "beforeunload" not in response.text
    assert "warnBeforeUnloadDuringAi" not in response.text
    assert "RECOGNITION_ACTIVE_SESSION_STORAGE_KEY" in response.text


def test_login_asset_is_served() -> None:
    response = client.get("/ui/login.js")
    assert response.status_code == 200
    assert "ohmstash_token" in response.text
