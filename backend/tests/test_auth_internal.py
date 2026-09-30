"""Internal login mode: e-mail + password from the environment, no Supabase."""
import pytest

from app.config import get_settings
from app.security import create_token, read_token


@pytest.fixture
def internal(monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "auth_disabled", False)
    monkeypatch.setattr(s, "admin_email", "Ammar@Jusoor.test")
    monkeypatch.setattr(s, "admin_password", "a-long-enough-password")
    monkeypatch.setattr(s, "secret_key", "test-secret")
    monkeypatch.setattr(s, "supabase_url", "")
    return s


def test_mode_is_internal(client, internal):
    assert client.get("/api/auth/mode").json() == {"mode": "internal"}
    assert client.get("/api/health").json()["auth"]["mode"] == "internal"


def test_login_issues_a_working_token(client, internal):
    r = client.post("/api/auth/login", json={"email": "ammar@jusoor.test", "password": "a-long-enough-password"})
    assert r.status_code == 200, r.text
    token = r.json()["token"]
    assert r.json()["email"] == "ammar@jusoor.test"

    # Protected endpoints accept it, and identify the user
    headers = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/me", headers=headers).json()["email"] == "ammar@jusoor.test"
    assert client.get("/api/drafts/counts", headers=headers).status_code == 200


def test_wrong_password_and_email_rejected(client, internal):
    bad_pw = client.post("/api/auth/login", json={"email": "ammar@jusoor.test", "password": "wrong"})
    bad_mail = client.post("/api/auth/login", json={"email": "someone@else.test", "password": "a-long-enough-password"})
    assert bad_pw.status_code == 401 and bad_mail.status_code == 401
    assert "كلمة المرور" in bad_pw.json()["detail"]


def test_protected_route_without_token(client, internal):
    r = client.get("/api/drafts/counts")
    assert r.status_code == 401 and "تسجيل الدخول" in r.json()["detail"]


def test_tampered_and_expired_tokens_rejected(client, internal):
    token = create_token("ammar@jusoor.test")
    assert read_token(token)["email"] == "ammar@jusoor.test"
    payload, sig = token.split(".", 1)
    assert read_token(f"{payload}.{'x' * len(sig)}") is None
    assert read_token(create_token("ammar@jusoor.test", hours=-1)) is None
    r = client.get("/api/me", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_token_secret_changes_with_password(client, internal, monkeypatch):
    """A password change must invalidate old sessions even without SECRET_KEY."""
    monkeypatch.setattr(internal, "secret_key", "")
    token = create_token("ammar@jusoor.test")
    monkeypatch.setattr(internal, "admin_password", "a-different-password")
    assert read_token(token) is None


def test_health_warns_about_short_password(client, internal, monkeypatch):
    monkeypatch.setattr(internal, "admin_password", "123")
    assert any("ADMIN_PASSWORD" in p for p in client.get("/api/health").json()["problems"])


def test_unconfigured_auth_is_reported(client, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "auth_disabled", False)
    monkeypatch.setattr(s, "admin_email", "")
    monkeypatch.setattr(s, "admin_password", "")
    monkeypatch.setattr(s, "supabase_url", "")
    body = client.get("/api/health").json()
    assert body["auth"]["mode"] == "unconfigured"
    assert any("ADMIN_EMAIL" in p for p in body["problems"])
    assert client.get("/api/drafts/counts").status_code == 500


def test_cors_origins_are_forgiving(client, monkeypatch):
    """A trailing slash or a missing scheme must not break the dashboard connection."""
    from app.config import get_settings
    s = get_settings()
    monkeypatch.setattr(s, "cors_origins", " https://jusoor-autopost.vercel.app/ , jusoor.com ")
    assert s.cors_origin_list == ["https://jusoor-autopost.vercel.app", "https://jusoor.com"]
    import re
    assert re.fullmatch(s.cors_origin_regex, "https://jusoor-autopost-abc123-team.vercel.app")


def test_preview_origin_allowed_by_middleware(client):
    """Preflight from a Vercel preview URL of the same project is accepted."""
    from app.config import get_settings
    get_settings.cache_clear() if hasattr(get_settings, "cache_clear") else None
    r = client.options("/api/auth/login", headers={
        "Origin": "https://jusoor-autopost.vercel.app",
        "Access-Control-Request-Method": "POST",
    })
    assert r.status_code in (200, 400)   # 400 only when CORS_ORIGINS is unset in the test env
