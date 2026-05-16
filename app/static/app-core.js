var API_BASE = "/api/v1";
var AUTH_TOKEN_STORAGE_KEY = "ohmstash_token";
var browserSessionStorage = window.sessionStorage || window.localStorage;
var THEME_STORAGE_KEY = "ohmstash_theme";
var RECOGNITION_DRAFT_STORAGE_KEY = "ohmstash_recognition_draft";
var RECOGNITION_ACTIVE_SESSION_STORAGE_KEY = "ohmstash_active_recognition_session";
var RECOGNITION_DRAFT_VERSION = 1;
var THEME_LABELS = {
    system: "跟随系统",
    light: "浅色",
    dark: "深色",
};
var CERTIFICATE_SOURCE_MODES = new Set(["self-signed", "path", "upload", "paste", "acme"]);
var ACME_CHALLENGE_TYPES = new Set(["http-01", "dns-01"]);

var VIEW_META = {
    dashboard: ["首页", "查看库存概览、未入库器件和近期盒子。"],
    recognition: ["识别入库", "拍照识别整盒内容，并批量写入已有盒子或新模板。"],
    manage: ["管理", "按盒子、分类或元器件维护现有库存。"],
    boxes: ["盒子", "创建盒子、查看布局并打印标签。"],
    search: ["搜索", "查找元器件位置并推荐空位。"],
    settings: ["设置", "管理 AI 供应商和标签库。"],
};

var STOCK_OPTIONS = ["充足", "少量", "紧张", "未知", "用尽"];
var MANAGE_CELL_MIN_WIDTH = 88;
var DISPLAY_ATTRIBUTE_FALLBACK_KEYS = [
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

var RECOGNITION_UPLOAD_OPTIMIZE_THRESHOLD_BYTES = 3 * 1024 * 1024;
var RECOGNITION_UPLOAD_TARGET_BYTES = 3 * 1024 * 1024;
var RECOGNITION_UPLOAD_MAX_SIDE = 2400;
var RECOGNITION_UPLOAD_JPEG_QUALITIES = [0.88, 0.82, 0.76, 0.7];
var RECOGNITION_UPLOAD_COMPRESSIBLE_EXTENSIONS = new Set(["jpg", "jpeg", "png", "webp"]);
var RECOGNITION_UPLOAD_COMPRESSIBLE_TYPES = new Set([
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
]);
var RECOGNITION_NETWORK_RETRY_COUNT = 2;
var RECOGNITION_NETWORK_RETRY_DELAYS_MS = [1200, 3000];
var RECOGNITION_WAKE_LOCK_TYPE = "screen";
var RECOGNITION_SESSION_POLL_INTERVAL_MS = 3000;

var ACTION_BUSY_TEXT = {
    "refresh-all": "刷新中...",
    "confirm-box-recognition": "入库中...",
    "verify-selected-components": "搜索中...",
    "refresh-recognition-sessions": "刷新中...",
    "open-recognition-session": "加载中...",
    "delete-recognition-session": "删除中...",
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

var SUBMIT_BUSY_TEXT = {
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

applyInitialThemeMode();

function applyInitialThemeMode() {
    const theme = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (theme === "dark" || theme === "light") {
        document.documentElement.dataset.theme = theme;
    }
}


var VERIFICATION_WARNING_PATTERNS = [
    /未检索到[^。；;，,\n]*(?:[。；;，,])?/g,
    /未找到[^。；;，,\n]*(?:[。；;，,])?/g,
    /没有可确认[^。；;，,\n]*(?:[。；;，,])?/g,
    /无法确认[^。；;，,\n]*(?:[。；;，,])?/g,
    /搜索结果不足[^。；;，,\n]*(?:[。；;，,])?/g,
    /(?:暂)?保留原标注/g,
];

var state = {
    authToken: browserSessionStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
        || window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)
        || "",
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
    recognitionHistoryFilter: "all",
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

var q = (selector) => document.querySelector(selector);
var qa = (selector) => Array.from(document.querySelectorAll(selector));

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
    browserSessionStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
}


function clearAuthToken() {
    state.authToken = "";
    state.currentUser = null;
    browserSessionStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
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

function escapeClassToken(value) {
    return String(value ?? "unknown").replace(/[^a-zA-Z0-9_-]/g, "-");
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

