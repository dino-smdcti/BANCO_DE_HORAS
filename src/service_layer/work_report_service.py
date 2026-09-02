"""Workforce HTML report service.

Builds structured, presentation-agnostic report data for the workforce module
over the caller's scoped teams, optionally filtered by a date range. The route
renders this as an HTML page (print-friendly) — serverless/Linux-safe, no Excel
binary generation. Reuses F0 scoping so employees see only their own team while
ADMIN/GESTOR see everything.
"""
from datetime import date

from src.service_layer.permissions import scoped_team_ids
from src.service_layer.unit_of_work import AbstractUnitOfWork


def build_work_report(uow: AbstractUnitOfWork, actor_id: int, *, period_start=None, period_end=None, team_id=None) -> dict:
        """Return a {teams, section summaries and row lists} report for the actor."""
        with uow:
                scoped = set(scoped_team_ids(uow, actor_id))
                if team_id is not None and team_id not in scoped:
                        raise PermissionError("Time fora do seu escopo.")
                teams = [t for t in scoped_ids_and_teams(uow, scoped) if team_id is None or t.team_id == team_id]
                team_labels = {t.team_id: t.name for t in teams}

                report = {
                        "period_start": period_start,
                        "period_end": period_end,
                        "team_labels": team_labels,
                        "sections": {
                                "tasks": _tasks(uow, teams, period_start, period_end),
                                "accomplishments": _accomplishments(uow, teams, period_start, period_end),
                                "ideas": _ideas(uow, teams, period_start, period_end),
                                "s5": _s5(uow, teams, period_start, period_end),
                                "kudos": _kudos(uow, teams, period_start, period_end),
                                "events": _events(uow, teams, period_start, period_end),
                                "wiki": _wiki(uow, teams, period_start, period_end),
                        },
                        "totals": {},
                }
                report["totals"] = {
                        "tasks": len(report["sections"]["tasks"]),
                        "accomplishments": len(report["sections"]["accomplishments"]),
                        "ideas": len(report["sections"]["ideas"]),
                        "s5": len(report["sections"]["s5"]),
                        "kudos": len(report["sections"]["kudos"]),
                        "events": len(report["sections"]["events"]),
                        "wiki": len(report["sections"]["wiki"]),
                        "teams": len(teams),
                }
                return report


def scoped_ids_and_teams(uow, scoped_ids):
        return [t for t in (uow.users.get_team_by_id(tid) for tid in scoped_ids) if t]


def _in_period(value, period_start, period_end):
        """True when a date falls within [period_start, period_end], if bounds given."""
        if value is None:
                return True
        if period_start is not None and value < period_start:
                return False
        if period_end is not None and value > period_end:
                return False
        return True


def _tasks(uow, teams, ps, pe):
        rows = []
        for team in teams:
                for task in uow.users.list_tasks_by_team(team.team_id):
                        if _in_period(task.created_at.date() if task.created_at else None, ps, pe):
                                rows.append({
                                        "team_id": team.team_id,
                                        "title": task.title,
                                        "status": task.status,
                                        "assignee_id": task.assignee_id,
                                        "due_date": task.due_date,
                                })
        return rows


def _accomplishments(uow, teams, ps, pe):
        rows = []
        for team in teams:
                for acc in uow.users.list_accomplishments_by_team(team.team_id):
                        anchor = acc.start_date or acc.end_date or (acc.created_at.date() if acc.created_at else None)
                        if _in_period(anchor, ps, pe):
                                rows.append({
                                        "team_id": team.team_id,
                                        "title": acc.title,
                                        "start_date": acc.start_date,
                                        "end_date": acc.end_date,
                                        "achieved_by_user_id": acc.achieved_by_user_id,
                                })
        return rows


def _ideas(uow, teams, ps, pe):
        rows = []
        for team in teams:
                for idea in uow.users.list_ideas_by_team(team.team_id):
                        if _in_period(idea.created_at.date() if idea.created_at else None, ps, pe):
                                rows.append({
                                        "team_id": team.team_id,
                                        "title": idea.title,
                                        "category": idea.category,
                                        "status": idea.status,
                                        "author_user_id": idea.author_user_id,
                                })
        return rows


def _s5(uow, teams, ps, pe):
        rows = []
        for team in teams:
                for audit in uow.users.list_s5_audits_by_team(team.team_id):
                        if _in_period(audit.date, ps, pe):
                                rows.append({
                                        "team_id": team.team_id,
                                        "date": audit.date,
                                        "auditor_id": audit.auditor_id,
                                        "score": audit.score,
                                })
        return rows


def _kudos(uow, teams, ps, pe):
        rows = []
        for team in teams:
                for kudo in uow.users.list_kudos_by_team(team.team_id):
                        if _in_period(kudo.created_at.date() if kudo.created_at else None, ps, pe):
                                rows.append({
                                        "team_id": team.team_id,
                                        "giver_id": kudo.giver_id,
                                        "receiver_id": kudo.receiver_id,
                                        "message": kudo.message,
                                })
        return rows


def _events(uow, teams, ps, pe):
        rows = []
        for team in teams:
                for event in uow.users.list_team_events_by_team(team.team_id):
                        if _in_period(event.date, ps, pe):
                                rows.append({
                                        "team_id": team.team_id,
                                        "title": event.title,
                                        "date": event.date,
                                })
        return rows


def _wiki(uow, teams, ps, pe):
        rows = []
        for team in teams:
                for article in uow.users.list_wiki_articles(team.team_id):
                        if _in_period(article.updated_at.date() if article.updated_at else None, ps, pe):
                                rows.append({
                                        "team_id": team.team_id,
                                        "title": article.title,
                                        "author_id": article.author_id,
                                })
        return rows