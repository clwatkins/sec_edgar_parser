import sys
import platform
import time
import threading
import os
import multiprocessing
from typing import List, Union, Optional

from numpy import ndarray
from sqlalchemy import distinct
import feedparser
import requests as rq
import bs4
import pandas as pd
import click

from .apis import api_name_to_ticker, api_cik_to_info
from .db import EdgarDatabase, FilingInfo, CompanyInfo
from .utilities import *


EDGAR_DB = EdgarDatabase()


# Click helper function for command line interface
@click.group()
def cli():
    """Basic command line tool for parsing accounting terms pulled from filings on the SEC's Edgar website.\n"""
    make_folders()
    _build_sic_table()


@cli.command()
@click.option('--manual', default=False, is_flag=True, help='Download filing data for a specific month.')
@click.option('--get_company_info', default=True, is_flag=True, help='Attempt to find additional information about companies that have filed.')
def update_filings(manual, get_company_info, print_data=True, bisection_search=True, db_write=True, update_timeframe=10):
    """
    Pulls filing information from Edgar, storing metadata locally, as well as pointers to Excel files containing filing financials.
    """

    # Allows user to specify month to get data from
    if manual:
        print('\nEnter 4-digit year and 2-digit month:')
        year = click.prompt('Year', type=int)
        month = click.prompt('Month', type=int)
        bisection_search = False

    else:
        print(f"\nFinding new filings in the SEC's Edgar database over the past {update_timeframe} days.")

        year = dt.datetime.now().year
        month = dt.datetime.now().month

    # use bisection search to cut down the number of entries passed to the database for writing
    if bisection_search:

        # suppress printing results until we've cut the number of filings to display
        rss_data = _download_filings(year, month, print_data=False)

        if not rss_data:
            print('\nNo filings found for this month. Please use the manual download feature.')
            sys.exit(0)

        # set acceptable margin of error for our search algorithm
        margin_error = dt.timedelta(hours=12)
        min_i = 0

        max_i = len(rss_data)

        date_to_find = dt.datetime.now() - dt.timedelta(days=update_timeframe)
        guess_i = (min_i + max_i) // 2
        guess_date = dt.datetime.strptime(rss_data[guess_i]['edgar_acceptancedatetime'], '%Y%m%d%H%M%S')
        loop_num = 0

        while abs(date_to_find - guess_date) >= margin_error and loop_num <= 20:
            guess_date = dt.datetime.strptime(rss_data[guess_i]['edgar_acceptancedatetime'], '%Y%m%d%H%M%S')

            if guess_date < date_to_find:
                max_i = guess_i
            else:
                min_i = guess_i

            guess_i = (min_i + max_i) // 2
            loop_num += 1

        # cuts rss_data list to include only those filings that are more recent than date_to_find
        rss_data = rss_data[:guess_i]

        if print_data:
            print(f'\n{len(rss_data)} filings submitted since '
                  f'{dt.datetime.strftime(date_to_find, "%Y-%m-%d %H:%M:%S")}:')
            print('')
            print('Company Name'.ljust(30), 'CIK'.ljust(10), 'Period'.ljust(10), 'Form Type'.ljust(10), sep=' | ')
            print('-' * 80)

            for item in rss_data:
                name = re.sub("[^a-zA-Z ]+", "", item['edgar_companyname']).replace("  ", " ").title()
                cik = item['edgar_ciknumber']
                form = item['edgar_formtype']
                try:
                    period = dt.datetime.strftime(dt.datetime.strptime(item['edgar_period'], '%Y%m%d'), '%m/%d/%Y')
                except KeyError:
                    period = ''

                print(name[:30].ljust(30), cik.ljust(10), period.ljust(10), form.ljust(10), sep=' | ')

    # if we're not using bisection search (aka not just refreshing the database for the first time in a couple of days),
    # simply call dl_filings respecting print_data state
    else:
        rss_data = _download_filings(year, month, print_data)

    if db_write:
        _update_filings(rss_data, get_company_info)
    else:
        return rss_data


# TODO modify search types for new company info
@cli.command()
@click.option('--search_type', type=click.Choice(['ticker', 'cik', 'all', 'exchange', 'industry', 'sector', 'name']),
              default='all', help='Category of search term(s). List of possible industry/sector values '
                                  'can be found at:\nhttps://biz.yahoo.com/ic/ind_index.html')
def search_filings(search_type, print_results=True):
    """Displays filing information stored for any companies matching the search criteria."""
    _searcher(search_type, print_results)


@cli.command()
@click.option('--search_type', type=click.Choice(['ticker', 'all', 'cik', 'exchange', 'industry', 'sector', 'name']),
              default='all', help='Category of search term(s). List of possible industry/sector values can be found '
                                  'at:\nhttps://biz.yahoo.com/ic/ind_index.html')
@click.option('--csv/--no-csv', default=False, help='Save all parsed data to CSV file.')
def parse_filings(search_type, csv=False):
    """
    Attempts to download, extract and store accounting data (P&L / BS) from filings for given companies / categories of
    companies within search parameters. Optionally writes all parsed data to a CSV file.
    """

    search_results = _searcher(search_type, print_results=False)
    print('\n')

    filings_to_download = []
    filings_to_parse = []
    parsing_successes = 0
    valid_results = 0

    print(f"Prepping filings. Looking for forms of type {', '.join(VALID_FORMS)} for parsing...")
    for filing in search_results:
        if filing.FilingInfo.form not in VALID_FORMS:
            continue

        valid_results += 1

        if filing.FilingInfo.parsed_data:
            parsing_successes += 1
            continue

        filings_to_parse.append(filing)

        if filing.FilingInfo.excel_path:
            continue

        filings_to_download.append(filing)

    if filings_to_download:
        print('\n')
        print('Downloading {} filings...'.format(len(filings_to_download)))
        chunk_size = len(filings_to_download)//MULTITHREADING_NUMBER

        if chunk_size > 0:
            xlsx_download_chunks = [filings_to_download[i:i + chunk_size] for i in
                                    range(0, len(filings_to_download), chunk_size)]
            for i in range(0, MULTITHREADING_NUMBER):
                threading.Thread(target=_download_xlsxs(xlsx_download_chunks[i])).start()
        else:
            _download_xlsxs(filings_to_download)

        EDGAR_DB.make_session()

        # inefficient to separate from download logic, but prevents threading issues with sqlite + multiple sessions
        for filing in filings_to_download:
            excel_write_path = normalize_file_path('xlsx_data/' + filing.FilingInfo.company_cik + '_' +
                                    filing.FilingInfo.filing_accession + '.xlsx')

            EDGAR_DB.update_excel_path(excel_write_path, filing.FilingInfo.filing_url)
            filing.FilingInfo.excel_path = str(excel_write_path)

    print('Download complete.')
    print('\n')

    parsing_errors = []
    with click.progressbar(label=f'Parsing {len(filings_to_parse)} filings...', length=len(filings_to_parse)) as bar:

        for filing in filings_to_parse:

            if filing.FilingInfo.excel_path:
                new_filing_bs_dfs = _build_filing_dfs(
                    filing.FilingInfo.excel_path,
                    re_search_terms=r'\bcond.*?\bconsol.*?\bbalance|\bbalance.*?\bsheet'
                )

                new_filing_pl_dfs = _build_filing_dfs(
                    filing.FilingInfo.excel_path,
                    re_search_terms=r'\bstate.*?\bope|\bcond.*?\bconso'
                )

                for filing_bs_df in new_filing_bs_dfs:
                    clean_filing_bs_data = _clean_data_file(filing_bs_df, r'\bbalance.*?\bsheet', r'.?')

                    # write filing data to db if parsing returns something
                    if clean_filing_bs_data is None:
                        parsing_errors.append('BS: ' + str(filing.FilingInfo.excel_path))
                    else:
                        EDGAR_DB.set_filing_data(filing, clean_filing_bs_data, filing_type='BS')
                        parsing_successes += 1

                for filing_pl_df in new_filing_pl_dfs:
                    clean_filing_pl_data = _clean_data_file(filing_pl_df, r'operations', '12 months')

                    # write filing data to db if parsing returns something
                    if clean_filing_pl_data is None:
                        parsing_errors.append('PL: ' + str(filing.FilingInfo.excel_path))
                        continue

                    if EDGAR_DB.set_filing_data(filing, clean_filing_pl_data, filing_type='PL') is not False:
                        parsing_successes += 1
                    else:
                        parsing_errors.append('PL: ' + str(filing.FilingInfo.excel_path))

            bar.update(1)

    print('\n')
    print('Parsing complete.')
    print('Total valid filings:', valid_results)
    print('Successful sheet parses:', parsing_successes)
    print('Unsuccessful sheet parses:', len(parsing_errors))

    error_log_loc = normalize_file_path('unsuccessful_parses.txt')

    with open(error_log_loc, 'w') as f:
        f.write('\n'.join(parsing_errors))

    print('Unsuccessful parse log written to:', error_log_loc)

    # TODO modify joins to include SIC data
    if csv:
        # generate a DataFrame via SQL query for all parsed values in the data table
        company_df = pd.read_sql_table(DB_COMPANY_TABLE, EDGAR_DB._db_eng)
        filing_info_df = pd.read_sql_table(DB_FILING_TABLE, EDGAR_DB._db_eng, parse_dates={'period':'%Y%m%d', 'filed':'%Y%m%d'})
        filing_data_df = pd.read_sql_table(DB_FILING_DATA_TABLE, EDGAR_DB._db_eng, parse_dates={'value_period':'%Y%m%d'})

        most_data_df = pd.merge(filing_data_df, filing_info_df, how='left')
        all_data_df = pd.merge(most_data_df, company_df, how='left')

        print('\n')
        print(all_data_df.head())
        print('\n')
        print(all_data_df.shape)

        # save to file, named for current time
        csv_write_path = normalize_file_path('parsed_data_{}.csv'.format(dt.datetime.now().strftime('%Y%m%d%H%M%S')))
        all_data_df.to_csv(csv_write_path)
        print('\nParsed data CSV written to:')
        print(csv_write_path)

    EDGAR_DB.close_session()
    return search_results


@cli.command()
def update_company_info():
    """Attempts to download information for all company CIKs without an associated ticker."""
    EDGAR_DB.make_session()

    to_update_ciks = EDGAR_DB.session.query(
        distinct(CompanyInfo.company_cik)).filter(CompanyInfo.company_ticker == None).all()

    EDGAR_DB.close_session()
    _update_company_info(to_update_ciks)


@cli.command()
def clear_parsed_files():
    """Deletes any downloaded Excel files that have been successfully parsed."""
    EDGAR_DB.make_session()

    parsed_excel_paths = EDGAR_DB.session.query(
        distinct(FilingInfo)).filter(FilingInfo.parsed_data == True).all()

    for parsed_excel in parsed_excel_paths:
        os.remove(parsed_excel.excel_path)

    EDGAR_DB.close_session()

    print(f'{len(parsed_excel_paths)} files deleted.')


def _searcher(search_type, print_results=True):
    """Prints any downloaded filing information associated with companies within search scope."""
    EDGAR_DB.make_session()

    if search_type == 'all':
        search_results = EDGAR_DB.select_all_filings()
    else:
        search_term = click.prompt('Please enter search term')

        # each of these generates a set of cik numbers for companies that meet search criteria
        if search_type == 'exchange':
            ciks_to_parse = EDGAR_DB.select_ciks_by_exchange(search_term)
        elif search_type == 'industry':
            ciks_to_parse = EDGAR_DB.select_ciks_by_industry(search_term)
        elif search_type == 'sector':
            ciks_to_parse = EDGAR_DB.select_ciks_by_sector(search_term)
        elif search_type == 'name':
            ciks_to_parse = EDGAR_DB.select_ciks_by_name(search_term)
        elif search_type == 'cik':
            ciks_to_parse = EDGAR_DB._select_distinct_ciks(CompanyInfo.company_cik, search_term)
        else:
            ciks_to_parse = EDGAR_DB.select_ciks_by_ticker(search_term)

        # for cik number matches get list of company-filing objects
        search_results = EDGAR_DB.select_filings_by_ciks(ciks_to_parse)

    if print_results:
        print('\nResults:\n')
        print('Company name'.ljust(30), 'Form type'.ljust(10), 'Period'.ljust(10), 'Filing URL', sep=' | ')
        print('-' * 100)

        for result in search_results:
            try:
                period = dt.datetime.strftime(dt.datetime.strptime(str(result.FilingInfo.period), '%Y%m%d'), '%m/%d/%Y')
            except ValueError:
                period = ''
            company_name = result.CompanyInfo.company_name
            if company_name is None:
                company_name = ''

            print(str(company_name[:30]).title().ljust(30),
                  str(result.FilingInfo.form).ljust(10),
                  str(period).ljust(10),
                  str(result.FilingInfo.filing_url), sep=' | ')
        print('\n')
        print('Filings:', len(search_results))

    EDGAR_DB.close_session()

    return search_results


def _download_filings(year, month, print_data=True):
    """Downloads list of filings from SEC's Edgar database for given time period."""
    print('\nDownloading filings XML...\n')

    edgar_url = ('http://www.sec.gov/Archives/edgar/monthly/xbrlrss-' + str(year).zfill(4) +
                 '-' + str(month).zfill(2) + '.xml')

    # use feedparser rss xml parser to enable selection by tag
    rss_data = feedparser.parse(edgar_url)

    if print_data:
        print(rss_data['feed']['title'] + ':', '\n')
        print('Company Name'.ljust(30), 'CIK'.ljust(10), 'Period'.ljust(10), 'Form Type'.ljust(10), sep=' | ')
        print('-'*80)

        for item in rss_data.entries:
            # do our normal company name formatting
            name = re.sub("[^a-zA-Z ]+", "", item['edgar_companyname']).replace("  ", " ").title()
            cik = item['edgar_ciknumber']
            form = item['edgar_formtype']
            try:
                # try to pretty-print filing period date
                period = dt.datetime.strftime(dt.datetime.strptime(item['edgar_period'], '%Y%m%d'), '%m/%d/%Y')
            except KeyError:
                period = ''

            print(name[:30].ljust(30), cik.ljust(10), period.ljust(10), form.ljust(10), sep=' | ')

    return rss_data.entries


def _download_xlsxs(filings):
    """
    Download XLSX files for a list of urls.
    """
    EDGAR_DB.make_session()

    for filing in filings:
        time.sleep(.25)
        try:
            # file name will be the cik plus accession numbers
            write_path = normalize_file_path('xlsx_data/' + filing.FilingInfo.company_cik + '_' +
                                             filing.FilingInfo.filing_accession + '.xlsx')

            if not write_path.exists():
                filing_excel = rq.get(filing.FilingInfo.excel_url)
                write_path.write_bytes(filing_excel.content)

            EDGAR_DB.update_excel_path(str(write_path), filing.FilingInfo.excel_url)

        except (FileNotFoundError, rq.Timeout, rq.ConnectionError, rq.ConnectTimeout):
            print('Unsuccessful:', filing.FilingInfo.excel_url)
            continue

    EDGAR_DB.close_session()


def _build_filing_dfs(file_path: str, re_search_terms: str) -> Union[None, List[pd.DataFrame]]:
    if not file_path:
        return None

    return_dfs = []

    if file_path.split(".")[-1] == 'xls' or 'xlsx':
        excel = pd.ExcelFile(file_path)

        for sheet_name in excel.sheet_names:
            if re.search(re_search_terms, sheet_name, flags=re.IGNORECASE):
                return_dfs.append(pd.read_excel(excel, sheet_name, header=None).dropna(how='all'))

    elif file_path.split(".")[-1] == 'csv':
        df_csv = pd.read_csv(file_path, header=None).dropna(how='all')

        header_vals_list = [str(item) for item in flatten(df_csv.iloc[:5, :].values.tolist())]
        header_vals_string = ' '.join([str(val) for val in header_vals_list])

        if not re.search(re_search_terms, header_vals_string):
            return_dfs.append(None)
        else:
            return return_dfs.append(df_csv)

    return return_dfs


def _clean_data_file(df: pd.DataFrame, re_search_filing_type: str, re_search_period: str) -> Optional[ndarray]:
    if type(df) is None:
        return None

    header_vals_list = [str(item) for item in flatten(df.iloc[:5, :].values.tolist())]
    header_vals_string = ' '.join([str(val) for val in header_vals_list])

    # unit correction to 1 USD
    if re.search('thousands|Thousands', header_vals_string):
        unit_multiplier = 1000
    elif re.search('millions|Millions', header_vals_string):
        unit_multiplier = 1000000
    elif re.search('billions|Billions', header_vals_string):
        unit_multiplier = 1000000000
    else:
        unit_multiplier = 1

    # confirm sheet type by looking at header values for relevant string pattern
    if re.search(re_search_filing_type, header_vals_string, flags=re.IGNORECASE) is None:
        return None

    if re.search(re_search_period, header_vals_string, flags=re.IGNORECASE) is None:
        return None

    dropped_df = df.dropna(how='any', subset=df.columns[1:])

    cleaned_df = dropped_df.applymap(lambda x: str(x).replace('\n', ' ').replace("'", "").replace(":", "")
                                     .replace('-', '').replace('*', '').replace('  ', ' ').replace('$', '').strip().title())

    for col in cleaned_df.columns[1:]:
        cleaned_df.loc[1:, col] = cleaned_df.loc[1:, col].apply(scale_array_val, args=(unit_multiplier,))

    final_df = cleaned_df.dropna()
    final_df = final_df.drop_duplicates(subset=[0], keep=False, inplace=False)

    return final_df.values


def _get_single_company_info(company_cik):
    time.sleep(.05)  # pause for crude rate limiting when hitting in parallel

    company_info = CompanyInfo()

    company_info.company_cik = company_cik

    company_info = api_cik_to_info(company_info)

    if company_info.company_name:
        company_info = api_name_to_ticker(company_info)

    return company_info


def _update_filings(rss_data, get_company_info):
    """
    Parse and store filing data defined by Edgar's filing feed (via a parsed XML file)
    """
    print('\nUpdating filings...')

    EDGAR_DB.make_session()

    duplicates = 0
    company_ciks_to_download = []

    with click.progressbar(length=len(rss_data), label=f'Adding {len(rss_data)} new items to database...') as bar:
        for i, item in enumerate(rss_data):
            bar.update(1)

            cik = str(item['edgar_ciknumber']).strip()
            filing_url = str(item['link']).strip()
            accession = str(item['edgar_accessionnumber']).strip()

            # handle key errors for the filing period as some form types don't have a period associated with them
            try:
                period = str(item['edgar_period']).strip()
            except KeyError:
                period = None

            if EDGAR_DB.check_cik_exists(cik) is False:
                company_ciks_to_download.append(cik)

            # if db search for filing returns a hit, skip writing that filing
            if EDGAR_DB.check_accession_exists(accession) is True:
                duplicates += 1
            else:
                EDGAR_DB.insert_objects(FilingInfo(
                    company_cik=cik,
                    filing_accession=accession,
                    form=str(item['edgar_formtype']).strip(),
                    period=period,
                    filed=str(item['edgar_acceptancedatetime']).strip(),
                    filing_url=filing_url,
                    excel_url='http://www.sec.gov/Archives/edgar/data/' + cik.lstrip("0") + '/' +
                              accession.replace("-", "") + '/Financial_Report.xlsx',
                    excel_path=None,
                    parsed_data=False))

    EDGAR_DB.close_session()

    # show user if we skipped writing any entries because they were already in database
    if duplicates > 0:
        print(f'{duplicates} duplicate entries skipped...')

    if len(company_ciks_to_download) > 0 and get_company_info:
        _update_company_info(company_ciks_to_download)


def _update_company_info(company_ciks_to_download):
    """Attempt to download info about a given company's CIK"""
    print('\n')
    print('Updating company info...')

    EDGAR_DB.make_session()

    print(f'Collecting info for {len(company_ciks_to_download)} companies...')
    company_download_pool = multiprocessing.Pool(processes=MULTIPROCESSING_NUMBER)
    info_to_insert = company_download_pool.map(_get_single_company_info, list(set(company_ciks_to_download)))
    company_download_pool.close()

    EDGAR_DB.insert_objects(info_to_insert)
    EDGAR_DB.close_session()


def _build_sic_table():

    try:
        pd.read_sql_table(DB_SIC_TABLE, EDGAR_DB._db_eng)
        return
    except ValueError:  # pandas will throw a valueerror if the table isn't found -- sign we need to create it
        pass

    sic_tables = bs4.BeautifulSoup(rq.get('https://www.sec.gov/info/edgar/siccodes.htm').content, 'html.parser')
    sic_table_found = sic_tables.findAll('p')[1].findAll('table')[0]

    sic_df = pd.read_html(sic_table_found.encode(), header=0)[0]
    sic_df.columns = ['sic_code', 'ad_office', 'drop', 'industry_title']
    sic_df = sic_df.drop('drop', axis='columns')

    sic_df.to_sql_table(DB_SIC_TABLE, EDGAR_DB._db_eng)


if __name__ == '__main__':
    # activate click command line commands when running module directly
    cli()
    # if using Windows pause at the end of the script so cmd doesn't automatically close
    if platform.system == 'Windows':
        click.pause()
