const API_BASE = "/api/v1";
const AUTH_TOKEN_STORAGE_KEY = "ohmstash_token";
const THEME_STORAGE_KEY = "ohmstash_theme";

applyInitialThemeMode();

function applyInitialThemeMode() {
    const theme = window.localStorage.getItem(THEME_STORAGE_KEY);
    if (theme === "dark" || theme === "light") {
        document.documentElement.dataset.theme = theme;
    }
}

function q(selector) {
    return document.querySelector(selector);
}

function getNextUrl() {
    const params = new URLSearchParams(window.location.search);
    const nextUrl = params.get("next") || "/ui/";
    return nextUrl.startsWith("/ui/") ? nextUrl : "/ui/";
}

function showLoginError(message) {
    const error = q("#login-error");
    error.textContent = message;
    error.classList.remove("hidden");
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
    return fallback;
}

async function login(event) {
    event.preventDefault();
    const button = q("#login-submit-button");
    button.disabled = true;
    button.textContent = "登录中...";
    q("#login-error").classList.add("hidden");
    try {
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
            throw new Error(extractErrorMessage(data, "登录失败"));
        }
        window.sessionStorage.setItem(AUTH_TOKEN_STORAGE_KEY, data.token);
        window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
        window.location.href = getNextUrl();
    } catch (error) {
        showLoginError(error.message);
    } finally {
        button.disabled = false;
        button.textContent = "登录";
    }
}

q("#login-form").addEventListener("submit", login);

const loginMessage = window.sessionStorage.getItem("ohmstash_login_message");
if (loginMessage) {
    window.sessionStorage.removeItem("ohmstash_login_message");
    showLoginError(loginMessage);
}
