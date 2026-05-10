const API_BASE = import.meta.env.VITE_API_BASE || "";

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

  return {
    telegram_id: Number(localStorage.getItem("devTelegramId") || "1001"),
    telegram_username: "dev_user",
    first_name: "Dev",
    last_name: "User",
  };
}

export async function login() {
  const initData = getTelegramInitData();
  if (initData) {
    try {
      return await api("/api/auth/telegram", {
        method: "POST",
        body: JSON.stringify({ init_data: initData }),
      });
    } catch (error) {
      console.warn("Telegram auth failed", error);
    }
  }

  return api("/api/auth/dev", {
    method: "POST",
    body: JSON.stringify(getTelegramUser()),
  });
}

export async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Ошибка запроса");
  }
  if (response.status === 204) return null;
  return response.json();
}

export function adminHeaders(user) {
  return { "X-Telegram-Id": String(user.telegram_id) };
}
