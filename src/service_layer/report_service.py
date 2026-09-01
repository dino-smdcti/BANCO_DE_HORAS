import io
from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter

from src.service_layer.unit_of_work import AbstractUnitOfWork
from src.service_layer.attendance_helpers import _require_user
from src.config import (
        MINUTES_PER_HOUR,
        REPORT_COLUMN_WIDTHS,
        REPORT_FIRST_DATA_ROW,
        REPORT_FONT_NAME,
        REPORT_HEADER_FILL_COLOR,
        REPORT_HEADER_FONT_SIZE,
        REPORT_HEADER_ROW,
        REPORT_LABEL_FONT_SIZE,
        REPORT_PERIOD_CELL,
        REPORT_PERIOD_END_COLUMN,
        REPORT_SHEET_NAME,
        REPORT_SIGNATURE_EMPLOYEE_COLUMNS,
        REPORT_SIGNATURE_GAP_ROWS,
        REPORT_SIGNATURE_MANAGER_COLUMNS,
        REPORT_TITLE_CELL,
        REPORT_TITLE_END_COLUMN,
        REPORT_TITLE_FONT_SIZE,
        REPORT_TITLE_TEXT,
        REPORT_VALUE_FONT_SIZE,
)

_SHEET_NAME = REPORT_SHEET_NAME
_COLUMN_WIDTHS = REPORT_COLUMN_WIDTHS

_REPORT_HEADERS = ["Data", "Chegada", "Saída Almoço", "Volta Almoço", "Fim Jornada", "Horas Trab.", "Status", "Observações"]


def generate_excel_report(uow: AbstractUnitOfWork, user_id: int, start_date: date = None, end_date: date = None) -> io.BytesIO:
        with uow:
                user = _require_user(uow, user_id)
                rows = _report_rows(user, start_date, end_date)
                period = _period_label(start_date, end_date)
                return _build_workbook(user, rows, period)


def _report_rows(user, start_date, end_date):
        return [_row_data(entry) for entry in _filter_entries(user.time_entries, start_date, end_date)]


def _filter_entries(entries, start_date, end_date):
        if start_date:
                entries = [entry for entry in entries if entry.entry_date >= start_date]
        if end_date:
                entries = [entry for entry in entries if entry.entry_date <= end_date]
        return sorted(entries, key=lambda entry: entry.entry_date)


def _row_data(entry):
        return {
                "Data": entry.entry_date.strftime("%d/%m/%Y"),
                "Chegada": _fmt_time(entry.arrival),
                "Saída Almoço": _fmt_time(entry.lunch_start),
                "Volta Almoço": _fmt_time(entry.lunch_end),
                "Fim Jornada": _fmt_time(entry.departure),
                "Horas Trab.": f"{entry.worked_minutes // MINUTES_PER_HOUR:02d}:{entry.worked_minutes % MINUTES_PER_HOUR:02d}",
                "Status": entry.status.value,
                "Observações": entry.notes or "",
        }


def _fmt_time(value):
        return value.strftime("%H:%M:%S") if value else "-"


def _period_label(start_date, end_date):
        if start_date and end_date:
                return f"{start_date.strftime('%d/%m/%Y')} até {end_date.strftime('%d/%m/%Y')}"
        if start_date:
                return f"A partir de {start_date.strftime('%d/%m/%Y')}"
        if end_date:
                return f"Até {end_date.strftime('%d/%m/%Y')}"
        return "Todo o período"


def _build_workbook(user, rows, period):
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = _SHEET_NAME
        styles = _report_styles()
        _write_column_headers(sheet, styles)
        _write_data_rows(sheet, rows, styles)
        _write_header(sheet, period, user, styles)
        _set_column_widths(sheet)
        _write_signatures(sheet, len(rows))
        output = io.BytesIO()
        workbook.save(output)
        output.seek(0)
        return output


def _report_styles():
        border = Border(left=Side(style="thin"), right=Side(style="thin"), top=Side(style="thin"), bottom=Side(style="thin"))
        return {
                "title": Font(name=REPORT_FONT_NAME, size=REPORT_TITLE_FONT_SIZE, bold=True),
                "header": Font(name=REPORT_FONT_NAME, size=REPORT_HEADER_FONT_SIZE, bold=True),
                "label": Font(name=REPORT_FONT_NAME, size=REPORT_LABEL_FONT_SIZE, bold=True),
                "value": Font(name=REPORT_FONT_NAME, size=REPORT_VALUE_FONT_SIZE),
                "border": border,
                "fill_header": PatternFill(start_color=REPORT_HEADER_FILL_COLOR, end_color=REPORT_HEADER_FILL_COLOR, fill_type="solid"),
        }


def _write_header(sheet, period, user, styles):
        _write_centered(sheet, REPORT_TITLE_CELL, REPORT_TITLE_END_COLUMN, REPORT_TITLE_TEXT, styles["title"])
        _write_centered(sheet, REPORT_PERIOD_CELL, REPORT_PERIOD_END_COLUMN, f"Período: {period}", styles["value"])
        for info in _employee_info(user):
                _write_info_row(sheet, info, styles)


def _write_centered(sheet, cell, end_column, text, font):
        sheet.merge_cells(f"{cell}:{end_column}{cell[1]}")
        sheet[cell] = text
        sheet[cell].font = font
        sheet[cell].alignment = Alignment(horizontal="center")


def _employee_info(user):
        profile = user.profile
        return [
                ("A3", "Funcionário:", "B3", profile.full_name or "Não informado", "E3", "Matrícula:", "F3", profile.registration_number or "-"),
                ("A4", "Cargo:", "B4", profile.position or "-", "E4", "Departamento:", "F4", profile.department or "-"),
                ("A5", "CPF:", "B5", _mask_cpf(profile.cpf), "E5", "Emitido em:", "F5", datetime.now().strftime("%d/%m/%Y %H:%M")),
        ]


def _mask_cpf(value):
        """Mask a CPF for LGPD compliance, revealing only the last two digits.

        e.g. "12345678901" -> "***.***.***-01". Returns "-" for empty/None.
        """
        if not value:
                return "-"
        digits = "".join(ch for ch in str(value) if ch.isdigit())[:11]
        if len(digits) < 2:
                return "-"
        return f"***.***.***-{digits[-2:]}"


def _write_info_row(sheet, info, styles):
        label_cell, label, value_cell, value, label2_cell, label2, value2_cell, value2 = info
        _write_cell(sheet, label_cell, label, styles["label"])
        _write_merged_value(sheet, value_cell, "D", value, styles["value"])
        _write_cell(sheet, label2_cell, label2, styles["label"])
        _write_merged_value(sheet, value2_cell, REPORT_TITLE_END_COLUMN, value2, styles["value"])


def _write_merged_value(sheet, cell, end_column, text, font):
        sheet.merge_cells(f"{cell}:{end_column}{cell[1]}")
        sheet[cell] = text
        sheet[cell].font = font


def _write_cell(sheet, cell, text, font):
        sheet[cell] = text
        sheet[cell].font = font


def _write_column_headers(sheet, styles):
        for column, header in enumerate(_REPORT_HEADERS, start=1):
                cell = sheet.cell(row=REPORT_HEADER_ROW, column=column, value=header)
                cell.font = styles["header"]
                cell.fill = styles["fill_header"]
                cell.border = styles["border"]
                cell.alignment = Alignment(horizontal="center")


def _write_data_rows(sheet, rows, styles):
        for offset, row in enumerate(rows):
                for column, header in enumerate(_REPORT_HEADERS):
                        cell = sheet.cell(row=REPORT_FIRST_DATA_ROW + offset, column=column + 1, value=row[header])
                        cell.font = styles["value"]
                        cell.border = styles["border"]
                        cell.alignment = Alignment(horizontal="center")


def _set_column_widths(sheet):
        for index, width in enumerate(_COLUMN_WIDTHS):
                sheet.column_dimensions[get_column_letter(index + 1)].width = width


def _write_signatures(sheet, row_count):
        signature_row = REPORT_HEADER_ROW + row_count + REPORT_SIGNATURE_GAP_ROWS
        _write_signature_block(sheet, REPORT_SIGNATURE_EMPLOYEE_COLUMNS[0], REPORT_SIGNATURE_EMPLOYEE_COLUMNS[1], signature_row, "Assinatura do Funcionário")
        _write_signature_block(sheet, REPORT_SIGNATURE_MANAGER_COLUMNS[0], REPORT_SIGNATURE_MANAGER_COLUMNS[1], signature_row, "Assinatura do Gestor / RH")


def _write_signature_block(sheet, start_column, end_column, row, label):
        line_cell = f"{start_column}{row}"
        sheet.merge_cells(f"{line_cell}:{end_column}{row}")
        sheet[line_cell].border = Border(top=Side(style="thin"))
        label_cell = f"{start_column}{row + 1}"
        sheet.merge_cells(f"{label_cell}:{end_column}{row + 1}")
        sheet[label_cell] = label
        sheet[label_cell].font = Font(name=REPORT_FONT_NAME, size=REPORT_VALUE_FONT_SIZE)
        sheet[label_cell].alignment = Alignment(horizontal="center")
