import pandas as pd
import os
import re
from glob import glob

# Define paths
input_dir = "../data/2_cleaned_data/japan_immigration_stats_CLEAN/monthly"
output_path = "../data/2_cleaned_data/japan_immigration_stats_CLEAN/japan_isa_nationality_by_airport_201301-202506.xlsx"

def extract_year_month_from_filename(filename):
    match = re.search(r"foreign_inbound_japan_(\d{4})_(\d{2})", filename)
    if match:
        return match.group(1), match.group(2)
    else:
        return None, None

def merge_cleaned_files(input_dir):
    all_files = glob(os.path.join(input_dir, "foreign_inbound_japan_*.xlsx"))
    merged_data = []

    for file_path in all_files:
        file_name = os.path.basename(file_path)
        year, month = extract_year_month_from_filename(file_name)
        if not year or not month:
            print(f"❌ Skipping invalid file name: {file_name}")
            continue

        df = pd.read_excel(file_path)

        # Normalize column names to avoid hidden issues
        df.columns = df.columns.str.strip().str.replace('\n', '').str.replace('　', '')  # remove full-width spaces too

        # print(f"📄 Columns in {file_name}: {df.columns.tolist()}")

        # Handle duplicate columns (like '후쿠이 (공항)' and '후쿠이 (공항).1')
        column_base_names = pd.Series(df.columns).str.replace(r'\.\d+$', '', regex=True)
        colname_to_basename = dict(zip(df.columns, column_base_names))
        duplicated_bases = column_base_names[column_base_names.duplicated()].unique()

        for base_col in duplicated_bases:
            dupes = [col for col, base in colname_to_basename.items() if base == base_col]
            if len(dupes) > 1:
                print(f"🔁 Merging duplicated columns in {file_name}: {dupes}")
                df[base_col] = df[dupes].sum(axis=1)
                df.drop(columns=[col for col in dupes if col != base_col], inplace=True)

        # Add Year and Month columns
        df.insert(0, "Month", month)
        df.insert(0, "Year", year)

        # Append to list
        merged_data.append(df)

    if merged_data:
        combined_df = pd.concat(merged_data, ignore_index=True, sort=True)
        print(f"\n✅ Combined dataframe columns: {combined_df.columns.tolist()}")

        # Save wide format
        wide_output_path = output_path.replace(".xlsx", "_wide.xlsx")
        combined_df.to_excel(wide_output_path, index=False)
        print(f"✅ Wide-format merged file saved to: {wide_output_path}")

        # Unpivot to long format
        id_vars = ["Year", "Month", "Country"]
        value_vars = [col for col in combined_df.columns if col not in id_vars]

        long_df = combined_df.melt(
            id_vars=id_vars,
            value_vars=value_vars,
            var_name="Airport",
            value_name="Value"
        )

        # Save long format as CSV (existing)
        long_output_path = output_path.replace(".xlsx", "_long.csv")
        long_df.to_csv(long_output_path, index=False, encoding="utf-8-sig")
        print(f"✅ Long-format merged CSV saved to: {long_output_path}")

        # ---- NEW: Save long format as Parquet (snappy) ----
        # (optional) shrink text columns a bit by categorizing
        for col in ["Country", "Airport"]:
            if col in long_df.columns and long_df[col].dtype == "object":
                long_df[col] = long_df[col].astype("category")

        long_parquet_path = output_path.replace(".xlsx", "_long.parquet")
        try:
            long_df.to_parquet(long_parquet_path, engine="pyarrow", compression="snappy", index=False)
            print(f"✅ Long-format merged Parquet saved to: {long_parquet_path} (snappy)")
        except Exception as e:
            # Fallback if pyarrow isn't available
            try:
                long_df.to_parquet(long_parquet_path, engine="fastparquet", compression="snappy", index=False)
                print(f"✅ Long-format merged Parquet saved to: {long_parquet_path} (snappy, fastparquet)")
            except Exception as e2:
                print(f"⚠️ Failed to write Parquet with pyarrow ({e}) and fastparquet ({e2}). Skipping Parquet save.")

        # Summary period print
        data_shape = long_df.shape

        # Ensure Year/Month are numeric (handles strings like "2025", "06")
        long_df["Year"]  = pd.to_numeric(long_df["Year"], errors="coerce")
        long_df["Month"] = pd.to_numeric(long_df["Month"], errors="coerce")

        # Keep only rows with valid year & month
        mask = long_df["Year"].notna() & long_df["Month"].notna()
        p = pd.PeriodIndex(
            year=long_df.loc[mask, "Year"].astype(int),
            month=long_df.loc[mask, "Month"].astype(int),
            freq="M"
        )

        start_str = p.min().strftime("%Y-%m")
        end_str   = p.max().strftime("%Y-%m")

        print(f"\n📊 Merged data shape: {data_shape}, covering period: {start_str} to {end_str}")

    else:
        print("⚠️ No valid files found for merging.")


if __name__ == "__main__":
    merge_cleaned_files(input_dir)



