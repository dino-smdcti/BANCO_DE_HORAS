import io

from openpyxl import load_workbook

from src.config import (
    REPORT_FIRST_DATA_ROW,
    REPORT_HEADER_ROW,
    REPORT_SHEET_NAME,
    REPORT_TITLE_TEXT,
)
from src.service_layer import services


def test_generate_excel_report_openpyxl_structure(uow):
    services.register_user(uow, "report@example.com", "password123")
    with uow:
        user = uow.users.get_user_by_email("report@example.com")
        user_id = user.user_id
    services.clock_in_out(uow, user_id, "Office")

    excel_file = services.generate_excel_report(uow, user_id)
    assert excel_file is not None
    assert excel_file.getbuffer().nbytes > 0

    workbook = load_workbook(io.BytesIO(excel_file.getbuffer()))
    assert REPORT_SHEET_NAME in workbook.sheetnames
    sheet = workbook[REPORT_SHEET_NAME]

    assert sheet["A1"].value == REPORT_TITLE_TEXT

    header_row = [sheet.cell(row=REPORT_HEADER_ROW, column=col).value for col in range(1, 9)]
    assert header_row == ["Data", "Chegada", "Saída Almoço", "Volta Almoço", "Fim Jornada", "Horas Trab.", "Status", "Observações"]

    assert sheet.cell(row=REPORT_FIRST_DATA_ROW, column=1).value is not None
    assert sheet.cell(row=REPORT_FIRST_DATA_ROW, column=6).value is not None