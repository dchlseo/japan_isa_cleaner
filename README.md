# Japan ISA Cleaner

A tool to clean and merge Japanese Immigration Services Agency (ISA) statistics data.

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
