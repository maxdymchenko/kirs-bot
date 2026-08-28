"""Delete product rows by code — filter and rewrite sheet (quota-friendly)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CREDS_PATH = Path(r"C:\Мой компьютер\Мои проекты(Программы)\Kirs_bot\midyear-respect-502706-i6-c5ddff36cd28.json")
SPREADSHEET_ID = "1HE1HmyuSevSIYBvk3UiRkoYZgRSdmGqH7ZvK6BFBBCg"

RAW_CODES = """
059, 067, 059, 061, 037, 038, 047, 083, 086, 106, 111, 112, 113, 115, 117, 122, 124, 125, 135, 136, 138, 148, 151, 152, 158, 160, 161, 168, 169, 170, 174, 192, 203, 206, 207, 208, 209, 223, 232, 236, 239, 241, 242, 254, 255, 285, 299, 300, 306, 310, 312, 320, 327, 329, 331, 336, 338, 347, 352, 358, 377, 380, 383, 384, 396, 398, 404, 406,  411, 416, 421, 423, 432, 436, 449, 452, 442, 443, 454, 462, 465, 468, 469, 478, 481, 482, 491, 496, 500, 503, 504, 505, 511, 512, 514, 516, 517, 522, 528, 530, 535, 538, 536,  546, 548, 550, 551, 556, 558, 555, 569, 570, 571, 572, 57, 588, 590, 591, 592, 593, 594, 595, 597, 598, 601, 602, 604, 612,619, 621, 622, 627, 629, 630, 632, 651, 658, 660, 670, 672, 674, 679, 681, 682, 686, 692, 694, 702, 704, 706, 711, 717, 718,  720, 721, 724, 725, 737, 738, 740, 742, 746, 752, 755, 756, 777, 777, 784, 789, 791, 792,795, 796, 818, 828, 829, 840, 843, 801, 807, 808, 809, 810, 813, 848, 851, 852, 854, 856, 859, 862, 866, 871, 872, 896, 899, 904, 905, 907, 908, 909, 910, 916, 921, 925, 926, 932, 934, 935, 946, 952, 958, 959, 965, 966, 961, 969, 976, 977, 978, 979, 980, 987, 999, 1005, 1022, 1027, 1036, 1038, 1039, 1040, 1046, 1053, 1054, 1058, 1066, 1070, 1071, 1083, 1089, 1090, 1091, 1092, 1111, 1112, 1115, 1120, 1121, 1129, 1131, 1132, 1137, 1151, 1152, 1153, 1155, 1156, 1157, 1163, 1165, 1166, 1167, 1168, 1169, 1170, 1172, 1177, 1184, 1193, 1202, 1204, 1253, 1255, 1266, 1268, 1269, 1271, 1272, 1273, 1276, 1285, 1302, 1305, 1314, 1315, 1317, 1318, 1319, 1322, 1323, 1328, 1333, 1347, 1348, 1357, 1358, 1359, 1360, 1361, 1378, 1379, 1380, 1381, 1382, 1383, 1384, 1385, 1388, 1389, 1391, 1392, 1393, 1394, 1395, 1397, 1435, 1445, 1446, 1467, 1505, 1526, 1553, 1604, 1605, 1607, 1649, 1672, 1673, 1706, 1777
"""


def normalize(code: str) -> str:
    code = str(code).strip().lstrip("'")
    return code.lstrip("0") or "0"


def parse_codes(raw: str) -> set[str]:
    parts = [p.strip() for p in raw.replace("\n", ",").split(",")]
    return {p for p in parts if p}


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
    delete_raw = parse_codes(RAW_CODES)
    delete_norm = {normalize(c) for c in delete_raw}
    print(f"Кодов в списке: {len(delete_raw)}")

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
    if not all_rows:
        print("Таблица пуста")
        return

    header = all_rows[0]
    kept = [header]
    removed = 0
    matched_codes: set[str] = set()
    code_col = 1  # column B index

    for row in all_rows[1:]:
        code = row[code_col] if len(row) > code_col else ""
        clean = str(code).strip().lstrip("'") if code else ""
        if clean and (clean in delete_raw or normalize(clean) in delete_norm):
            removed += 1
            matched_codes.add(clean)
            continue
        # pad row to header width
        if len(row) < len(header):
            row = row + [""] * (len(header) - len(row))
        kept.append(row[: len(header)])

    print(f"Было строк данных: {len(all_rows) - 1}")
    print(f"Удаляем сейчас: {removed}")
    print(f"Останется: {len(kept) - 1}")
    print(f"Уникальных кодов среди удаляемых: {len(matched_codes)}")

    if removed == 0:
        print("Нечего удалять — список уже очищен.")
        return

    # Force product codes as text so leading zeros stay
    for row in kept[1:]:
        if len(row) > 1 and row[1]:
            code = str(row[1]).lstrip("'")
            row[1] = f"'{code}"

    print("Очищаю лист и записываю обратно...")
    with_retry(lambda: ws.clear())
    # Write in chunks to avoid payload limits
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
    print(f"Удалено строк в этом прогоне: {removed}")
    print(f"Строк в таблице сейчас: {len(kept) - 1} (+ заголовок)")


if __name__ == "__main__":
    main()
