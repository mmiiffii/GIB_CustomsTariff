# Gibraltar Tariff Scraper

This repo contains a small Python script and GitHub Action that scrape all
Gibraltar customs tariff chapters and export all individual harmonised codes
into a single CSV file.

## Files

- `export_gibraltar_tariff.py` – Python scraper script.
- `requirements.txt` – Python dependencies.
- `.github/workflows/scrape-tariff.yml` – GitHub Actions workflow that:
  - Runs daily at 02:00 UTC (and on manual dispatch).
  - Scrapes all chapters (01–99).
  - Writes `data/gibraltar_harmonised_codes.csv`.
  - Uploads the CSV as a build artifact.
  - Commits the CSV back into the repo (if it changed).

## Local usage

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python export_gibraltar_tariff.py --outfile data/gibraltar_harmonised_codes.csv
```

The resulting CSV has columns:

- `chapter`
- `code`
- `description`
