name: Scrape Gibraltar Tariff Codes

on:
  workflow_dispatch:
  schedule:
    # Weekly at 02:00 UTC on Sunday
    - cron: "0 2 * * 0"

permissions:
  contents: read

jobs:
  scrape:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.x"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run scraper
        run: |
          mkdir -p data
          python export_gibraltar_tariff.py \
            --codes-outfile data/gibraltar_harmonised_codes.csv \
            --chapters-outfile data/gibraltar_chapters.csv

      - name: Upload CSV artifacts
        uses: actions/upload-artifact@v4
        with:
          name: gibraltar-harmonised-codes-and-chapters
          path: |
            data/gibraltar_harmonised_codes.csv
            data/gibraltar_chapters.csv
