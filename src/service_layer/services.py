"""Facade re-exporting the service-layer use cases under the historic `services` namespace."""
from src.service_layer.attestation_service import add_attestation, remove_attestation_day
from src.service_layer.facultativo_service import add_facultativo
from src.service_layer.holiday_service import add_holiday, seed_holidays
from src.service_layer.settings_service import get_start_analysis_date
from src.service_layer.team_service import assign_user_team, create_team, list_team_members, list_teams
from src.service_layer.vacation_service import add_vacation, remove_vacation_day
from src.service_layer.clock_service import (
        clock_in_out,
        delete_ponto_entry,
        dismiss_justification,
        list_pending_corrections,
        manual_ponto_correction,
        remove_missing_excuse,
        review_anomaly_badge,
        review_correction_request,
        submit_correction_request,
)
from src.service_layer.notifications import add_notification, mark_notifications_as_read
from src.service_layer.permissions import ensure_manager, ensure_managed_user, ensure_not_self
from src.service_layer.report_service import generate_excel_report
from src.service_layer.schedule_service import (
        create_journey_type,
        delete_journey_type,
        get_journey_type,
        list_journey_types,
        set_work_schedule,
        update_journey_type,
)
from src.service_layer.retroactive_logs_service import complete_retroactive_logs
from src.service_layer.user_service import (
        delete_user,
        demote_to_employee,
        get_all_employees,
        promote_to_manager,
        register_user,
        update_credentials,
        update_user_profile,
)

__all__ = [
        "add_attestation",
        "assign_user_team",
        "complete_retroactive_logs",
        "add_facultativo",
        "add_holiday",
        "add_notification",
        "add_vacation",
        "clock_in_out",
        "create_journey_type",
        "create_team",
        "delete_journey_type",
        "delete_ponto_entry",
        "delete_user",
        "demote_to_employee",
        "dismiss_justification",
        "ensure_manager",
        "ensure_managed_user",
        "ensure_not_self",
        "generate_excel_report",
        "get_all_employees",
        "get_journey_type",
        "get_start_analysis_date",
        "list_journey_types",
        "list_pending_corrections",
        "list_team_members",
        "list_teams",
        "manual_ponto_correction",
        "mark_notifications_as_read",
        "promote_to_manager",
        "register_user",
        "remove_attestation_day",
        "remove_missing_excuse",
        "remove_vacation_day",
        "review_anomaly_badge",
        "review_correction_request",
        "seed_holidays",
        "set_work_schedule",
        "submit_correction_request",
        "update_credentials",
        "update_journey_type",
        "update_user_profile",
]
