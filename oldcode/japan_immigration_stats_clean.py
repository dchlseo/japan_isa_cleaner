import pandas as pd
import json
import os
import re
from glob import glob
from openpyxl.utils import column_index_from_string
from datetime import datetime
from dateutil.relativedelta import relativedelta
from collections import Counter



def load_translation_dicts(dict_dir):
    with open(os.path.join(dict_dir, "japanese_to_korean_ports.json"), encoding="utf-8") as f:
        jp_to_kr_ports = json.load(f)
    with open(os.path.join(dict_dir, "japanese_to_english_ports.json"), encoding="utf-8") as f:
        jp_to_en_ports = json.load(f)
    with open(os.path.join(dict_dir, "japanese_to_korean_countries.json"), encoding="utf-8") as f:
        jp_to_kr_countries = json.load(f)
    with open(os.path.join(dict_dir, "japanese_to_english_countries.json"), encoding="utf-8") as f:
        jp_to_en_countries = json.load(f)
    return {
        "korean": (jp_to_kr_ports, jp_to_kr_countries),
        "english": (jp_to_en_ports, jp_to_en_countries),
    }


def _parse_filename(fname: str):
    base = os.path.basename(fname)

    # allow .xls or .xlsx
    ext_pat = r'(?:xls|xlsx)'

    m4 = re.match(rf'^(?P<yy>\d{{2}})-(?P<mm>\d{{2}})-(?P<seg3>\d{{1,2}})-(?P<seg4>\d{{1,2}})\.{ext_pat}$', base)
    if m4:
        yy, mm = m4.group('yy'), m4.group('mm')
        year_full = f"20{yy}" if int(yy) < 50 else f"19{yy}"
        return {"yy": yy, "mm": mm, "year_full": year_full, "pattern": "4seg"}

    m3 = re.match(rf'^(?P<yy>\d{{2}})-(?P<mm>\d{{2}})-(?P<seg3>\d{{1,2}})\.{ext_pat}$', base)
    if m3:
        yy, mm = m3.group('yy'), m3.group('mm')
        year_full = f"20{yy}" if int(yy) < 50 else f"19{yy}"
        return {"yy": yy, "mm": mm, "year_full": year_full, "pattern": "3seg"}

    raise ValueError(f"Unrecognized filename format: {base}")



def _resolve_cell_refs(file_name: str, yy: str, mm: str, year_full: str, cell_reference_map: dict | None):
    """
    Priority:
      1) exact filename key in cell_reference_map
      2) 'yy-mm' key in cell_reference_map (shared per-month rule, regardless of variant)
      3) fallback heuristic by year (<=2021 -> old layout; else new)
    """
    if cell_reference_map:
        if file_name in cell_reference_map:
            return cell_reference_map[file_name]["column"], cell_reference_map[file_name]["row"]
        ym_key = f"{yy}-{mm}"
        if ym_key in cell_reference_map:
            return cell_reference_map[ym_key]["column"], cell_reference_map[ym_key]["row"]

    # Fallback heuristic
    if int(year_full) <= 2021:
        return "D3", "B4"
    else:
        return "B4", "A5"


def _read_excel_any(path):
    base = os.path.basename(path).lower()
    try:
        if base.endswith(".xlsx"):
            return pd.read_excel(path, header=None, engine="openpyxl")
        elif base.endswith(".xls"):
            # requires xlrd installed (for .xls)
            return pd.read_excel(path, header=None, engine="xlrd")
        else:
            raise ValueError("Unsupported extension")
    except Exception as e:
        raise RuntimeError(f"Failed to read {base}: {e}")



def translate_excel(
    input_path: str,
    output_path: str,
    port_dict,
    country_dict,
    column_header_cell: str,
    row_header_cell: str
):
    # Read raw Excel file without headers
    # df = pd.read_excel(input_path, header=None)
    df = _read_excel_any(input_path)

    # Parse cell locations (supports A..Z only; extend if needed)
    col_row = int(column_header_cell[1:]) - 1
    col_start = column_index_from_string(column_header_cell[0]) - 1

    row_col = column_index_from_string(row_header_cell[0]) - 1
    row_start = int(row_header_cell[1:]) - 1

    # Translate column headers (e.g., ports/regions)
    raw_columns = df.iloc[col_row, col_start:]
    clean_columns = [str(c).replace("\n", "").replace("　", "").replace(" ", "").strip() for c in raw_columns]

    # Filter columns that contain "（空港）" after cleaning
    airport_mask = ["（空港）" in col for col in clean_columns]
    filtered_clean_columns = [col for col, keep in zip(clean_columns, airport_mask) if keep]

    # Normalize keys in the dictionary
    port_dict_keys_normalized = {k.replace("\n", "").replace("　", "").replace(" ", "").strip(): v for k, v in port_dict.items()}
    translated_columns = [port_dict_keys_normalized.get(c, c) for c in filtered_clean_columns]

    # Translate row headers (e.g., countries)
    raw_rows = df.iloc[row_start:, row_col]
    translated_rows = [
        country_dict.get(str(r).strip(), str(r).strip())
        for r in raw_rows
    ]

    # Filter the DataFrame to keep only airport columns
    df_trimmed = df.iloc[row_start:, col_start:]
    df_trimmed = df_trimmed.loc[:, airport_mask]
    df_trimmed.columns = translated_columns
    df_trimmed.insert(0, "Country", translated_rows)

    # Filter out rows where 'Country' still contains Japanese characters (Kanji, Hiragana, Katakana)
    df_trimmed = df_trimmed[~df_trimmed["Country"].str.contains(r'[\u3040-\u30ff\u4e00-\u9faf]', na=False)]

    # Save the translated version
    df_trimmed.to_excel(output_path, index=False)
    print(f"Translated Excel saved to: {output_path}")


def batch_translate_excels(
    input_dir: str,
    output_dir: str,
    dict_dir: str,
    lang: str = "korean",
    cell_reference_map: dict | None = None
):
    os.makedirs(output_dir, exist_ok=True)
    translation_dicts = load_translation_dicts(dict_dir)
    port_dict, country_dict = translation_dicts[lang]

    # excel_files = glob(os.path.join(input_dir, "*.xlsx"))
    # print(f'Found {len(excel_files)} Excel files in {input_dir}')
    # print(excel_files)

    excel_files = []
    excel_files += glob(os.path.join(input_dir, "*.xlsx"))
    excel_files += glob(os.path.join(input_dir, "*.xls"))
    excel_files.sort()  # stable order
    print(f"Found {len(excel_files)} Excel files in {input_dir}")
    print("First 10 files:", [os.path.basename(p) for p in excel_files[:10]])

    by_year = Counter()
    skipped = []

    for file_path in excel_files:
        file_name = os.path.basename(file_path)
        if not re.match(r"^\d", file_name):
            skipped.append((file_name, "non-numeric prefix"))
            continue

        try:
            meta = _parse_filename(file_name)
        except ValueError as e:
            print(f"[WARN] {e} — skipping.")
            skipped.append((file_name, "pattern not matched"))
            continue

        yy, mm, year_full = meta["yy"], meta["mm"], meta["year_full"]
        by_year[year_full] += 1

        try:
            column_header_cell, row_header_cell = _resolve_cell_refs(
                file_name=file_name, yy=yy, mm=mm, year_full=year_full, cell_reference_map=cell_reference_map
            )
            translate_excel(
                input_path=file_path,
                output_path=os.path.join(output_dir, f"foreign_inbound_japan_{year_full}_{mm}.xlsx"),
                port_dict=port_dict,
                country_dict=country_dict,
                column_header_cell=column_header_cell,
                row_header_cell=row_header_cell
            )
        except Exception as e:
            print(f"[ERROR] {file_name} failed: {e}")
            skipped.append((file_name, f"read/translate error: {e}"))

    print("Processed counts by year:", dict(sorted(by_year.items())))
    if skipped:
        print("Skipped files (reason):")
        for nm, rsn in skipped[:20]:
            print(f"  - {nm}: {rsn}")
        if len(skipped) > 20:
            print(f"  ... and {len(skipped)-20} more")

###### run batch usage:

## each file has different header cell locations (for yearly data. not used anymore)
# cell_map = {
#     "15-00-02.xlsx": {"column": "D3", "row": "B5"},
#     "16-00-02.xlsx": {"column": "D3", "row": "B5"},
#     "17-00-02.xlsx": {"column": "D3", "row": "B5"},
#     "18-00-02.xlsx": {"column": "D3", "row": "B5"},
#     "19-00-02.xlsx": {"column": "D3", "row": "B5"},
#     "20-00-02.xlsx": {"column": "D2", "row": "B4"},
#     "21-00-02.xlsx": {"column": "B2", "row": "A4"},
#     "22-00-02.xlsx": {"column": "B4", "row": "A5"},
#     "23-00-02.xlsx": {"column": "B4", "row": "A5"},
# }

# for monthly (manually checked)
# cell_map = {
#     "24-01-01-2.xlsx": {"column": "B4", "row": "A5"},
#     "24-02-01-2.xlsx": {"column": "B4", "row": "A5"},
# }

cell_map = {}

start_date = datetime(2013, 1, 1)
end_date = datetime(2025, 6, 1)

current = start_date
while current <= end_date:
    key = current.strftime("%y-%m-01-2.xlsx")
    if current.year <= 2021:
        cell_map[key] = {"column": "D3", "row": "B4"}
    else:
        cell_map[key] = {"column": "B4", "row": "A5"}
    current += relativedelta(months=1)

# # Optional: Print or inspect the first few
# for k in list(cell_map.keys())[:5]:
#     print(f"{k}: {cell_map[k]}")


batch_translate_excels(
    input_dir="../data/1_rawdata/japan_immigration_stats_RAW/monthly",
    output_dir="../data/2_cleaned_data/japan_immigration_stats_CLEAN/monthly",
    dict_dir="../data/1_rawdata/japan_immigration_stats_RAW",
    lang="korean",
    cell_reference_map=cell_map
)

