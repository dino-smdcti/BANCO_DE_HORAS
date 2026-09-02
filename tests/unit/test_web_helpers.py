import unittest
from datetime import date, time
from flask import Flask, session
from src.entrypoints.web_helpers import (
        INVALID_DATE,
        flash_redirect,
        parse_date,
        parse_date_arg,
        parse_time,
        parse_time_arg,
        redirect_to_employee_logs,
        render_markdown,
        plain_text_snippet,
        snippet_filter,
)
from src.config import DATE_FORMAT, TIME_FORMAT


class TestDateHelpers(unittest.TestCase):
        def test_parse_date_arg_parses_valid(self):
                value = date(2026, 9, 1).strftime(DATE_FORMAT)
                self.assertEqual(parse_date_arg(value), date(2026, 9, 1))

        def test_parse_date_arg_raises_on_empty(self):
                with self.assertRaises(ValueError):
                        parse_date_arg("")

        def test_parse_date_arg_raises_on_malformed(self):
                with self.assertRaises(ValueError):
                        parse_date_arg("01-99-2026")

        def test_parse_date_lenient_semantics_unchanged(self):
                self.assertIsNone(parse_date(""))
                self.assertIs(parse_date("not-a-date"), INVALID_DATE)
                self.assertEqual(parse_date(date(2026, 9, 1).strftime(DATE_FORMAT)), date(2026, 9, 1))

        def test_parse_time_arg_parses_valid(self):
                self.assertEqual(parse_time_arg("14:30"), time(14, 30))

        def test_parse_time_arg_raises_on_malformed(self):
                with self.assertRaises(ValueError):
                        parse_time_arg("not-a-time")

        def test_parse_time_lenient_semantics_unchanged(self):
                self.assertIsNone(parse_time(""))
                self.assertEqual(parse_time("09:05"), time(9, 5))
                self.assertEqual(parse_time("09:05:07"), time(9, 5, 7))


class TestRedirectHelpers(unittest.TestCase):
        def setUp(self):
                self.app = Flask(__name__)
                self.app.config["TESTING"] = True
                self.app.secret_key = "test"

                @self.app.route("/manager/view-logs/<int:employee_id>")
                def view_employee_logs(employee_id):
                        return "logs"

                @self.app.route("/dashboard")
                def dashboard():
                        return "dashboard"

        def test_redirect_to_employee_logs(self):
                with self.app.test_request_context():
                        response = redirect_to_employee_logs(42)
                        self.assertEqual(response.status_code, 302)
                        self.assertIn("/manager/view-logs/42", response.headers["Location"])

        def test_flash_redirect_flashes_and_redirects(self):
                with self.app.test_request_context():
                        response = flash_redirect("dashboard", "Ops", category="warning")
                        self.assertEqual(response.status_code, 302)
                        self.assertIn("/dashboard", response.headers["Location"])
                        self.assertIn(("warning", "Ops"), list(session.get("_flashes", [])))


class TestMarkdownRendering(unittest.TestCase):
        def test_render_markdown_empty(self):
                self.assertEqual(str(render_markdown("")), "")
                self.assertEqual(str(render_markdown(None)), "")

        def test_render_markdown_inline(self):
                out = str(render_markdown("**negrito** e [link](https://ex.com)"))
                self.assertIn("<strong>negrito</strong>", out)
                self.assertIn('<a href="https://ex.com"', out)
                self.assertEqual(out.count("<p>"), 1)

        def test_render_markdown_headers_and_lists(self):
                out = str(render_markdown("# Titulo\n\n- item a\n- item b"))
                self.assertIn("<h1>Titulo</h1>", out)
                self.assertIn("<ul>", out)
                self.assertIn("<li>item a</li>", out)

        def test_render_markdown_strips_unsafe_html(self):
                out = str(render_markdown("<script>alert(1)</script>TEXTO"))
                self.assertNotIn("<script>", out)
                self.assertIn("TEXTO", out)

        def test_render_markdown_strips_event_handlers(self):
                out = str(render_markdown("<img src=x onerror=alert(1)>"))
                self.assertNotIn("onerror", out)

        def test_render_markdown_returns_markup_safe(self):
                allocated = render_markdown("**a**")
                from markupsafe import Markup

                self.assertIsInstance(allocated, Markup)


class TestSnippet(unittest.TestCase):
        def test_snippet_empty(self):
                self.assertEqual(plain_text_snippet(""), "")
                self.assertEqual(plain_text_snippet(None), "")

        def test_snippet_short_text_not_truncated(self):
                self.assertEqual(plain_text_snippet("**olá** mundo"), "olá mundo")

        def test_snippet_strips_markup_and_limits(self):
                out = plain_text_snippet("**a**" * 200, limit=40)
                self.assertLessEqual(len(out), 41)
                self.assertNotIn("<strong>", out)
                self.assertTrue(out.endswith("…"))

        def test_snippet_does_not_split_words(self):
                out = plain_text_snippet("uma frase " * 50, limit=30)
                self.assertTrue(out.endswith("…"))

        def test_snippet_filter_returns_markup(self):
                from markupsafe import Markup

                self.assertIsInstance(snippet_filter("**x**"), Markup)


if __name__ == "__main__":
        unittest.main()