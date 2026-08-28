"""Delete letter-suffixed product codes, keeping exceptions."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CREDS_PATH = Path(
    r"C:\Мой компьютер\Мои проекты(Программы)\Kirs_bot\midyear-respect-502706-i6-c5ddff36cd28.json"
)
SPREADSHEET_ID = "1HE1HmyuSevSIYBvk3UiRkoYZgRSdmGqH7ZvK6BFBBCg"

KEEP = {
    "612Б",
    "612БЕ",
    "612Ж",
    "612КБ",
    "612М",
    "612Н",
    "612Р",
    "612ЧБ",
    "1169М",
}

DELETE_CODES = {
    "207Д",
    "208А",
    "208К",
    "208М",
    "208Т",
    "208Ч",
    "223А",
    "236К",
    "236С",
    "329Б",
    "329В",
    "347А",
    "347Б",
    "347В",
    "347Г",
    "347Д",
    "347Е",
    "384М",
    "384Р",
    "384С",
    "396Х",
    "406А",
    "406Г",
    "406М",
    "411А",
    "411В",
    "462Р",
    "504А",
    "504К",
    "504П",
    "504Р",
    "504С",
    "505Ж",
    "505М",
    "505С",
    "505Ч",
    "514А",
    "514В",
    "516А",
    "516Б",
    "516Д",
    "516Ж",
    "516Л",
    "516Т",
    "516ТБ",
    "516ТЧ",
    "516Ч",
    "555А",
    "555Б",
    "555Д",
    "555ДБ",
    "555ДВ",
    "556К",
    "558Б",
    "558И",
    "570А",
    "570Б",
    "570К",
    "571Г",
    "571Р",
    "571С",
    "571Ч",
    "590А",
    "590Б",
    "590В",
    "590Г",
    "592А",
    "592Б",
    "592В",
    "594Б",
    "594В",
    "595Б",
    "595В",
    "595Г",
    "597К",
    "597Ч",
    "598К",
    "601Ч",
    "602С",
    "621К",
    "621М",
    "621Ч",
    "629К",
    "629Ф",
    "629Ч",
    "632К",
    "672Б",
    "672М",
    "672ТТ",
    "682Ч",
    "692К",
    "694СК",
    "694ТК",
    "694Ч",
    "737Ж",
    "737Р",
    "737С",
    "737Ч",
    "738Б",
    "738К",
    "738Ч",
    "740А",
    "740В",
    "791М",
    "791Ч",
    "796С",
    "796Ч",
    "813К",
    "813Н",
    "813Т",
    "896СК",
    "896ТК",
    "896Ч",
    "932Г",
    "932Р",
    "959-1К",
    "966К",
    "966КР",
    "966Ч",
    "987Х",
    "999Х",
    "1022Б",
    "1022М",
    "1053Г",
    "1058К",
    "1070СК",
    "1070ТК",
    "1089КР",
    "1120Г",
    "1120Р",
    "1137Д",
    "1168ГГ",
    "1168ГФ",
    "1168МФ",
    "1184ГЧ",
    "1184КЛ",
    "1184ЛВ",
    "1202Б",
    "1253СК",
    "1253ТК",
    "1255Д",
    "1255С",
    "1255Т",
    "1268Б",
    "1268Ч",
    "1269Б",
    "1269С",
    "1285Д",
    "1305Ж",
    "1305Р",
    "1305Ч",
    "1333+Р",
    "1348КЛ",
    "1388Ж",
    "1388М",
    "1445К",
    "1446К",
    "1526С",
}

# Safety: never delete KEEP codes even if somehow listed
DELETE_CODES -= KEEP


def with_retry(fn, retries: int = 8):
    for attempt in range(retries):
        try:
            return fn()
        except APIError as exc:
            if "429" not in str(exc) and "Quota" not in str(exc):
                raise
            wait = 15 * (attempt + 1)
            print(f"Квота API, жду {wait} сек...")
            time.sleep(wait)
    return fn()


def main() -> None:
    print(f"К удалению кодов: {len(DELETE_CODES)}")
    print(f"Сохраняем: {', '.join(sorted(KEEP))}")

    creds = Credentials.from_service_account_file(
        str(CREDS_PATH),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).sheet1

    print("Читаю таблицу...")
    all_rows = with_retry(lambda: ws.get_all_values())
    header = all_rows[0]
    kept = [header]
    removed = 0
    matched: set[str] = set()
    kept_exceptions: set[str] = set()

    for row in all_rows[1:]:
        code = row[1].strip().lstrip("'") if len(row) > 1 and row[1] else ""
        if code in KEEP:
            kept_exceptions.add(code)
            if len(row) < len(header):
                row = row + [""] * (len(header) - len(row))
            kept.append(row[: len(header)])
            continue
        if code in DELETE_CODES:
            removed += 1
            matched.add(code)
            continue
        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))
        kept.append(row[: len(header)])

    print(f"Было строк: {len(all_rows) - 1}")
    print(f"Удаляем: {removed}")
    print(f"Останется: {len(kept) - 1}")
    print(f"Найдено кодов к удалению: {len(matched)}")
    print(f"Сохранённые исключения в таблице: {sorted(kept_exceptions)}")

    not_found = sorted(DELETE_CODES - matched)
    if not_found:
        print(f"Не найдено в таблице ({len(not_found)}): {', '.join(not_found[:40])}"
              + (" ..." if len(not_found) > 40 else ""))

    if removed == 0:
        print("Нечего удалять.")
        return

    for row in kept[1:]:
        if len(row) > 1 and row[1]:
            code = str(row[1]).lstrip("'")
            row[1] = f"'{code}"

    print("Очищаю лист и записываю обратно...")
    with_retry(lambda: ws.clear())
    chunk = 1000
    for start in range(0, len(kept), chunk):
        part = kept[start : start + chunk]
        start_row = start + 1
        end_row = start + len(part)
        print(f"  Пишу строки {start_row}-{end_row}...")
        with_retry(
            lambda part=part, start_row=start_row: ws.update(
                values=part,
                range_name=f"A{start_row}",
                value_input_option="USER_ENTERED",
            )
        )
        time.sleep(1)

    print("Готово.")
    print(f"Удалено строк: {removed}")
    print(f"Строк сейчас: {len(kept) - 1}")


if __name__ == "__main__":
    main()
