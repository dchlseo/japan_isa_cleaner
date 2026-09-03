# Japan ISA Cleaner (Immigration Services Agency Statistics; 出入国管理統計)

A small ETL tool that cleans and merges one specific Japanese government statistics
table — monthly foreign arrivals by **nationality × port of entry** — into tidy,
analysis-ready CSV/Parquet files, with optional translation of Japanese port and
country names into Korean or English.

> **Scope note:** despite the name, this tool does **not** cover the full Immigration
> Services Agency (ISA) statistics catalog. It handles exactly one monthly table. See
> [Data Source](#data-source) below for what that means in practice.

## Data Source

The data comes from **e-Stat**, Japan's official government statistics portal, under
the statistics category:

**Immigration Control Statistics (出入国管理統計)** — compiled by the Immigration
Services Agency (出入国在留管理庁) and published via the Ministry of Justice (法務省).

That category alone contains **thousands of files** across many sub-tables (visa
statistics, asylum statistics, deportation statistics, annual vs. monthly cuts, etc.).
Full metadata directory (all files under this category):

https://www.e-stat.go.jp/stat-search/files?page=1&toukei=00250011&cycle_facet=tclass1&metadata=1&data=1

**This repository handles only one of those tables**: the monthly *"Nationality and
Region of Foreigners Arriving at Each Port"* table, i.e. the file whose toukei code
carries the suffix `-01-2` (e.g. data for December 2025 is `25-12-01-2.xlsx`). Direct
link to that table series:

https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00250011&tstat=000001012480&cycle=1&tclass1=000001012481&cycle_facet=tclass1&tclass2val=0&metadata=1&data=1

If you need any other ISA/e-Stat table (residency status, deportations, asylum,
annual summaries, etc.), this tool will not parse it correctly — the cell layout and
column filtering are specific to this one table's format.

## Features

- **Raw Data Organization**: Automatically organizes loose `.xls`/`.xlsx` files
  dropped in `data/raw/` into a date-range folder.
- **Cleaning**: Translates ports and countries out of Japanese using the dictionaries
  in `configs/`.
- **Merging**: Merges multiple months into a single wide/long dataset.
- **Scalability**: Uses temporary per-file storage during processing so large batches
  don't need to fit in memory at once.
- **Logging**: Detailed execution logs saved to `data/log/`.

## Directory Structure

```
root/
├── etl.py              # Main execution script
├── requirements.txt    # Dependencies
├── configs/             # Japanese→Korean / Japanese→English translation dictionaries (JSON)
├── data/
│   ├── raw/            # Place your downloaded source files here (recursive search)
│   ├── cleaned/         # Output files (CSV + Parquet)
│   ├── log/             # Execution logs
│   └── temp/             # Temporary per-file storage (auto-deleted after each run)
├── notebooks/           # Ad-hoc data inspection notebooks (not part of the pipeline)
└── oldcode/              # Legacy scripts superseded by etl.py — kept for reference,
                          # slated for removal (see Roadmap)
```

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Prepare Data**:
    -   Place your raw Excel files (`.xls`, `.xlsx`) in `data/raw/`.
    -   You can dump them all in the root of `data/raw/` or keep them in subdirectories; the script handles both.

## Current Workflow

The current input workflow is entirely manual:

1. Download the source Excel files yourself from e-Stat (see [Data Source](#data-source)).
2. Place the files under `data/raw/`.
3. Either leave them loose in `data/raw/` (the script auto-organizes loose files into
   a date-range folder on the next run), or create a period subdirectory yourself,
   e.g. `data/raw/202601-202612`.
4. Run `python etl.py` (optionally with `--lang`, see [Usage](#usage)).

### Known limitations of this workflow

This is convenient for single-person, single-dataset use, but it doesn't scale well
and isn't self-explanatory to a new user. Specifically:

- **Single-source assumption** — everything under `data/raw/` is assumed to belong to
  the one nationality × port table described above. Mixing in files from a different
  ISA/e-Stat table will silently produce wrong or skipped output.
- **Source identity isn't encoded** — nothing in the directory structure or filenames
  records *which* e-Stat table a file came from; it's inferred implicitly from the
  fact that only one table is supported today.
- **Manual period folders** — date-range subdirectories (e.g. `202601-202612`) are
  named by hand; there's no validation that the name actually matches the files
  inside it.
- **Manual acquisition** — there is no automated download step. Files must be fetched
  from e-Stat by hand, every time.

These are tracked, not fixed, in this pass — see [Roadmap / TODO](#roadmap--todo).

## Usage

Run the ETL script:

```bash
python etl.py
```

By default, port/country names are translated to Korean. To get English output instead, pass `--lang`:

```bash
python etl.py --lang english
```

Supported values: `korean` (default), `english`.

## Language Support

- **Korean is the default and most complete** translated output.
- **English support exists but is currently incomplete** — the English port
  dictionary covers noticeably fewer entries than the Korean one (particularly
  smaller regional airports). Any name without a translation is left in the original
  Japanese, and a summary count of untranslated names is logged as a warning.
- Translation mappings are plain JSON lookup tables maintained by hand under
  `configs/` (`japanese_to_korean_ports.json`, `japanese_to_english_ports.json`,
  and the corresponding `*_countries.json` files). There is no fuzzy matching or
  automated translation — only exact-string lookup.

**Do not assume full multilingual support.** If you need a name that isn't yet in the
selected language's dictionary, either add it to the relevant JSON file or expect it
to come through untranslated.

Improving English coverage is a near-term priority (see below) — several related
Japanese tourism datasets (e.g. JNTO) already publish English place names that could
seed a more complete English dictionary, and English is arguably the better
long-term default for a broader audience.

## Output

The cleaned and merged data will be saved in a subdirectory within `data/cleaned/`, named after the date range and selected language (e.g., `data/cleaned/japan_isa_nationality_by_airport_202507-202510_korean/`).

Inside that folder, you will find 4 files:
- `japan_isa_nationality_by_airport_YYYYMM-YYYYMM_<lang>_wide.csv`
- `japan_isa_nationality_by_airport_YYYYMM-YYYYMM_<lang>_wide.parquet`
- `japan_isa_nationality_by_airport_YYYYMM-YYYYMM_<lang>_long.csv`
- `japan_isa_nationality_by_airport_YYYYMM-YYYYMM_<lang>_long.parquet`

## Logging

Check `data/log/` for detailed processing logs if you encounter any issues — each run
writes a fresh timestamped log file, and warnings (e.g. untranslated names, skipped
files) are recorded there as well as printed to the console.

## Roadmap / TODO

### Near-term
- [ ] Improve English translation coverage for ports and countries.
- [ ] Make dataset/source identity explicit in the `data/raw/` and `configs/`
      structure instead of assuming a single source.
- [ ] Reduce reliance on hand-typed period folder names (derive and/or validate the
      range instead of trusting the folder name).
- [ ] Improve validation and error messages (e.g. a clearer error when a file doesn't
      match the expected table layout, instead of a generic parse failure).
- [ ] Lower the onboarding bar for new users/contributors (sample input file,
      clearer first-run instructions).
- [ ] Remove or archive `oldcode/` now that it's fully superseded by `etl.py`.

### Medium-term
Support more than one e-Stat table without hardcoding a single format into `etl.py`.
**Recommended direction:** a small **dataset registry / adapter pattern**, not a
general-purpose ETL framework — each supported table gets a lightweight "source
spec" (an identifier, a filename-pattern matcher, its cell-reference rules, and which
`configs/` dictionaries apply), and `etl.py` dispatches to the matching adapter
instead of assuming one layout. This scales incrementally — a new supported table is
a new spec, not a new framework — and stays appropriately sized for a project with
one primary dataset today.

### Long-term / "one day"
- Automated source acquisition (downloading/scraping directly from e-Stat).
- A separate, connected project providing an end-to-end pipeline:
  `acquire → clean → translate → aggregate → publish/dashboard`. That's intentionally
  out of scope for this repository, which stays focused on the clean/translate step.

## Contributing

This started as a personal data-cleaning script, so several assumptions (see
[Known limitations](#known-limitations-of-this-workflow)) are narrower than a
general-purpose tool would need. Issues and PRs are welcome, especially around
English translation coverage or supporting additional e-Stat tables — please open an
issue first for anything beyond a small fix, so scope can be discussed before a lot
of code gets written.

## Research / Showcase

This repository's output was used to compile the statistics behind:

- **Yanolja Research Brief Vol.11**, *"Opening the Gate to Regional Tourism: How Japan
  Turned Regional Airports into Inbound Engines"* —
  https://www.yanolja-research.com/brief/view/695?lang=en
- **Regional Airport Revitalization: Northeast Asia Air Network Analysis and Lessons
  from Japan** — https://www.yanolja-research.com/report/view/736?lang=en
  (Korean only)

Shared here as a real-world use case, in hopes that other researchers might find this
pipeline useful and contribute to it.

## License

MIT — see [LICENSE](LICENSE).
