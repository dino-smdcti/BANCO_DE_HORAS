from src.domain.model import S5Audit, S5Item
from src.service_layer.audit import log_action
from src.service_layer.permissions import managed_team_ids, scoped_team_ids
from src.service_layer.unit_of_work import AbstractUnitOfWork

DEFAULT_S5_ITEMS = [
        "Seiri: apenas itens necessários no local",
        "Seiton: tudo em seu devido lugar identificado",
        "Seiso: limpeza e inspeção asseguradas",
        "Seiketsu: padrão e rotina visual mantidos",
        "Shitsuke: disciplina e autodisciplina no padrão",
]


def _ensure_manager_scope(uow, actor_id, team_id):
        if int(team_id) not in set(managed_team_ids(uow, actor_id)):
                raise PermissionError("Ação restrita ao seu time.")


def create_s5_audit(
        uow: AbstractUnitOfWork,
        actor_id: int,
        *,
        team_id: int,
        date,
        passed_ids=None,
        notes: str = None,
) -> S5Audit:
        with uow:
                _ensure_manager_scope(uow, actor_id, team_id)
                if not date:
                        raise ValueError("A data da auditoria é obrigatória.")
                passed_ids = set(passed_ids or [])
                audit = S5Audit(team_id=int(team_id), date=date, auditor_id=actor_id, notes=(notes or "").strip() or None)
                uow.users.add_s5_audit(audit)
                uow.commit()
                items: list[S5Item] = []
                for index, label in enumerate(DEFAULT_S5_ITEMS):
                        item = S5Item(s5_audit_id=audit.s5_audit_id, label=label, passed=(index in passed_ids))
                        uow.users.add_s5_item(item)
                        items.append(item)
                passed = sum(1 for i in items if i.passed)
                total = len(items)
                score = round((passed / total) * 100, 1) if total else 0.0
                uow.users.update_s5_score(audit.s5_audit_id, score)
                uow.commit()
                log_action(uow, actor_id, "CREATE_S5_AUDIT", target_id=audit.s5_audit_id, details=f"Time {team_id} 5S score {score}")
                return audit


def list_s5_audits(uow: AbstractUnitOfWork, actor_id: int, team_id: int = None) -> list[S5Audit]:
        with uow:
                if team_id is not None:
                        if int(team_id) not in set(scoped_team_ids(uow, actor_id)):
                                raise PermissionError("Ação restrita ao seu time.")
                        return uow.users.list_s5_audits_by_team(int(team_id))
                result: list[S5Audit] = []
                for tid in set(scoped_team_ids(uow, actor_id)):
                        result.extend(uow.users.list_s5_audits_by_team(tid))
                return result


def get_s5_average(uow: AbstractUnitOfWork, actor_id: int, team_id: int) -> float:
        with uow:
                if int(team_id) not in set(scoped_team_ids(uow, actor_id)):
                        raise PermissionError("Ação restrita ao seu time.")
                return uow.users.average_s5_score_by_team(int(team_id))


def delete_s5_audit(uow: AbstractUnitOfWork, actor_id: int, s5_audit_id: int):
        with uow:
                audit = uow.users.get_s5_audit_by_id(s5_audit_id)
                if not audit:
                        raise ValueError("Auditoria não encontrada.")
                _ensure_manager_scope(uow, actor_id, audit.team_id)
                uow.users.delete_s5_audit(s5_audit_id)
                uow.commit()
                log_action(uow, actor_id, "DELETE_S5_AUDIT", target_id=s5_audit_id, details="Auditoria 5S excluída")