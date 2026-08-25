from app.config import get_settings
from app.routers import broadcasts


class FakeSession:
    async def close(self):
        return None


class FakeBot:
    sent: list[int] = []

    def __init__(self, token: str):
        self.token = token
        self.session = FakeSession()

    async def send_message(self, *, chat_id: int, text: str, reply_markup=None):
        self.sent.append(chat_id)


def test_broadcast_preview_and_repeat_are_idempotent(client, admin_headers, monkeypatch):
    settings = get_settings()
    previous_token = settings.bot_token
    settings.bot_token = "test-token"
    FakeBot.sent = []
    monkeypatch.setattr(broadcasts, "Bot", FakeBot)
    try:
        preview = client.get("/api/admin/broadcasts/registration-fixed/preview", headers=admin_headers)
        assert preview.status_code == 200
        assert preview.json()["pending"] >= 1

        first = client.post("/api/admin/broadcasts/registration-fixed", headers=admin_headers)
        assert first.status_code == 200
        assert first.json()["sent"] == preview.json()["pending"]

        sent_after_first_run = len(FakeBot.sent)
        second = client.post("/api/admin/broadcasts/registration-fixed", headers=admin_headers)
        assert second.status_code == 200
        assert second.json()["sent"] == 0
        assert second.json()["skipped"] == preview.json()["total"]
        assert len(FakeBot.sent) == sent_after_first_run
    finally:
        settings.bot_token = previous_token
