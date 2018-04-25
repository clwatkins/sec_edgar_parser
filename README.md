# SEC Edgar parser

In the process of development.

- Command-line tool to parse the [SEC's Edgar database](https://www.sec.gov/edgar/searchedgar/companysearch.html)
- Aiming to facilitate ML-type analysis on large sets of accounting terms

## Instructions
- Download / clone repository
- Set ROOT_DIR var in `config.py` to define where downloaded files / database will be stored (defaults to user's home directory)
- Run `pip install {path to top-level sec_edgar_parser directory}` to install command line alias
- Run `secparse --help` in termal/cmd prompt to see available commands

## Envisioned workflow
- Install package and confirm working
- Run update_filings to download info about latest submitted filings from Edgar. Can specify a manual date range to backfill filing info
- Run parse_filings to download filing financial data (stored in Excel files), parse, and store accounting terms in the database where possible. The --csv flag will create a CSV file with all current parsed accounting information
- Run clear_parsed_files as a utility function to delete Excel documents that have been successfully parsed for their contents

## Current issues
- Sector / industry information for companies not being parsed
- Parser only knows limited number of form types with relatively limited fault tolerance for non-standard filing formats
