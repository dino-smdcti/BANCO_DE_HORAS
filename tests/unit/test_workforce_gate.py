import src.config as config
from src.entrypoints import work_routes


class _StubApp:
    def __init__(self):
        self.urls = []

    def add_url_rule(self, rule, endpoint, view_func, methods=None):
        self.urls.append(rule)


def test_register_routes_gates_workforce(monkeypatch):
    monkeypatch.setattr(config, "WORKFORCE_ENABLED", False)
    import importlib
    work_routes_ = importlib.reload(work_routes)
    app = _StubApp()
    work_routes_.register_routes(app)
    assert app.urls == []


def test_register_routes_registers_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "WORKFORCE_ENABLED", True)
    import importlib
    work_routes_ = importlib.reload(work_routes)
    app = _StubApp()
    work_routes_.register_routes(app)
    assert "/work/tasks" in app.urls
    assert "/work/exec" in app.urls