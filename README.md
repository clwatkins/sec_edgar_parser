# sec_edgar_parser

In the process of development.

- Command-line tool to parse the SEC's Edgar database
- Aiming to facilitate ML-type analysis on large set of accounting terms across companies and time

## Instructions
- Set AUTH and ROOT_DIR global vars in main.py (AUTH keys can be generated from [https://developer.yahoo.com/apps/create/](https://developer.yahoo.com/apps/create/))
- Run 'pip install [folder path]' to install command line
- Run 'secparse --help' in termal/cmd

## Current issues
- Parser only knows limited number of form types
- Latest version of Excel on OSX will ask for permissions each time parser tries to open XLSX file to grab accounting terms
- Slow when making lots of sequential API calls/opening Excel files
- General code replication/inefficiency
