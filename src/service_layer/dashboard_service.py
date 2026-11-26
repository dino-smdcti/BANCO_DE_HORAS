"""Aggregates for the workforce data dashboard (charts rendered on the Painel).

Produces presentation-ready, JSON-serialisable series consumed by Chart.js on
the workforce landing page. Scoping follows the rest of the module: ADMIN/GESTOR
see every team, MANAGER their own, EMPLOYEE read-only their own.
"""
from collections import Counter, defaultdict

from src.config import BOARD_STAGES, IDEA_STATUSES, TASK_STATUS_LABELS
from src.service_layer.permissions import scoped_team_ids
from src.service_layer.unit_of_work import AbstractUnitOfWork

_IDEA_STATUS_LABELS = {
    "open": "Aberta",
    "under_review": "Em revisão",
    "implemented": "Implementada",
    "declined": "Recusada",
}


def dashboard_metrics(uow: AbstractUnitOfWork, actor_id: int) -> dict:
    """Return chart series for the workforce dashboard over the actor's scope."""
    with uow:
        scoped = set(scoped_team_ids(uow, actor_id))
        teams = [t for t in (uow.users.get_team_by_id(tid) for tid in scoped) if t]

        task_counts = Counter({stage: 0 for stage in BOARD_STAGES})
        idea_counts = Counter({status: 0 for status in IDEA_STATUSES})
        likes_by_team = []
        s5_trend = defaultdict(list)

        for team in teams:
            for task in uow.users.list_tasks_by_team(team.team_id):
                stage = _normalise_stage(task.status)
                if stage in task_counts:
                    task_counts[stage] += 1
            for idea in uow.users.list_ideas_by_team(team.team_id):
                if idea.status in idea_counts:
                    idea_counts[idea.status] += 1
            likes_by_team.append(
                {"label": team.name, "value": uow.users.count_kudos_by_team(team.team_id)}
            )
            for audit in uow.users.list_s5_audits_by_team(team.team_id):
                s5_trend[audit.date.strftime("%Y-%m")].append(audit.score)

        return {
            "task_stage_counts": [
                {"label": TASK_STATUS_LABELS[stage], "value": task_counts[stage]}
                for stage in BOARD_STAGES
            ],
            "idea_status_counts": [
                {"label": _IDEA_STATUS_LABELS.get(status, status), "value": idea_counts[status]}
                for status in IDEA_STATUSES
            ],
            "likes_by_team": likes_by_team,
            "s5_trend": [
                {"label": key, "avg": round(sum(values) / len(values), 1)}
                for key, values in sorted(s5_trend.items())
            ],
        }


def _normalise_stage(status):
    """Map legacy task statuses to the current board stages."""
    legacy = {"todo": "backlog", "in_progress": "in_execution"}
    return legacy.get(status, status)
