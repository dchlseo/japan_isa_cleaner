# Japan ISA Cleaner

A tool to clean and merge Japanese Immigration Services Agency (ISA) statistics data.

Source data: [Monthly Japan Immigration Service Agency (ISA) Statistics](https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00250011&tstat=000001012480&cycle=1&tclass1=000001012481&cycle_facet=tclass1&tclass2val=0&metadata=1&data=1)
- For accessing "Nationality and Region of Foreigners Arriving at Each Port" tables (which identifies specific airports/ports of entry), access data with the suffix "-01-2" I(e.g., Data for December 2025 would be "25-12-01-2")
- Download and place the excel data in the repository's data/raw/ directory. For timeseries analysis, i usually create a subdirectory that contains multiple data files for different months (e.g., data/raw/202601-202512)

## Features
- **Raw Data Organization**: Automatically organizes loose `.xls` and `.xlsx` files into date-range folders.
- **Cleaning**: Translates ports and countries from Japanese using provided dictionaries.
- **Merging**: Merges monthly data into a single dataset.
- **Scalability**: Handles large datasets by using temporary storage during processing.
- **Logging**: Detailed execution logs saved to `data/log/`.

## Directory Structure
```
root/
├── etl.py              # Main execution script
├── requirements.txt    # Dependencies
├── configs/            # Translation dictionaries (JSON)
├── data/
│   ├── raw/            # Place your data here (recursive search)
│   ├── cleaned/        # Output files (CSV)
│   ├── log/            # Execution logs
│   └── temp/           # Temporary files (auto-deleted)
```

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Prepare Data**:
    -   Place your raw Excel files (`.xls`, `.xlsx`) in `data/raw/`.
    -   You can dump them all in the root of `data/raw/` or keep them in subdirectories; the script handles both.

## Usage

Run the ETL script:

```bash
python etl.py
```

## Output

The cleaned and merged data will be saved in a subdirectory within `data/cleaned/`, named after the date range (e.g., `data/cleaned/japan_isa_nationality_by_airport_202507-202510/`).

Inside that folder, you will find 4 files:
- `japan_isa_nationality_by_airport_YYYYMM-YYYYMM_wide.csv`
- `japan_isa_nationality_by_airport_YYYYMM-YYYYMM_wide.parquet`
- `japan_isa_nationality_by_airport_YYYYMM-YYYYMM_long.csv`
- `japan_isa_nationality_by_airport_YYYYMM-YYYYMM_long.parquet`

## Logging

Check `data/log/` for detailed processing logs if you encounter any issues.
