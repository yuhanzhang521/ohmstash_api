const API_BASE = "/api/v1";
const THEME_STORAGE_KEY = "ohmstash_theme";
const RECOGNITION_DRAFT_STORAGE_KEY = "ohmstash_recognition_draft";
const RECOGNITION_ACTIVE_SESSION_STORAGE_KEY = "ohmstash_active_recognition_session";
const RECOGNITION_DRAFT_VERSION = 1;
const THEME_LABELS = {
    system: "跟随系统",
    light: "浅色",
    dark: "深色",
};
const CERTIFICATE_SOURCE_MODES = new Set(["self-signed", "path", "upload", "paste", "acme"]);
const ACME_CHALLENGE_TYPES = new Set(["http-01", "dns-01"]);

const VIEW_META = {
    dashboard: ["首页", "查看库存概览、未入库器件和近期盒子。"],
    recognition: ["识别入库", "拍照识别整盒内容，并批量写入已有盒子或新模板。"],
    manage: ["管理", "按盒子、分类或元器件维护现有库存。"],
    boxes: ["盒子", "创建盒子、查看布局并打印标签。"],
    search: ["搜索", "查找元器件位置并推荐空位。"],
    settings: ["设置", "管理 AI 供应商和标签库。"],
};

const STOCK_OPTIONS = ["充足", "少量", "紧张", "未知", "用尽"];
const MANAGE_CELL_MIN_WIDTH = 88;
const DISPLAY_ATTRIBUTE_FALLBACK_KEYS = [
    "阻值",
    "电阻值",
    "容值",
    "容量",
    "电容量",
    "电感值",
    "感值",
    "型号",
    "料号",
    "订货号",
    "MPN",
    "Part Number",
    "Manufacturer Part Number",
    "Resistance",
    "Capacitance",
    "Inductance",
];

const RECOGNITION_UPLOAD_OPTIMIZE_THRESHOLD_BYTES = 3 * 1024 * 1024;
const RECOGNITION_UPLOAD_TARGET_BYTES = 3 * 1024 * 1024;
const RECOGNITION_UPLOAD_MAX_SIDE = 2400;
const RECOGNITION_UPLOAD_JPEG_QUALITIES = [0.88, 0.82, 0.76, 0.7];
const RECOGNITION_UPLOAD_COMPRESSIBLE_EXTENSIONS = new Set(["jpg", "jpeg", "png", "webp"]);
const RECOGNITION_UPLOAD_COMPRESSIBLE_TYPES = new Set([
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
]);
const RECOGNITION_NETWORK_RETRY_COUNT = 2;
const RECOGNITION_NETWORK_RETRY_DELAYS_MS = [1200, 3000];
const RECOGNITION_WAKE_LOCK_TYPE = "screen";
const RECOGNITION_SESSION_POLL_INTERVAL_MS = 3000;

const ACTION_BUSY_TEXT = {
    "refresh-all": "刷新中...",
    "confirm-box-recognition": "入库中...",
    "verify-selected-components": "搜索中...",
    "refresh-recognition-sessions": "刷新中...",
    "open-recognition-session": "加载中...",
    "recognize-template-layout": "识别中...",
    "delete-component": "删除中...",
    "delete-template": "删除中...",
    "delete-box": "删除中...",
    "show-box-map": "加载中...",
    "open-manage-box": "加载中...",
    "ai-fill-cell": "搜索中...",
    "delete-cell-inventory": "删除中...",
    "load-placement-recommendations": "推荐中...",
    "create-bulk-box-for-placement": "创建中...",
    "apply-manage-bulk-stock": "更新中...",
    "refresh-logs": "刷新中...",
    "refresh-api-keys": "刷新中...",
    "clear-database": "清空中...",
    "logout": "退出中...",
    "test-search-provider": "测试中...",
    "test-current-search-provider-form": "测试中...",
    "set-default-search-provider": "切换中...",
    "delete-search-provider": "删除中...",
    "test-vlm": "测试中...",
    "test-current-vlm-form": "测试中...",
    "set-default-vlm": "切换中...",
    "delete-vlm": "删除中...",
    "seed-default-tags": "导入中...",
    "delete-selected-tag": "删除中...",
    "restart-service": "重启中...",
};

const SUBMIT_BUSY_TEXT = {
    "#template-form": "保存中...",
    "#box-form": "保存中...",
    "#placement-form": "入库中...",
    "#search-form": "搜索中...",
    "#recommendation-form": "推荐中...",
    "#vlm-form": "保存中...",
    "#search-provider-form": "保存中...",
    "#log-settings-form": "保存中...",
    "#server-config-form": "保存中...",
    "#login-form": "登录中...",
    "#password-form": "更新中...",
    "#api-key-form": "创建中...",
    "#tag-form": "保存中...",
    "#cell-editor-form": "保存中...",
};

const VERIFICATION_WARNING_PATTERNS = [
    /未检索到[^。；;，,\n]*(?:[。；;，,])?/g,
    /未找到[^。；;，,\n]*(?:[。；;，,])?/g,
    /没有可确认[^。；;，,\n]*(?:[。；;，,])?/g,
    /无法确认[^。；;，,\n]*(?:[。；;，,])?/g,
    /搜索结果不足[^。；;，,\n]*(?:[。；;，,])?/g,
    /(?:暂)?保留原标注/g,
];

const state = {
    authToken: window.localStorage.getItem("ohmstash_token") || "",
    themeMode: readStoredThemeMode(),
    currentUser: null,
    apiKeys: [],
    tags: [],
    components: [],
    templates: [],
    boxes: [],
    inventory: [],
    allSubBoxes: [],
    vlmConfigs: [],
    currentVlm: null,
    searchProviderConfigs: [],
    serverConfig: null,
    serverCertificateSource: "self-signed",
    serverAcmeChallengeType: "http-01",
    logConfig: null,
    logClearLineCount: 0,
    latestLogTotalLines: 0,
    boxOverviews: new Map(),
    editingVlmConfigId: null,
    editingSearchProviderConfigId: null,
    editingTemplateId: null,
    editingBoxId: null,
    editingTagId: null,
    recognitionCells: [],
    recognitionMode: "existing_box",
    recognitionEditing: false,
    recognizedBoxName: "",
    recognizedBoxReadableId: "",
    recognizedTemplate: null,
    matchedTemplateId: null,
    lastRecognition: null,
    recognitionSessions: [],
    activeRecognitionSessionId: readActiveRecognitionSessionId(),
    loadedRecognitionSessionId: null,
    recognitionSessionPollTimer: null,
    previewUrls: {},
    templateNameAuto: true,
    manageMode: "boxes",
    selectedManageBoxId: null,
    selectedManageCategory: null,
    selectedBoxOverview: null,
    manageSelectionMode: false,
    manageSelectedSubBoxIds: new Set(),
    cellEditor: null,
    placement: {
        componentId: null,
        selectedSubBoxId: null,
    },
    scanner: {
        mode: null,
        stream: null,
        detector: null,
        timer: null,
        busy: false,
        serverDecode: false,
    },
};

const q = (selector) => document.querySelector(selector);
const qa = (selector) => Array.from(document.querySelectorAll(selector));

function readStoredThemeMode() {
    const mode = window.localStorage.getItem(THEME_STORAGE_KEY) || "system";
    return Object.prototype.hasOwnProperty.call(THEME_LABELS, mode) ? mode : "system";
}

function applyThemeMode(mode) {
    if (mode === "dark" || mode === "light") {
        document.documentElement.dataset.theme = mode;
        return;
    }
    delete document.documentElement.dataset.theme;
}

function renderThemeControls() {
    qa("[data-theme-mode]").forEach((button) => {
        const active = button.dataset.themeMode === state.themeMode;
        button.classList.toggle("active", active);
        button.setAttribute("aria-checked", String(active));
    });
    setText("#theme-current-label", THEME_LABELS[state.themeMode]);
}

function setThemeMode(mode) {
    state.themeMode = Object.prototype.hasOwnProperty.call(THEME_LABELS, mode) ? mode : "system";
    if (state.themeMode === "system") {
        window.localStorage.removeItem(THEME_STORAGE_KEY);
    } else {
        window.localStorage.setItem(THEME_STORAGE_KEY, state.themeMode);
    }
    applyThemeMode(state.themeMode);
    renderThemeControls();
}

function setText(selector, value) {
    const element = q(selector);
    if (element) {
        element.textContent = value;
    }
}

function stripVerificationPhrases(value) {
    const correction = splitModelCorrectionNote(value);
    if (correction.note) {
        return correction.note;
    }
    return removeVerificationWarnings(value)
        .replace(/(?:联网)?搜索摘要确认[:：]?\s*/g, "")
        .replace(/联网确认[:：]?\s*/g, "")
        .trim();
}

function extractVerificationWarning(value) {
    const text = String(value || "");
    if (!text) {
        return "";
    }
    const correction = splitModelCorrectionNote(text);
    if (correction.warning) {
        return correction.warning;
    }
    for (const pattern of VERIFICATION_WARNING_PATTERNS) {
        const matches = text.match(pattern);
        if (matches?.length) {
            const warning = matches.join(" ").replace(/[。；;，,\s]+$/g, "").trim();
            return warning || "联网搜索未取得可确认资料，已保留原标注";
        }
    }
    return "";
}

function splitModelCorrectionNote(value) {
    const text = String(value || "").replace(/\s+/g, " ").trim();
    if (!text.includes("搜索结果指向")) {
        return {note: "", warning: ""};
    }
    const match = text.match(/搜索结果指向\s*([^：:。；;，,\n]+)(?:[：:]\s*([^。；;\n]+))?[。；;，,\s]*(原始[^。；;\n]*(?:疑似|可能)[^。；;\n]*)/);
    if (!match) {
        return {note: "", warning: ""};
    }
    const target = match[1].trim();
    const summary = (match[2] || "").trim();
    const warningTail = match[3].trim();
    return {
        note: target && summary ? `${target}：${summary}` : "",
        warning: target ? `搜索结果指向 ${target}，${warningTail}` : warningTail,
    };
}

function removeVerificationWarnings(value) {
    let text = String(value || "");
    VERIFICATION_WARNING_PATTERNS.forEach((pattern) => {
        text = text.replace(pattern, "");
    });
    return text.replace(/^[。；;，,\s]+|[。；;，,\s]+$/g, "").trim();
}

function startControlBusy(control, busyText) {
    if (!control || control.disabled) {
        return null;
    }
    const previousText = control.textContent;
    const previousDisabled = control.disabled;
    control.disabled = true;
    control.setAttribute("aria-busy", "true");
    if (busyText) {
        control.textContent = busyText;
    }
    return {
        restore() {
            control.disabled = previousDisabled;
            control.removeAttribute("aria-busy");
            if (busyText) {
                control.textContent = previousText;
            }
        },
    };
}

function startActionBusy(target, action) {
    if ("disabled" in target && target.disabled) {
        return null;
    }
    const busyText = ACTION_BUSY_TEXT[action];
    const canDisable = "disabled" in target;
    if (!busyText || !canDisable) {
        return {
            restore() {},
        };
    }
    return startControlBusy(target, busyText) || {
        restore() {},
    };
}

function startSubmitBusy(event, busyText) {
    const form = event.currentTarget;
    const submitter = event.submitter || form.querySelector('[type="submit"]');
    return startControlBusy(submitter, busyText);
}

async function handleBusySubmit(event, handler, busyText) {
    event.preventDefault();
    const busy = startSubmitBusy(event, busyText);
    if (!busy) {
        return;
    }
    try {
        await handler(event);
    } catch (error) {
        showToast(error.message);
    } finally {
        busy.restore();
    }
}

function scrollToElement(selector) {
    const element = q(selector);
    if (element) {
        element.scrollIntoView({behavior: "smooth", block: "start"});
    }
}

function showToast(message) {
    const toast = q("#toast");
    toast.textContent = message;
    toast.classList.add("visible");
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => {
        toast.classList.remove("visible");
    }, 2800);
}

function updateImagePreview(inputSelector, previewSelector) {
    const input = q(inputSelector);
    const preview = q(previewSelector);
    const file = input?.files?.[0];
    if (!input || !preview) {
        return;
    }
    if (state.previewUrls[inputSelector]) {
        URL.revokeObjectURL(state.previewUrls[inputSelector]);
        delete state.previewUrls[inputSelector];
    }
    if (!file) {
        preview.innerHTML = "";
        preview.classList.add("hidden");
        return;
    }
    const objectUrl = URL.createObjectURL(file);
    state.previewUrls[inputSelector] = objectUrl;
    preview.innerHTML = `
        <img src="${objectUrl}" alt="${escapeHtml(file.name)}">
        <span>${escapeHtml(file.name)} · ${formatFileSize(file.size)}</span>
    `;
    preview.classList.remove("hidden");
}

function formatFileSize(size) {
    if (size < 1024) {
        return `${size} B`;
    }
    if (size < 1024 * 1024) {
        return `${(size / 1024).toFixed(1)} KB`;
    }
    return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

async function prepareRecognitionUploadFile(file, statusCallback = null) {
    const original = {
        file,
        filename: file.name || "recognition-image",
        compressed: false,
        originalSize: file.size,
        uploadSize: file.size,
    };
    if (
        !isRecognitionImageCompressible(file)
        || file.size <= RECOGNITION_UPLOAD_OPTIMIZE_THRESHOLD_BYTES
    ) {
        return original;
    }

    try {
        statusCallback?.(`正在压缩图片：${file.name || "照片"} · ${formatFileSize(file.size)}`);
        const image = await loadImageForCompression(file);
        const width = image.naturalWidth || image.width;
        const height = image.naturalHeight || image.height;
        const scale = Math.min(1, RECOGNITION_UPLOAD_MAX_SIDE / Math.max(width, height));
        const targetWidth = Math.max(1, Math.round(width * scale));
        const targetHeight = Math.max(1, Math.round(height * scale));
        const blob = await compressImageToJpegBlob(image, targetWidth, targetHeight);
        if (!blob || blob.size >= file.size) {
            return original;
        }

        const filename = buildCompressedImageFilename(file.name || "recognition-image");
        const uploadFile = typeof File === "function"
            ? new File([blob], filename, {
                type: "image/jpeg",
                lastModified: file.lastModified || Date.now(),
            })
            : blob;
        return {
            file: uploadFile,
            filename,
            compressed: true,
            originalSize: file.size,
            uploadSize: blob.size,
        };
    } catch (error) {
        statusCallback?.(
            `图片压缩失败，正在尝试原图上传：${String(error?.message || error)}`,
        );
        return original;
    }
}

function isRecognitionImageCompressible(file) {
    const contentType = String(file.type || "").toLowerCase();
    if (RECOGNITION_UPLOAD_COMPRESSIBLE_TYPES.has(contentType)) {
        return true;
    }
    return RECOGNITION_UPLOAD_COMPRESSIBLE_EXTENSIONS.has(getFileExtension(file.name));
}

function getFileExtension(filename = "") {
    const parts = String(filename).toLowerCase().split(".");
    return parts.length > 1 ? parts.pop() : "";
}

function buildCompressedImageFilename(filename) {
    const normalized = String(filename || "recognition-image");
    const dotIndex = normalized.lastIndexOf(".");
    const stem = dotIndex > 0 ? normalized.slice(0, dotIndex) : normalized;
    return `${stem}-compressed.jpg`;
}

function loadImageForCompression(file) {
    return new Promise((resolve, reject) => {
        const objectUrl = URL.createObjectURL(file);
        const image = new Image();
        image.decoding = "async";
        image.onload = () => {
            URL.revokeObjectURL(objectUrl);
            resolve(image);
        };
        image.onerror = () => {
            URL.revokeObjectURL(objectUrl);
            reject(
                new Error(
                    "浏览器无法读取这张图片，请尝试在相册中另存为 JPEG 后再上传。",
                ),
            );
        };
        image.src = objectUrl;
    });
}

async function compressImageToJpegBlob(image, width, height) {
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
        throw new Error("浏览器不支持图片压缩，请换用 JPEG 小图后再上传。");
    }
    context.fillStyle = "#fff";
    context.fillRect(0, 0, width, height);
    context.drawImage(image, 0, 0, width, height);

    let bestBlob = null;
    for (const quality of RECOGNITION_UPLOAD_JPEG_QUALITIES) {
        const blob = await canvasToBlob(canvas, "image/jpeg", quality);
        if (!blob) {
            continue;
        }
        if (blob.size <= RECOGNITION_UPLOAD_TARGET_BYTES) {
            clearCanvas(canvas);
            return blob;
        }
        if (!bestBlob || blob.size < bestBlob.size) {
            bestBlob = blob;
        }
    }
    clearCanvas(canvas);
    return bestBlob;
}

function canvasToBlob(canvas, contentType, quality) {
    if (typeof canvas.toBlob !== "function") {
        return Promise.resolve(dataUrlToBlob(canvas.toDataURL(contentType, quality)));
    }
    return new Promise((resolve) => {
        canvas.toBlob(resolve, contentType, quality);
    });
}

function dataUrlToBlob(dataUrl) {
    const [header, data] = dataUrl.split(",");
    const contentType = header.match(/data:([^;]+)/)?.[1] || "image/jpeg";
    const binary = window.atob(data);
    const bytes = new Uint8Array(binary.length);
    for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
    }
    return new Blob([bytes], {type: contentType});
}

function clearCanvas(canvas) {
    canvas.width = 1;
    canvas.height = 1;
}

function setAuthToken(token) {
    state.authToken = token;
    window.localStorage.setItem("ohmstash_token", token);
}

function clearAuthToken() {
    state.authToken = "";
    state.currentUser = null;
    window.localStorage.removeItem("ohmstash_token");
}

function showLoginModal(message = "") {
    if (message) {
        window.sessionStorage.setItem("ohmstash_login_message", message);
    }
    const nextUrl = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/ui/login.html?next=${nextUrl}`;
}

function hideLoginModal() {
}

function normalizePath(path) {
    return path.startsWith("/") ? path : `/${path}`;
}

async function apiRequest(path, options = {}, requestOptions = {}) {
    const isFormDataBody = typeof FormData !== "undefined" && options.body instanceof FormData;
    const headers = isFormDataBody
        ? options.headers || {}
        : {"Content-Type": "application/json", ...(options.headers || {})};
    if (state.authToken) {
        headers.Authorization = `Bearer ${state.authToken}`;
    }
    let response;
    try {
        response = await fetchWithNetworkRetry(
            `${API_BASE}${normalizePath(path)}`,
            {
                ...options,
                headers,
            },
            requestOptions,
        );
    } catch (error) {
        throw new Error(getNetworkErrorMessage(error));
    }
    const data = await parseResponse(response);
    if (response.status === 401) {
        clearAuthToken();
        showLoginModal();
    }
    if (!response.ok) {
        throw new Error(extractErrorMessage(data, response.statusText));
    }
    return data;
}

async function apiFormRequest(path, formData, requestOptions = {}) {
    return apiRequest(path, {
        method: "POST",
        body: formData,
    }, requestOptions);
}

async function apiBlobRequest(path, options = {}) {
    const headers = {...(options.headers || {})};
    if (state.authToken) {
        headers.Authorization = `Bearer ${state.authToken}`;
    }
    let response;
    try {
        response = await fetch(`${API_BASE}${normalizePath(path)}`, {
            ...options,
            headers,
        });
    } catch (error) {
        throw new Error(getNetworkErrorMessage(error));
    }
    if (response.status === 401) {
        clearAuthToken();
        showLoginModal();
        throw new Error("请先登录");
    }
    if (!response.ok) {
        const fallback = await parseResponse(response);
        throw new Error(extractErrorMessage(fallback, response.statusText));
    }
    return response.blob();
}

async function fetchWithNetworkRetry(url, fetchOptions = {}, requestOptions = {}) {
    const retryCount = Math.max(Number(requestOptions.retryCount || 0), 0);
    const retryDelaysMs = requestOptions.retryDelaysMs || [];
    let lastError = null;

    for (let attemptIndex = 0; attemptIndex <= retryCount; attemptIndex += 1) {
        try {
            return await fetch(url, fetchOptions);
        } catch (error) {
            lastError = error;
            if (!isTransientNetworkError(error)) {
                throw error;
            }
            if (attemptIndex >= retryCount) {
                throw new Error(
                    `网络请求失败：已自动重试 ${retryCount} 次仍未连通，请保持页面打开并检查网络后重试。`,
                );
            }

            const delayMs = retryDelaysMs[attemptIndex] ?? ((attemptIndex + 1) * 1000);
            requestOptions.onRetry?.({
                attemptIndex,
                nextAttemptNumber: attemptIndex + 2,
                totalAttempts: retryCount + 1,
                delayMs,
                error,
            });
            await waitMs(delayMs);
        }
    }

    throw lastError || new Error("网络请求失败");
}

function isTransientNetworkError(error) {
    const message = String(error?.message || error || "");
    return /load failed|failed to fetch|networkerror|network request failed|connection|timeout/i
        .test(message);
}

function getNetworkErrorMessage(error) {
    const message = String(error?.message || "网络请求失败");
    if (isTransientNetworkError(error)) {
        return "网络请求失败：连接可能短暂中断，请保持页面打开并重试。";
    }
    return message;
}

function waitMs(delayMs) {
    return new Promise((resolve) => {
        window.setTimeout(resolve, delayMs);
    });
}

async function requestRecognitionWakeLock() {
    if (
        typeof navigator === "undefined"
        || !navigator.wakeLock?.request
    ) {
        return null;
    }

    try {
        return await navigator.wakeLock.request(RECOGNITION_WAKE_LOCK_TYPE);
    } catch {
        return null;
    }
}

function releaseRecognitionWakeLock(wakeLock) {
    if (!wakeLock?.release) {
        return;
    }
    wakeLock.release().catch(() => {});
}

function buildRecognitionNetworkRetryOptions(statusCallback) {
    return {
        retryCount: RECOGNITION_NETWORK_RETRY_COUNT,
        retryDelaysMs: RECOGNITION_NETWORK_RETRY_DELAYS_MS,
        onRetry: ({nextAttemptNumber, totalAttempts, delayMs}) => {
            statusCallback?.(
                `网络连接中断，${(delayMs / 1000).toFixed(1)} 秒后自动重试 `
                + `(${nextAttemptNumber}/${totalAttempts})...`,
            );
        },
    };
}

function readLocalStorageJson(key) {
    try {
        const rawValue = window.localStorage.getItem(key);
        return rawValue ? JSON.parse(rawValue) : null;
    } catch {
        return null;
    }
}

function writeLocalStorageJson(key, value) {
    try {
        window.localStorage.setItem(key, JSON.stringify(value));
        return true;
    } catch {
        return false;
    }
}

function removeLocalStorageItem(key) {
    try {
        window.localStorage.removeItem(key);
    } catch {
    }
}

function readActiveRecognitionSessionId() {
    const value = Number(window.localStorage.getItem(RECOGNITION_ACTIVE_SESSION_STORAGE_KEY) || 0);
    return Number.isFinite(value) && value > 0 ? value : null;
}

function writeActiveRecognitionSessionId(sessionId) {
    if (!sessionId) {
        removeLocalStorageItem(RECOGNITION_ACTIVE_SESSION_STORAGE_KEY);
        return;
    }
    window.localStorage.setItem(RECOGNITION_ACTIVE_SESSION_STORAGE_KEY, String(sessionId));
}

async function parseResponse(response) {
    const text = await response.text();
    if (!text) {
        return null;
    }
    try {
        return JSON.parse(text);
    } catch {
        return text;
    }
}

function extractErrorMessage(data, fallback) {
    if (!data) {
        return fallback;
    }
    if (typeof data === "string") {
        return data;
    }
    if (typeof data.detail === "string") {
        return data.detail;
    }
    if (data.detail?.message) {
        const status = data.detail.status_code ? ` (HTTP ${data.detail.status_code})` : "";
        return `${data.detail.message}${status}`;
    }
    return fallback;
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

function getAttributeDisplayValue(attributes, key) {
    if (!attributes || !key || !Object.prototype.hasOwnProperty.call(attributes, key)) {
        return "";
    }
    return String(attributes[key] ?? "").trim();
}

function chooseDisplayAttributeKey(attributes, preferredKey = "") {
    const preferredValue = getAttributeDisplayValue(attributes, preferredKey);
    if (preferredValue) {
        return preferredKey;
    }
    const fallbackKey = DISPLAY_ATTRIBUTE_FALLBACK_KEYS.find((key) => {
        return getAttributeDisplayValue(attributes, key);
    });
    if (fallbackKey) {
        return fallbackKey;
    }
    return Object.keys(attributes || {}).find((key) => {
        return getAttributeDisplayValue(attributes, key);
    }) || "";
}

function getAttributeDisplayText(attributes, preferredKey = "") {
    const displayKey = chooseDisplayAttributeKey(attributes, preferredKey);
    return getAttributeDisplayValue(attributes, displayKey);
}

function setView(view) {
    if (!VIEW_META[view]) {
        return;
    }
    qa("[data-view-panel]").forEach((panel) => {
        panel.classList.toggle("active", panel.dataset.viewPanel === view);
    });
    qa("[data-view]").forEach((button) => {
        button.classList.toggle("active", button.dataset.view === view);
    });
    const [title, subtitle] = VIEW_META[view];
    q("#view-title").textContent = title;
    q("#view-subtitle").textContent = subtitle;
    if (view === "dashboard") {
        renderDashboard();
    }
    if (view === "manage") {
        renderManageView();
    }
    if (view === "recognition" && state.authToken) {
        refreshRecognitionSessions().catch((error) => showToast(error.message));
    }
}

function setSettingsView(view) {
    qa("[data-settings-panel]").forEach((panel) => {
        panel.classList.toggle("active", panel.dataset.settingsPanel === view);
    });
    qa("[data-settings-view]").forEach((button) => {
        button.classList.toggle("active", button.dataset.settingsView === view);
    });
    if (view === "logs") {
        refreshLogs().catch((error) => showToast(error.message));
    }
    if (view === "server") {
        refreshServerConfig().catch((error) => showToast(error.message));
    }
    if (view === "account" && state.authToken) {
        refreshCurrentUser()
            .then(refreshApiKeys)
            .catch((error) => showToast(error.message));
    }
}

function setOptions(select, items, labeler, options = {}) {
    const currentValue = select.value;
    select.innerHTML = "";
    if (options.blankLabel) {
        const option = document.createElement("option");
        option.value = "";
        option.textContent = options.blankLabel;
        select.append(option);
    }
    items.forEach((item) => {
        const option = document.createElement("option");
        option.value = item.id;
        option.textContent = labeler(item);
        select.append(option);
    });
    if (Array.from(select.options).some((option) => option.value === currentValue)) {
        select.value = currentValue;
    }
}

function updateMetrics() {
    setText("#metric-components", state.components.length);
    setText("#metric-tags", state.tags.length);
    setText("#metric-boxes", state.boxes.length);
    setText("#metric-inventory", state.inventory.length);
    setText("#template-count", `${state.templates.length} 个`);
    setText("#box-count", `${state.boxes.length} 个`);
}

async function refreshAll() {
    try {
        await apiRequest("/system/health");
        q("#service-text").textContent = state.currentUser
            ? `已登录：${state.currentUser.username}`
            : "后端在线";
        await Promise.all([
            refreshAi(),
            refreshSearchProviders(),
            refreshRecognitionSessions(),
            refreshParts(),
            refreshStorage(),
            refreshServerConfig(),
            refreshLogsConfig(),
        ]);
        updateMetrics();
        renderDashboard();
        renderManageView();
    } catch (error) {
        q("#service-text").textContent = "后端离线";
        showToast(error.message);
    }
}

async function refreshAi() {
    try {
        state.currentVlm = await apiRequest("/ai/vlm_config");
    } catch {
        state.currentVlm = null;
    }
    state.vlmConfigs = await apiRequest("/ai/vlm_configs/");
    renderVlmConfigs();
}

async function refreshSearchProviders() {
    state.searchProviderConfigs = await apiRequest("/search/providers/");
    renderSearchProviderConfigs();
    renderSearchProviderSelectors();
}

async function refreshRecognitionSessions() {
    state.recognitionSessions = await apiRequest("/ai/recognition_sessions?limit=30");
    renderRecognitionSessionList();
    return state.recognitionSessions;
}

function upsertRecognitionSession(session) {
    const index = state.recognitionSessions.findIndex((item) => item.id === session.id);
    if (index >= 0) {
        state.recognitionSessions[index] = session;
    } else {
        state.recognitionSessions.unshift(session);
    }
    state.recognitionSessions.sort((left, right) => {
        return new Date(right.created_at || 0) - new Date(left.created_at || 0);
    });
}

async function refreshParts() {
    const [tags, components] = await Promise.all([
        apiRequest("/tags/"),
        apiRequest("/components/"),
    ]);
    state.tags = tags;
    state.components = components;
    renderTags();
    renderComponents();
}

async function refreshStorage() {
    const [templates, boxes, inventory] = await Promise.all([
        apiRequest("/box_templates/"),
        apiRequest("/boxes/"),
        apiRequest("/inventory/"),
    ]);
    state.templates = templates;
    state.boxes = boxes;
    state.inventory = inventory;
    state.allSubBoxes = await loadAllSubBoxes(boxes);
    renderTemplatesAndBoxes();
    renderPlacementSelectors();
}

async function refreshServerConfig() {
    state.serverConfig = await apiRequest("/system/config");
    renderServerConfig();
}

function renderServerConfig() {
    const serverConfig = state.serverConfig;
    if (!serverConfig) {
        return;
    }
    applyServerDeploymentMode(serverConfig);
    if (serverConfig.behind_reverse_proxy) {
        renderReverseProxyServerStatus(serverConfig);
        q("#server-restart-warning").classList.add("hidden");
        q("#server-restart-warning").textContent = "";
        return;
    }
    const acmeEnabled = serverConfig.https_enabled && serverConfig.certificate_source === "acme";
    const certificateStatus = acmeEnabled
        ? `ACME ${formatAcmeChallengeType(serverConfig.acme_challenge_type)}`
        : (serverConfig.using_self_signed_certificate
        ? "使用自签证书"
        : (serverConfig.ssl_configured ? "已配置证书" : "未配置证书"));
    const tlsStatus = serverConfig.https_enabled ? "HTTPS 已启用" : "HTTPS 未启用";
    const endpointHost = acmeEnabled && serverConfig.acme_domain
        ? serverConfig.acme_domain
        : serverConfig.host;
    const endpoint = `${serverConfig.scheme}://${endpointHost}:${serverConfig.active_port}`;
    q("#server-config-summary").textContent = `${tlsStatus} · ${certificateStatus}`;
    q("#server-config-endpoint").textContent = endpoint;
    q("#server-config-ports").textContent = acmeEnabled
        ? formatAcmePortStatus(serverConfig)
        : (serverConfig.https_enabled
        ? `HTTP ${serverConfig.http_port} / HTTPS ${serverConfig.https_port}`
        : `HTTP ${serverConfig.http_port} / HTTPS 未启用`);
    q("#server-config-certfile").textContent = acmeEnabled
        ? (serverConfig.acme_domain || "未设置域名")
        : (serverConfig.https_enabled
        ? (serverConfig.ssl_certfile || "未设置")
        : "未启用");
    q("#server-config-keyfile").textContent = acmeEnabled
        ? `Cloudflare ${serverConfig.acme_cloudflare_api_token_configured ? "已配置" : "未配置"}`
        : (serverConfig.https_enabled
        ? (serverConfig.ssl_keyfile || "未设置")
        : "未启用");
    q("#server-config-restart").textContent = serverConfig.restart_required ? "需要重启" : "无需重启";
    q("#server-host").value = serverConfig.host;
    q("#server-http-port").value = serverConfig.http_port;
    q("#server-https-enabled").checked = serverConfig.https_enabled;
    q("#server-https-port").value = serverConfig.https_port;
    q("#server-ssl-certfile").value = serverConfig.using_self_signed_certificate ? "" : (serverConfig.ssl_certfile || "");
    q("#server-ssl-keyfile").value = serverConfig.using_self_signed_certificate ? "" : (serverConfig.ssl_keyfile || "");
    q("#server-ssl-cert-pem").value = "";
    q("#server-ssl-key-pem").value = "";
    q("#server-acme-domain").value = serverConfig.acme_domain || "";
    q("#server-acme-email").value = serverConfig.acme_email || "";
    q("#server-acme-cloudflare-token").value = "";
    q("#server-acme-cloudflare-token-status").textContent = serverConfig.acme_cloudflare_api_token_configured
        ? "已保存 Token，留空则继续使用"
        : "未保存 Token";
    resetServerCertificateUploadFields();
    state.serverCertificateSource = normalizeServerCertificateSource(
        serverConfig.certificate_source
        || (serverConfig.ssl_configured && !serverConfig.using_self_signed_certificate ? "path" : "self-signed"),
    );
    state.serverAcmeChallengeType = normalizeServerAcmeChallengeType(
        serverConfig.acme_challenge_type,
    );
    updateServerHttpsVisibility();
    q("#server-restart-warning").classList.toggle("hidden", !serverConfig.restart_required);
    q("#server-restart-warning").textContent = serverConfig.restart_required
        ? "服务设置已保存，重启后端服务后生效。"
        : "";
}

function applyServerDeploymentMode(serverConfig) {
    const reverseProxy = Boolean(serverConfig.behind_reverse_proxy);
    qa("[data-server-standalone-only]").forEach((element) => {
        element.classList.toggle("hidden", reverseProxy);
    });
    const saveButton = q("#server-config-save-button");
    if (saveButton) {
        saveButton.classList.toggle("hidden", reverseProxy);
    }
    const heading = q("#server-config-heading");
    if (heading) {
        heading.classList.toggle("hidden", reverseProxy);
    }
    const notice = q("#server-reverse-proxy-notice");
    if (notice) {
        notice.classList.toggle("hidden", !reverseProxy);
    }
}

function renderReverseProxyServerStatus(serverConfig) {
    const publicUrl = serverConfig.public_base_url || "由反代决定";
    const mode = serverConfig.deployment_mode || "reverse_proxy";
    q("#server-config-summary").textContent = `部署模式：${mode} · TLS 由外部反代终止`;
    q("#server-config-endpoint").textContent = publicUrl;
    q("#server-config-ports").textContent = `内部 HTTP ${serverConfig.http_port}`;
    q("#server-config-certfile").textContent = "由反代管理";
    q("#server-config-keyfile").textContent = "由反代管理";
    q("#server-config-restart").textContent = "由部署侧重启容器生效";
}

function formatAcmeChallengeType(challengeType) {
    return normalizeServerAcmeChallengeType(challengeType).toUpperCase();
}

function formatAcmePortStatus(serverConfig) {
    const challengeType = normalizeServerAcmeChallengeType(serverConfig.acme_challenge_type);
    if (challengeType === "http-01") {
        return `Caddy 80/443 -> 后端 HTTP ${serverConfig.http_port}`;
    }
    return `Caddy 443 -> 后端 HTTP ${serverConfig.http_port}`;
}

function normalizeServerCertificateSource(source) {
    return CERTIFICATE_SOURCE_MODES.has(source) ? source : "self-signed";
}

function setServerCertificateSource(source) {
    state.serverCertificateSource = normalizeServerCertificateSource(source);
    updateServerCertificateSourceVisibility();
}

function normalizeServerAcmeChallengeType(challengeType) {
    return ACME_CHALLENGE_TYPES.has(challengeType) ? challengeType : "http-01";
}

function setServerAcmeChallengeType(challengeType) {
    state.serverAcmeChallengeType = normalizeServerAcmeChallengeType(challengeType);
    updateServerAcmeChallengeVisibility();
    applyServerAcmePortRules();
}

function updateServerHttpsVisibility() {
    const enabled = q("#server-https-enabled")?.checked || false;
    const httpsOptions = q("#server-https-options");
    if (httpsOptions) {
        httpsOptions.classList.toggle("hidden", !enabled);
    }
    const httpsPort = q("#server-https-port");
    if (httpsPort) {
        httpsPort.disabled = !enabled;
        httpsPort.required = enabled;
    }
    updateServerCertificateSourceVisibility();
    applyServerAcmePortRules();
}

function updateServerCertificateSourceVisibility() {
    const enabled = q("#server-https-enabled")?.checked || false;
    const source = normalizeServerCertificateSource(state.serverCertificateSource);
    qa("[data-certificate-source]").forEach((button) => {
        const active = button.dataset.certificateSource === source;
        button.classList.toggle("active", active);
        button.disabled = !enabled;
        button.setAttribute("aria-checked", String(active));
    });
    qa("[data-certificate-source-panel]").forEach((panel) => {
        const active = enabled && panel.dataset.certificateSourcePanel === source;
        panel.classList.toggle("hidden", !active);
        qaControls(panel).forEach((control) => {
            control.disabled = !active;
        });
    });
    updateServerAcmeChallengeVisibility();
    applyServerAcmePortRules();
}

function updateServerAcmeChallengeVisibility() {
    const enabled = q("#server-https-enabled")?.checked || false;
    const source = normalizeServerCertificateSource(state.serverCertificateSource);
    const challengeType = normalizeServerAcmeChallengeType(state.serverAcmeChallengeType);
    const acmeActive = enabled && source === "acme";
    qa("[data-acme-challenge]").forEach((button) => {
        const active = button.dataset.acmeChallenge === challengeType;
        button.classList.toggle("active", active);
        button.disabled = !acmeActive;
        button.setAttribute("aria-checked", String(active));
    });
    qa("[data-acme-challenge-panel]").forEach((panel) => {
        const active = acmeActive && panel.dataset.acmeChallengePanel === challengeType;
        panel.classList.toggle("hidden", !active);
        qaControls(panel).forEach((control) => {
            control.disabled = !active;
        });
    });
}

function applyServerAcmePortRules() {
    const enabled = q("#server-https-enabled")?.checked || false;
    const source = normalizeServerCertificateSource(state.serverCertificateSource);
    const acmeActive = enabled && source === "acme";
    const httpPort = q("#server-http-port");
    const httpsPort = q("#server-https-port");
    if (httpPort) {
        httpPort.readOnly = false;
    }
    if (httpsPort) {
        if (acmeActive) {
            httpsPort.value = 443;
        }
        httpsPort.readOnly = acmeActive;
    }
}

function qaControls(element) {
    return Array.from(element.querySelectorAll("input, textarea, select, button"));
}

function resetServerCertificateUploadFields() {
    const certUpload = q("#server-ssl-cert-upload");
    const keyUpload = q("#server-ssl-key-upload");
    if (certUpload) {
        certUpload.value = "";
    }
    if (keyUpload) {
        keyUpload.value = "";
    }
    setText("#server-ssl-cert-upload-status", "未选择文件");
    setText("#server-ssl-key-upload-status", "未选择文件");
}

async function refreshLogsConfig() {
    state.logConfig = await apiRequest("/system/logs/config");
    q("#log-level").value = state.logConfig.level;
    q("#log-file-path").textContent = state.logConfig.log_file_path;
}

async function refreshCurrentUser() {
    state.currentUser = await apiRequest("/auth/me");
    q("#service-text").textContent = `已登录：${state.currentUser.username}`;
}

async function refreshApiKeys() {
    state.apiKeys = await apiRequest("/auth/api_keys");
    renderApiKeys();
}

function renderApiKeys() {
    const list = q("#api-key-list");
    if (!list) {
        return;
    }
    list.innerHTML = "";
    if (!state.apiKeys.length) {
        list.innerHTML = '<div class="empty-panel compact-empty">还没有 API 密钥。</div>';
        return;
    }
    state.apiKeys.forEach((apiKey) => {
        const card = document.createElement("article");
        card.className = "provider-card";
        card.innerHTML = `
            <h4>${escapeHtml(apiKey.name)}</h4>
            <p>${escapeHtml(apiKey.prefix)}... · ${apiKey.is_active ? "启用" : "停用"}</p>
            <div class="card-actions">
                <button class="danger-button" type="button" data-action="delete-api-key" data-id="${apiKey.id}">删除</button>
            </div>
        `;
        list.append(card);
    });
}

async function refreshLogs() {
    const response = await apiRequest("/system/logs?limit=300");
    state.logConfig = {
        level: response.level,
        log_file_path: response.log_file_path,
    };
    q("#log-level").value = response.level;
    q("#log-file-path").textContent = response.log_file_path;
    state.latestLogTotalLines = response.total_lines;
    const visibleLines = filterVisibleLogLines(response.lines, response.total_lines);
    q("#log-viewer").textContent = visibleLines.length
        ? visibleLines.slice().reverse().join("\n")
        : "暂无日志。";
}

function filterVisibleLogLines(lines, totalLines) {
    const startIndex = Math.max(0, state.logClearLineCount - (totalLines - lines.length));
    return lines.slice(startIndex);
}

async function loadAllSubBoxes(boxes) {
    if (!boxes.length) {
        return [];
    }
    const groups = await Promise.all(
        boxes.map((box) => apiRequest(`/sub_boxes/?box_id=${encodeURIComponent(box.id)}`)),
    );
    return groups.flat();
}

function renderTags() {
    setOptions(q("#manage-tag-filter"), state.tags, (tag) => tag.name, {blankLabel: "全部标签"});

    const board = q("#tag-board");
    board.innerHTML = "";
    if (!state.tags.length) {
        board.innerHTML = '<div class="empty-panel compact-empty">还没有标签，可以导入默认分类或手动创建。</div>';
        return;
    }

    const groups = new Map();
    state.tags.forEach((tag) => {
        const [groupName, childName] = tag.name.includes("/")
            ? tag.name.split("/", 2)
            : [tag.name, null];
        if (!groups.has(groupName)) {
            groups.set(groupName, []);
        }
        groups.get(groupName).push({tag, childName});
    });

    groups.forEach((entries, groupName) => {
        const group = document.createElement("article");
        group.className = "tag-group";
        const childrenHtml = entries.map(({tag, childName}) => {
            const label = childName || "基础类";
            return `
                <button class="tag-chip-button ${tag.id === state.editingTagId ? "selected" : ""}" type="button" data-action="edit-tag" data-id="${tag.id}">
                    ${escapeHtml(label)}
                </button>
            `;
        }).join("");
        group.innerHTML = `<h4>${escapeHtml(groupName)}</h4><div class="chip-row">${childrenHtml}</div>`;
        board.append(group);
    });
}

function renderComponents() {
    setOptions(
        q("#cell-component-select"),
        state.components,
        (component) => component.name,
        {blankLabel: "新建器件"},
    );
    renderManageView();
}

function createComponentSummaryHtml(component) {
    const tags = getComponentTagNames(component);
    const tagHtml = renderTagChips(tags);
    const attributeHtml = renderAttributesView(component.attributes || {});
    const locations = getComponentLocations(component.id);
    const description = component.description
        ? `<p class="component-description">${escapeHtml(component.description)}</p>`
        : "";
    const locationHtml = locations.length
        ? `<div class="location-line">${locations.map((item) => {
            return `<span>${escapeHtml(item)}</span>`;
        }).join("")}</div>`
        : '<div class="location-line muted-text">未入库</div>';
    return `
        <div class="component-row-head">
            <div>
                <h4>${escapeHtml(component.name || `Component #${component.id}`)}</h4>
                ${description}
            </div>
            <div class="card-actions">
                <button class="small-button" type="button" data-action="edit-component" data-id="${component.id}">编辑</button>
                <button class="small-button" type="button" data-action="place-component" data-id="${component.id}">入库</button>
                <button class="danger-button" type="button" data-action="delete-component" data-id="${component.id}">删除</button>
            </div>
        </div>
        <div class="chip-row">${tagHtml || '<span class="muted-text">无标签</span>'}</div>
        <div class="attribute-grid component-attributes">${attributeHtml || '<span class="muted-text">无结构化属性</span>'}</div>
        ${locationHtml}
    `;
}

function getComponentLocations(componentId) {
    return state.inventory
        .filter((item) => item.component_id === componentId)
        .map((item) => {
            return `${findSubBoxLabel(item.sub_box_id)} · ${getInventoryQuantityText(item)}`;
        });
}

function getUnplacedComponents() {
    const placedIds = new Set(state.inventory.map((item) => item.component_id));
    return state.components.filter((component) => !placedIds.has(component.id));
}

function renderTemplatesAndBoxes() {
    setOptions(q("#box-template-id"), state.templates, (template) => `${template.name} (${template.id})`);
    setOptions(q("#recognition-box-id"), state.boxes, (box) => `${box.readable_id} ${box.name || ""}`);
    setOptions(q("#recognition-template-id"), state.templates, (template) => `${template.name} (${template.id})`);
    setOptions(
        q("#recommendation-box-id"),
        state.boxes,
        (box) => `${box.readable_id} ${box.name || ""}`,
        {blankLabel: "不限"},
    );
    renderTemplateList();
    renderBoxList();
    renderManageView();
}

function renderTemplateList() {
    const list = q("#template-list");
    list.innerHTML = "";
    if (!state.templates.length) {
        list.innerHTML = '<div class="empty-panel compact-empty">还没有模板。</div>';
        return;
    }
    state.templates.forEach((template) => {
        const card = document.createElement("article");
        card.className = "item-card";
        card.innerHTML = `
            <h4>${escapeHtml(template.name)}</h4>
            <p>${escapeHtml(template.layout_type)} · ${escapeHtml(formatLayoutDefinition(template))}</p>
            <div class="card-actions">
                <button class="small-button" type="button" data-action="edit-template" data-id="${template.id}">编辑</button>
                <button class="danger-button" type="button" data-action="delete-template" data-id="${template.id}">删除</button>
            </div>
        `;
        list.append(card);
    });
}

function renderBoxList() {
    const list = q("#box-list");
    if (!list) {
        return;
    }
    list.innerHTML = "";
    if (!state.boxes.length) {
        list.innerHTML = '<div class="empty-panel compact-empty">还没有盒子。</div>';
        return;
    }
    state.boxes.forEach((box) => {
        const template = state.templates.find((item) => item.id === box.template_id);
        const card = document.createElement("article");
        card.className = "box-card";
        card.innerHTML = `
            <div class="box-card-head">
                <h4>${escapeHtml(box.readable_id)}</h4>
                ${renderReprintBadge(box)}
            </div>
            <p>${escapeHtml(box.name || "未命名盒子")}</p>
            <p>${escapeHtml(template?.name || "未知模板")}</p>
            ${renderBoxCategorySummary(box)}
            <div class="card-actions">
                <button class="small-button" type="button" data-action="open-manage-box" data-id="${box.id}">进入</button>
                <button class="small-button" type="button" data-action="show-box-label" data-id="${box.id}">标签</button>
                <button class="small-button" type="button" data-action="show-box-map" data-id="${box.id}">布局</button>
                <button class="small-button" type="button" data-action="edit-box" data-id="${box.id}">编辑</button>
                <button class="danger-button" type="button" data-action="delete-box" data-id="${box.id}">删除</button>
            </div>
        `;
        list.append(card);
    });
}

function renderDashboard() {
    if (!q("#dashboard-summary")) {
        return;
    }
    const unplaced = getUnplacedComponents();
    const placedCount = state.components.length - unplaced.length;
    const occupiedSubBoxIds = new Set(state.inventory.map((item) => item.sub_box_id));
    const emptySlots = state.allSubBoxes.filter((subBox) => {
        const box = state.boxes.find((item) => item.id === subBox.box_id);
        return !occupiedSubBoxIds.has(subBox.id) && !isBulkBox(box);
    });
    const bulkBoxes = getBulkBoxes();
    setText("#dashboard-summary", `${state.components.length} 个器件，${state.boxes.length} 个盒子`);
    setText("#dashboard-placed-count", placedCount);
    setText("#dashboard-unplaced-count", unplaced.length);
    setText("#dashboard-empty-slot-count", emptySlots.length);
    setText("#dashboard-bulk-count", bulkBoxes.length);
    setText("#dashboard-unplaced-label", `${unplaced.length} 个`);
    setText("#dashboard-box-label", `${state.boxes.length} 个`);
    renderUnplacedList(q("#dashboard-unplaced-list"), unplaced);
    renderDashboardBoxes();
}

function renderDashboardBoxes() {
    const list = q("#dashboard-box-list");
    if (!list) {
        return;
    }
    list.innerHTML = "";
    state.boxes.slice(0, 8).forEach((box) => {
        const template = state.templates.find((item) => item.id === box.template_id);
        const card = document.createElement("article");
        card.className = "box-card";
        card.innerHTML = `
            <div class="box-card-head">
                <h4>${escapeHtml(box.readable_id)}</h4>
                ${renderReprintBadge(box)}
            </div>
            <p>${escapeHtml(box.name || "未命名盒子")}</p>
            <p>${escapeHtml(template?.name || "未知模板")}</p>
            ${renderBoxCategorySummary(box)}
            <div class="card-actions">
                <button class="small-button" type="button" data-action="open-manage-box" data-id="${box.id}">进入</button>
            </div>
        `;
        list.append(card);
    });
    if (!state.boxes.length) {
        list.innerHTML = '<div class="empty-panel compact-empty">还没有盒子。</div>';
    }
}

function renderUnplacedDrawer() {
    const list = q("#unplaced-list");
    if (!list) {
        return;
    }
    const unplaced = getUnplacedComponents();
    setText("#unplaced-count", unplaced.length);
    renderUnplacedList(list, unplaced);
}

function renderUnplacedList(list, components) {
    if (!list) {
        return;
    }
    list.innerHTML = "";
    if (!components.length) {
        list.innerHTML = '<div class="empty-panel compact-empty">没有暂存的未入库器件。</div>';
        return;
    }
    list.append(createComponentRowList(components));
}

function renderPlacementSelectors() {
    const boxSelect = q("#placement-box-id");
    if (!boxSelect) {
        return;
    }
    setOptions(
        boxSelect,
        getStandardBoxes(),
        (box) => `${box.readable_id} ${box.name || ""}`,
        {blankLabel: "选择已有盒子"},
    );
    renderPlacementSubBoxOptions(Number(boxSelect.value || 0));
    setOptions(
        q("#placement-bulk-box-id"),
        getBulkBoxes(),
        (box) => `${box.readable_id} ${box.name || "整理箱"}`,
        {blankLabel: "不放入整理箱"},
    );
}

function renderPlacementSubBoxOptions(boxId) {
    const select = q("#placement-sub-box-id");
    if (!select) {
        return;
    }
    const subBoxes = boxId ? getEmptySubBoxesForBox(boxId) : [];
    setOptions(
        select,
        subBoxes,
        (subBox) => `${subBox.position_identifier} (${subBox.readable_id})`,
        {blankLabel: "选择空位"},
    );
    if (state.placement.selectedSubBoxId) {
        select.value = String(state.placement.selectedSubBoxId);
    }
}

function renderManageView() {
    const list = q("#manage-list");
    if (!list) {
        return;
    }
    qa("[data-action='set-manage-mode']").forEach((button) => {
        button.classList.toggle("active", button.dataset.mode === state.manageMode);
    });
    renderUnplacedDrawer();
    const layout = q("#manage-layout");
    layout.classList.toggle("components-only", state.manageMode === "components");
    layout.classList.toggle("categories-mode", state.manageMode === "categories");
    if (state.manageMode === "boxes") {
        renderManageBoxes();
        renderManageBoxDetail();
        return;
    }
    if (state.manageMode === "categories") {
        renderManageCategories();
        renderManageCategoryDetail();
        return;
    }
    if (state.manageMode === "components") {
        renderManageComponents();
    }
}

function renderManageBoxes() {
    const list = q("#manage-list");
    const query = q("#manage-query").value.trim().toLowerCase();
    const boxes = state.boxes.filter((box) => {
        const template = state.templates.find((item) => item.id === box.template_id);
        const haystack = `${box.readable_id} ${box.name || ""} ${template?.name || ""}`.toLowerCase();
        return !query || haystack.includes(query);
    });
    q("#manage-list-title").textContent = "盒子";
    q("#manage-result-count").textContent = `${boxes.length} 项`;
    list.innerHTML = "";
    if (!boxes.length) {
        list.innerHTML = '<div class="empty-panel compact-empty">没有匹配盒子。</div>';
        return;
    }
    boxes.forEach((box) => {
        const template = state.templates.find((item) => item.id === box.template_id);
        const card = document.createElement("article");
        card.className = `item-card selectable-card ${box.id === state.selectedManageBoxId ? "selected" : ""}`;
        card.dataset.action = "open-manage-box";
        card.dataset.id = box.id;
        card.innerHTML = `
            <div class="box-card-head">
                <h4>${escapeHtml(box.readable_id)}</h4>
                ${renderReprintBadge(box)}
            </div>
            <p>${escapeHtml(box.name || "未命名盒子")} · ${escapeHtml(template?.name || "未知模板")}</p>
            ${renderBoxCategorySummary(box)}
            <div class="card-actions">
                <button class="small-button" type="button" data-action="edit-box" data-id="${box.id}">编辑</button>
                <button class="small-button" type="button" data-action="show-box-label" data-id="${box.id}">标签</button>
                <button class="danger-button" type="button" data-action="delete-box" data-id="${box.id}">删除</button>
            </div>
        `;
        list.append(card);
    });
}

function renderManageCategories() {
    const list = q("#manage-list");
    const filtered = getFilteredComponents();
    const groups = groupComponentsByCategory(filtered);
    const groupNames = Array.from(groups.keys()).sort((left, right) => left.localeCompare(right, "zh-CN"));
    if (!groupNames.includes(state.selectedManageCategory)) {
        state.selectedManageCategory = groupNames[0] || null;
    }
    q("#manage-list-title").textContent = "分类";
    q("#manage-result-count").textContent = `${groups.size} 类`;
    list.innerHTML = "";
    if (!groups.size) {
        list.innerHTML = '<div class="empty-panel compact-empty">没有匹配分类。</div>';
        return;
    }
    groupNames.forEach((groupName) => {
        const components = groups.get(groupName);
        const card = document.createElement("article");
        card.className = `item-card selectable-card category-card ${
            groupName === state.selectedManageCategory ? "selected" : ""
        }`;
        card.dataset.action = "select-manage-category";
        card.dataset.category = groupName;
        const sampleTags = components.slice(0, 4).map((component) => {
            return `<span class="tag-chip">${escapeHtml(component.name)}</span>`;
        }).join("");
        card.innerHTML = `
            <h4>${escapeHtml(groupName)}</h4>
            <p>${components.length} 个器件</p>
            <div class="chip-row">${sampleTags}</div>
        `;
        list.append(card);
    });
}

function renderManageCategoryDetail() {
    const detail = q("#manage-box-detail");
    const groups = groupComponentsByCategory(getFilteredComponents());
    const components = groups.get(state.selectedManageCategory) || [];
    if (!state.selectedManageCategory) {
        q("#manage-detail-title").textContent = "分类明细";
        q("#manage-detail-subtitle").textContent = "选择左侧分类";
        detail.innerHTML = '<div class="empty-panel compact-empty">左侧点击分类后，这里按行展示器件。</div>';
        return;
    }
    q("#manage-detail-title").textContent = state.selectedManageCategory;
    q("#manage-detail-subtitle").textContent = `${components.length} 个器件`;
    detail.innerHTML = "";
    detail.append(createComponentRowList(components));
}

function renderManageComponents() {
    const list = q("#manage-list");
    const components = getFilteredComponents();
    q("#manage-list-title").textContent = "元器件";
    q("#manage-result-count").textContent = `${components.length} 项`;
    list.innerHTML = "";
    if (!components.length) {
        list.innerHTML = '<div class="empty-panel compact-empty">没有匹配器件。</div>';
        return;
    }
    list.append(createComponentRowList(components));
}

function createComponentRowList(components) {
    const rowList = document.createElement("div");
    rowList.className = "component-row-list";
    components.forEach((component) => {
        const row = document.createElement("article");
        row.className = "component-row";
        row.innerHTML = createComponentSummaryHtml(component);
        rowList.append(row);
    });
    return rowList;
}

function groupComponentsByCategory(components) {
    const groups = new Map();
    components.forEach((component) => {
        const groupName = getComponentCategoryName(component);
        if (!groups.has(groupName)) {
            groups.set(groupName, []);
        }
        groups.get(groupName).push(component);
    });
    return groups;
}

function getComponentCategoryName(component) {
    const tags = getComponentTagNames(component);
    return tags[0]?.split("/", 1)[0] || "未分类";
}

function renderManageBoxDetail() {
    const detail = q("#manage-box-detail");
    const overview = state.selectedBoxOverview;
    if (!overview) {
        q("#manage-detail-title").textContent = "盒内布局";
        q("#manage-detail-subtitle").textContent = "选择一个盒子";
        detail.innerHTML = '<div class="empty-panel compact-empty">从左侧进入盒子后，可点击格子编辑库存和器件信息。</div>';
        return;
    }
    const validSubBoxIds = new Set(overview.sub_boxes.map((subBox) => subBox.id));
    state.manageSelectedSubBoxIds = new Set(
        Array.from(state.manageSelectedSubBoxIds).filter((subBoxId) => {
            return validSubBoxIds.has(subBoxId);
        }),
    );
    q("#manage-detail-title").textContent = overview.readable_id;
    const selectedCount = state.manageSelectedSubBoxIds.size;
    q("#manage-detail-subtitle").textContent = selectedCount
        ? `${overview.name || overview.template.name} · 已选 ${selectedCount} 格`
        : overview.name || overview.template.name;
    const cols = getOverviewColumnCount(overview);
    const layoutCellsByPosition = new Map(
        getLayoutCells(overview.template.layout_definition).map((cell) => [getLayoutCellPosition(cell), cell]),
    );
    const map = document.createElement("div");
    map.className = "box-map editable-map";
    map.style.gridTemplateColumns = getManageGridTemplateColumns(cols);
    map.style.minWidth = getManageGridMinWidth(cols);
    if (overview.template.layout_type === "irregular") {
        map.classList.add("irregular-map");
        applyIrregularGridRows(
            map,
            overview.template.layout_definition,
            overview.sub_boxes.length,
            44,
        );
    }
    overview.sub_boxes.forEach((subBox) => {
        const button = document.createElement("button");
        const names = subBox.inventory.map((item) => item.component_name).filter(Boolean);
        const displayNames = subBox.inventory.map(getInventoryDisplayTitle).filter(Boolean);
        const quantities = subBox.inventory.map((item) => {
            return item.stock_mode === "exact" ? item.quantity_exact : item.quantity_fuzzy;
        }).filter(Boolean);
        button.type = "button";
        button.className = [
            "box-cell-detail",
            names.length ? "filled" : "",
            state.manageSelectedSubBoxIds.has(subBox.id) ? "selected" : "",
        ].filter(Boolean).join(" ");
        button.dataset.action = state.manageSelectionMode
            ? "toggle-manage-cell-selection"
            : "open-cell-editor";
        button.dataset.id = subBox.id;
        button.title = names.join(", ") || `${subBox.position_identifier} / 空`;
        button.innerHTML = `
            <span>${escapeHtml(subBox.position_identifier)}</span>
            <strong>${escapeHtml(displayNames.join(", ") || "空")}</strong>
            <small>${escapeHtml(quantities.join(", "))}</small>
        `;
        applyLayoutCellPlacement(button, layoutCellsByPosition.get(subBox.position_identifier));
        map.append(button);
    });
    const mapScroller = document.createElement("div");
    mapScroller.className = "box-map-scroll";
    mapScroller.append(map);
    detail.innerHTML = "";
    detail.append(createManageBulkToolbar());
    detail.append(mapScroller);
}

function createManageBulkToolbar() {
    const toolbar = document.createElement("div");
    toolbar.className = "manage-bulk-toolbar";
    const selectedCount = state.manageSelectedSubBoxIds.size;
    const selectableIds = getSelectableManageSubBoxIds();
    const allSelectableSelected = selectableIds.length > 0
        && selectableIds.every((subBoxId) => state.manageSelectedSubBoxIds.has(subBoxId));
    const selectAllButton = state.manageSelectionMode
        ? `
            <button class="secondary-button" type="button" data-action="toggle-manage-all-selection" ${selectableIds.length ? "" : "disabled"}>
                ${allSelectableSelected ? "退出全选" : "全选"}
            </button>
        `
        : "";
    toolbar.innerHTML = `
        <button class="secondary-button" type="button" data-action="toggle-manage-selection-mode">
            ${state.manageSelectionMode ? "退出多选" : "多选格子"}
        </button>
        ${selectAllButton}
        <span class="muted-text">已选 ${selectedCount} 格</span>
        <select id="manage-bulk-stock-mode" ${selectedCount ? "" : "disabled"}>
            ${STOCK_OPTIONS.map((value) => `<option value="${value}">${value}</option>`).join("")}
            <option value="custom">自定义数量</option>
        </select>
        <input class="hidden" id="manage-bulk-quantity-exact" type="number" min="0" value="1" ${selectedCount ? "" : "disabled"}>
        <button class="secondary-button" type="button" data-action="apply-manage-bulk-stock" ${selectedCount ? "" : "disabled"}>
            批量设置库存
        </button>
    `;
    toolbar.querySelector("#manage-bulk-stock-mode").addEventListener(
        "change",
        updateManageBulkExactVisibility,
    );
    return toolbar;
}

function getManageGridTemplateColumns(cols) {
    return `repeat(${cols}, minmax(${MANAGE_CELL_MIN_WIDTH}px, 1fr))`;
}

function getManageGridMinWidth(cols) {
    const gapWidth = 6;
    const trackWidth = cols * MANAGE_CELL_MIN_WIDTH;
    const totalGapWidth = Math.max(cols - 1, 0) * gapWidth;
    return `max(100%, ${trackWidth + totalGapWidth}px)`;
}

function getInventoryDisplayTitle(item) {
    const attributes = item.attributes || {};
    return item.display_name
        || getAttributeDisplayText(attributes, item.display_attribute || "")
        || item.component_name
        || "";
}

function getSelectableManageSubBoxIds() {
    const overview = state.selectedBoxOverview;
    if (!overview) {
        return [];
    }
    return overview.sub_boxes
        .filter((subBox) => subBox.inventory.length > 0)
        .map((subBox) => subBox.id);
}

function updateManageBulkExactVisibility() {
    const exactInput = q("#manage-bulk-quantity-exact");
    if (!exactInput) {
        return;
    }
    exactInput.classList.toggle("hidden", q("#manage-bulk-stock-mode").value !== "custom");
}

function toggleManageSelectionMode() {
    state.manageSelectionMode = !state.manageSelectionMode;
    if (!state.manageSelectionMode) {
        state.manageSelectedSubBoxIds.clear();
    }
    renderManageBoxDetail();
}

function toggleManageCellSelection(subBoxId) {
    if (state.manageSelectedSubBoxIds.has(subBoxId)) {
        state.manageSelectedSubBoxIds.delete(subBoxId);
    } else {
        state.manageSelectedSubBoxIds.add(subBoxId);
    }
    renderManageBoxDetail();
}

function toggleManageAllCellSelection() {
    const selectableIds = getSelectableManageSubBoxIds();
    if (!selectableIds.length) {
        throw new Error("没有可全选的非空格子");
    }
    const allSelected = selectableIds.every((subBoxId) => {
        return state.manageSelectedSubBoxIds.has(subBoxId);
    });
    state.manageSelectedSubBoxIds = allSelected ? new Set() : new Set(selectableIds);
    renderManageBoxDetail();
}

async function applyManageBulkStock() {
    const overview = state.selectedBoxOverview;
    if (!overview || !state.manageSelectedSubBoxIds.size) {
        throw new Error("请先选择要批量修改的格子");
    }
    const inventoryItems = overview.sub_boxes
        .filter((subBox) => state.manageSelectedSubBoxIds.has(subBox.id))
        .flatMap((subBox) => subBox.inventory);
    if (!inventoryItems.length) {
        throw new Error("所选格子没有库存记录");
    }
    const quantityMode = q("#manage-bulk-stock-mode").value;
    const payload = quantityMode === "custom"
        ? {
            stock_mode: "exact",
            quantity_exact: Number(q("#manage-bulk-quantity-exact").value || 0),
            quantity_fuzzy: null,
        }
        : {
            stock_mode: "fuzzy",
            quantity_exact: null,
            quantity_fuzzy: quantityMode,
        };
    await Promise.all(
        inventoryItems.map((item) => apiRequest(`/inventory/${item.inventory_id}`, {
            method: "PUT",
            body: JSON.stringify(payload),
        })),
    );
    const selectedBoxId = state.selectedManageBoxId;
    state.manageSelectedSubBoxIds.clear();
    state.manageSelectionMode = false;
    await refreshAll();
    if (selectedBoxId) {
        await openManageBox(selectedBoxId);
    }
    showToast(`已更新 ${inventoryItems.length} 条库存记录`);
}

function getFilteredComponents() {
    const query = q("#manage-query").value.trim().toLowerCase();
    const tagId = Number(q("#manage-tag-filter").value || 0);
    const attributes = parseAttributes(q("#manage-attribute-filter").value);
    return state.components.filter((component) => {
        const tags = getComponentTagNames(component);
        const haystack = [
            component.name,
            component.description || "",
            tags.join(" "),
            serializeAttributes(component.attributes || {}),
        ].join(" ").toLowerCase();
        if (query && !haystack.includes(query)) {
            return false;
        }
        if (tagId && !component.tags?.some((tag) => tag.id === tagId)) {
            return false;
        }
        return Object.entries(attributes).every(([key, value]) => {
            const actual = component.attributes?.[key];
            return actual !== undefined && String(actual).toLowerCase().includes(String(value).toLowerCase());
        });
    });
}

function getOverviewColumnCount(overview) {
    if (overview.template.layout_type === "irregular") {
        return getIrregularColumnCount(overview.template.layout_definition, overview.sub_boxes.length);
    }
    if (overview.template.layout_type !== "grid") {
        return Math.min(Math.max(overview.sub_boxes.length, 1), 4);
    }
    return Number(overview.template.layout_definition?.cols || 1);
}

function getLayoutCells(layoutDefinition) {
    if (Array.isArray(layoutDefinition)) {
        return layoutDefinition;
    }
    if (Array.isArray(layoutDefinition?.cells)) {
        return layoutDefinition.cells;
    }
    return [];
}

function isBulkTemplate(template) {
    const config = template?.physical_dimensions || {};
    return config.container_type === "bulk" || config.container_kind === "bulk" || template?.name === "整理箱";
}

function getStandardBoxes() {
    return state.boxes.filter((box) => !isBulkBox(box));
}

function isBulkBox(box) {
    const template = state.templates.find((item) => item.id === box?.template_id);
    return isBulkTemplate(template);
}

function getBulkBoxes() {
    return state.boxes.filter((box) => isBulkBox(box));
}

function getOccupiedSubBoxIds() {
    return new Set(state.inventory.map((item) => item.sub_box_id));
}

function getEmptySubBoxesForBox(boxId) {
    const occupiedSubBoxIds = getOccupiedSubBoxIds();
    return state.allSubBoxes.filter((subBox) => {
        return subBox.box_id === boxId && !occupiedSubBoxIds.has(subBox.id);
    });
}

function getBulkSubBox(boxId) {
    return state.allSubBoxes.find((subBox) => subBox.box_id === Number(boxId));
}

function getLayoutCellPosition(cell) {
    return String(cell?.id || cell?.position_identifier || cell?.label || "");
}

function getIrregularColumnCount(layoutDefinition, fallbackCount = 1) {
    const cells = getLayoutCells(layoutDefinition);
    const declaredCols = Number(layoutDefinition?.cols || layoutDefinition?.columns || 0);
    const maxCol = cells.reduce((maxValue, cell) => {
        const col = Number(cell.col || cell.column || 0);
        const span = Number(cell.col_span || cell.column_span || 1);
        return col > 0 ? Math.max(maxValue, col + span - 1) : maxValue;
    }, 0);
    if (declaredCols > 0) {
        return Math.max(declaredCols, maxCol);
    }
    if (maxCol > 0) {
        return maxCol;
    }
    return Math.min(Math.max(fallbackCount, 1), 4);
}

function getIrregularRowCount(layoutDefinition, fallbackCount = 1) {
    const cells = getLayoutCells(layoutDefinition);
    const declaredRows = Number(layoutDefinition?.rows || 0);
    const maxRow = cells.reduce((maxValue, cell) => {
        const row = Number(cell.row || 0);
        const span = Number(cell.row_span || cell.rowSpan || 1);
        return row > 0 ? Math.max(maxValue, row + span - 1) : maxValue;
    }, 0);
    if (declaredRows > 0) {
        return Math.max(declaredRows, maxRow);
    }
    if (maxRow > 0) {
        return maxRow;
    }
    return Math.min(Math.max(fallbackCount, 1), 4);
}

function getLayoutCellRowSpan(layoutCell) {
    return Math.max(Number(layoutCell?.row_span || layoutCell?.rowSpan || 1), 1);
}

function getIrregularRowUnitHeight(layoutDefinition, baseCellHeight) {
    const cells = getLayoutCells(layoutDefinition);
    const minRowSpan = cells.reduce((minValue, cell) => {
        return Math.min(minValue, getLayoutCellRowSpan(cell));
    }, Number.POSITIVE_INFINITY);
    if (!Number.isFinite(minRowSpan) || minRowSpan <= 0) {
        return baseCellHeight;
    }
    return Math.max(Math.floor(baseCellHeight / minRowSpan), 18);
}

function applyIrregularGridRows(map, layoutDefinition, fallbackCount, baseCellHeight) {
    const rows = getIrregularRowCount(layoutDefinition, fallbackCount);
    const rowHeight = getIrregularRowUnitHeight(layoutDefinition, baseCellHeight);
    map.style.gridTemplateRows = `repeat(${rows}, minmax(${rowHeight}px, auto))`;
    map.style.gridAutoRows = "auto";
}

function applyLayoutCellPlacement(element, layoutCell) {
    if (!layoutCell) {
        return;
    }
    const row = Number(layoutCell.row || 0);
    const col = Number(layoutCell.col || layoutCell.column || 0);
    const rowSpan = getLayoutCellRowSpan(layoutCell);
    const colSpan = Number(layoutCell.col_span || layoutCell.column_span || layoutCell.colSpan || 1);
    if (row > 0) {
        element.style.gridRow = `${row} / span ${Math.max(rowSpan, 1)}`;
    }
    if (col > 0) {
        element.style.gridColumn = `${col} / span ${Math.max(colSpan, 1)}`;
    }
    const orientation = String(layoutCell.orientation || "").toLowerCase();
    if (orientation.includes("90") || orientation.includes("vertical") || orientation.includes("portrait")) {
        element.classList.add("vertical-cell");
    }
}

async function openManageBox(boxId) {
    const overview = await apiRequest(`/boxes/${boxId}/overview`);
    state.manageMode = "boxes";
    state.selectedManageBoxId = Number(boxId);
    state.selectedBoxOverview = overview;
    state.manageSelectionMode = false;
    state.manageSelectedSubBoxIds.clear();
    state.boxOverviews.set(Number(boxId), overview);
    setView("manage");
    renderManageView();
}

function findSubBoxLabel(subBoxId) {
    const subBox = state.allSubBoxes.find((item) => item.id === subBoxId);
    if (!subBox) {
        return `SubBox #${subBoxId}`;
    }
    const box = state.boxes.find((item) => item.id === subBox.box_id);
    return box ? `${box.readable_id} / ${subBox.position_identifier}` : subBox.readable_id;
}

function getComponentTagNames(component) {
    return (component.tags || []).map((tag) => tag.name);
}

function renderVlmConfigs() {
    q("#default-vlm-label").textContent = state.currentVlm
        ? `默认：${state.currentVlm.name}`
        : "未设置默认";
    const list = q("#vlm-config-list");
    list.innerHTML = "";
    if (!state.vlmConfigs.length) {
        list.innerHTML = '<div class="empty-panel compact-empty">还没有 AI 供应商。</div>';
        fillVlmForm(null);
        return;
    }
    state.vlmConfigs.forEach((config) => {
        const card = document.createElement("article");
        card.className = "provider-card";
        card.innerHTML = `
            <h4>${escapeHtml(config.name)}${config.is_default ? " · 默认" : ""}</h4>
            <p>${escapeHtml(config.provider)} · ${escapeHtml(config.model_name)}</p>
            <p>${config.has_api_key ? "API Key 已保存" : "未保存 API Key"}</p>
            <div class="card-actions">
                <button class="small-button" type="button" data-action="edit-vlm" data-id="${config.id}">编辑</button>
                <button class="small-button" type="button" data-action="test-vlm" data-id="${config.id}">测试</button>
                <button class="small-button" type="button" data-action="set-default-vlm" data-id="${config.id}">切换默认</button>
                <button class="danger-button" type="button" data-action="delete-vlm" data-id="${config.id}">删除</button>
            </div>
        `;
        list.append(card);
    });
}

function renderSearchProviderConfigs() {
    const defaultProvider = getDefaultSearchProviderConfig();
    q("#default-search-provider-label").textContent = defaultProvider
        ? `默认：${defaultProvider.name}`
        : "默认：DuckDuckGo HTML";
    const list = q("#search-provider-list");
    list.innerHTML = "";
    if (!state.searchProviderConfigs.length) {
        list.innerHTML = '<div class="empty-panel compact-empty">还没有搜索源，当前会使用 DuckDuckGo HTML 兜底。</div>';
        fillSearchProviderForm(null);
        return;
    }
    state.searchProviderConfigs.forEach((config) => {
        const modelText = config.extra_config?.model_name
            ? ` · ${escapeHtml(config.extra_config.model_name)}`
            : "";
        const card = document.createElement("article");
        card.className = "provider-card";
        card.innerHTML = `
            <h4>${escapeHtml(config.name)}${config.is_default ? " · 默认" : ""}</h4>
            <p>${escapeHtml(formatSearchProviderName(config.provider))}${modelText}</p>
            <p>${config.has_api_key ? "API Key 已保存" : "未保存 API Key"}</p>
            <div class="card-actions">
                <button class="small-button" type="button" data-action="edit-search-provider" data-id="${config.id}">编辑</button>
                <button class="small-button" type="button" data-action="test-search-provider" data-id="${config.id}">测试</button>
                <button class="small-button" type="button" data-action="set-default-search-provider" data-id="${config.id}">切换默认</button>
                <button class="danger-button" type="button" data-action="delete-search-provider" data-id="${config.id}">删除</button>
            </div>
        `;
        list.append(card);
    });
}

function getDefaultSearchProviderConfig() {
    return state.searchProviderConfigs.find((config) => config.is_default) || null;
}

function getSelectedSearchProviderConfigId() {
    const cellModalVisible = !q("#cell-editor-modal")?.classList.contains("hidden");
    const selector = cellModalVisible ? "#cell-search-provider-id" : "#verification-search-provider-id";
    const value = q(selector)?.value || "";
    return value ? Number(value) : null;
}

function formatSearchProviderName(provider) {
    return {
        brave: "Brave Search API",
        tavily: "Tavily",
        openai_web_search: "OpenAI Web Search",
        duckduckgo: "DuckDuckGo HTML",
    }[provider] || provider;
}

function renderSearchProviderSelectors() {
    const selects = [
        q("#verification-search-provider-id"),
        q("#cell-search-provider-id"),
    ].filter(Boolean);
    selects.forEach((select) => {
        const currentValue = select.value;
        select.innerHTML = "";
        const fallbackOption = document.createElement("option");
        fallbackOption.value = "";
        fallbackOption.textContent = "DuckDuckGo HTML";
        select.append(fallbackOption);
        state.searchProviderConfigs.filter((config) => config.is_active).forEach((config) => {
            const option = document.createElement("option");
            option.value = config.id;
            option.textContent = config.is_default ? `${config.name}（默认）` : config.name;
            select.append(option);
        });
        const defaultProvider = getDefaultSearchProviderConfig();
        if (!currentValue && defaultProvider) {
            select.value = String(defaultProvider.id);
            return;
        }
        if (Array.from(select.options).some((option) => option.value === currentValue)) {
            select.value = currentValue;
            return;
        }
        select.value = defaultProvider ? String(defaultProvider.id) : "";
    });
}

function fillSearchProviderForm(config) {
    state.editingSearchProviderConfigId = config?.id || null;
    q("#search-provider-name").value = config?.name || "";
    q("#search-provider-type").value = config?.provider || "brave";
    q("#search-provider-api-key").value = "";
    q("#search-provider-model-name").value = config?.extra_config?.model_name || "";
    q("#search-provider-base-url").value = config?.extra_config?.base_url || "";
    q("#search-provider-active").checked = config?.is_active ?? true;
    q("#search-provider-submit-button").textContent = config ? "保存修改" : "保存搜索源";
    updateSearchProviderFieldVisibility();
    clearSearchProviderTestResult();
}

function updateSearchProviderFieldVisibility() {
    const isOpenAiWebSearch = q("#search-provider-type").value === "openai_web_search";
    q("#search-provider-model-line").classList.toggle("hidden", !isOpenAiWebSearch);
    q("#search-provider-base-url-line").classList.toggle("hidden", !isOpenAiWebSearch);
}

function clearSearchProviderTestResult() {
    const line = q("#search-provider-test-result");
    line.textContent = "";
    line.classList.add("hidden");
    line.classList.remove("warning-line");
    line.classList.add("muted-text");
}

function showSearchProviderTestResult(result) {
    const line = q("#search-provider-test-result");
    const latency = result.latency_ms == null ? "" : ` · ${result.latency_ms}ms`;
    const status = result.status_code ? ` · HTTP ${result.status_code}` : "";
    const firstResult = result.results?.[0]?.title ? ` · ${result.results[0].title}` : "";
    line.textContent = result.ok
        ? `测试通过${latency}${firstResult}`
        : `测试失败${status}${latency}：${result.message}`;
    line.classList.toggle("warning-line", !result.ok);
    line.classList.toggle("muted-text", result.ok);
    line.classList.remove("hidden");
}

function buildSearchProviderPayload() {
    const existingConfig = state.searchProviderConfigs.find((config) => {
        return config.id === state.editingSearchProviderConfigId;
    });
    const extraConfig = {...(existingConfig?.extra_config || {})};
    const provider = q("#search-provider-type").value;
    const modelName = q("#search-provider-model-name").value.trim();
    const baseUrl = q("#search-provider-base-url").value.trim();
    if (provider === "openai_web_search") {
        if (modelName) {
            extraConfig.model_name = modelName;
        } else {
            delete extraConfig.model_name;
        }
        if (baseUrl) {
            extraConfig.base_url = baseUrl;
        } else {
            delete extraConfig.base_url;
        }
    } else {
        delete extraConfig.model_name;
        delete extraConfig.base_url;
    }
    const payload = {
        name: q("#search-provider-name").value.trim(),
        provider,
        is_active: q("#search-provider-active").checked,
        is_default: existingConfig?.is_default || state.searchProviderConfigs.length === 0,
        extra_config: extraConfig,
    };
    const apiKey = q("#search-provider-api-key").value.trim();
    if (apiKey) {
        payload.api_key = apiKey;
    }
    return payload;
}

function fillVlmForm(config) {
    state.editingVlmConfigId = config?.id || null;
    q("#vlm-name").value = config?.name || "";
    q("#vlm-provider").value = config?.provider || "openai-compatible";
    q("#vlm-base-url").value = config?.base_url || "";
    q("#vlm-model-name").value = config?.model_name || "";
    q("#vlm-api-key").value = "";
    q("#vlm-timeout-seconds").value = config?.extra_config?.timeout_seconds || 90;
    q("#vlm-active").checked = config?.is_active ?? true;
    q("#vlm-submit-button").textContent = config ? "保存修改" : "保存供应商";
}

function buildVlmConfigPayload() {
    const existingConfig = state.vlmConfigs.find((config) => config.id === state.editingVlmConfigId);
    const extraConfig = {...(existingConfig?.extra_config || {})};
    extraConfig.timeout_seconds = Number(q("#vlm-timeout-seconds").value || 90);
    const payload = {
        name: q("#vlm-name").value.trim(),
        provider: q("#vlm-provider").value,
        base_url: q("#vlm-base-url").value.trim() || null,
        model_name: q("#vlm-model-name").value.trim(),
        is_active: q("#vlm-active").checked,
        is_default: existingConfig?.is_default || state.vlmConfigs.length === 0,
        extra_config: extraConfig,
    };
    const apiKey = q("#vlm-api-key").value.trim();
    if (apiKey) {
        payload.api_key = apiKey;
    }
    return payload;
}

function setRecognitionBusy(isBusy) {
    const button = q("#recognition-submit-button");
    button.disabled = isBusy;
    button.textContent = isBusy ? "识别中..." : "上传识别";
}

function setTemplateRecognitionBusy(isBusy) {
    const button = q("#template-recognition-button");
    button.disabled = isBusy;
    button.textContent = isBusy ? "识别中..." : "识别并填入模板";
}

function setRecognitionStatus(message, isError = false) {
    q("#recognition-summary").textContent = isError ? "失败" : "进行中";
    const viewer = q("#ai-result-viewer");
    viewer.innerHTML = `<div class="empty-panel ${isError ? "error" : ""}">${escapeHtml(message)}</div>`;
}

function renderRecognitionSessionList() {
    const list = q("#recognition-session-list");
    if (!list) {
        return;
    }
    if (!state.recognitionSessions.length) {
        list.innerHTML = '<div class="empty-panel compact-empty">暂无识别会话。</div>';
        return;
    }
    list.innerHTML = state.recognitionSessions.map((session) => {
        const active = session.id === state.activeRecognitionSessionId ? " active" : "";
        const title = [
            getRecognitionSessionModeLabel(session.mode),
            session.filename || `会话 #${session.id}`,
        ].filter(Boolean).join(" · ");
        const meta = [
            formatRecognitionSessionTime(session.created_at),
            getRecognitionSessionStatusLabel(session),
            getRecognitionSessionVerificationLabel(session),
        ].filter(Boolean).join(" · ");
        return `
            <article class="recognition-session-card${active}">
                <div class="recognition-session-main">
                    <div class="recognition-session-title" title="${escapeHtml(title)}">${escapeHtml(title)}</div>
                    <div class="recognition-session-meta">${escapeHtml(meta)}</div>
                </div>
                <button class="small-button" type="button" data-action="open-recognition-session" data-id="${session.id}">打开</button>
            </article>
        `;
    }).join("");
}

function getRecognitionSessionModeLabel(mode) {
    return {
        single_image: "单图识别",
        existing_box: "更新已有盒子",
        new_box: "按模板新建盒子",
        auto_template_box: "识别样式",
    }[mode] || "识别";
}

function getRecognitionSessionStatusLabel(session) {
    return {
        queued: "排队中",
        running: "识别中",
        succeeded: "已完成",
        failed: "失败",
    }[session.status] || session.status;
}

function getRecognitionSessionVerificationLabel(session) {
    return {
        idle: "",
        running: "自动搜索中",
        succeeded: "已自动搜索",
        failed: "自动搜索失败",
        skipped: "无需自动搜索",
    }[session.verification_status] || "";
}

function formatRecognitionSessionTime(value) {
    const date = value ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) {
        return "";
    }
    return date.toLocaleString();
}

function isRecognitionSessionFinished(session) {
    return ["succeeded", "failed"].includes(session.status);
}

function setActiveRecognitionSessionId(sessionId) {
    state.activeRecognitionSessionId = sessionId || null;
    writeActiveRecognitionSessionId(state.activeRecognitionSessionId);
    renderRecognitionSessionList();
}

async function openRecognitionSession(sessionId) {
    const session = await apiRequest(`/ai/recognition_sessions/${sessionId}`);
    activateRecognitionSession(session, {fromHistory: true});
}

function activateRecognitionSession(session, options = {}) {
    upsertRecognitionSession(session);
    setActiveRecognitionSessionId(session.id);
    applyRecognitionSessionContext(session);
    if (session.result?.parsed_result) {
        loadRecognitionSessionResult(session, options);
    } else if (session.status === "failed") {
        setRecognitionStatus(session.error_message || "识别会话失败。", true);
    } else {
        setRecognitionStatus(getRecognitionSessionWaitingMessage(session));
    }
    if (isRecognitionSessionFinished(session)) {
        stopRecognitionSessionPolling();
    } else {
        startRecognitionSessionPolling(session.id);
    }
}

function getRecognitionSessionWaitingMessage(session) {
    if (session.verification_status === "running") {
        return "识别已完成，正在自动联网搜索默认选中的器件...";
    }
    return "后台识别会话已创建，结果会写入识别历史。";
}

function applyRecognitionSessionContext(session) {
    const mode = normalizeRecognitionDraftMode(session.mode);
    q("#recognition-mode").value = mode;
    state.recognitionMode = mode;
    setDraftFieldValue("#recognition-box-id", session.box_id || "");
    setDraftFieldValue("#recognition-template-id", session.template_id || "");
    setDraftFieldValue("#recognition-layout-type", session.layout_type || "grid");
    setDraftFieldValue("#recognition-prompt", session.additional_prompt || "");
    setDraftFieldValue(
        "#verification-search-provider-id",
        session.search_provider_config_id || "",
    );
    if (q("#recognition-overwrite-existing")) {
        q("#recognition-overwrite-existing").checked = Boolean(session.overwrite_existing);
    }
    updateRecognitionModeFields();
}

function loadRecognitionSessionResult(session, options = {}) {
    const shouldRender = state.loadedRecognitionSessionId !== session.id
        || options.fromHistory
        || session.verification_status === "succeeded";
    if (!shouldRender) {
        return;
    }
    renderRecognitionResult(session.result);
    state.loadedRecognitionSessionId = session.id;
    const autoSearchText = getRecognitionSessionVerificationLabel(session);
    if (options.fromHistory && autoSearchText) {
        showToast(`已打开识别会话，${autoSearchText}`);
    }
}

function startRecognitionSessionPolling(sessionId) {
    stopRecognitionSessionPolling();
    state.recognitionSessionPollTimer = window.setInterval(async () => {
        try {
            const session = await apiRequest(`/ai/recognition_sessions/${sessionId}`);
            activateRecognitionSession(session);
            if (isRecognitionSessionFinished(session)) {
                await refreshRecognitionSessions();
                if (session.status === "succeeded") {
                    showToast("识别会话已完成");
                }
            }
        } catch (error) {
            stopRecognitionSessionPolling();
            showToast(error.message);
        }
    }, RECOGNITION_SESSION_POLL_INTERVAL_MS);
}

function stopRecognitionSessionPolling() {
    if (!state.recognitionSessionPollTimer) {
        return;
    }
    window.clearInterval(state.recognitionSessionPollTimer);
    state.recognitionSessionPollTimer = null;
}

function restoreActiveRecognitionSession() {
    if (!state.activeRecognitionSessionId) {
        return false;
    }
    const session = state.recognitionSessions.find((item) => {
        return item.id === state.activeRecognitionSessionId;
    });
    if (!session) {
        setActiveRecognitionSessionId(null);
        return false;
    }
    activateRecognitionSession(session);
    return true;
}

function resetRecognitionResultState() {
    state.recognitionCells = [];
    state.recognitionEditing = false;
    state.recognizedBoxName = "";
    state.recognizedBoxReadableId = "";
    state.recognizedTemplate = null;
    state.matchedTemplateId = null;
    state.lastRecognition = null;
    setDraftFieldValue("#recognized-box-name", "");
    setDraftFieldValue("#recognized-box-readable-id", "");
    setDraftFieldValue("#recognized-template-name", "");
    setDraftFieldValue("#recognized-template-rows", "1");
    setDraftFieldValue("#recognized-template-cols", "1");
    setDraftFieldValue("#recognized-template-layout-json", "");
    updateRecognitionEditButton();
    updateRecognizedFieldsVisibility();
}

function discardRecognitionResult(message) {
    clearRecognitionDraft();
    resetRecognitionResultState();
    q("#recognition-summary").textContent = "暂无结果";
    q("#ai-result-viewer").innerHTML = `<div class="empty-panel">${escapeHtml(message)}</div>`;
}

function clearRecognitionDraft() {
    removeLocalStorageItem(RECOGNITION_DRAFT_STORAGE_KEY);
}

function saveRecognitionDraftIfAvailable() {
    if (!state.recognitionCells.length) {
        return;
    }
    saveRecognitionDraftFromCurrentState();
}

function saveRecognitionDraftFromCurrentState() {
    const draft = buildRecognitionDraftFromCurrentState();
    if (!draft) {
        return false;
    }
    return writeLocalStorageJson(RECOGNITION_DRAFT_STORAGE_KEY, draft);
}

function buildRecognitionDraftFromCurrentState() {
    const cells = getRecognitionDraftCells();
    if (!cells.length) {
        return null;
    }
    const mode = q("#recognition-mode")?.value || state.recognitionMode || "existing_box";
    const recognizedTemplate = mode === "auto_template_box"
        ? readRecognitionDraftTemplate()
        : state.recognizedTemplate;
    return {
        version: RECOGNITION_DRAFT_VERSION,
        username: state.currentUser?.username || "",
        updated_at: new Date().toISOString(),
        mode,
        box_id: q("#recognition-box-id")?.value || "",
        template_id: q("#recognition-template-id")?.value || "",
        layout_type: q("#recognition-layout-type")?.value || "grid",
        overwrite_existing: Boolean(q("#recognition-overwrite-existing")?.checked),
        additional_prompt: q("#recognition-prompt")?.value || "",
        search_provider_config_id: q("#verification-search-provider-id")?.value || "",
        recognized_box_name: q("#recognized-box-name")?.value.trim() || state.recognizedBoxName || "",
        recognized_box_readable_id: q("#recognized-box-readable-id")?.value.trim()
            || state.recognizedBoxReadableId
            || "",
        recognized_template: recognizedTemplate,
        recognized_template_form: readRecognitionDraftTemplateForm(),
        matched_template_id: state.matchedTemplateId || null,
        last_recognition: state.lastRecognition
            ? {
                filename: state.lastRecognition.filename || "",
                latency_ms: state.lastRecognition.latency_ms ?? null,
                config_id: state.lastRecognition.config_id ?? null,
                content_type: state.lastRecognition.content_type || "",
            }
            : null,
        cells,
    };
}

function getRecognitionDraftCells() {
    if (state.recognitionEditing) {
        try {
            return syncRecognitionCellsFromEditor().map((cell, index) => {
                return normalizeRecognitionCell(cell, index);
            });
        } catch {
            return state.recognitionCells.map((cell, index) => normalizeRecognitionCell(cell, index));
        }
    }
    syncDisplayVerificationSelection();
    return state.recognitionCells.map((cell, index) => normalizeRecognitionCell(cell, index));
}

function readRecognitionDraftTemplate() {
    try {
        return readRecognizedTemplateFields();
    } catch {
        return state.recognizedTemplate;
    }
}

function readRecognitionDraftTemplateForm() {
    return {
        name: q("#recognized-template-name")?.value || "",
        rows: q("#recognized-template-rows")?.value || "",
        cols: q("#recognized-template-cols")?.value || "",
        layout_json: q("#recognized-template-layout-json")?.value || "",
    };
}

function restoreRecognitionDraft() {
    const draft = readLocalStorageJson(RECOGNITION_DRAFT_STORAGE_KEY);
    if (!isRestorableRecognitionDraft(draft)) {
        return false;
    }

    const mode = normalizeRecognitionDraftMode(draft.mode);
    q("#recognition-mode").value = mode;
    state.recognitionMode = mode;
    setDraftFieldValue("#recognition-box-id", draft.box_id);
    setDraftFieldValue("#recognition-template-id", draft.template_id);
    setDraftFieldValue("#recognition-layout-type", draft.layout_type || "grid");
    if (q("#recognition-overwrite-existing")) {
        q("#recognition-overwrite-existing").checked = Boolean(draft.overwrite_existing);
    }
    setDraftFieldValue("#recognition-prompt", draft.additional_prompt);
    setDraftFieldValue("#verification-search-provider-id", draft.search_provider_config_id);

    state.recognizedBoxName = draft.recognized_box_name || "";
    state.recognizedBoxReadableId = draft.recognized_box_readable_id || "";
    setDraftFieldValue("#recognized-box-name", state.recognizedBoxName);
    setDraftFieldValue("#recognized-box-readable-id", state.recognizedBoxReadableId);
    state.recognizedTemplate = mode === "auto_template_box"
        ? normalizeRecognitionDraftTemplate(draft)
        : null;
    state.matchedTemplateId = draft.matched_template_id || null;
    state.lastRecognition = draft.last_recognition || null;
    state.recognitionEditing = false;
    state.recognitionCells = draft.cells.map((cell, index) => normalizeRecognitionCell(cell, index));

    if (state.recognizedTemplate) {
        fillRecognizedTemplateFields(state.recognizedTemplate);
    } else {
        applyRecognitionDraftTemplateForm(draft.recognized_template_form);
    }

    updateRecognitionModeFields();
    updateRecognitionEditButton();
    updateRecognizedFieldsVisibility();
    renderRecognitionCards();
    renderRecognitionDraftSummary(draft);
    return true;
}

function isRestorableRecognitionDraft(draft) {
    if (!draft || draft.version !== RECOGNITION_DRAFT_VERSION || !Array.isArray(draft.cells)) {
        return false;
    }
    if (!draft.cells.length) {
        return false;
    }
    const draftUsername = String(draft.username || "");
    const currentUsername = String(state.currentUser?.username || "");
    return !draftUsername || !currentUsername || draftUsername === currentUsername;
}

function normalizeRecognitionDraftMode(mode) {
    return ["existing_box", "new_box", "auto_template_box"].includes(mode)
        ? mode
        : "existing_box";
}

function normalizeRecognitionDraftTemplate(draft) {
    if (draft.recognized_template?.layout_type) {
        return draft.recognized_template;
    }
    const form = draft.recognized_template_form || {};
    const layoutType = draft.layout_type === "irregular" ? "irregular" : "grid";
    if (layoutType === "grid") {
        const rows = Number(form.rows || 1);
        const cols = Number(form.cols || 1);
        return {
            name: form.name || buildStructureTemplateName("grid", {rows, cols}),
            layout_type: "grid",
            layout_definition: {rows, cols},
        };
    }
    let layoutDefinition = [];
    try {
        layoutDefinition = parseIrregularLayout(form.layout_json || "");
    } catch {
        layoutDefinition = [];
    }
    return {
        name: form.name || buildStructureTemplateName("irregular", layoutDefinition),
        layout_type: "irregular",
        layout_definition: layoutDefinition,
    };
}

function applyRecognitionDraftTemplateForm(form = {}) {
    setDraftFieldValue("#recognized-template-name", form.name);
    setDraftFieldValue("#recognized-template-rows", form.rows || 1);
    setDraftFieldValue("#recognized-template-cols", form.cols || 1);
    setDraftFieldValue("#recognized-template-layout-json", form.layout_json);
}

function setDraftFieldValue(selector, value) {
    const element = q(selector);
    if (!element || value === undefined || value === null) {
        return;
    }
    element.value = String(value);
}

function renderRecognitionDraftSummary(draft) {
    const updatedAt = draft.updated_at ? new Date(draft.updated_at) : null;
    const updatedText = updatedAt && !Number.isNaN(updatedAt.getTime())
        ? updatedAt.toLocaleString()
        : "上次";
    const filename = draft.last_recognition?.filename
        ? `${draft.last_recognition.filename} · `
        : "";
    q("#recognition-summary").textContent = `${filename}已恢复未入库结果 · ${updatedText}`;
}

function updateRecognitionModeFields() {
    const mode = q("#recognition-mode").value;
    q("#recognition-box-line").classList.toggle("hidden", mode !== "existing_box");
    q("#recognition-template-line").classList.toggle("hidden", mode !== "new_box");
    q("#recognition-layout-line").classList.toggle("hidden", mode !== "auto_template_box");
    q("#recognition-overwrite-line").classList.toggle("hidden", mode !== "existing_box");
    state.recognitionMode = mode;
    updateRecognizedFieldsVisibility();
}

function updateRecognizedFieldsVisibility() {
    const mode = q("#recognition-mode").value;
    const hasRecognition = state.recognitionCells.length > 0;
    const showsBoxFields = hasRecognition && ["new_box", "auto_template_box"].includes(mode);
    const showsTemplateFields = hasRecognition && mode === "auto_template_box";
    q("#recognized-info-panel").classList.toggle(
        "hidden",
        !showsBoxFields && !showsTemplateFields,
    );
    q("#recognized-box-fields").classList.toggle(
        "hidden",
        !showsBoxFields,
    );
    q("#recognized-template-fields").classList.toggle(
        "hidden",
        !showsTemplateFields,
    );
}

function updateRecognitionEditButton() {
    q("#recognition-edit-toggle").textContent = state.recognitionEditing ? "退出编辑" : "编辑";
}

function toggleRecognitionEditMode() {
    const shouldEdit = !state.recognitionEditing;
    if (shouldEdit && !state.recognitionEditing) {
        syncDisplayVerificationSelection();
    }
    if (!shouldEdit && state.recognitionEditing) {
        syncRecognitionCellsFromEditor();
    }
    state.recognitionEditing = shouldEdit;
    updateRecognitionEditButton();
    if (state.recognitionCells.length) {
        renderRecognitionCards();
    }
    saveRecognitionDraftIfAvailable();
}

function renderRecognitionResult(result) {
    state.lastRecognition = result;
    state.recognitionMode = q("#recognition-mode").value;
    state.recognitionEditing = false;
    updateRecognitionEditButton();
    const parsed = result.parsed_result;
    if (!parsed) {
        setRecognitionStatus("模型返回内容无法解析。", true);
        return;
    }

    state.recognizedBoxName = sanitizeBoxDisplayName(parsed.box_name || "");
    state.recognizedBoxReadableId = parsed.box_readable_id || "";
    q("#recognized-box-name").value = state.recognizedBoxName;
    q("#recognized-box-readable-id").value = state.recognizedBoxReadableId;
    if (state.recognitionMode === "auto_template_box") {
        state.recognizedTemplate = normalizeRecognizedTemplate(parsed);
        fillRecognizedTemplateFields(state.recognizedTemplate);
    } else {
        state.recognizedTemplate = null;
    }
    state.recognitionCells = prepareRecognitionCellsFromParsed(parsed);
    q("#recognition-summary").textContent = `${result.filename} · ${result.latency_ms}ms`;
    maybeReuseExistingTemplate();
    updateRecognizedFieldsVisibility();
    renderRecognitionCards();
    saveRecognitionDraftFromCurrentState();
}

function maybeReuseExistingTemplate() {
    if (state.recognitionMode !== "auto_template_box" || !state.recognizedTemplate) {
        state.matchedTemplateId = null;
        return;
    }
    const matchedTemplate = findMatchingTemplate(state.recognizedTemplate);
    state.matchedTemplateId = matchedTemplate?.id || null;
    if (!matchedTemplate) {
        return;
    }
    const useExisting = window.confirm(
        `检测到已有模板“${matchedTemplate.name}”与本次识别布局相同。\n`
        + "点击“确定”使用已有模板；点击“取消”仍新建模板。",
    );
    if (!useExisting) {
        return;
    }
    q("#recognition-mode").value = "new_box";
    state.recognitionMode = "new_box";
    updateRecognitionModeFields();
    q("#recognition-template-id").value = String(matchedTemplate.id);
    state.recognizedTemplate = null;
    showToast(`已切换为使用已有模板：${matchedTemplate.name}`);
}

function findMatchingTemplate(template) {
    return state.templates.find((candidate) => {
        return areTemplateLayoutsEquivalent(candidate, template);
    }) || null;
}

function areTemplateLayoutsEquivalent(left, right) {
    if (!left || !right || left.layout_type !== right.layout_type) {
        return false;
    }
    if (left.layout_type === "grid") {
        return Number(left.layout_definition?.rows || 0) === Number(right.layout_definition?.rows || 0)
            && Number(left.layout_definition?.cols || 0) === Number(right.layout_definition?.cols || 0);
    }
    const leftCells = getLayoutCells(left.layout_definition).map(normalizeLayoutSignatureCell);
    const rightCells = getLayoutCells(right.layout_definition).map(normalizeLayoutSignatureCell);
    if (leftCells.length !== rightCells.length) {
        return false;
    }
    leftCells.sort(compareSignatureCells);
    rightCells.sort(compareSignatureCells);
    return JSON.stringify(leftCells) === JSON.stringify(rightCells);
}

function normalizeLayoutSignatureCell(cell) {
    return {
        row: Number(cell.row || 0),
        col: Number(cell.col || cell.column || 0),
        row_span: Number(cell.row_span || cell.rowSpan || 1),
        col_span: Number(cell.col_span || cell.column_span || cell.colSpan || 1),
        orientation: isPortraitOrientation(cell.orientation) ? "portrait" : "landscape",
    };
}

function compareSignatureCells(left, right) {
    return left.row - right.row
        || left.col - right.col
        || left.row_span - right.row_span
        || left.col_span - right.col_span
        || left.orientation.localeCompare(right.orientation);
}

function prepareRecognitionCellsFromParsed(parsed) {
    const rawCells = Array.isArray(parsed.cells) ? parsed.cells : [];
    if (
        state.recognitionMode === "auto_template_box"
        && state.recognizedTemplate?.layout_type === "irregular"
    ) {
        const layoutCells = getLayoutCells(state.recognizedTemplate.layout_definition);
        if (layoutCells.length) {
            return layoutCells.map((layoutCell, index) => {
                const rawCell = findRecognitionCellForLayout(rawCells, layoutCell, index);
                return normalizeRecognitionCell(
                    {
                        ...(rawCell || {is_empty: true}),
                        position_identifier: getLayoutCellPosition(layoutCell),
                    },
                    index,
                );
            });
        }
    }
    const cells = rawCells.length ? rawCells : [{...parsed, position_identifier: "单图"}];
    return cells.map((cell, index) => normalizeRecognitionCell(cell, index));
}

function findRecognitionCellForLayout(rawCells, layoutCell, index) {
    const candidates = [
        layoutCell.source_id,
        layoutCell.source_position,
        layoutCell.original_id,
        getLayoutCellPosition(layoutCell),
    ].filter(Boolean).map((item) => String(item));
    return rawCells.find((cell) => {
        const position = String(cell.position_identifier || cell.id || cell.label || "");
        return candidates.includes(position);
    }) || rawCells[index] || null;
}

function normalizeRecognitionCell(cell, index) {
    const warning = cell.verification_warning || extractVerificationWarning(cell.notes || "");
    const normalized = {
        position_identifier: cell.position_identifier || cell.id || `#${index + 1}`,
        is_empty: Boolean(cell.is_empty),
        name: cell.name || "",
        tags: Array.isArray(cell.tags) ? cell.tags : [],
        attributes: cell.attributes && typeof cell.attributes === "object" ? cell.attributes : {},
        display_attribute: cell.display_attribute || "",
        confidence: cell.confidence ?? null,
        notes: stripVerificationPhrases(cell.notes || ""),
        verification_warning: warning,
        stock_mode: cell.stock_mode || "fuzzy",
        quantity_exact: cell.quantity_exact ?? null,
        quantity_fuzzy: cell.quantity_fuzzy || "未知",
    };
    normalized.verify_selected = cell.verify_selected ?? shouldVerifyCell(normalized);
    return normalized;
}

function renderRecognitionCards() {
    const viewer = q("#ai-result-viewer");
    viewer.innerHTML = "";
    const template = getRecognitionTemplate();
    const isGrid = template?.layout_type === "grid";
    const isIrregular = template?.layout_type === "irregular";
    const useIrregularMap = isIrregular;
    const rows = Number(template?.layout_definition?.rows || 0);
    const cols = Number(template?.layout_definition?.cols || 0);
    const layoutCells = isIrregular ? getLayoutCells(template.layout_definition) : [];
    const layoutCellsByPosition = new Map(
        layoutCells.map((cell) => [getLayoutCellPosition(cell), cell]),
    );
    const positions = buildRecognitionPositions(isGrid, rows, cols, template);
    const cellsByPosition = new Map(
        state.recognitionCells.map((cell, index) => [
            String(cell.position_identifier || index),
            {...cell, _index: index},
        ]),
    );
    const grid = document.createElement("div");
    grid.className = `recognition-grid ${state.recognitionEditing ? "editing" : "displaying"}`;
    if (useIrregularMap) {
        grid.classList.add("irregular-map");
    }
    if (useIrregularMap) {
        const displayCols = getIrregularColumnCount(template?.layout_definition, state.recognitionCells.length);
        grid.style.gridTemplateColumns = `repeat(${displayCols}, minmax(132px, 1fr))`;
    } else {
        const displayCols = isGrid && cols > 0 ? cols : Math.min(Math.max(state.recognitionCells.length, 1), 4);
        grid.style.gridTemplateColumns = `repeat(${displayCols}, minmax(132px, 1fr))`;
    }
    if (useIrregularMap) {
        const baseCellHeight = state.recognitionEditing ? 260 : 132;
        applyIrregularGridRows(
            grid,
            template?.layout_definition,
            state.recognitionCells.length,
            baseCellHeight,
        );
    }
    const renderedCells = [];
    positions.forEach((position, fallbackIndex) => {
        const cell = cellsByPosition.get(position) || normalizeRecognitionCell({
            position_identifier: position,
            is_empty: true,
            name: "",
            tags: [],
            attributes: {},
            display_attribute: "",
            quantity_fuzzy: "未知",
        }, state.recognitionCells.length + fallbackIndex);
        renderedCells.push(cell);
        const card = createRecognitionCard(
            cell,
            useIrregularMap ? layoutCellsByPosition.get(position) : null,
        );
        grid.append(card);
    });
    state.recognitionCells = renderedCells;
    viewer.append(grid);
}

function buildRecognitionPositions(isGrid, rows, cols, template) {
    if (isGrid && rows > 0 && cols > 0) {
        const positions = [];
        for (let row = 1; row <= rows; row += 1) {
            for (let col = 1; col <= cols; col += 1) {
                positions.push(`R${row}C${col}`);
            }
        }
        return positions;
    }
    if (template?.layout_type === "irregular") {
        const positions = getLayoutCells(template.layout_definition)
            .map((cell) => getLayoutCellPosition(cell))
            .filter(Boolean);
        if (positions.length) {
            return positions;
        }
    }
    return state.recognitionCells.map((cell, index) => cell.position_identifier || `#${index + 1}`);
}

function getSelectedRecognitionBox() {
    const boxId = Number(q("#recognition-box-id").value);
    return state.boxes.find((box) => box.id === boxId);
}

function getRecognitionTemplate() {
    if (state.recognitionMode === "existing_box") {
        const box = getSelectedRecognitionBox();
        return state.templates.find((item) => item.id === box?.template_id);
    }
    if (state.recognitionMode === "new_box") {
        const templateId = Number(q("#recognition-template-id").value);
        return state.templates.find((item) => item.id === templateId);
    }
    if (state.recognitionMode === "auto_template_box") {
        return readRecognizedTemplateFields();
    }
    return null;
}

function createRecognitionCard(cell, layoutCell = null) {
    const card = document.createElement("article");
    card.className = `recognition-card ${cell.is_empty ? "empty" : ""}`;
    card.dataset.position = cell.position_identifier || "";
    card.innerHTML = state.recognitionEditing
        ? createRecognitionEditHtml(cell)
        : createRecognitionDisplayHtml(cell);
    applyLayoutCellPlacement(card, layoutCell);
    return card;
}

function createRecognitionDisplayHtml(cell) {
    const quantityText = getCellQuantityText(cell);
    const displayTitle = getRecognitionCellDisplayTitle(cell);
    const tagsHtml = renderTagChips(cell.tags || []);
    const attributesHtml = renderAttributesView(cell.attributes || {});
    const warningHtml = cell.verification_warning
        ? `<p class="warning-line">${escapeHtml(cell.verification_warning)}</p>`
        : "";
    return `
        <div class="card-head">
            <span class="position-pill">${escapeHtml(cell.position_identifier || "单图")}</span>
            <label class="verify-check" title="勾选后可联网搜索核对">
                <input data-field="verify_selected" type="checkbox" aria-label="联网搜索核对" ${cell.verify_selected ? "checked" : ""}>
            </label>
        </div>
        <div class="display-name" title="${escapeHtml(cell.name || "")}">${escapeHtml(displayTitle)}</div>
        <div class="chip-row">${tagsHtml || '<span class="muted-text">无标签</span>'}</div>
        <div class="attribute-grid">${attributesHtml || '<span class="muted-text">无结构化属性</span>'}</div>
        <div class="meta-line">${escapeHtml(quantityText)}${cell.confidence ? ` · 置信度 ${escapeHtml(cell.confidence)}` : ""}</div>
        ${cell.notes ? `<p class="note-line">${escapeHtml(cell.notes)}</p>` : ""}
        ${warningHtml}
    `;
}

function getRecognitionCellDisplayTitle(cell) {
    if (cell.is_empty) {
        return "空格";
    }
    return getAttributeDisplayText(cell.attributes || {}, cell.display_attribute || "")
        || cell.name
        || "未命名";
}

function createRecognitionEditHtml(cell) {
    const tagsText = (cell.tags || []).join(", ");
    const quantityValue = cell.stock_mode === "exact" ? "custom" : (cell.quantity_fuzzy || "未知");
    const exactValue = cell.quantity_exact ?? "";
    return `
        <div class="card-head">
            <span class="position-pill">${escapeHtml(cell.position_identifier || "单图")}</span>
            <label class="verify-check" title="勾选后可联网搜索核对">
                <input data-field="verify_selected" type="checkbox" aria-label="联网搜索核对" ${cell.verify_selected ? "checked" : ""}>
            </label>
        </div>
        <label>名称<input data-field="name" type="text" value="${escapeHtml(cell.name || "")}"></label>
        <label>标签<input data-field="tags" type="text" value="${escapeHtml(tagsText)}" placeholder="IC/电源芯片, 贴片"></label>
        <div class="attribute-editor" data-role="attribute-editor">
            <div class="editor-label">属性</div>
            ${renderAttributeEditor(cell.attributes || {})}
            <button class="small-button" type="button" data-action="add-recognition-attribute">添加属性</button>
        </div>
        <div class="quantity-row">
            <label>数量
                <select data-field="quantity_mode">
                    ${STOCK_OPTIONS.map((value) => {
                        return `<option value="${value}" ${quantityValue === value ? "selected" : ""}>${value}</option>`;
                    }).join("")}
                    <option value="custom" ${quantityValue === "custom" ? "selected" : ""}>自定义数量</option>
                </select>
            </label>
            <label class="${quantityValue === "custom" ? "" : "hidden"}" data-role="exact-line">数量
                <input data-field="quantity_exact" type="number" min="0" value="${escapeHtml(exactValue)}">
            </label>
        </div>
        <label>备注<input data-field="notes" type="text" value="${escapeHtml(cell.notes || "")}"></label>
    `;
}

function renderAttributeEditor(attributes) {
    const entries = Object.entries(attributes);
    const rows = entries.length ? entries : [["", ""]];
    return rows.map(([key, value]) => `
        <div class="attribute-row" data-role="attribute-row">
            <input data-field="attribute_key" type="text" value="${escapeHtml(key)}" placeholder="属性名">
            <input data-field="attribute_value" type="text" value="${escapeHtml(value)}" placeholder="属性值">
            <button class="icon-button" type="button" data-action="remove-recognition-attribute">×</button>
        </div>
    `).join("");
}

function addAttributeEditorRow(target) {
    const editor = target.closest(".attribute-editor");
    const rows = editor?.querySelector('[data-role="attribute-rows"]');
    if (rows) {
        rows.insertAdjacentHTML("beforeend", renderAttributeEditor({"": ""}));
        return;
    }
    target.insertAdjacentHTML("beforebegin", renderAttributeEditor({"": ""}));
}

function renderTagChips(tags) {
    return tags.map((tag) => {
        return `<span class="tag-chip ${getTagToneClass(tag)}">${escapeHtml(tag)}</span>`;
    }).join("");
}

function renderBoxCategorySummary(box) {
    const summary = Array.isArray(box?.category_summary) ? box.category_summary : [];
    if (!summary.length) {
        return "";
    }
    return `<div class="chip-row category-chip-row">${renderTagChips(summary)}</div>`;
}

function renderReprintBadge(box) {
    if (!box || !box.label_needs_reprint) {
        return "";
    }
    return '<span class="reprint-badge" title="盒内内容已变化，建议重新打印标签">待重打印</span>';
}

function renderAttributesView(attributes) {
    return Object.entries(attributes).map(([key, value]) => `
        <div class="attribute-pill">
            <span>${escapeHtml(key)}:</span>
            <strong>${escapeHtml(value)}</strong>
        </div>
    `).join("");
}

function getTagToneClass(tag) {
    const tones = ["tone-a", "tone-b", "tone-c", "tone-d", "tone-e"];
    const hash = Array.from(String(tag)).reduce((sum, char) => sum + char.charCodeAt(0), 0);
    return tones[hash % tones.length];
}

function getCellQuantityText(cell) {
    if (cell.stock_mode === "exact") {
        return `数量 ${cell.quantity_exact ?? 0}`;
    }
    return `数量 ${cell.quantity_fuzzy || "未知"}`;
}

function getInventoryQuantityText(item) {
    if (item.stock_mode === "exact") {
        return `数量 ${item.quantity_exact ?? 0}`;
    }
    return `数量 ${item.quantity_fuzzy || "未知"}`;
}

function collectRecognitionCells() {
    if (!state.recognitionEditing) {
        syncDisplayVerificationSelection();
        return state.recognitionCells.map((cell, index) => normalizeRecognitionCell(cell, index));
    }
    return syncRecognitionCellsFromEditor();
}

function syncDisplayVerificationSelection() {
    qa(".recognition-card").forEach((card) => {
        const cell = state.recognitionCells.find((item) => item.position_identifier === card.dataset.position);
        const checkbox = card.querySelector('[data-field="verify_selected"]');
        if (cell && checkbox) {
            cell.verify_selected = checkbox.checked;
        }
    });
}

function syncRecognitionCellsFromEditor() {
    state.recognitionCells = qa(".recognition-card").map((card, index) => {
        const quantityMode = card.querySelector('[data-field="quantity_mode"]').value;
        const exactInput = card.querySelector('[data-field="quantity_exact"]');
        const exactValue = Number(exactInput?.value || 0);
        const name = card.querySelector('[data-field="name"]').value.trim();
        const attributes = collectAttributeRows(card);
        const existingCell = state.recognitionCells.find((item) => {
            return item.position_identifier === card.dataset.position;
        });
        return normalizeRecognitionCell({
            position_identifier: card.dataset.position,
            is_empty: !name,
            name: name || null,
            tags: parseList(card.querySelector('[data-field="tags"]').value),
            attributes,
            display_attribute: chooseDisplayAttributeKey(
                attributes,
                existingCell?.display_attribute || "",
            ),
            notes: card.querySelector('[data-field="notes"]').value.trim() || null,
            verification_warning: existingCell?.verification_warning || "",
            stock_mode: quantityMode === "custom" ? "exact" : "fuzzy",
            quantity_exact: quantityMode === "custom" ? exactValue : null,
            quantity_fuzzy: quantityMode === "custom" ? null : quantityMode,
            verify_selected: card.querySelector('[data-field="verify_selected"]')?.checked || false,
        }, index);
    });
    return state.recognitionCells;
}

function collectAttributeRows(card) {
    const attributes = {};
    card.querySelectorAll('[data-role="attribute-row"]').forEach((row) => {
        const key = row.querySelector('[data-field="attribute_key"]').value.trim();
        const value = row.querySelector('[data-field="attribute_value"]').value.trim();
        if (key) {
            attributes[key] = value;
        }
    });
    return attributes;
}

function shouldVerifyCell(cell) {
    if (cell.is_empty || !cell.name) {
        return false;
    }
    const text = `${cell.name} ${(cell.tags || []).join(" ")}`.toLowerCase();
    const simpleTerms = ["电阻", "resistor", "电容", "capacitor", "电感", "连接器", "connector", "螺丝", "screw"];
    if (simpleTerms.some((term) => text.includes(term))) {
        return false;
    }
    const richTerms = [
        "ic",
        "芯片",
        "mcu",
        "mosfet",
        "模块",
        "传感器",
        "sensor",
        "电源芯片",
        "运放",
        "风扇",
        "fan",
        "开关",
        "switch",
        "继电器",
        "电机",
        "motor",
    ];
    return richTerms.some((term) => text.includes(term)) || /[a-z]{2,}\d{2,}/i.test(cell.name);
}

function toggleRecognitionVerification() {
    const cells = collectRecognitionCells();
    const eligibleCells = cells.filter((cell) => !cell.is_empty && cell.name);
    if (!eligibleCells.length) {
        throw new Error("没有可选择的器件");
    }
    const shouldSelect = eligibleCells.some((cell) => !cell.verify_selected);
    state.recognitionCells = cells.map((cell) => {
        if (!cell.is_empty && cell.name) {
            return {...cell, verify_selected: shouldSelect};
        }
        return cell;
    });
    renderRecognitionCards();
    eventTargetToggleText(shouldSelect);
    saveRecognitionDraftFromCurrentState();
}

function eventTargetToggleText(selected) {
    const button = q('[data-action="toggle-recognition-verification"]');
    button.textContent = selected ? "取消全选" : "全选";
}

function parseList(value) {
    return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
}

function parseAttributes(value) {
    const attributes = {};
    value.split(";").map((item) => item.trim()).filter(Boolean).forEach((entry) => {
        const [key, ...rest] = entry.split("=");
        if (key && rest.length) {
            attributes[key.trim()] = rest.join("=").trim();
        }
    });
    return attributes;
}

function serializeAttributes(attributes) {
    return Object.entries(attributes || {}).map(([key, value]) => `${key}=${value}`).join("; ");
}

async function ensureTagIds(tagNames) {
    const ids = [];
    for (const tagName of tagNames) {
        let tag = state.tags.find((item) => item.name === tagName);
        if (!tag) {
            tag = await apiRequest("/tags/", {
                method: "POST",
                body: JSON.stringify({name: tagName, attribute_definitions: []}),
            });
            state.tags.push(tag);
        }
        ids.push(tag.id);
    }
    return ids;
}

function defaultTemplateName() {
    const layoutType = q("#template-layout-type").value;
    const rows = Number(q("#template-rows").value || 1);
    const cols = Number(q("#template-cols").value || 1);
    if (layoutType === "grid") {
        return buildStructureTemplateName("grid", {rows, cols});
    }
    let layoutDefinition = [];
    try {
        layoutDefinition = parseIrregularLayout(q("#template-layout-json").value || "[]");
    } catch {
        layoutDefinition = [];
    }
    return buildStructureTemplateName("irregular", layoutDefinition);
}

function buildStructureTemplateName(layoutType, layoutDefinition) {
    if (layoutType === "grid") {
        const rows = Number(layoutDefinition?.rows || 1);
        const cols = Number(layoutDefinition?.cols || 1);
        return `${cols}x${rows}格`;
    }
    const count = getLayoutCells(layoutDefinition).length || 1;
    return `不规则${count}格`;
}

function sanitizeBoxDisplayName(value) {
    let text = String(value || "").trim();
    if (!text) {
        return "";
    }
    const suffixes = [
        "收纳盒",
        "元器件盒",
        "元件盒",
        "器件盒",
        "零件盒",
        "盒子",
        "盒",
    ];
    let changed = true;
    while (changed) {
        changed = false;
        suffixes.forEach((suffix) => {
            if (text.endsWith(suffix) && text.length > suffix.length) {
                text = text.slice(0, -suffix.length).trim();
                changed = true;
            }
        });
    }
    return text.slice(0, 7);
}

function updateTemplateNameSuggestion(force = false) {
    if (!force && !state.templateNameAuto) {
        return;
    }
    q("#template-name").value = defaultTemplateName();
    state.templateNameAuto = true;
}

function updateTemplateLayoutFieldVisibility(prefix) {
    const layoutTypeControl = q(`#${prefix}-layout-type`);
    const layoutType = layoutTypeControl?.value
        || state.recognizedTemplate?.layout_type
        || q("#recognition-layout-type")?.value
        || "grid";
    q(`#${prefix}-rows-line`).classList.toggle("hidden", layoutType !== "grid");
    q(`#${prefix}-cols-line`).classList.toggle("hidden", layoutType !== "grid");
    q(`#${prefix}-layout-json-line`).classList.toggle("hidden", layoutType === "grid");
}

function readTemplateFormLayout() {
    const layoutType = q("#template-layout-type").value;
    if (layoutType === "grid") {
        return {
            layout_type: layoutType,
            layout_definition: {
                rows: Number(q("#template-rows").value),
                cols: Number(q("#template-cols").value),
            },
        };
    }
    return {
        layout_type: layoutType,
        layout_definition: parseIrregularLayout(q("#template-layout-json").value),
    };
}

function readRecognizedTemplateFields() {
    const layoutType = state.recognizedTemplate?.layout_type
        || q("#recognition-layout-type").value
        || "grid";
    if (layoutType === "grid") {
        const rows = Number(q("#recognized-template-rows").value || 1);
        const cols = Number(q("#recognized-template-cols").value || 1);
        return {
            name: q("#recognized-template-name").value.trim()
                || buildStructureTemplateName("grid", {rows, cols}),
            layout_type: "grid",
            layout_definition: {
                rows,
                cols,
            },
        };
    }
    const layoutDefinition = parseIrregularLayout(q("#recognized-template-layout-json").value);
    return {
        name: q("#recognized-template-name").value.trim()
            || buildStructureTemplateName("irregular", layoutDefinition),
        layout_type: "irregular",
        layout_definition: layoutDefinition,
    };
}

function parseIrregularLayout(value) {
    if (!value.trim()) {
        return [];
    }
    const parsed = JSON.parse(value);
    if (Array.isArray(parsed)) {
        return normalizeIrregularLayoutDefinition(parsed);
    }
    if (Array.isArray(parsed.cells)) {
        return normalizeIrregularLayoutDefinition(parsed);
    }
    throw new Error("不规则布局 JSON 必须是数组，或包含 cells 数组");
}

function normalizeRecognizedTemplate(parsed, preferredLayoutType = q("#recognition-layout-type").value) {
    const layoutType = parsed.layout_type || preferredLayoutType || "grid";
    const rawDefinition = parsed.layout_definition || {};
    if (layoutType === "grid") {
        const rows = Number(rawDefinition.rows || parsed.rows || 1);
        const cols = Number(rawDefinition.cols || parsed.cols || 1);
        return {
            name: buildStructureTemplateName("grid", {rows, cols}),
            layout_type: "grid",
            layout_definition: {rows, cols},
        };
    }
    const layoutDefinitionSource = Array.isArray(rawDefinition)
        ? rawDefinition
        : {...rawDefinition, cells: rawDefinition.cells || parsed.cells || []};
    const layoutDefinition = normalizeIrregularLayoutDefinition(layoutDefinitionSource);
    return {
        name: buildStructureTemplateName("irregular", layoutDefinition),
        layout_type: "irregular",
        layout_definition: layoutDefinition,
    };
}

function normalizeIrregularLayoutDefinition(layoutDefinition) {
    const cells = Array.isArray(layoutDefinition)
        ? layoutDefinition
        : layoutDefinition.cells || [];
    const normalizedCells = normalizeIrregularLayoutCells(cells);
    if (Array.isArray(layoutDefinition)) {
        return normalizedCells;
    }
    const normalizedDefinition = {
        ...layoutDefinition,
        cells: normalizedCells,
    };
    normalizedDefinition.cols = getIrregularColumnCount(normalizedDefinition, normalizedCells.length);
    normalizedDefinition.rows = getIrregularRowCount(normalizedDefinition, normalizedCells.length);
    return normalizedDefinition;
}

function normalizeIrregularLayoutCells(cells) {
    const baseCells = cells.map((cell, index) => {
        const fallbackId = `CELL-${String(index + 1).padStart(2, "0")}`;
        const sourceId = cell.id || cell.position_identifier || fallbackId;
        return {
            ...cell,
            source_id: sourceId,
            id: sourceId,
            label: cell.label || cell.position_identifier || sourceId,
            source_index: index,
        };
    });
    const placedCells = inferIrregularCellPlacement(baseCells);
    if (!placedCells.some((cell) => Number(cell.row || 0) > 0 && Number(cell.col || cell.column || 0) > 0)) {
        return placedCells.map((cell) => {
            const cleanCell = {...cell};
            delete cleanCell.source_index;
            return cleanCell;
        });
    }

    const sortedCells = [...placedCells].sort((left, right) => {
        const leftCol = Number(left.col || left.column || 0);
        const rightCol = Number(right.col || right.column || 0);
        const leftRow = Number(left.row || 0);
        const rightRow = Number(right.row || 0);
        return leftCol - rightCol || leftRow - rightRow || left.source_index - right.source_index;
    });
    const columnKeys = [];
    sortedCells.forEach((cell) => {
        const key = String(Number(cell.col || cell.column || 0));
        if (!columnKeys.includes(key)) {
            columnKeys.push(key);
        }
    });
    const rowsByColumn = new Map();
    const normalizedByIndex = new Map();
    sortedCells.forEach((cell) => {
        const columnKey = String(Number(cell.col || cell.column || 0));
        const columnIndex = columnKeys.indexOf(columnKey);
        const rowIndex = (rowsByColumn.get(columnKey) || 0) + 1;
        rowsByColumn.set(columnKey, rowIndex);
        const cleanCell = {...cell};
        const sourceIndex = cleanCell.source_index;
        delete cleanCell.source_index;
        const sourcePosition = String(cleanCell.source_id || cleanCell.id || "");
        const position = parseLayoutPositionCode(sourcePosition)
            ? sourcePosition
            : `${toColumnName(columnIndex)}${rowIndex}`;
        normalizedByIndex.set(sourceIndex, {
            ...cleanCell,
            id: position,
            position_identifier: position,
            label: cleanCell.label || position,
        });
    });
    return placedCells.map((cell) => normalizedByIndex.get(cell.source_index));
}

function inferIrregularCellPlacement(cells) {
    const inferredCells = cells.map((cell) => ({...cell}));
    const parsedEntries = inferredCells.map((cell, index) => ({
        index,
        code: parseLayoutPositionCode(cell.id || cell.position_identifier || cell.source_id),
    }));
    const columnGroups = new Map();
    parsedEntries.forEach((entry) => {
        if (!entry.code) {
            return;
        }
        if (entry.code.type === "grid") {
            const cell = inferredCells[entry.index];
            if (Number(cell.row || 0) <= 0) {
                cell.row = entry.code.row;
            }
            if (Number(cell.col || cell.column || 0) <= 0) {
                cell.col = entry.code.col;
            }
            return;
        }
        if (!columnGroups.has(entry.code.column_name)) {
            columnGroups.set(entry.code.column_name, []);
        }
        columnGroups.get(entry.code.column_name).push(entry);
    });
    const maxGroupSize = Math.max(
        0,
        ...Array.from(columnGroups.values()).map((entries) => entries.length),
    );
    const groupLayouts = new Map();
    const portraitRowCounts = [];
    columnGroups.forEach((entries, columnName) => {
        const sortedEntries = [...entries].sort((left, right) => {
            return left.code.row - right.code.row || left.index - right.index;
        });
        const allPortrait = sortedEntries.every((entry) => {
            return isPortraitOrientation(inferredCells[entry.index].orientation);
        });
        const splitPortraitGroup = allPortrait
            && sortedEntries.length >= 4
            && sortedEntries.length % 2 === 0
            && maxGroupSize > sortedEntries.length;
        const fillHeightPortraitGroup = allPortrait
            && !splitPortraitGroup
            && sortedEntries.length > 0
            && maxGroupSize > sortedEntries.length;
        const portraitRowCount = splitPortraitGroup
            ? sortedEntries.length / 2
            : (fillHeightPortraitGroup ? sortedEntries.length : 0);
        if (portraitRowCount > 0) {
            portraitRowCounts.push(portraitRowCount);
        }
        groupLayouts.set(columnName, {
            sortedEntries,
            splitPortraitGroup,
            fillHeightPortraitGroup,
            portraitRowCount,
        });
    });
    const totalRowUnits = portraitRowCounts.length
        ? getLeastCommonMultiple([maxGroupSize, ...portraitRowCounts])
        : maxGroupSize;
    const baseRowSpan = maxGroupSize > 0
        ? Math.max(totalRowUnits / maxGroupSize, 1)
        : 1;
    groupLayouts.forEach(({
        sortedEntries,
        splitPortraitGroup,
        fillHeightPortraitGroup,
        portraitRowCount,
    }) => {
        const portraitRowSpan = portraitRowCount > 0
            ? Math.max(totalRowUnits / portraitRowCount, 1)
            : 1;
        sortedEntries.forEach((entry, groupIndex) => {
            const cell = inferredCells[entry.index];
            if (splitPortraitGroup) {
                cell.row = Math.floor(groupIndex / 2) * portraitRowSpan + 1;
                cell.col = entry.code.col + (groupIndex % 2);
                cell.row_span = portraitRowSpan;
                return;
            }
            if (fillHeightPortraitGroup) {
                cell.row = groupIndex * portraitRowSpan + 1;
                cell.col = entry.code.col;
                cell.row_span = portraitRowSpan;
                return;
            }
            if (baseRowSpan > 1) {
                cell.row = (entry.code.row - 1) * baseRowSpan + 1;
                cell.row_span = baseRowSpan;
            } else if (Number(cell.row || 0) <= 0) {
                cell.row = entry.code.row;
            }
            if (Number(cell.col || cell.column || 0) <= 0) {
                cell.col = entry.code.col;
            }
        });
    });
    return inferredCells;
}

function getLeastCommonMultiple(values) {
    return values
        .map((value) => Math.max(Math.trunc(Number(value) || 1), 1))
        .reduce((result, value) => {
            return Math.abs(result * value) / getGreatestCommonDivisor(result, value);
        }, 1);
}

function getGreatestCommonDivisor(left, right) {
    let a = Math.abs(left);
    let b = Math.abs(right);
    while (b > 0) {
        const next = a % b;
        a = b;
        b = next;
    }
    return a || 1;
}

function parseLayoutPositionCode(value) {
    const text = String(value || "").trim();
    const gridMatch = text.match(/^R(\d+)C(\d+)$/i);
    if (gridMatch) {
        return {
            type: "grid",
            row: Number(gridMatch[1]),
            col: Number(gridMatch[2]),
        };
    }
    const columnMatch = text.match(/^([A-Za-z]+)(\d+)$/);
    if (!columnMatch) {
        return null;
    }
    const columnName = columnMatch[1].toUpperCase();
    return {
        type: "column",
        column_name: columnName,
        row: Number(columnMatch[2]),
        col: columnNameToNumber(columnName),
    };
}

function columnNameToNumber(value) {
    return String(value || "").toUpperCase().split("").reduce((sum, char) => {
        const code = char.charCodeAt(0);
        if (code < 65 || code > 90) {
            return sum;
        }
        return sum * 26 + code - 64;
    }, 0);
}

function isPortraitOrientation(value) {
    const orientation = String(value || "").toLowerCase();
    return orientation.includes("90")
        || orientation.includes("vertical")
        || orientation.includes("portrait")
        || orientation.includes("竖");
}

function toColumnName(index) {
    let value = index + 1;
    let name = "";
    while (value > 0) {
        const remainder = (value - 1) % 26;
        name = String.fromCharCode(65 + remainder) + name;
        value = Math.floor((value - 1) / 26);
    }
    return name;
}

function fillRecognizedTemplateFields(template) {
    q("#recognized-template-name").value = template.name || "";
    if (template.layout_type === "grid") {
        q("#recognized-template-rows").value = template.layout_definition?.rows || 1;
        q("#recognized-template-cols").value = template.layout_definition?.cols || 1;
        q("#recognized-template-layout-json").value = "";
    } else {
        q("#recognized-template-rows").value = 1;
        q("#recognized-template-cols").value = 1;
        q("#recognized-template-layout-json").value = JSON.stringify(template.layout_definition || [], null, 2);
    }
    updateTemplateLayoutFieldVisibility("recognized-template");
    renderRecognizedTemplatePreview();
}

function fillTemplateFormFromRecognizedTemplate(template) {
    state.editingTemplateId = null;
    state.templateNameAuto = false;
    q("#template-name").value = template.name || "";
    q("#template-layout-type").value = template.layout_type || "grid";
    if (template.layout_type === "grid") {
        q("#template-rows").value = template.layout_definition?.rows || 1;
        q("#template-cols").value = template.layout_definition?.cols || 1;
        q("#template-layout-json").value = "";
    } else {
        q("#template-rows").value = 1;
        q("#template-cols").value = 1;
        q("#template-layout-json").value = JSON.stringify(template.layout_definition || [], null, 2);
    }
    q("#template-submit-button").textContent = "保存模板";
    updateTemplateLayoutFieldVisibility("template");
    renderTemplateFormPreview();
}

function renderTemplateFormPreview() {
    const preview = q("#template-layout-preview");
    if (!preview) {
        return;
    }
    try {
        renderLayoutPreview(preview, readTemplateFormLayout());
    } catch (error) {
        preview.innerHTML = `<div class="empty-panel compact-empty">${escapeHtml(error.message)}</div>`;
    }
}

function renderRecognizedTemplatePreview() {
    const preview = q("#recognized-template-preview");
    if (!preview) {
        return;
    }
    try {
        renderLayoutPreview(preview, readRecognizedTemplateFields());
    } catch (error) {
        preview.innerHTML = `<div class="empty-panel compact-empty">${escapeHtml(error.message)}</div>`;
    }
}

function renderLayoutPreview(preview, template) {
    preview.innerHTML = "";
    const map = document.createElement("div");
    map.className = "box-map preview-map";
    if (template.layout_type === "grid") {
        const rows = Number(template.layout_definition?.rows || 1);
        const cols = Number(template.layout_definition?.cols || 1);
        map.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
        for (let row = 1; row <= rows; row += 1) {
            for (let col = 1; col <= cols; col += 1) {
                const cell = document.createElement("div");
                cell.className = "box-cell";
                cell.textContent = `R${row}C${col}`;
                map.append(cell);
            }
        }
        preview.append(map);
        return;
    }

    const cells = getLayoutCells(template.layout_definition);
    if (!cells.length) {
        preview.innerHTML = '<div class="empty-panel compact-empty">填写不规则布局 JSON 后显示位置预览。</div>';
        return;
    }
    map.classList.add("irregular-map");
    map.style.gridTemplateColumns = `repeat(${getIrregularColumnCount(template.layout_definition, cells.length)}, minmax(0, 1fr))`;
    applyIrregularGridRows(map, template.layout_definition, cells.length, 44);
    cells.forEach((layoutCell) => {
        const cell = document.createElement("div");
        cell.className = "box-cell";
        cell.textContent = getLayoutCellPosition(layoutCell);
        applyLayoutCellPlacement(cell, layoutCell);
        map.append(cell);
    });
    preview.append(map);
}

function formatLayoutDefinition(template) {
    if (template.layout_type === "grid") {
        const rows = template.layout_definition?.rows || 0;
        const cols = template.layout_definition?.cols || 0;
        return `${cols}列 x ${rows}行`;
    }
    const cells = Array.isArray(template.layout_definition)
        ? template.layout_definition
        : template.layout_definition?.cells || [];
    return `${cells.length} 个格子`;
}

const labelObjectUrls = {svg: "", wdfx: ""};

async function showBoxLabel(boxId) {
    const box = state.boxes.find((item) => item.id === Number(boxId));
    const preview = q("#label-preview");
    const link = q("#label-download-link");
    const altText = box?.readable_id || "Box label";

    if (labelObjectUrls.svg) {
        URL.revokeObjectURL(labelObjectUrls.svg);
        labelObjectUrls.svg = "";
    }
    if (labelObjectUrls.wdfx) {
        URL.revokeObjectURL(labelObjectUrls.wdfx);
        labelObjectUrls.wdfx = "";
    }

    preview.innerHTML = '<div class="empty-panel compact-empty">标签加载中…</div>';
    link.removeAttribute("href");
    link.classList.add("disabled-link");

    try {
        const [svgBlob, wdfxBlob] = await Promise.all([
            apiBlobRequest(`/boxes/${boxId}/label.svg?ts=${Date.now()}`),
            apiBlobRequest(`/boxes/${boxId}/label.wdfx?ts=${Date.now()}`),
        ]);
        labelObjectUrls.svg = URL.createObjectURL(svgBlob);
        labelObjectUrls.wdfx = URL.createObjectURL(
            new Blob([wdfxBlob], {type: "application/octet-stream"}),
        );
        preview.innerHTML = `<img src="${labelObjectUrls.svg}" alt="${escapeHtml(altText)}">`;
        link.href = labelObjectUrls.wdfx;
        link.download = `${box?.readable_id || "box"}-label.wdfx`;
        link.classList.remove("disabled-link");
    } catch (error) {
        preview.innerHTML = `<div class="empty-panel compact-empty">标签加载失败：${escapeHtml(error.message || "未知错误")}</div>`;
    }
}

async function showBoxMap(boxId) {
    const overview = await apiRequest(`/boxes/${boxId}/overview`);
    const cols = getOverviewColumnCount(overview);
    const layoutCellsByPosition = new Map(
        getLayoutCells(overview.template.layout_definition).map((item) => [getLayoutCellPosition(item), item]),
    );
    const map = document.createElement("div");
    map.className = "box-map";
    map.style.gridTemplateColumns = `repeat(${cols}, minmax(0, 1fr))`;
    if (overview.template.layout_type === "irregular") {
        map.classList.add("irregular-map");
        applyIrregularGridRows(
            map,
            overview.template.layout_definition,
            overview.sub_boxes.length,
            44,
        );
    }
    overview.sub_boxes.forEach((subBox) => {
        const cell = document.createElement("div");
        const names = subBox.inventory.map((item) => item.component_name).filter(Boolean);
        cell.className = names.length ? "box-cell filled" : "box-cell";
        cell.textContent = names.length ? names.join(", ") : subBox.position_identifier;
        applyLayoutCellPlacement(cell, layoutCellsByPosition.get(subBox.position_identifier));
        map.append(cell);
    });
    q("#label-preview").innerHTML = "";
    q("#label-preview").append(map);
}

function bindEvents() {
    document.addEventListener("click", handleActionClick);
    qa("[data-view]").forEach((button) => {
        button.addEventListener("click", () => setView(button.dataset.view));
    });
    qa("[data-settings-view]").forEach((button) => {
        button.addEventListener("click", () => setSettingsView(button.dataset.settingsView));
    });
    qa("[data-theme-mode]").forEach((button) => {
        button.addEventListener("click", () => setThemeMode(button.dataset.themeMode));
    });

    q("#recognition-form").addEventListener("submit", uploadRecognition);
    Object.entries(SUBMIT_BUSY_TEXT).forEach(([selector, busyText]) => {
        const form = q(selector);
        const handler = {
            "#template-form": saveTemplate,
            "#box-form": saveBox,
            "#placement-form": savePlacement,
            "#search-form": runSearch,
            "#recommendation-form": runRecommendation,
            "#vlm-form": saveVlmConfig,
            "#search-provider-form": saveSearchProviderConfig,
            "#log-settings-form": saveLogSettings,
            "#server-config-form": saveServerConfig,
            "#login-form": login,
            "#password-form": changePassword,
            "#api-key-form": createApiKey,
            "#tag-form": saveTag,
            "#cell-editor-form": saveCellEditor,
        }[selector];
        if (!form) {
            return;
        }
        form.addEventListener("submit", (event) => handleBusySubmit(event, handler, busyText));
    });

    q("#cell-stock-mode").addEventListener("change", () => {
        q("#cell-exact-line").classList.toggle(
            "hidden",
            q("#cell-stock-mode").value !== "custom",
        );
    });
    q("#cell-component-select").addEventListener("change", fillCellComponentFromSelect);
    q("#placement-stock-mode").addEventListener("change", () => {
        q("#placement-exact-line").classList.toggle(
            "hidden",
            q("#placement-stock-mode").value !== "custom",
        );
    });
    q("#placement-box-id").addEventListener("change", () => {
        renderPlacementSubBoxOptions(Number(q("#placement-box-id").value || 0));
    });
    q("#recognition-mode").addEventListener("change", () => {
        updateRecognitionModeFields();
        saveRecognitionDraftIfAvailable();
    });
    q("#recognized-template-rows").addEventListener("input", () => {
        renderRecognizedTemplatePreview();
        renderRecognitionCards();
        saveRecognitionDraftIfAvailable();
    });
    q("#recognized-template-cols").addEventListener("input", () => {
        renderRecognizedTemplatePreview();
        renderRecognitionCards();
        saveRecognitionDraftIfAvailable();
    });
    q("#ai-result-viewer").addEventListener("change", (event) => {
        const select = event.target.closest('[data-field="quantity_mode"]');
        if (select) {
            const card = select.closest(".recognition-card");
            card.querySelector('[data-role="exact-line"]').classList.toggle(
                "hidden",
                select.value !== "custom",
            );
        }
        saveRecognitionDraftIfAvailable();
    });
    q("#ai-result-viewer").addEventListener("input", () => {
        saveRecognitionDraftIfAvailable();
    });
    [
        "#recognition-box-id",
        "#recognition-template-id",
        "#recognition-layout-type",
        "#recognition-overwrite-existing",
        "#verification-search-provider-id",
    ].forEach((selector) => {
        q(selector).addEventListener("change", saveRecognitionDraftIfAvailable);
    });
    [
        "#recognition-prompt",
        "#recognized-box-name",
        "#recognized-box-readable-id",
        "#recognized-template-name",
        "#recognized-template-layout-json",
    ].forEach((selector) => {
        q(selector).addEventListener("input", saveRecognitionDraftIfAvailable);
    });
    q("#template-name").addEventListener("input", () => {
        state.templateNameAuto = q("#template-name").value.trim() === defaultTemplateName();
    });
    ["#template-rows", "#template-cols", "#template-layout-type"].forEach((selector) => {
        q(selector).addEventListener("input", () => {
            updateTemplateNameSuggestion();
            updateTemplateLayoutFieldVisibility("template");
            renderTemplateFormPreview();
        });
        q(selector).addEventListener("change", () => {
            updateTemplateNameSuggestion();
            updateTemplateLayoutFieldVisibility("template");
            renderTemplateFormPreview();
        });
    });
    q("#template-layout-json").addEventListener("input", () => {
        updateTemplateNameSuggestion();
        renderTemplateFormPreview();
    });
    q("#recognized-template-layout-json").addEventListener("input", () => {
        renderRecognizedTemplatePreview();
        if (state.recognitionCells.length) {
            renderRecognitionCards();
        }
        saveRecognitionDraftIfAvailable();
    });
    ["#manage-query", "#manage-tag-filter", "#manage-attribute-filter"].forEach((selector) => {
        q(selector).addEventListener("input", renderManageView);
        q(selector).addEventListener("change", renderManageView);
    });
    q("#search-provider-type").addEventListener("change", () => {
        updateSearchProviderFieldVisibility();
        clearSearchProviderTestResult();
    });
    q("#server-https-enabled").addEventListener("change", () => {
        updateServerHttpsVisibility();
    });
    q("#server-ssl-cert-upload").addEventListener("change", handleServerCertificateUpload);
    q("#server-ssl-key-upload").addEventListener("change", handleServerKeyUpload);
    ["#new-password", "#confirm-password"].forEach((selector) => {
        q(selector).addEventListener("input", updatePasswordMatchWarning);
    });
    q("#recognition-file").addEventListener("change", () => {
        updateImagePreview("#recognition-file", "#recognition-file-preview");
    });
    q("#template-recognition-file").addEventListener("change", () => {
        updateImagePreview("#template-recognition-file", "#template-recognition-file-preview");
    });
}

async function handleActionClick(event) {
    const target = event.target.closest("[data-action]");
    if (!target) {
        return;
    }
    const action = target.dataset.action;
    const id = target.dataset.id;
    const busy = startActionBusy(target, action);
    if (!busy) {
        return;
    }
    try {
        if (action === "refresh-all") {
            await refreshAll();
        }
        if (action === "logout") {
            await logout();
        }
        if (action === "toggle-password-visibility") {
            togglePasswordVisibility(target);
        }
        if (action === "set-server-certificate-source") {
            setServerCertificateSource(target.dataset.certificateSource);
        }
        if (action === "set-server-acme-challenge") {
            setServerAcmeChallengeType(target.dataset.acmeChallenge);
        }
        if (action === "confirm-box-recognition") {
            await confirmBoxRecognition();
        }
        if (action === "verify-selected-components") {
            await verifySelectedComponents();
        }
        if (action === "refresh-recognition-sessions") {
            await refreshRecognitionSessions();
        }
        if (action === "open-recognition-session") {
            await openRecognitionSession(Number(id));
        }
        if (action === "toggle-recognition-verification") {
            toggleRecognitionVerification();
        }
        if (action === "toggle-recognition-edit-mode") {
            toggleRecognitionEditMode();
        }
        if (
            action === "add-recognition-attribute"
            || action === "add-cell-attribute"
        ) {
            addAttributeEditorRow(target);
        }
        if (action === "remove-recognition-attribute") {
            target.closest('[data-role="attribute-row"]')?.remove();
        }
        if (action === "new-component") {
            openComponentEditor(null);
        }
        if (action === "edit-component") {
            openComponentEditor(state.components.find((component) => String(component.id) === id));
        }
        if (action === "place-component") {
            openPlacementModal(Number(id));
        }
        if (action === "delete-component") {
            await deleteEntity(`/components/${id}`, "元器件");
            await refreshAll();
        }
        if (action === "edit-template") {
            fillTemplateForm(state.templates.find((template) => String(template.id) === id));
            setView("boxes");
            scrollToElement("#template-form");
            showToast("模板已载入编辑表单");
        }
        if (action === "delete-template") {
            await deleteEntity(`/box_templates/${id}`, "模板");
            await refreshAll();
        }
        if (action === "clear-template-form") {
            fillTemplateForm(null);
        }
        if (action === "recognize-template-layout") {
            await recognizeTemplateLayout();
        }
        if (action === "edit-box") {
            fillBoxForm(state.boxes.find((box) => String(box.id) === id));
            setView("boxes");
            scrollToElement("#box-form");
            showToast("盒子已载入编辑表单");
        }
        if (action === "delete-box") {
            const deleted = await deleteBoxWithOptions(Number(id));
            if (deleted) {
                await refreshAll();
            }
        }
        if (action === "clear-box-form") {
            fillBoxForm(null);
        }
        if (action === "show-box-label") {
            showBoxLabel(id);
            setView("boxes");
        }
        if (action === "show-box-map") {
            await showBoxMap(id);
            setView("boxes");
        }
        if (action === "set-manage-mode") {
            state.manageMode = target.dataset.mode;
            state.manageSelectionMode = false;
            state.manageSelectedSubBoxIds.clear();
            renderManageView();
        }
        if (action === "select-manage-category") {
            state.selectedManageCategory = target.dataset.category;
            renderManageView();
        }
        if (action === "open-manage-box") {
            await openManageBox(id);
        }
        if (action === "open-cell-editor") {
            openCellEditor(Number(id));
        }
        if (action === "toggle-manage-selection-mode") {
            toggleManageSelectionMode();
        }
        if (action === "toggle-manage-cell-selection") {
            toggleManageCellSelection(Number(id));
        }
        if (action === "toggle-manage-all-selection") {
            toggleManageAllCellSelection();
        }
        if (action === "apply-manage-bulk-stock") {
            await applyManageBulkStock();
        }
        if (action === "close-cell-editor") {
            closeCellEditor();
        }
        if (action === "ai-fill-cell") {
            await aiFillCell();
        }
        if (action === "delete-cell-inventory") {
            await deleteCellInventory();
        }
        if (action === "edit-tag") {
            await fillTagForm(Number(id));
            setSettingsView("tags");
            setView("settings");
        }
        if (action === "clear-tag-form") {
            clearTagForm();
        }
        if (action === "delete-selected-tag") {
            await deleteSelectedTag();
        }
        if (action === "close-placement") {
            closePlacementModal();
        }
        if (action === "load-placement-recommendations") {
            await loadPlacementRecommendations();
        }
        if (action === "use-placement-recommendation") {
            usePlacementRecommendation(Number(id));
        }
        if (action === "create-bulk-box-for-placement") {
            await createBulkBoxForPlacement();
        }
        if (action === "refresh-logs") {
            await refreshLogs();
        }
        if (action === "refresh-api-keys") {
            await refreshApiKeys();
        }
        if (action === "clear-log-view") {
            clearLogView();
        }
        if (action === "clear-database") {
            await clearDatabase();
        }
        if (action === "restart-service") {
            await restartService();
        }
        if (action === "open-box-scanner") {
            await openBoxScanner("manage");
        }
        if (action === "scan-recognition-box") {
            await openBoxScanner("recognition");
        }
        if (action === "close-box-scanner") {
            closeBoxScanner();
        }
        if (action === "use-scanned-box-code") {
            await useScannedBoxCode(q("#box-scanner-code").value);
        }
        if (action === "edit-vlm") {
            fillVlmForm(state.vlmConfigs.find((config) => String(config.id) === id));
        }
        if (action === "edit-search-provider") {
            fillSearchProviderForm(state.searchProviderConfigs.find((config) => String(config.id) === id));
        }
        if (action === "test-search-provider") {
            await testSearchProviderConfig(id);
        }
        if (action === "test-current-search-provider-form") {
            await testCurrentSearchProviderForm();
        }
        if (action === "set-default-search-provider") {
            await apiRequest(`/search/providers/${id}/set_default`, {method: "POST"});
            await refreshSearchProviders();
            qa("#verification-search-provider-id, #cell-search-provider-id").forEach((select) => {
                select.value = id;
            });
            showToast("默认搜索源已切换");
        }
        if (action === "delete-search-provider") {
            await deleteEntity(`/search/providers/${id}`, "搜索源");
            await refreshSearchProviders();
        }
        if (action === "delete-api-key") {
            await deleteApiKey(Number(id));
        }
        if (action === "close-api-key-modal") {
            closeApiKeyCreatedModal();
        }
        if (action === "copy-created-api-key") {
            await copyCreatedApiKey();
        }
        if (action === "clear-search-provider-form") {
            fillSearchProviderForm(null);
        }
        if (action === "test-vlm") {
            await testVlmConfig(id);
        }
        if (action === "test-current-vlm-form") {
            await testCurrentVlmForm();
        }
        if (action === "set-default-vlm") {
            await apiRequest(`/ai/vlm_configs/${id}/set_default`, {method: "POST"});
            await refreshAi();
            showToast("默认供应商已切换");
        }
        if (action === "delete-vlm") {
            await deleteEntity(`/ai/vlm_configs/${id}`, "供应商");
            await refreshAi();
        }
        if (action === "clear-vlm-form") {
            fillVlmForm(null);
        }
        if (action === "seed-default-tags") {
            await apiRequest("/tags/defaults/seed", {method: "POST"});
            await refreshParts();
            showToast("默认标签库已导入");
        }
    } catch (error) {
        showToast(error.message);
    } finally {
        busy.restore();
    }
}

async function deleteEntity(path, label) {
    if (!window.confirm(`确定删除这个${label}？`)) {
        return false;
    }
    await apiRequest(path, {method: "DELETE"});
    showToast(`${label}已删除`);
    return true;
}

async function deleteBoxWithOptions(boxId) {
    const box = state.boxes.find((item) => item.id === boxId);
    const label = box ? `${box.readable_id} ${box.name || ""}`.trim() : `#${boxId}`;
    if (!window.confirm(`确定删除盒子 ${label} 吗？盒内库存位置会一同删除。`)) {
        return false;
    }
    const overview = await apiRequest(`/boxes/${boxId}/overview`);
    const componentIds = new Set();
    overview.sub_boxes.forEach((subBox) => {
        subBox.inventory.forEach((item) => {
            if (item.component_id) {
                componentIds.add(item.component_id);
            }
        });
    });
    const deleteComponents = componentIds.size > 0 && window.confirm(
        `盒内有 ${componentIds.size} 个元器件记录。是否一同删除这些元器件？\n\n`
        + "确定：删除盒子，并删除仅存在于此盒子的元器件记录。\n"
        + "取消：只删除盒子和盒内库存记录。",
    );
    await apiRequest(`/boxes/${boxId}?delete_components=${deleteComponents ? "true" : "false"}`, {
        method: "DELETE",
    });
    if (state.selectedManageBoxId === boxId) {
        state.selectedManageBoxId = null;
        state.selectedBoxOverview = null;
        state.manageSelectedSubBoxIds.clear();
        state.manageSelectionMode = false;
    }
    showToast("盒子已删除");
    return true;
}

async function uploadRecognition(event) {
    event.preventDefault();
    setRecognitionBusy(true);
    setRecognitionStatus("正在上传图片并创建后台识别会话...");
    try {
        const file = q("#recognition-file").files[0];
        if (!file) {
            throw new Error("请选择图片");
        }
        const mode = q("#recognition-mode").value;
        const uploadFile = await prepareRecognitionUploadFile(file, setRecognitionStatus);
        if (uploadFile.compressed) {
            setRecognitionStatus(
                `已压缩图片 ${formatFileSize(uploadFile.originalSize)} -> ${formatFileSize(uploadFile.uploadSize)}，正在创建后台会话...`,
            );
        } else {
            setRecognitionStatus("正在上传图片并创建后台识别会话...");
        }
        const formData = new FormData();
        formData.append("file", uploadFile.file, uploadFile.filename);
        formData.append("mode", mode);
        formData.append("additional_prompt", q("#recognition-prompt").value);
        const searchProviderConfigId = getSelectedSearchProviderConfigId();
        if (searchProviderConfigId) {
            formData.append("search_provider_config_id", String(searchProviderConfigId));
        }
        if (mode === "existing_box") {
            const boxId = q("#recognition-box-id").value;
            if (!boxId) {
                throw new Error("请先选择盒子");
            }
            formData.append("box_id", boxId);
            formData.append("overwrite_existing", q("#recognition-overwrite-existing").checked ? "true" : "false");
        }
        if (mode === "new_box") {
            const templateId = q("#recognition-template-id").value;
            if (!templateId) {
                throw new Error("请先选择盒子模板");
            }
            formData.append("template_id", templateId);
        }
        if (mode === "auto_template_box") {
            formData.append("layout_type", q("#recognition-layout-type").value);
        }
        clearRecognitionDraft();
        resetRecognitionResultState();
        const session = await apiFormRequest(
            "/ai/recognition_sessions",
            formData,
            buildRecognitionNetworkRetryOptions(setRecognitionStatus),
        );
        activateRecognitionSession(session);
        await refreshRecognitionSessions();
        showToast("识别会话已创建，可稍后从历史记录打开");
    } catch (error) {
        setRecognitionStatus(error.message, true);
        showToast(error.message);
    } finally {
        setRecognitionBusy(false);
    }
}

async function confirmBoxRecognition() {
    const mode = q("#recognition-mode").value;
    const cells = collectRecognitionCells();
    if (!cells.length) {
        throw new Error("没有可入库的识别结果");
    }

    let result;
    if (mode === "existing_box") {
        const boxId = Number(q("#recognition-box-id").value);
        if (!boxId) {
            throw new Error("请先选择盒子");
        }
        result = await apiRequest("/ai/box_recognitions/confirm", {
            method: "POST",
            body: JSON.stringify({
                box_id: boxId,
                cells,
                overwrite_existing: q("#recognition-overwrite-existing").checked,
            }),
        });
    }
    if (mode === "new_box") {
        const templateId = Number(q("#recognition-template-id").value);
        if (!templateId) {
            throw new Error("请先选择盒子模板");
        }
        result = await apiRequest("/ai/new_box_recognitions/confirm", {
            method: "POST",
            body: JSON.stringify({
                template_id: templateId,
                box_name: q("#recognized-box-name").value.trim()
                    || state.recognizedBoxName
                    || null,
                readable_id: q("#recognized-box-readable-id").value.trim() || null,
                cells,
            }),
        });
    }
    if (mode === "auto_template_box") {
        const template = readRecognizedTemplateFields();
        result = await apiRequest("/ai/auto_box_recognitions/confirm", {
            method: "POST",
            body: JSON.stringify({
                template_name: template.name,
                layout_type: template.layout_type,
                layout_definition: template.layout_definition,
                physical_dimensions: {},
                box_name: q("#recognized-box-name").value.trim()
                    || state.recognizedBoxName
                    || null,
                readable_id: q("#recognized-box-readable-id").value.trim() || null,
                cells,
            }),
        });
    }
    await refreshAll();
    if (result.box_id) {
        showBoxLabel(result.box_id);
    }
    discardRecognitionResult("本次识别结果已入库。重新上传图片后会生成新的识别结果。");
    setActiveRecognitionSessionId(null);
    state.loadedRecognitionSessionId = null;
    showToast(`已入库：${result.created_inventory_items} 条库存`);
}

async function verifySelectedComponents() {
    const cells = collectRecognitionCells();
    const selectedCells = cells.filter((cell) => cell.verify_selected && !cell.is_empty && cell.name);
    if (!selectedCells.length) {
        throw new Error("请先勾选需要联网搜索的器件");
    }
    showToast(`正在联网搜索 ${selectedCells.length} 个器件并让 AI 核对属性...`);
    const result = await apiRequest("/ai/verify_components", {
        method: "POST",
        body: JSON.stringify({
            items: selectedCells,
            use_web: true,
            search_provider_config_id: getSelectedSearchProviderConfigId(),
            additional_prompt: q("#recognition-prompt").value.trim(),
        }),
    });
    const verifiedByPosition = new Map(
        result.verified_items.map((cell, index) => [
            cell.position_identifier || selectedCells[index]?.position_identifier,
            cell,
        ]),
    );
    state.recognitionCells = cells.map((cell, index) => {
        const verified = verifiedByPosition.get(cell.position_identifier);
        return verified ? normalizeRecognitionCell({...cell, ...verified}, index) : cell;
    });
    renderRecognitionCards();
    saveRecognitionDraftFromCurrentState();
    const errorCount = (result.web_contexts || []).filter((context) => {
        return Array.isArray(context.errors) && context.errors.length > 0;
    }).length;
    if (errorCount) {
        showToast(`AI 核对完成，${errorCount} 个器件搜索异常，详见黄色提示`);
        return;
    }
    showToast(result.web_used ? "AI 核对完成" : "AI 核对完成，未取得网页摘要");
}

async function recognizeTemplateLayout() {
    const file = q("#template-recognition-file").files[0];
    if (!file) {
        throw new Error("请选择模板照片");
    }
    setTemplateRecognitionBusy(true);
    showToast("正在识别模板布局...");
    let wakeLock = null;
    try {
        wakeLock = await requestRecognitionWakeLock();
        const uploadFile = await prepareRecognitionUploadFile(file, showToast);
        if (uploadFile.compressed) {
            showToast(
                `已压缩图片 ${formatFileSize(uploadFile.originalSize)} -> ${formatFileSize(uploadFile.uploadSize)}，正在识别...`,
            );
        }
        const formData = new FormData();
        formData.append("file", uploadFile.file, uploadFile.filename);
        formData.append("layout_type", q("#template-recognition-layout-type").value);
        formData.append("additional_prompt", q("#template-recognition-prompt").value);
        const result = await apiFormRequest(
            "/ai/recognize_box_layout_image",
            formData,
            buildRecognitionNetworkRetryOptions(showToast),
        );
        const parsed = result.parsed_result;
        if (!parsed) {
            throw new Error("模型返回内容无法解析");
        }
        fillTemplateFormFromRecognizedTemplate(
            normalizeRecognizedTemplate(parsed, q("#template-recognition-layout-type").value),
        );
        showToast("模板识别结果已填入表单");
    } finally {
        releaseRecognitionWakeLock(wakeLock);
        setTemplateRecognitionBusy(false);
    }
}

function openComponentEditor(component) {
    state.cellEditor = {
        mode: "component",
        componentId: component?.id || null,
        isNew: !component,
        displayAttribute: component?.display_attribute || "",
    };
    q("#cell-editor-title").textContent = component ? "编辑器件" : "新建器件";
    q("#cell-position-line").classList.add("hidden");
    q("#cell-component-select-line").classList.add("hidden");
    q("#cell-stock-mode-line").classList.add("hidden");
    q("#cell-exact-line").classList.add("hidden");
    q("#cell-inventory-notes-line").classList.add("hidden");
    q('[data-action="delete-cell-inventory"]').classList.add("hidden");
    q("#cell-editor-submit-button").textContent = "保存器件";
    q("#cell-position").value = "器件信息";
    q("#cell-ai-warning").classList.add("hidden");
    q("#cell-ai-warning").textContent = "";
    q("#cell-component-select").value = "";
    fillCellComponentFields(component || null);
    q("#cell-ai-prompt").value = "";
    q("#cell-stock-mode").value = "未知";
    q("#cell-quantity-exact").value = 1;
    q("#cell-inventory-notes").value = "";
    q("#cell-editor-modal").classList.remove("hidden");
    q("#cell-component-name").focus();
}

function openPlacementModal(componentId) {
    const component = state.components.find((item) => item.id === componentId);
    if (!component) {
        throw new Error("未找到要入库的器件");
    }
    state.placement = {
        componentId,
        selectedSubBoxId: null,
    };
    q("#placement-component-name").value = component.name;
    q("#placement-stock-mode").value = "充足";
    q("#placement-quantity-exact").value = 1;
    q("#placement-notes").value = "";
    q("#placement-new-bulk-name").value = "";
    q("#placement-exact-line").classList.add("hidden");
    q("#placement-recommendations").innerHTML = '<div class="empty-panel compact-empty">点击推荐后显示空位建议。</div>';
    renderPlacementSelectors();
    q("#placement-modal").classList.remove("hidden");
}

function closePlacementModal() {
    state.placement = {
        componentId: null,
        selectedSubBoxId: null,
    };
    q("#placement-modal").classList.add("hidden");
}

async function openBoxScanner(mode) {
    state.scanner.mode = mode;
    q("#box-scanner-title").textContent = mode === "recognition"
        ? "扫码选择盒子"
        : "扫码进入盒子";
    q("#box-scanner-code").value = "";
    q("#box-scanner-status").textContent = "";
    q("#box-scanner-status").classList.add("hidden");
    q("#box-scanner-modal").classList.remove("hidden");
    await startBoxScanner();
}

async function startBoxScanner() {
    if (!navigator.mediaDevices?.getUserMedia) {
        setScannerStatus("当前页面无法调用摄像头。请使用 localhost 或 HTTPS 打开，或手动输入盒子编号。");
        return;
    }
    try {
        state.scanner.stream = await openScannerVideoStream();
        const video = q("#box-scanner-video");
        video.srcObject = state.scanner.stream;
        await video.play();
        if (!("BarcodeDetector" in window)) {
            state.scanner.serverDecode = true;
            state.scanner.timer = window.setInterval(decodeBoxCodeFrameViaServer, 900);
            return;
        }
        const requestedFormats = ["data_matrix", "qr_code"];
        const supportedFormats = typeof window.BarcodeDetector.getSupportedFormats === "function"
            ? await window.BarcodeDetector.getSupportedFormats()
            : requestedFormats;
        const formats = requestedFormats.filter((format) => supportedFormats.includes(format));
        state.scanner.detector = formats.length
            ? new window.BarcodeDetector({formats})
            : new window.BarcodeDetector();
        state.scanner.serverDecode = false;
        state.scanner.timer = window.setInterval(detectBoxCodeFrame, 600);
    } catch (error) {
        let message = `无法启动扫码：${error.message}`;
        if (!window.isSecureContext && !isLocalhost()) {
            message = "手机浏览器通过局域网访问时必须使用 HTTPS 才能调用摄像头。请使用 HTTPS 地址打开，或手动输入盒子编号。";
        } else if (error.name === "NotAllowedError") {
            message = "浏览器拒绝了摄像头权限，请允许摄像头后重试，或手动输入盒子编号。";
        }
        setScannerStatus(message);
    }
}

function isLocalhost() {
    return ["localhost", "127.0.0.1", "::1"].includes(window.location.hostname);
}

async function openScannerVideoStream() {
    const preferredConstraints = {
        video: {
            facingMode: {ideal: "environment"},
            width: {ideal: 1280, max: 1280},
            height: {ideal: 960, max: 960},
            aspectRatio: {ideal: 1.333333},
            advanced: [{zoom: 2}],
        },
    };
    try {
        const stream = await navigator.mediaDevices.getUserMedia(preferredConstraints);
        await applyScannerZoom(stream, 2);
        return stream;
    } catch (error) {
        if (error.name !== "OverconstrainedError") {
            throw error;
        }
        const stream = await navigator.mediaDevices.getUserMedia({
            video: {facingMode: {ideal: "environment"}},
        });
        await applyScannerZoom(stream, 2);
        return stream;
    }
}

async function applyScannerZoom(stream, zoomLevel) {
    const track = stream.getVideoTracks()[0];
    if (!track || typeof track.getCapabilities !== "function" || typeof track.applyConstraints !== "function") {
        return;
    }
    const capabilities = track.getCapabilities();
    if (!("zoom" in capabilities)) {
        return;
    }
    const zoom = Math.min(
        capabilities.max,
        Math.max(capabilities.min, zoomLevel),
    );
    await track.applyConstraints({advanced: [{zoom}]});
}

async function detectBoxCodeFrame() {
    if (state.scanner.busy || !state.scanner.detector) {
        return;
    }
    const video = q("#box-scanner-video");
    if (!video.videoWidth || !video.videoHeight) {
        return;
    }
    state.scanner.busy = true;
    try {
        const barcodes = await state.scanner.detector.detect(video);
        if (barcodes.length) {
            await useScannedBoxCode(barcodes[0].rawValue || "");
        }
    } catch (error) {
        setScannerStatus(`扫码失败：${error.message}`);
    } finally {
        state.scanner.busy = false;
    }
}

async function decodeBoxCodeFrameViaServer() {
    if (state.scanner.busy) {
        return;
    }
    const video = q("#box-scanner-video");
    if (!video.videoWidth || !video.videoHeight) {
        return;
    }
    state.scanner.busy = true;
    try {
        const blob = await captureScannerFrameBlob(video);
        const formData = new FormData();
        formData.append("file", blob, "scanner-frame.png");
        const result = await apiFormRequest("/system/decode_box_code", formData);
        const code = result.box_codes?.[0] || result.raw_codes?.[0] || "";
        if (code) {
            await useScannedBoxCode(code);
        }
    } catch (error) {
        setScannerStatus(`扫码识别失败：${error.message}`);
    } finally {
        state.scanner.busy = false;
    }
}

async function captureScannerFrameBlob(video) {
    const sourceSize = Math.floor(Math.min(video.videoWidth, video.videoHeight) * 0.46);
    const sourceX = Math.floor((video.videoWidth - sourceSize) / 2);
    const sourceY = Math.floor((video.videoHeight - sourceSize) / 2);
    const targetSize = 512;
    const canvas = document.createElement("canvas");
    canvas.width = targetSize;
    canvas.height = targetSize;
    const context = canvas.getContext("2d", {willReadFrequently: true});
    context.drawImage(
        video,
        sourceX,
        sourceY,
        sourceSize,
        sourceSize,
        0,
        0,
        targetSize,
        targetSize,
    );
    const imageData = context.getImageData(0, 0, targetSize, targetSize);
    const data = imageData.data;
    for (let index = 0; index < data.length; index += 4) {
        const luminance = Math.round(
            data[index] * 0.299
            + data[index + 1] * 0.587
            + data[index + 2] * 0.114,
        );
        data[index] = luminance;
        data[index + 1] = luminance;
        data[index + 2] = luminance;
    }
    context.putImageData(imageData, 0, 0);
    return new Promise((resolve, reject) => {
        canvas.toBlob((blob) => {
            if (blob) {
                resolve(blob);
                return;
            }
            reject(new Error("无法截取扫码画面"));
        }, "image/png");
    });
}

function closeBoxScanner() {
    if (state.scanner.timer) {
        window.clearInterval(state.scanner.timer);
    }
    if (state.scanner.stream) {
        state.scanner.stream.getTracks().forEach((track) => track.stop());
    }
    state.scanner = {
        mode: null,
        stream: null,
        detector: null,
        timer: null,
        busy: false,
        serverDecode: false,
    };
    q("#box-scanner-video").srcObject = null;
    q("#box-scanner-modal").classList.add("hidden");
}

async function useScannedBoxCode(rawCode) {
    const readableId = extractBoxReadableId(rawCode);
    if (!readableId) {
        setScannerStatus("没有识别到有效盒子编号。");
        return;
    }
    q("#box-scanner-code").value = readableId;
    const box = state.boxes.find((item) => item.readable_id.toUpperCase() === readableId.toUpperCase());
    if (!box) {
        setScannerStatus(`未找到盒子：${readableId}`);
        return;
    }
    const mode = state.scanner.mode;
    closeBoxScanner();
    if (mode === "recognition") {
        q("#recognition-mode").value = "existing_box";
        updateRecognitionModeFields();
        q("#recognition-box-id").value = String(box.id);
        showToast(`已选择盒子：${box.readable_id}`);
        return;
    }
    await openManageBox(box.id);
    showToast(`已进入盒子：${box.readable_id}`);
}

function extractBoxReadableId(rawCode) {
    const text = String(rawCode || "").trim();
    if (!text) {
        return "";
    }
    const match = text.match(/BOX-[A-Za-z0-9_-]+/i);
    return (match ? match[0] : text).trim();
}

function setScannerStatus(message) {
    q("#box-scanner-status").textContent = message;
    q("#box-scanner-status").classList.remove("hidden");
}

function getPlacementTargetSubBoxId() {
    const selectedSubBoxId = Number(q("#placement-sub-box-id").value || 0);
    if (selectedSubBoxId) {
        return selectedSubBoxId;
    }
    const bulkBoxId = Number(q("#placement-bulk-box-id").value || 0);
    if (!bulkBoxId) {
        return null;
    }
    return getBulkSubBox(bulkBoxId)?.id || null;
}

async function savePlacement(event) {
    event.preventDefault();
    const componentId = state.placement.componentId;
    if (!componentId) {
        throw new Error("请先选择要入库的器件");
    }
    const subBoxId = getPlacementTargetSubBoxId();
    if (!subBoxId) {
        throw new Error("请选择盒子空位或整理箱");
    }
    await apiRequest("/inventory/", {
        method: "POST",
        body: JSON.stringify(buildInventoryPayload(
            subBoxId,
            componentId,
            q("#placement-stock-mode").value,
            Number(q("#placement-quantity-exact").value),
            q("#placement-notes").value.trim() || null,
        )),
    });
    closePlacementModal();
    await refreshAll();
    showToast("器件已入库");
}

async function loadPlacementRecommendations() {
    const component = state.components.find((item) => item.id === state.placement.componentId);
    if (!component) {
        throw new Error("请先选择要入库的器件");
    }
    const result = await apiRequest("/search/recommend_locations", {
        method: "POST",
        body: JSON.stringify({
            text: [component.name, component.description || ""].join(" ").trim(),
            tag_names: getComponentTagNames(component),
            limit: 8,
        }),
    });
    const list = q("#placement-recommendations");
    list.innerHTML = "";
    if (!result.recommendations.length) {
        list.innerHTML = '<div class="empty-panel compact-empty">暂时没有可推荐的空位。</div>';
        return;
    }
    result.recommendations.forEach((item) => {
        const card = document.createElement("article");
        card.className = "item-card recommendation-card";
        card.innerHTML = `
            <h4>${escapeHtml(item.box_readable_id)} / ${escapeHtml(item.position_identifier)}</h4>
            <p>${escapeHtml(item.box_name || "未命名盒子")}</p>
            <p>${escapeHtml(item.reason)}</p>
            <div class="card-actions">
                <button class="small-button" type="button" data-action="use-placement-recommendation" data-id="${item.sub_box_id}">使用</button>
            </div>
        `;
        list.append(card);
    });
}

function usePlacementRecommendation(subBoxId) {
    const subBox = state.allSubBoxes.find((item) => item.id === subBoxId);
    if (!subBox) {
        throw new Error("推荐位置不存在");
    }
    const box = state.boxes.find((item) => item.id === subBox.box_id);
    if (isBulkBox(box)) {
        q("#placement-bulk-box-id").value = String(box.id);
        q("#placement-box-id").value = "";
        state.placement.selectedSubBoxId = null;
        renderPlacementSubBoxOptions(0);
    } else {
        q("#placement-bulk-box-id").value = "";
        q("#placement-box-id").value = String(subBox.box_id);
        state.placement.selectedSubBoxId = subBoxId;
        renderPlacementSubBoxOptions(subBox.box_id);
    }
    showToast("已选择推荐位置");
}

async function createBulkBoxForPlacement() {
    let template = state.templates.find((item) => isBulkTemplate(item));
    if (!template) {
        template = await apiRequest("/box_templates/", {
            method: "POST",
            body: JSON.stringify({
                name: "整理箱",
                layout_type: "irregular",
                layout_definition: [{id: "CONTENTS", label: "内容"}],
                physical_dimensions: {container_type: "bulk"},
            }),
        });
    }
    const box = await apiRequest("/boxes/", {
        method: "POST",
        body: JSON.stringify({
            name: q("#placement-new-bulk-name").value.trim() || "整理箱",
            template_id: template.id,
        }),
    });
    await refreshAll();
    q("#placement-bulk-box-id").value = String(box.id);
    q("#placement-box-id").value = "";
    state.placement.selectedSubBoxId = null;
    renderPlacementSubBoxOptions(0);
    showToast(`整理箱已创建：${box.readable_id}`);
}

async function saveTemplate(event) {
    event.preventDefault();
    const layout = readTemplateFormLayout();
    const payload = {
        name: q("#template-name").value.trim(),
        layout_type: layout.layout_type,
        layout_definition: layout.layout_definition,
        physical_dimensions: {},
    };
    const path = state.editingTemplateId
        ? `/box_templates/${state.editingTemplateId}`
        : "/box_templates/";
    await apiRequest(path, {
        method: state.editingTemplateId ? "PUT" : "POST",
        body: JSON.stringify(payload),
    });
    fillTemplateForm(null);
    await refreshAll();
    showToast("模板已保存");
}

function fillTemplateForm(template) {
    state.editingTemplateId = template?.id || null;
    state.templateNameAuto = !template;
    q("#template-name").value = template?.name || "";
    q("#template-layout-type").value = template?.layout_type || "grid";
    if (template?.layout_type === "irregular") {
        q("#template-rows").value = 1;
        q("#template-cols").value = 1;
        q("#template-layout-json").value = JSON.stringify(template.layout_definition || [], null, 2);
    } else {
        q("#template-rows").value = template?.layout_definition?.rows || 7;
        q("#template-cols").value = template?.layout_definition?.cols || 4;
        q("#template-layout-json").value = "";
    }
    if (!template) {
        updateTemplateNameSuggestion(true);
    }
    q("#template-submit-button").textContent = template ? "保存修改" : "保存模板";
    updateTemplateLayoutFieldVisibility("template");
    renderTemplateFormPreview();
}

async function saveBox(event) {
    event.preventDefault();
    const readableId = q("#box-readable-id").value.trim();
    const payload = {
        name: q("#box-name").value.trim() || null,
        template_id: Number(q("#box-template-id").value),
    };
    if (readableId || !state.editingBoxId) {
        payload.readable_id = readableId || null;
    }
    const path = state.editingBoxId ? `/boxes/${state.editingBoxId}` : "/boxes/";
    const box = await apiRequest(path, {
        method: state.editingBoxId ? "PUT" : "POST",
        body: JSON.stringify(payload),
    });
    fillBoxForm(null);
    await refreshAll();
    showBoxLabel(box.id);
    showToast(`盒子已保存：${box.readable_id}`);
}

function fillBoxForm(box) {
    state.editingBoxId = box?.id || null;
    q("#box-name").value = box?.name || "";
    q("#box-readable-id").value = box?.readable_id || "";
    if (box?.template_id) {
        q("#box-template-id").value = box.template_id;
    }
    q("#box-submit-button").textContent = box ? "保存盒子修改" : "创建盒子并生成标签";
}

function buildInventoryPayload(subBoxId, componentId, mode, exactQuantity, notes) {
    return {
        sub_box_id: subBoxId,
        component_id: componentId,
        stock_mode: mode === "custom" ? "exact" : "fuzzy",
        quantity_exact: mode === "custom" ? exactQuantity : null,
        quantity_fuzzy: mode === "custom" ? null : mode,
        notes,
    };
}

async function saveTag(event) {
    event.preventDefault();
    const payload = {
        name: q("#tag-name").value.trim(),
        attribute_definitions: parseList(q("#tag-attributes-text").value),
    };
    const path = state.editingTagId ? `/tags/${state.editingTagId}` : "/tags/";
    await apiRequest(path, {
        method: state.editingTagId ? "PUT" : "POST",
        body: JSON.stringify(payload),
    });
    clearTagForm();
    await refreshParts();
    updateMetrics();
    showToast("标签已保存");
}

async function fillTagForm(tagId) {
    const tag = await apiRequest(`/tags/${tagId}`);
    state.editingTagId = tag.id;
    q("#tag-name").value = tag.name;
    q("#tag-attributes-text").value = (tag.attribute_definitions || [])
        .map((item) => item.attribute_name)
        .join(", ");
    q("#tag-submit-button").textContent = "保存修改";
    q("#tag-delete-button").classList.remove("hidden");
    renderTags();
}

function clearTagForm() {
    state.editingTagId = null;
    q("#tag-form").reset();
    q("#tag-submit-button").textContent = "保存标签";
    q("#tag-delete-button").classList.add("hidden");
    renderTags();
}

async function deleteSelectedTag() {
    if (!state.editingTagId) {
        throw new Error("请先选择要删除的标签");
    }
    const deleted = await deleteEntity(`/tags/${state.editingTagId}`, "标签");
    if (!deleted) {
        return;
    }
    clearTagForm();
    await refreshParts();
    updateMetrics();
}

function openCellEditor(subBoxId) {
    const overview = state.selectedBoxOverview;
    if (!overview) {
        return;
    }
    const subBox = overview.sub_boxes.find((item) => item.id === subBoxId);
    if (!subBox) {
        return;
    }
    const inventoryItem = subBox.inventory[0] || null;
    const component = inventoryItem
        ? state.components.find((item) => item.id === inventoryItem.component_id)
        : null;
    state.cellEditor = {
        mode: "cell",
        subBoxId,
        inventoryId: inventoryItem?.inventory_id || null,
        componentId: component?.id || null,
        displayAttribute: component?.display_attribute || "",
    };
    setOptions(
        q("#cell-component-select"),
        state.components,
        (item) => item.name,
        {blankLabel: "新建器件"},
    );
    q("#cell-editor-title").textContent = "编辑格子";
    q("#cell-position-line").classList.remove("hidden");
    q("#cell-component-select-line").classList.remove("hidden");
    q("#cell-stock-mode-line").classList.remove("hidden");
    q("#cell-inventory-notes-line").classList.remove("hidden");
    q('[data-action="delete-cell-inventory"]').classList.toggle("hidden", !inventoryItem);
    q("#cell-editor-submit-button").textContent = "保存格子";
    q("#cell-position").value = `${overview.readable_id} / ${subBox.position_identifier}`;
    q("#cell-component-select").value = component?.id || "";
    fillCellComponentFields(component);
    if (inventoryItem) {
        q("#cell-stock-mode").value = inventoryItem.stock_mode === "exact" ? "custom" : inventoryItem.quantity_fuzzy;
        q("#cell-quantity-exact").value = inventoryItem.quantity_exact || 1;
        q("#cell-inventory-notes").value = inventoryItem.notes || "";
    } else {
        q("#cell-stock-mode").value = "未知";
        q("#cell-quantity-exact").value = 1;
        q("#cell-inventory-notes").value = "";
    }
    q("#cell-ai-prompt").value = "";
    q("#cell-ai-warning").classList.add("hidden");
    q("#cell-ai-warning").textContent = "";
    q("#cell-exact-line").classList.toggle("hidden", q("#cell-stock-mode").value !== "custom");
    q("#cell-editor-modal").classList.remove("hidden");
}

function fillCellComponentFromSelect() {
    const componentId = Number(q("#cell-component-select").value || 0);
    const component = state.components.find((item) => item.id === componentId) || null;
    state.cellEditor.componentId = component?.id || null;
    state.cellEditor.displayAttribute = component?.display_attribute || "";
    fillCellComponentFields(component);
}

function fillCellComponentFields(component) {
    q("#cell-component-name").value = component?.name || "";
    q("#cell-component-tags").value = getComponentTagNames(component || {}).join(", ");
    q("#cell-component-attribute-list").innerHTML = renderAttributeEditor(component?.attributes || {});
    q("#cell-component-description").value = component?.description || "";
}

function closeCellEditor() {
    state.cellEditor = null;
    q("#cell-editor-modal").classList.add("hidden");
}

async function aiFillCell() {
    if (!state.cellEditor) {
        return;
    }
    const prompt = q("#cell-ai-prompt").value.trim();
    const name = q("#cell-component-name").value.trim() || prompt;
    if (!prompt && !name) {
        throw new Error("请输入描述或名称");
    }
    showToast("正在联网搜索并填充信息...");
    const response = await apiRequest("/ai/verify_components", {
        method: "POST",
        body: JSON.stringify({
            items: [
                {
                    position_identifier: q("#cell-position").value,
                    is_empty: false,
                    name,
                    tags: parseList(q("#cell-component-tags").value),
                    attributes: collectAttributeRows(q("#cell-component-attribute-list")),
                    notes: q("#cell-component-description").value.trim() || prompt,
                    stock_mode: "fuzzy",
                    quantity_fuzzy: "未知",
                },
            ],
            use_web: true,
            search_provider_config_id: getSelectedSearchProviderConfigId(),
            additional_prompt: prompt,
        }),
    });
    const item = response.verified_items[0];
    if (!item) {
        throw new Error("AI 没有返回可填充信息");
    }
    q("#cell-component-name").value = item.name || name;
    q("#cell-component-tags").value = (item.tags || []).join(", ");
    q("#cell-component-attribute-list").innerHTML = renderAttributeEditor(item.attributes || {});
    state.cellEditor.displayAttribute = item.display_attribute || "";
    q("#cell-component-description").value = stripVerificationPhrases(
        item.notes || q("#cell-component-description").value,
    );
    const warning = item.verification_warning || "";
    q("#cell-ai-warning").textContent = warning;
    q("#cell-ai-warning").classList.toggle("hidden", !warning);
    showToast("AI 填充完成");
}

async function saveCellEditor(event) {
    event.preventDefault();
    if (!state.cellEditor) {
        return;
    }
    const componentPayload = await buildCellComponentPayload();
    if (state.cellEditor.mode === "component") {
        const wasNew = state.cellEditor.isNew;
        const componentId = state.cellEditor.componentId;
        const component = componentId
            ? await apiRequest(`/components/${componentId}`, {
                method: "PUT",
                body: JSON.stringify(componentPayload),
            })
            : await apiRequest("/components/", {
                method: "POST",
                body: JSON.stringify(componentPayload),
            });
        closeCellEditor();
        await refreshAll();
        if (wasNew) {
            openPlacementModal(component.id);
            showToast("器件已保存，请选择入库位置");
            return;
        }
        showToast("器件已保存");
        return;
    }
    let componentId = Number(q("#cell-component-select").value || 0) || state.cellEditor.componentId;
    if (componentId) {
        const component = await apiRequest(`/components/${componentId}`, {
            method: "PUT",
            body: JSON.stringify(componentPayload),
        });
        componentId = component.id;
    } else {
        const component = await apiRequest("/components/", {
            method: "POST",
            body: JSON.stringify(componentPayload),
        });
        componentId = component.id;
    }
    const inventoryPayload = buildInventoryPayload(
        state.cellEditor.subBoxId,
        componentId,
        q("#cell-stock-mode").value,
        Number(q("#cell-quantity-exact").value),
        q("#cell-inventory-notes").value.trim() || null,
    );
    if (state.cellEditor.inventoryId) {
        await apiRequest(`/inventory/${state.cellEditor.inventoryId}`, {
            method: "PUT",
            body: JSON.stringify(inventoryPayload),
        });
    } else {
        await apiRequest("/inventory/", {
            method: "POST",
            body: JSON.stringify(inventoryPayload),
        });
    }
    const selectedBoxId = state.selectedManageBoxId;
    closeCellEditor();
    await refreshAll();
    if (selectedBoxId) {
        await openManageBox(selectedBoxId);
    }
    showToast("格子已保存");
}

async function buildCellComponentPayload() {
    const tagIds = await ensureTagIds(parseList(q("#cell-component-tags").value));
    const attributes = collectAttributeRows(q("#cell-component-attribute-list"));
    return {
        name: q("#cell-component-name").value.trim(),
        description: q("#cell-component-description").value.trim() || null,
        attributes,
        display_attribute: chooseDisplayAttributeKey(
            attributes,
            state.cellEditor?.displayAttribute || "",
        ),
        tag_ids: tagIds,
    };
}

async function deleteCellInventory() {
    if (!state.cellEditor?.inventoryId) {
        throw new Error("这个格子没有库存记录");
    }
    const deleted = await deleteEntity(
        `/inventory/${state.cellEditor.inventoryId}`,
        "库存记录",
    );
    if (!deleted) {
        return;
    }
    const selectedBoxId = state.selectedManageBoxId;
    closeCellEditor();
    await refreshAll();
    if (selectedBoxId) {
        await openManageBox(selectedBoxId);
    }
}

async function runSearch(event) {
    event.preventDefault();
    const query = q("#search-query").value.trim();
    q("#ai-search-summary").classList.add("hidden");
    q("#ai-search-summary").textContent = "";
    if (q("#search-mode").value === "ai") {
        await runAiSearchQuery(query);
        return;
    }
    const results = await apiRequest(`/search/?q=${encodeURIComponent(query)}`);
    renderSearchResults(results, "没有匹配结果。");
}

async function runAiSearch(event) {
    event?.preventDefault();
    const query = q("#search-query").value.trim();
    await runAiSearchQuery(query);
}

async function runAiSearchQuery(query) {
    if (!query) {
        throw new Error("请输入自然语言需求");
    }
    const response = await apiRequest("/search/semantic", {
        method: "POST",
        body: JSON.stringify({query, use_llm: true, limit: 20}),
    });
    renderAiSearchSummary(response);
    renderSearchResults(response.results, "AI 没有在已有库存中找到合适器件。");
    showToast(response.parsed_query.llm_used ? "AI 搜索完成" : "已使用关键字兜底搜索");
}

function renderSearchResults(results, emptyMessage) {
    const list = q("#search-result-list");
    list.innerHTML = "";
    if (!results.length) {
        list.innerHTML = `<div class="empty-panel compact-empty">${escapeHtml(emptyMessage)}</div>`;
        return;
    }
    results.forEach((result) => {
        const locations = result.locations.map((location) => {
            return `${location.box_readable_id} -> ${location.sub_box_readable_id}`;
        }).join("；") || "未入库";
        const card = document.createElement("article");
        card.className = "item-card";
        card.innerHTML = `<h4>${escapeHtml(result.name)}</h4><p>${escapeHtml(result.tags.join(", "))}</p><p>${escapeHtml(locations)}</p>`;
        list.append(card);
    });
}

function renderAiSearchSummary(response) {
    const summary = q("#ai-search-summary");
    const parsedQuery = response.parsed_query || {};
    const raw = parsedQuery.raw || {};
    const text = raw.reason
        || parsedQuery.reason
        || parsedQuery.llm_error
        || (parsedQuery.llm_used ? "AI 已完成已有库存筛选。" : "AI 未启用，已按关键字兜底搜索。");
    summary.textContent = text;
    summary.classList.remove("hidden");
}

async function runRecommendation(event) {
    event.preventDefault();
    const result = await apiRequest("/search/recommend_locations", {
        method: "POST",
        body: JSON.stringify({
            text: q("#recommendation-text").value.trim() || null,
            tag_names: parseList(q("#recommendation-tags").value),
            preferred_box_id: q("#recommendation-box-id").value ? Number(q("#recommendation-box-id").value) : null,
        }),
    });
    const list = q("#recommendation-list");
    list.innerHTML = "";
    if (!result.recommendations.length) {
        list.innerHTML = '<div class="empty-panel compact-empty">暂时没有可推荐的空位。</div>';
        return;
    }
    result.recommendations.forEach((item) => {
        const card = document.createElement("article");
        card.className = "item-card";
        card.innerHTML = `<h4>${escapeHtml(item.sub_box_readable_id)}</h4><p>${escapeHtml(item.box_readable_id)} · ${escapeHtml(item.position_identifier)}</p><p>${escapeHtml(item.reason)}</p>`;
        list.append(card);
    });
    showToast("推荐完成");
}

async function saveVlmConfig(event) {
    event.preventDefault();
    const payload = buildVlmConfigPayload();
    const path = state.editingVlmConfigId
        ? `/ai/vlm_configs/${state.editingVlmConfigId}`
        : "/ai/vlm_configs/";
    await apiRequest(path, {
        method: state.editingVlmConfigId ? "PUT" : "POST",
        body: JSON.stringify(payload),
    });
    fillVlmForm(null);
    await refreshAi();
    showToast("供应商已保存");
}

async function saveSearchProviderConfig(event) {
    event.preventDefault();
    const payload = buildSearchProviderPayload();
    const path = state.editingSearchProviderConfigId
        ? `/search/providers/${state.editingSearchProviderConfigId}`
        : "/search/providers/";
    await apiRequest(path, {
        method: state.editingSearchProviderConfigId ? "PUT" : "POST",
        body: JSON.stringify(payload),
    });
    fillSearchProviderForm(null);
    await refreshSearchProviders();
    showToast("搜索源已保存");
}

async function saveLogSettings(event) {
    event.preventDefault();
    const response = await apiRequest("/system/logs/config", {
        method: "PUT",
        body: JSON.stringify({level: q("#log-level").value}),
    });
    state.logConfig = response;
    q("#log-level").value = response.level;
    q("#log-file-path").textContent = response.log_file_path;
    await refreshLogs();
    showToast("日志设置已保存");
}

async function saveServerConfig(event) {
    event.preventDefault();
    if (state.serverConfig?.behind_reverse_proxy) {
        showToast("当前为反代部署模式，服务配置由外部反代管理");
        return;
    }
    const payload = await buildServerConfigPayload();
    const response = await apiRequest("/system/config", {
        method: "PUT",
        body: JSON.stringify(payload),
    });
    state.serverConfig = response;
    renderServerConfig();
    q("#server-ssl-cert-pem").value = "";
    q("#server-ssl-key-pem").value = "";
    resetServerCertificateUploadFields();
    const restartNow = window.confirm("服务配置已保存，是否现在重启服务？");
    if (restartNow) {
        await restartService({skipConfirm: true});
        return;
    }
    showToast("服务配置已保存，请稍后重启后生效");
}

async function buildServerConfigPayload() {
    const httpsEnabled = q("#server-https-enabled").checked;
    const source = normalizeServerCertificateSource(state.serverCertificateSource);
    const challengeType = normalizeServerAcmeChallengeType(state.serverAcmeChallengeType);
    const payload = {
        host: q("#server-host").value.trim(),
        http_port: Number(q("#server-http-port").value),
        https_enabled: httpsEnabled,
        https_port: Number(q("#server-https-port").value || state.serverConfig?.https_port || 443),
        certificate_source: source,
        ssl_certfile: null,
        ssl_keyfile: null,
        ssl_cert_pem: null,
        ssl_key_pem: null,
        acme_challenge_type: challengeType,
        acme_domain: q("#server-acme-domain").value.trim() || null,
        acme_email: q("#server-acme-email").value.trim() || null,
        acme_cloudflare_api_token: q("#server-acme-cloudflare-token").value.trim() || null,
    };
    const certfile = q("#server-ssl-certfile").value.trim();
    const keyfile = q("#server-ssl-keyfile").value.trim();
    if (!httpsEnabled) {
        payload.ssl_certfile = certfile || null;
        payload.ssl_keyfile = keyfile || null;
        return payload;
    }
    if (source === "acme") {
        if (!payload.acme_domain) {
            throw new Error("请填写 ACME 域名。");
        }
        payload.https_port = 443;
        if (
            challengeType === "dns-01"
            && !payload.acme_cloudflare_api_token
            && !state.serverConfig?.acme_cloudflare_api_token_configured
        ) {
            throw new Error("DNS-01 需要填写 Cloudflare API Token。");
        }
        return payload;
    }
    if (source === "path") {
        if (!certfile || !keyfile) {
            throw new Error("请同时填写证书文件路径和私钥文件路径。");
        }
        payload.ssl_certfile = certfile;
        payload.ssl_keyfile = keyfile;
        return payload;
    }
    if (source === "upload") {
        const certFile = q("#server-ssl-cert-upload").files?.[0] || null;
        const keyFile = q("#server-ssl-key-upload").files?.[0] || null;
        if (!certFile || !keyFile) {
            throw new Error("请同时上传证书 PEM 和私钥 PEM。");
        }
        payload.ssl_cert_pem = (await certFile.text()).trim();
        payload.ssl_key_pem = (await keyFile.text()).trim();
        return payload;
    }
    if (source === "paste") {
        const certPem = q("#server-ssl-cert-pem").value.trim();
        const keyPem = q("#server-ssl-key-pem").value.trim();
        if (!certPem || !keyPem) {
            throw new Error("请同时粘贴证书 PEM 和私钥 PEM。");
        }
        payload.ssl_cert_pem = certPem;
        payload.ssl_key_pem = keyPem;
    }
    return payload;
}

async function restartService(options = {}) {
    const confirmed = options.skipConfirm
        || window.confirm("确定立即重启服务吗？保存但未生效的设置会在重启后加载。");
    if (!confirmed) {
        return;
    }
    const response = await apiRequest("/system/restart", {method: "POST"});
    showToast(response.message);
}

async function handleServerCertificateUpload(event) {
    const file = event.target.files?.[0] || null;
    if (!file) {
        return;
    }
    setText("#server-ssl-cert-upload-status", `${file.name} · ${formatFileSize(file.size)}`);
}

async function handleServerKeyUpload(event) {
    const file = event.target.files?.[0] || null;
    if (!file) {
        return;
    }
    setText("#server-ssl-key-upload-status", `${file.name} · ${formatFileSize(file.size)}`);
}

function togglePasswordVisibility(button) {
    const input = q(button.dataset.passwordTarget);
    if (!input) {
        return;
    }
    const visible = input.type === "password";
    input.type = visible ? "text" : "password";
    button.textContent = visible ? "隐藏" : "显示";
    button.setAttribute("aria-label", `${visible ? "隐藏" : "显示"}${input.closest("label")?.firstChild?.textContent?.trim() || "密码"}`);
}

function resetPasswordVisibility() {
    qa("[data-password-target]").forEach((button) => {
        const input = q(button.dataset.passwordTarget);
        if (input) {
            input.type = "password";
        }
        button.textContent = "显示";
    });
}

function updatePasswordMatchWarning() {
    const warning = q("#password-match-warning");
    if (!warning) {
        return;
    }
    const newPassword = q("#new-password").value;
    const confirmPassword = q("#confirm-password").value;
    const mismatch = Boolean(newPassword && confirmPassword && newPassword !== confirmPassword);
    warning.classList.toggle("hidden", !mismatch);
    warning.textContent = mismatch ? "两次输入的新密码不一致。" : "";
}

async function login(event) {
    event.preventDefault();
    const response = await fetch(`${API_BASE}/auth/login`, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            username: q("#login-username").value.trim(),
            password: q("#login-password").value,
        }),
    });
    const data = await parseResponse(response);
    if (!response.ok) {
        const message = extractErrorMessage(data, "登录失败");
        showLoginModal(message);
        throw new Error(message);
    }
    setAuthToken(data.token);
    hideLoginModal();
    q("#login-password").value = "";
    await refreshCurrentUser();
    await refreshAll();
    showToast("已登录");
}

async function logout() {
    clearAuthToken();
    showLoginModal();
}

async function changePassword(event) {
    event.preventDefault();
    const newPassword = q("#new-password").value;
    const confirmPassword = q("#confirm-password").value;
    if (newPassword !== confirmPassword) {
        updatePasswordMatchWarning();
        throw new Error("两次输入的新密码不一致。");
    }
    await apiRequest("/auth/password", {
        method: "PUT",
        body: JSON.stringify({
            current_password: q("#current-password").value,
            new_password: newPassword,
        }),
    });
    q("#password-form").reset();
    resetPasswordVisibility();
    updatePasswordMatchWarning();
    showToast("密码已更新");
}

async function createApiKey(event) {
    event.preventDefault();
    const response = await apiRequest("/auth/api_keys", {
        method: "POST",
        body: JSON.stringify({name: q("#api-key-name").value.trim()}),
    });
    showApiKeyCreatedModal(response.api_key);
    q("#api-key-form").reset();
    await refreshApiKeys();
}

function showApiKeyCreatedModal(apiKey) {
    q("#api-key-created-value").value = apiKey;
    q("#api-key-created-modal").classList.remove("hidden");
    q("#api-key-created-value").focus();
    q("#api-key-created-value").select();
}

function closeApiKeyCreatedModal() {
    q("#api-key-created-value").value = "";
    q("#api-key-created-modal").classList.add("hidden");
}

async function copyCreatedApiKey() {
    const apiKey = q("#api-key-created-value").value;
    if (!apiKey) {
        return;
    }
    await navigator.clipboard.writeText(apiKey);
    showToast("API 密钥已复制");
}

async function deleteApiKey(apiKeyId) {
    const deleted = await deleteEntity(`/auth/api_keys/${apiKeyId}`, "API 密钥");
    if (deleted) {
        await refreshApiKeys();
    }
}

async function clearDatabase() {
    const firstConfirm = window.confirm("确定清空数据库吗？盒子、元器件、库存、标签和模板都会删除。");
    if (!firstConfirm) {
        return;
    }
    const secondConfirm = window.confirm("请再次确认：此操作不可撤销，但会保留 AI/API 配置、账户和 API 密钥。");
    if (!secondConfirm) {
        return;
    }
    const result = await apiRequest("/system/database", {method: "DELETE"});
    await refreshAll();
    showToast(`已清空：${result.deleted_boxes} 个盒子，${result.deleted_components} 个元器件`);
}

function clearLogView() {
    state.logClearLineCount = state.latestLogTotalLines;
    q("#log-viewer").textContent = "暂无日志。";
    showToast("已清空当前日志显示");
}

async function testSearchProviderConfig(configId) {
    const result = await apiRequest(`/search/providers/${configId}/test`, {method: "POST"});
    showSearchProviderTestResult(result);
    showToast(result.ok ? `测试通过 ${result.latency_ms ?? "-"}ms` : result.message);
}

async function testCurrentSearchProviderForm() {
    const result = await apiRequest("/search/providers/test", {
        method: "POST",
        body: JSON.stringify({config: buildSearchProviderPayload()}),
    });
    showSearchProviderTestResult(result);
    showToast(result.ok ? `测试通过 ${result.latency_ms ?? "-"}ms` : result.message);
}

async function testVlmConfig(configId) {
    const result = await apiRequest(`/ai/vlm_configs/${configId}/test`, {method: "POST"});
    showToast(result.ok ? `测试通过 ${result.latency_ms ?? "-"}ms` : result.message);
}

async function testCurrentVlmForm() {
    const result = await apiRequest("/ai/vlm_config/test", {
        method: "POST",
        body: JSON.stringify({config: buildVlmConfigPayload()}),
    });
    showToast(result.ok ? `测试通过 ${result.latency_ms ?? "-"}ms` : result.message);
}

async function boot() {
    applyThemeMode(state.themeMode);
    bindEvents();
    renderThemeControls();
    fillVlmForm(null);
    fillSearchProviderForm(null);
    fillTemplateForm(null);
    updateTemplateLayoutFieldVisibility("recognized-template");
    clearTagForm();
    updateRecognitionModeFields();
    updateServerHttpsVisibility();
    updatePasswordMatchWarning();
    if (!state.authToken) {
        q("#service-text").textContent = "请登录";
        showLoginModal();
        return;
    }
    try {
        await refreshCurrentUser();
        await refreshAll();
        if (!restoreActiveRecognitionSession()) {
            restoreRecognitionDraft();
        }
        hideLoginModal();
    } catch (error) {
        clearAuthToken();
        q("#service-text").textContent = "请登录";
        showLoginModal(error.message);
    }
}

boot();
