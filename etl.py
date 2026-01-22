import pandas as pd
import json
import os
import re
import shutil
import logging
import sys
from glob import glob
from openpyxl.utils import column_index_from_string
from datetime import datetime
from collections import Counter

# --- Configuration ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
CLEANED_DIR = os.path.join(DATA_DIR, "cleaned")
TEMP_DIR = os.path.join(DATA_DIR, "temp")
LOG_DIR = os.path.join(DATA_DIR, "log")
CONFIG_DIR = os.path.join(BASE_DIR, "configs")

# --- Logging Setup ---
def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(LOG_DIR, f"etl_{timestamp}.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info(f"Logging started. Log file: {log_file}")

# --- Helper Functions (Ported from oldcode) ---

def load_translation_dicts(dict_dir):
    try:
        with open(os.path.join(dict_dir, "japanese_to_korean_ports.json"), encoding="utf-8") as f:
            jp_to_kr_ports = json.load(f)
        with open(os.path.join(dict_dir, "japanese_to_english_ports.json"), encoding="utf-8") as f:
            jp_to_en_ports = json.load(f)
        with open(os.path.join(dict_dir, "japanese_to_korean_countries.json"), encoding="utf-8") as f:
            jp_to_kr_countries = json.load(f)
        with open(os.path.join(dict_dir, "japanese_to_english_countries.json"), encoding="utf-8") as f:
            jp_to_en_countries = json.load(f)
        
        logging.info("Translation dictionaries loaded successfully.")
        return {
            "korean": (jp_to_kr_ports, jp_to_kr_countries),
            "english": (jp_to_en_ports, jp_to_en_countries),
        }
    except Exception as e:
        logging.error(f"Failed to load translation dictionaries: {e}")
        raise

def _parse_filename(fname: str):
    base = os.path.basename(fname)
    ext_pat = r'(?:xls|xlsx)'

    m4 = re.match(rf'^(?P<yy>\d{{2}})-(?P<mm>\d{{2}})-(?P<seg3>\d{{1,2}})-(?P<seg4>\d{{1,2}})\.{ext_pat}$', base)
    if m4:
        yy, mm = m4.group('yy'), m4.group('mm')
        year_full = f"20{yy}" if int(yy) < 50 else f"19{yy}"
        return {"yy": yy, "mm": mm, "year_full": year_full}

    m3 = re.match(rf'^(?P<yy>\d{{2}})-(?P<mm>\d{{2}})-(?P<seg3>\d{{1,2}})\.{ext_pat}$', base)
    if m3:
        yy, mm = m3.group('yy'), m3.group('mm')
        year_full = f"20{yy}" if int(yy) < 50 else f"19{yy}"
        return {"yy": yy, "mm": mm, "year_full": year_full}

    raise ValueError(f"Unrecognized filename format: {base}")

def _resolve_cell_refs(year_full: str):
    # Fallback heuristic based on year
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
            return pd.read_excel(path, header=None, engine="xlrd")
        else:
            raise ValueError("Unsupported extension")
    except Exception as e:
        raise RuntimeError(f"Failed to read {base}: {e}")

# --- Core ETL Functions ---

def organize_raw_data():
    """Moves loose .xls/.xlsx files in RAW_DIR to a date-range specific subdirectory."""
    logging.info("Checking for loose raw data files...")
    
    files = glob(os.path.join(RAW_DIR, "*.xls")) + glob(os.path.join(RAW_DIR, "*.xlsx"))
    if not files:
        logging.info("No loose raw files found to organize.")
        return

    years = []
    months = []
    
    valid_files = []
    for f in files:
        try:
            meta = _parse_filename(os.path.basename(f))
            years.append(meta['year_full'])
            months.append(meta['mm'])
            valid_files.append(f)
        except ValueError:
            logging.warning(f"Skipping organization for unrecognized file: {os.path.basename(f)}")
            continue

    if not valid_files:
        logging.info("No valid files to organize.")
        return

    # Determine range
    # Create simple sortable YYYYMM integers
    dates = [int(y + m) for y, m in zip(years, months)]
    min_date = str(min(dates))
    max_date = str(max(dates))
    
    folder_name = f"{min_date}-{max_date}"
    target_dir = os.path.join(RAW_DIR, folder_name)
    os.makedirs(target_dir, exist_ok=True)
    
    logging.info(f"Organizing files into {target_dir}...")
    for f in valid_files:
        shutil.move(f, os.path.join(target_dir, os.path.basename(f)))
    
    logging.info(f"Moved {len(valid_files)} files to {target_dir}.")

def clean_data():
    """Iterates over all excel files in RAW_DIR (recursive), cleans them, and saves to TEMP_DIR."""
    os.makedirs(TEMP_DIR, exist_ok=True)
    
    # Load Dicts
    trans_dicts = load_translation_dicts(CONFIG_DIR)
    port_dict, country_dict = trans_dicts["korean"] # Defaulting to Korean as per legacy code
    
    # Find all files recursively
    all_files = glob(os.path.join(RAW_DIR, "**", "*.xls*"), recursive=True)
    # Filter out files in TEMP_DIR or CLEANED_DIR if they are somehow inside RAW_DIR (unlikely but safe)
    # Also ignore files in dict/config if they are somehow there.
    excel_files = [f for f in all_files if f.endswith(('.xls', '.xlsx')) and "dict" not in f]
    
    logging.info(f"Found {len(excel_files)} files to process.")
    
    processed_count = 0
    
    for file_path in excel_files:
        file_name = os.path.basename(file_path)
        
        try:
            meta = _parse_filename(file_name)
        except ValueError:
            logging.warning(f"Skipping non-data file: {file_name}")
            continue
            
        yy, mm, year_full = meta["yy"], meta["mm"], meta["year_full"]
        col_cell, row_cell = _resolve_cell_refs(year_full)
        
        try:
            df = _read_excel_any(file_path)
            
            # Parse headers
            col_row = int(col_cell[1:]) - 1
            col_start = column_index_from_string(col_cell[0]) - 1
            row_col = column_index_from_string(row_cell[0]) - 1
            row_start = int(row_cell[1:]) - 1
            
            # Columns (Airports)
            raw_columns = df.iloc[col_row, col_start:]
            clean_columns = [str(c).replace("\n", "").replace("　", "").replace(" ", "").strip() for c in raw_columns]
            airport_mask = ["（空港）" in col for col in clean_columns]
            filtered_cols = [col for col, keep in zip(clean_columns, airport_mask) if keep]
            
            # Dictionary Normalization
            port_norm = {k.replace("\n", "").replace("　", "").replace(" ", "").strip(): v for k, v in port_dict.items()}
            translated_cols = [port_norm.get(c, c) for c in filtered_cols]
            
            # Rows (Countries)
            raw_rows = df.iloc[row_start:, row_col]
            translated_rows = [country_dict.get(str(r).strip(), str(r).strip()) for r in raw_rows]
            
            # Trim & Construct
            df_trimmed = df.iloc[row_start:, col_start:]
            df_trimmed = df_trimmed.loc[:, airport_mask]
            df_trimmed.columns = translated_cols
            df_trimmed.insert(0, "Country", translated_rows)
            
            # Filter bad rows
            df_trimmed = df_trimmed[~df_trimmed["Country"].str.contains('[\u3040-\u30ff\u4e00-\u9faf]', na=False)]
            
            # Add metadata columns for merging later
            df_trimmed.insert(0, "Month", mm)
            df_trimmed.insert(0, "Year", year_full)

            # Deduplicate columns (Parquet requires unique names, and direct access fails on dupes)
            # We mangle duplicates (e.g. Name, Name.1) which allows merge_data to recognize and sum them later.
            if len(df_trimmed.columns) != len(set(df_trimmed.columns)):
                new_cols = pd.Series(df_trimmed.columns)
                for dup in new_cols[new_cols.duplicated()].unique():
                    mask = new_cols == dup
                    new_cols[mask] = [dup + (f".{i}" if i > 0 else "") for i in range(mask.sum())]
                df_trimmed.columns = new_cols

            # Save to temp
            temp_name = f"temp_{year_full}_{mm}.parquet"

            # Explicitly casting object columns to string to avoid parquet issues with mixed types
            for col in df_trimmed.columns:
                if df_trimmed[col].dtype == 'object':
                    df_trimmed[col] = df_trimmed[col].astype(str)
            
            df_trimmed.to_parquet(os.path.join(TEMP_DIR, temp_name), index=False)
            processed_count += 1
            
        except Exception as e:
            logging.error(f"Failed to process {file_name}: {e}")
            continue
            
    logging.info(f"Successfully cleaned and saved {processed_count} files to temporary storage.")

def merge_data():
    """Merges all parquet files in TEMP_DIR and saves output."""
    temp_files = glob(os.path.join(TEMP_DIR, "*.parquet"))
    if not temp_files:
        logging.warning("No temp files found to merge.")
        return

    logging.info(f"Merging {len(temp_files)} temporary files...")
    
    merged_data = []
    for f in temp_files:
        try:
            df = pd.read_parquet(f)
            merged_data.append(df)
        except Exception as e:
            logging.error(f"Failed to read temp file {f}: {e}")

    if not merged_data:
        logging.error("No data successfully loaded for merging.")
        return

    combined_df = pd.concat(merged_data, ignore_index=True, sort=True)
    
    # Post-merge duplicate column handling
    # Normalize naming
    combined_df.columns = combined_df.columns.str.strip().str.replace('\n', '').str.replace('　', '')
    
    # Handle duplicates (e.g. Airport, Airport.1)
    col_base_names = pd.Series(combined_df.columns).str.replace(r'\.\d+$', '', regex=True)
    col_map = dict(zip(combined_df.columns, col_base_names))
    dupes = col_base_names[col_base_names.duplicated()].unique()
    
    for base in dupes:
        cols_to_merge = [c for c, b in col_map.items() if b == base]
        if len(cols_to_merge) > 1:
            logging.info(f"Merging duplicated columns: {cols_to_merge} -> {base}")
            # Ensure numeric conversion before sum
            for c in cols_to_merge:
                combined_df[c] = pd.to_numeric(combined_df[c], errors='coerce').fillna(0)
            
            combined_df[base] = combined_df[cols_to_merge].sum(axis=1)
            combined_df.drop(columns=[c for c in cols_to_merge if c != base], inplace=True)

    # Determine date range for filename
    try:
        years = pd.to_numeric(combined_df["Year"], errors='coerce')
        months = pd.to_numeric(combined_df["Month"], errors='coerce')
        
        valid_date_mask = years.notna() & months.notna()
        if valid_date_mask.any():
            min_idx = (years[valid_date_mask] * 100 + months[valid_date_mask]).idxmin()
            max_idx = (years[valid_date_mask] * 100 + months[valid_date_mask]).idxmax()
            
            start_str = f"{int(years[min_idx])}{int(months[min_idx]):02d}"
            end_str = f"{int(years[max_idx])}{int(months[max_idx]):02d}"
        else:
            start_str, end_str = "unknown", "unknown"
    except Exception as e:
        logging.warning("Could not determine date range from data.")
        start_str, end_str = "unknown", "unknown"

    os.makedirs(CLEANED_DIR, exist_ok=True)
    base_name = f"japan_isa_nationality_by_airport_{start_str}-{end_str}"
    
    # Create subdirectory for this specific output
    output_subdir = os.path.join(CLEANED_DIR, base_name)
    os.makedirs(output_subdir, exist_ok=True)
    
    # Ensure all value columns are numeric before saving
    # This prevents mixed-type errors in Parquet and ensures cleaner CSVs
    id_vars = ["Year", "Month", "Country"]
    value_vars = [c for c in combined_df.columns if c not in id_vars]

    for col in value_vars:
        combined_df[col] = pd.to_numeric(combined_df[col], errors='coerce').fillna(0)

    # Save Wide
    wide_path = os.path.join(output_subdir, f"{base_name}_wide.csv")
    combined_df.to_csv(wide_path, index=False, encoding="utf-8-sig")
    logging.info(f"Saved wide format to {wide_path}")

    wide_parquet = os.path.join(output_subdir, f"{base_name}_wide.parquet")
    combined_df.to_parquet(wide_parquet, index=False)
    logging.info(f"Saved wide format to {wide_parquet}")

    # Save Long
    id_vars = ["Year", "Month", "Country"]
    value_vars = [c for c in combined_df.columns if c not in id_vars]
    
    long_df = combined_df.melt(id_vars=id_vars, value_vars=value_vars, var_name="Airport", value_name="Value")
    
    # Ensure Value is numeric (redundant but safe)
    long_df["Value"] = pd.to_numeric(long_df["Value"], errors='coerce').fillna(0)

    long_path = os.path.join(output_subdir, f"{base_name}_long.csv")
    long_df.to_csv(long_path, index=False, encoding="utf-8-sig")
    logging.info(f"Saved long format to {long_path}")

    long_parquet = os.path.join(output_subdir, f"{base_name}_long.parquet")
    long_df.to_parquet(long_parquet, index=False)
    logging.info(f"Saved long format to {long_parquet}")
    
    # Cleanup Temp
    logging.info("Cleaning up temporary files...")
    shutil.rmtree(TEMP_DIR)
    logging.info("Etl process completed successfully.")

def main():
    setup_logging()
    logging.info("Starting ETL process...")
    
    try:
        organize_raw_data()
        clean_data()
        merge_data()
    except Exception as e:
        logging.critical(f"ETL process failed: {e}", exc_info=True)

if __name__ == "__main__":
    main()
