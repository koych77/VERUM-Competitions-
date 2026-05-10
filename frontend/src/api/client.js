const API_BASE = import.meta.env.VITE_API_BASE || "";

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
