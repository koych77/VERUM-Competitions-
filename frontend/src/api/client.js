const API_BASE = import.meta.env.VITE_API_BASE || "";
let accessToken = "";

function getTelegramInitData() {
  const tg = window.Telegram?.WebApp;
  if (tg?.initData) {
    return tg.initData;
  }

  const hashParams = new URLSearchParams(window.location.hash.replace(/^#/, ""));
  const searchParams = new URLSearchParams(window.location.search);
  return hashParams.get("tgWebAppData") || searchParams.get("tgWebAppData") || "";
}

export function getTelegramUser() {
  const tg = window.Telegram?.WebApp;
  const user = tg?.initDataUnsafe?.user;
  if (user) {
    return {
      telegram_id: user.id,
      telegram_username: user.username || null,
      first_name: user.first_name || null,
      last_name: user.last_name || null,
    };
  }
  return null;
}

export async function login() {
  const initData = getTelegramInitData();
  if (initData) {
    const session = await api("/api/auth/telegram", {
      method: "POST",
      body: JSON.stringify({ init_data: initData }),
      skipAuth: true,
    });
    accessToken = session.access_token;
    return session;
  }

  const developmentTelegramId = Number(import.meta.env.VITE_DEV_TELEGRAM_ID || 0);
  if (import.meta.env.DEV && developmentTelegramId > 0) {
    const session = await api("/api/auth/dev", {
      method: "POST",
      body: JSON.stringify({
        telegram_id: developmentTelegramId,
        telegram_username: "local_dev",
        first_name: "Local",
        last_name: "Developer",
      }),
      skipAuth: true,
    });
    accessToken = session.access_token;
    return session;
  }

  throw new Error("Откройте приложение из бота Telegram, чтобы продолжить.");
}

export async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData) && options.body !== undefined && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  if (accessToken && !options.skipAuth && !headers.Authorization) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  const { skipAuth, ...fetchOptions } = options;
  const response = await fetch(`${API_BASE}${path}`, { ...fetchOptions, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail = Array.isArray(body.detail)
      ? body.detail.map((item) => item.msg || String(item)).join("; ")
      : body.detail;
    throw new Error(detail || "Не удалось выполнить запрос. Попробуйте ещё раз.");
  }
  if (response.status === 204) return null;
  return response.json();
}

export function adminHeaders(user) {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

export function authHeaders() {
  return accessToken ? { Authorization: `Bearer ${accessToken}` } : {};
}

export async function downloadFile(path, filename) {
  const response = await fetch(`${API_BASE}${path}`, { headers: authHeaders() });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Не удалось скачать файл.");
  }
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
}
