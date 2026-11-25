"""Per-employee metrics and consolidated bulk reports.

Reintroduces the filterable metrics panel (admin) that the Phase 4 refactor
dropped, adapted to the team-based model. Metrics mirror the domain balance
rules (worked / expected / missed / conceded / balance) for a chosen period.
"""
import io
from datetime import date
from typing import List, Optional

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from src.domain.model import PontoStatus, User, UserRole
from src.service_layer.unit_of_work import AbstractUnitOfWork

_CLOCKING_ROLES = (UserRole.EMPLOYEE, UserRole.MANAGER, UserRole.GESTOR)


def compute_period_metrics(user: User, start_date: date, end_date: date) -> dict:
        """Aggregate a user's worked/expected/missed/conceded/balance over a period."""
        metrics = {
                "worked_minutes": 0,
                "expected_minutes": 0,
                "missed_minutes": 0,
                "conceded_minutes": 0,
                "balance_minutes": 0,
                "days_counted": 0,
        }
        schedule = user.work_schedule
        if not schedule:
                return metrics

        target = schedule.daily_target_minutes()
        profile = user.profile

        for ponto in user.time_entries:
                day = ponto.entry_date
                if day < start_date or day > end_date:
                        continue
                if profile and profile.start_analysis_date and day < profile.start_analysis_date:
                        continue
                if not schedule.is_work_day(day):
                        continue
                if any(v.start_date <= day <= v.end_date for v in user.vacations):
                        continue

                metrics["days_counted"] += 1
                metrics["expected_minutes"] += target

                if ponto.status in (PontoStatus.MISSING, PontoStatus.REJECTED):
                        if ponto.status == PontoStatus.MISSING and (ponto.missing_approved or ponto.missing_excused):
                                metrics["conceded_minutes"] += target
                        else:
                                metrics["missed_minutes"] += target
                                metrics["balance_minutes"] -= target
                        continue

                if ponto.status in (PontoStatus.DISMISSED, PontoStatus.JUSTIFIED):
                        metrics["conceded_minutes"] += target
                        continue

                excused = _has_excused_anomaly(ponto)
                day_worked = ponto.get_predicted_worked_minutes(schedule) if excused else ponto.worked_minutes
                metrics["worked_minutes"] += day_worked
                metrics["balance_minutes"] += (day_worked - target)

        return metrics


def _has_excused_anomaly(ponto) -> bool:
        flags = [
                ponto.arrival_late_approved,
                ponto.lunch_start_late_approved,
                ponto.lunch_end_late_approved,
                ponto.departure_early_approved,
                ponto.lunch_start_early_approved,
                ponto.arrival_late_excused,
                ponto.lunch_start_late_excused,
                ponto.lunch_end_late_excused,
                ponto.departure_early_excused,
                ponto.lunch_start_early_excused,
        ]
        return any(flags)


def list_clocking_users(uow: AbstractUnitOfWork, team_id: Optional[int] = None) -> List[User]:
        """Users who punch the clock (employee/manager/gestor), optionally team-scoped."""
        users = [
                user for user in uow.users.list_all()
                if user.role in _CLOCKING_ROLES and user.is_active
        ]
        if team_id:
                users = [user for user in users if user.team_id == team_id]
        return sorted(users, key=lambda user: (user.profile.full_name or user.email).lower())


def team_name_for(uow: AbstractUnitOfWork, user: User) -> str:
        if user.team_id:
                team = uow.users.get_team_by_id(user.team_id)
                return team.name if team else "-"
        return "-"


def format_minutes(minutes: int) -> str:
        sign = "-" if minutes < 0 else ""
        value = abs(int(minutes))
        return f"{sign}{value // 60}h {value % 60:02d}m"


def generate_bulk_report_excel(uow: AbstractUnitOfWork, start_date: date, end_date: date, team_id: Optional[int] = None) -> io.BytesIO:
        """Consolidated per-employee metrics spreadsheet for a period."""
        with uow:
                users = list_clocking_users(uow, team_id)
                workbook = _build_bulk_workbook(uow, users, start_date, end_date)
        return workbook


def _build_bulk_workbook(uow, users, start_date, end_date):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Banco de Horas"

        title_font = Font(bold=True, size=14)
        header_font = Font(bold=True, size=10)
        value_font = Font(size=10)
        header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
        border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))

        sheet.merge_cells("A1:G1")
        sheet["A1"] = "RELATÓRIO DE BANCO DE HORAS"
        sheet["A1"].font = title_font
        sheet["A1"].alignment = Alignment(horizontal="center")

        sheet.merge_cells("A2:G2")
        sheet["A2"] = f"Período: {start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')}"
        sheet["A2"].font = value_font
        sheet["A2"].alignment = Alignment(horizontal="center")

        headers = ["Funcionário", "Matrícula", "Equipe", "Horas Trabalhadas", "Horas Faltantes", "Horas Concedidas", "Saldo"]
        for column, header in enumerate(headers, start=1):
                cell = sheet.cell(row=4, column=column, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.border = border
                cell.alignment = Alignment(horizontal="center")

        row = 5
        for user in users:
                metrics = compute_period_metrics(user, start_date, end_date)
                values = [
                        user.profile.full_name or user.email,
                        user.profile.registration_number or "-",
                        team_name_for(uow, user),
                        format_minutes(metrics["worked_minutes"]),
                        format_minutes(metrics["missed_minutes"]),
                        format_minutes(metrics["conceded_minutes"]),
                        format_minutes(metrics["balance_minutes"]),
                ]
                for column, value in enumerate(values, start=1):
                        cell = sheet.cell(row=row, column=column, value=value)
                        cell.font = value_font
                        cell.border = border
                        cell.alignment = Alignment(horizontal="center")
                row += 1

        for index, width in enumerate([32, 14, 18, 18, 16, 18, 14], start=1):
                sheet.column_dimensions[get_column_letter(index)].width = width

        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        return output
