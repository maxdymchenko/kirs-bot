"""Fill Google Sheet column D (Цвет/модель) from Excel characteristics."""

from __future__ import annotations

import sys
from pathlib import Path

import gspread
import openpyxl
from google.oauth2.service_account import Credentials

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXCEL_PATH = Path(r"C:\Users\brett\Downloads\export-products-15-07-26_10-31-25 (1).xlsx")
SHEET_NAME = "Export Products Sheet"
CREDS_PATH = Path(r"C:\Мой компьютер\Мои проекты(Программы)\Kirs_bot\midyear-respect-502706-i6-c5ddff36cd28.json")
SPREADSHEET_ID = "1HE1HmyuSevSIYBvk3UiRkoYZgRSdmGqH7ZvK6BFBBCg"

# Excel columns (1-based)
COL_GROUP = 19  # Название_группы
COL_ID = 25  # Уникальный_идентификатор
CHAR_NAME_COLS = list(range(52, 200, 3))  # 52, 55, 58, ...

WATCH_CATEGORIES = {"Женские часы", "Мужские часы"}


def extract_color(char_map: dict[str, str], category: str) -> str:
    """Apply category-specific color rules."""
    if category in WATCH_CATEGORIES:
        if "Цвет" in char_map and char_map["Цвет"]:
            return char_map["Цвет"]
        if "Цвет корпуса" in char_map and char_map["Цвет корпуса"]:
            return char_map["Цвет корпуса"]
        return ""

    # Корневая группа and all others: only exact "Цвет"
    return char_map.get("Цвет", "") or ""


def build_id_to_color() -> dict[str, str]:
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
    ws = wb[SHEET_NAME]

    result: dict[str, str] = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or len(row) < COL_ID:
            continue
        product_id = row[COL_ID - 1]
        if product_id is None:
            continue
        category = str(row[COL_GROUP - 1] or "").strip()

        char_map: dict[str, str] = {}
        for name_col in CHAR_NAME_COLS:
            name_idx = name_col - 1
            value_idx = name_col + 1  # name, measure, value
            if value_idx >= len(row):
                break
            name = row[name_idx]
            value = row[value_idx]
            if not name or value is None or value == "":
                continue
            name = str(name).strip()
            value = str(value).strip()
            # Keep first non-empty value for each characteristic name
            if name not in char_map:
                char_map[name] = value

        color = extract_color(char_map, category)
        result[str(product_id).strip()] = color

    wb.close()
    return result


def main() -> None:
    print("Читаю цвета из Excel...")
    id_to_color = build_id_to_color()
    with_color = sum(1 for v in id_to_color.values() if v)
    print(f"Товаров в Excel: {len(id_to_color)}, с цветом: {with_color}")

    creds = Credentials.from_service_account_file(
        str(CREDS_PATH),
        scopes=[
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ],
    )
    gc = gspread.authorize(creds)
    ws = gc.open_by_key(SPREADSHEET_ID).sheet1

    print("Читаю ID и текущие цвета из Google Sheet...")
    ids = ws.col_values(1)  # column A
    existing_colors = ws.col_values(4)  # column D

    # Pad existing_colors to same length as ids
    while len(existing_colors) < len(ids):
        existing_colors.append("")

    updates: list[list[str]] = []
    matched = 0
    filled = 0
    missing_in_excel = 0
    preserved = 0

    for i, raw_id in enumerate(ids):
        if i == 0:
            # Keep header
            updates.append([existing_colors[i] if existing_colors[i] else ""])
            continue

        product_id = str(raw_id).strip() if raw_id else ""
        current = existing_colors[i] if i < len(existing_colors) else ""

        if not product_id:
            # No ID — keep whatever is already in D (manual rows)
            updates.append([current])
            if current:
                preserved += 1
            continue

        if product_id not in id_to_color:
            updates.append([current])
            missing_in_excel += 1
            continue

        matched += 1
        color = id_to_color[product_id]
        if color:
            filled += 1
        updates.append([color])

    if len(updates) < 2:
        print("Нет данных для записи")
        return

    values = updates[1:]  # from row 2
    end_row = 1 + len(values)
    print(f"Пишу цвета в D2:D{end_row}...")
    ws.update(f"D2:D{end_row}", values, value_input_option="USER_ENTERED")

    print("Готово.")
    print(f"  Совпало по ID: {matched}")
    print(f"  Заполнено цветом: {filled}")
    print(f"  Без цвета (по правилам): {matched - filled}")
    print(f"  Сохранены старые строки без ID: {preserved}")
    print(f"  ID в таблице, нет в Excel: {missing_in_excel}")

    samples = []
    for i, row in enumerate(values[:30], start=2):
        if row[0] and ids[i - 1]:
            samples.append(f"  row {i}: {ids[i - 1]} -> {row[0]}")
    if samples:
        print("Примеры:")
        print("\n".join(samples[:5]))


if __name__ == "__main__":
    main()
