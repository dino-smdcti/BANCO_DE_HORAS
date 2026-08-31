import re
from unittest.mock import patch

import pytest

from src.entrypoints.flask_app import app


@pytest.fixture
def csrf_client(session_factory):
    app.config["TESTING"] = True
    # Force CSRF on for the scope of these tests, then restore it.
    old = app.config.get("WTF_CSRF_ENABLED", True)
    app.config["WTF_CSRF_ENABLED"] = True

    patcher = patch("src.entrypoints.flask_app.process_daily_absences", lambda uow: None)
    patcher.start()
    try:
        with patch("src.entrypoints.flask_app.SqlAlchemyUnitOfWork", lambda: __import__(
                "src.service_layer.unit_of_work", fromlist=["SqlAlchemyUnitOfWork"]
        ).SqlAlchemyUnitOfWork(session_factory)):
            with app.test_client() as c:
                yield c
    finally:
        patcher.stop()
        app.config["WTF_CSRF_ENABLED"] = old


def _get_csrf_token(client, path="/forgot-password"):
    r = client.get(path)
    assert r.status_code == 200
    m = re.search(rb'name="csrf-token" content="([^"]+)"', r.data)
    assert m, "csrftoken meta tag not rendered"
    return m.group(1).decode("utf-8")


class TestCsrfProtection:
    def test_post_without_token_rejected(self, csrf_client):
        r = csrf_client.post("/forgot-password", data={"email": "nobody@test.com"})
        assert r.status_code == 400

    def test_post_with_token_accepted(self, csrf_client):
        token = _get_csrf_token(csrf_client)
        r = csrf_client.post(
            "/forgot-password",
            data={"email": "nobody@test.com"},
            headers={"X-CSRFToken": token},
        )
        assert r.status_code == 302

    def test_rendered_pages_expose_csrf_token(self, csrf_client):
        # Both token-emitting channels (meta tag for fetch() and hidden input
        # for regular forms) must be present on a page that renders a form.
        r = csrf_client.get("/forgot-password")
        assert b'name="csrf-token" content="' in r.data
        assert re.search(rb'<input[^>]*name="csrf_token"[^>]*>', r.data), "csrf hidden input not rendered"
