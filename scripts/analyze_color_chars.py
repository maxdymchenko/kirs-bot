import re
import sys
from collections import defaultdict
from pathlib import Path

import openpyxl

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EXCEL_PATH = Path(r"C:\Users\brett\Downloads\export-products-15-07-26_10-31-25 (1).xlsx")
SHEET = "Export Products Sheet"

COLOR_PATTERN = re.compile(r"цвет|color|колір", re.IGNORECASE)


def main() -> None:
    wb = openpyxl.load_workbook(EXCEL_PATH, read_only=True, data_only=True)
    ws = wb[SHEET]

    # Columns (1-based): S=19 group, T=20 subgroup, Y=25 id
    GROUP_COL = 19
    SUBGROUP_COL = 20

    # Characteristic triplets start at col 52
    char_name_cols = list(range(52, 200, 3))  # 52, 55, 58, ...

    cat_color_names: dict[str, set[str]] = defaultdict(set)
    cat_product_count: dict[str, int] = defaultdict(int)
    cat_subgroup: dict[str, set[str]] = defaultdict(set)

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or len(row) < GROUP_COL:
            continue
        group = row[GROUP_COL - 1]
        if not group:
            continue
        cat = str(group).strip()
        cat_product_count[cat] += 1

        if row[SUBGROUP_COL - 1]:
            cat_subgroup[cat].add(str(row[SUBGROUP_COL - 1]).strip())

        for col_idx in char_name_cols:
            if col_idx - 1 >= len(row):
                break
            char_name = row[col_idx - 1]
            if not char_name:
                continue
            char_name = str(char_name).strip()
            if COLOR_PATTERN.search(char_name):
                cat_color_names[cat].add(char_name)

    wb.close()

    # Sort categories by product count desc
    categories = sorted(cat_product_count.keys(), key=lambda c: (-cat_product_count[c], c))

    print("=" * 80)
    print("КАТЕГОРИИ И ВАРИАНТЫ НАЗВАНИЙ ХАРАКТЕРИСТИК «ЦВЕТ»")
    print("=" * 80)
    print(f"Всего категорий: {len(categories)}")
    print(f"Категорий с цветовыми характеристиками: {sum(1 for c in categories if cat_color_names.get(c))}")
    print()

    for i, cat in enumerate(categories, 1):
        color_names = sorted(cat_color_names.get(cat, set()))
        subgroups = sorted(cat_subgroup.get(cat, set()))
        count = cat_product_count[cat]

        print(f"{i}. {cat}")
        print(f"   Товаров: {count}")
        if subgroups:
            print(f"   Подразделы: {', '.join(subgroups[:5])}" + (" ..." if len(subgroups) > 5 else ""))
        if color_names:
            print(f"   Варианты названия «цвет»:")
            for name in color_names:
                print(f"      • {name}")
        else:
            print("   ⚠ Цветовая характеристика НЕ найдена")
        print()

    # Summary: all unique color characteristic names across file
    all_color_names: set[str] = set()
    for names in cat_color_names.values():
        all_color_names.update(names)

    print("=" * 80)
    print("ВСЕ УНИКАЛЬНЫЕ НАЗВАНИЯ ЦВЕТОВЫХ ХАРАКТЕРИСТИК В ФАЙЛЕ:")
    print("=" * 80)
    for name in sorted(all_color_names):
        cats_with = [c for c in categories if name in cat_color_names.get(c, set())]
        print(f"  • {name}  ({len(cats_with)} категорий)")


if __name__ == "__main__":
    main()
