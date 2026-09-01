import pytest
from unittest.mock import patch

from src.entrypoints import flask_app
from src.entrypoints.flask_app import app


@pytest.fixture(autouse=True)
def _config():
    app.config["MAIL_USERNAME"] = "sender@example.com"
    app.config["MAIL_PASSWORD"] = "smtp-password"
    app.config["MAIL_SERVER"] = "smtp.gmail.com"
    app.config["MAIL_PORT"] = 587
    yield


class TestBrevoFallback:
    def test_brevo_tried_when_smtp_fails(self):
        with patch.object(flask_app, "_send_smtp", return_value=False), \
             patch.object(flask_app, "_send_brevo", return_value=True) as mock_brevo, \
             patch.dict("os.environ", {"BREVO_API_KEY": "key"}, clear=False):
            assert flask_app.send_email("to@example.com", "subj", "<p>html</p>") is True
        mock_brevo.assert_called_once()

    def test_brevo_not_tried_when_smtp_succeeds(self):
        with patch.object(flask_app, "_send_smtp", return_value=True) as mock_smtp, \
             patch.object(flask_app, "_send_brevo") as mock_brevo:
            assert flask_app.send_email("to@example.com", "subj", "<p>html</p>") is True
        mock_smtp.assert_called_once()
        mock_brevo.assert_not_called()

    def test_returns_false_when_both_fail(self):
        with patch.object(flask_app, "_send_smtp", return_value=False), \
             patch.object(flask_app, "_send_brevo", return_value=False):
            assert flask_app.send_email("to@example.com", "subj", "html") is False

    def test_brevo_skipped_without_api_key(self):
        with patch.object(flask_app, "_send_smtp", return_value=False), \
             patch.dict("os.environ", {}, clear=False) as env, \
             patch.object(flask_app.urllib.request, "urlopen") as mock_open:
            env.pop("BREVO_API_KEY", None)
            assert flask_app.send_email("to@example.com", "subj", "html") is False
        mock_open.assert_not_called()


class TestBrevoSender:
    def test_payload_uses_sender_and_content(self):
        import json
        def fake_urlopen(req, timeout=None):
            payload = json.loads(req.data.decode("utf-8"))
            assert payload["sender"]["email"] == "sender@example.com"
            assert payload["to"] == [{"email": "to@example.com"}]
            assert payload["subject"] == "subj"
            assert payload["htmlContent"] == "<p>hi</p>"
            class R:
                status = 201
                def __enter__(self): return self
                def __exit__(self, *a): return False
            return R()

        with patch.object(flask_app, "_send_smtp", return_value=False), \
             patch.object(flask_app.urllib.request, "urlopen", side_effect=fake_urlopen) as mock_open, \
             patch.dict("os.environ", {"BREVO_API_KEY": "secret-key"}, clear=False):
            assert flask_app.send_email("to@example.com", "subj", "<p>hi</p>") is True
        args, _ = mock_open.call_args
        req = args[0]
        assert req.full_url == flask_app.BREVO_API_URL
        assert req.headers.get("Api-key") == "secret-key"
