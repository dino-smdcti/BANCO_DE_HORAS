"""Executive KPI dashboard (workforce vertical A7).

Aggregates cross-team indicators for leadership: members, tasks in-flight,
ideas implemented, accomplishments, average 5S score, and kudos per team.
Scoping follows F0: ADMIN/GESTOR see all, MANAGER own team, EMPLOYEE read-only
own team (list_exec_kpis is read-only, so employees can view their team).
"""
from src.service_layer.permissions import scoped_team_ids
from src.service_layer.unit_of_work import AbstractUnitOfWork


def list_exec_kpis(uow: AbstractUnitOfWork, actor_id: int, *, period_start=None, period_end=None) -> list:
        """Return a per-team KPI rollup visible to the actor."""
        with uow:
                scoped = set(scoped_team_ids(uow, actor_id))
                teams = [uow.users.get_team_by_id(t) for t in scoped]
                result = []
                for team in teams:
                        if not team:
                                continue
                        accomplishments = uow.users.list_accomplishments_by_team(team.team_id)
                        if period_start or period_end:
                                accomplishments = _filter_accomplishments(accomplishments, period_start, period_end)
                        result.append(
                                {
                                        "team_id": team.team_id,
                                        "name": team.name,
                                        "secretariat": team.secretariat,
                                        "lead_user_id": team.lead_user_id,
                                        "members": uow.users.count_team_members(team.team_id),
                                        "open_tasks": uow.users.count_open_tasks_by_team(team.team_id),
                                        "open_ideas": uow.users.count_open_ideas_by_team(team.team_id),
                                        "implemented_ideas": uow.users.count_implemented_ideas_by_team(team.team_id),
                                        "accomplishments": len(accomplishments),
                                        "avg_5s": round(uow.users.average_s5_score_by_team(team.team_id) or 0.0, 1),
                                        "kudos": uow.users.count_kudos_by_team(team.team_id),
                                }
                        )
                return result


def _filter_accomplishments(accomplishments, period_start, period_end) -> list:
        def _kept(acc):
                acc_start = acc.start_date
                acc_end = acc.end_date if acc.end_date is not None else acc_start
                if acc_start is None:
                        return True
                if period_start is not None and acc_end < period_start:
                        return False
                if period_end is not None and acc_start > period_end:
                        return False
                return True
        return [a for a in accomplishments if _kept(a)]