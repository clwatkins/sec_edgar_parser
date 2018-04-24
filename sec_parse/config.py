from pathlib import Path
import requests_oauthlib

# ROOT_DIR defines where filing data should be stored
ROOT_DIR = Path.home().joinpath("sec_parse_data")
DB_FILE_LOC = ROOT_DIR.joinpath("sec_parse_db.sqlite3")

# Parallelisation numbers
MULTIPROCESSING_NUMBER = 35
MULTITHREADING_NUMBER = 4

# Valid form types to try parsing
VALID_FORMS = ['10-Q', '10-K', '10-Q/A', 'S-4', '8-K']

# DB table name
DB_FILING_TABLE = 'filing_info'
DB_FILING_DATA_TABLE = 'filing_data'
DB_COMPANY_TABLE = 'company_info'

# Yahoo API key (some finance tables require authorisation)
AUTH = requests_oauthlib.OAuth1(
    'dj0yJmk9anpzUDNHSjdoaEZvJmQ9WVdrOVIwZDBXRlpTTkdNbWNHbzlNQS0tJnM9Y29uc3VtZXJzZWNyZXQmeD0xOA--',
    'f839901ff46492b372e81fa8325ab61483f0e538'
)
