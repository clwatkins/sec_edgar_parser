# @cli.command()
# @click.option('--download', is_flag=True, default=False, help='Make new CSV file from internet. '
#                                                               'WARNING: this takes a while.')
# def get_company_info(download):
#     """Prepares CSV file with all publicly-traded tickers to instantiate company info database table.
#     Default behaviour is to download pre-built file.\n"""
#
#     if download:
#         print('\nGathering data for all tickers...')
#
#         # build df of industry names|ids
#         industry_df = pd.DataFrame.from_dict(api_industry_ids_names(), orient='index')
#         industry_df.columns = ['industry']
#         industry_df['industry_id'] = industry_df.index
#
#         # build df of industries|sectors
#         sectors_file = requests.get('http://www.clwatkins.co/files/sectors.csv').content
#         sector_df = pd.read_csv(io.StringIO(sectors_file.decode('utf-8')), names=['industry', 'sector'])
#
#         # merge df to include industry name|industry id|sector name
#         industry_sector_df = pd.merge(industry_df, sector_df, on=['industry'])
#
#         # build list of tickers for each industry id
#         tickers_by_industry = []
#
#         print('\n')
#
#         # display progress bar
#         with click.progressbar(length=len(industry_df['industry_id'].tolist()), label='Getting list of tickers in each '
#                                                                                       'industry...'.zfill(50)
#                                                                                       .replace('0', ' ')) as bar:
#             for industry_id in industry_df['industry_id'].tolist():
#                 tickers_by_industry.append(api_tickers_in_industry(industry_id))
#                 bar.update(1)
#
#         # flatten list
#         flat_tickers_by_industry = [item for sublist in tickers_by_industry for item in sublist]
#
#         # build df for ticker|industry id
#         tickers_industry_df = pd.DataFrame(flat_tickers_by_industry, columns=['industry_id', 'ticker'])
#
#         # get additional info for each ticker: ticker|company name|exchange|currency
#         # break list of tickers to query Yahoo Finance for so we don't exceed query length limits and return errors
#         tickers_info_list = []
#         tickers_list = tickers_industry_df['ticker'].tolist()
#         ticker_chunks = [tickers_list[i:i + 40] for i in range(0, len(tickers_list), 40)]
#
#         print('\n')
#
#         with click.progressbar(length=len(ticker_chunks), label='Getting ticker info...'.zfill(50)
#                                                                                         .replace('0', ' ')) as bar:
#             for chunk in ticker_chunks:
#                 tickers_info_list.extend(api_ticker_info(chunk))
#                 bar.update(1)
#
#         tickers_info_df = pd.DataFrame(tickers_info_list, columns=['ticker', 'name', 'exchange', 'currency'])
#
#         # get cik number for each ticker by multi-threading so it doesn't take so long.
#         # Adjust processes number if taxing computer.
#         print('\nGetting CIK numbers...')
#         tickers_list = tickers_info_df['ticker'].tolist()
#         pool = multiprocessing.Pool(processes=MULTIPROCESSING_NUMBER)
#         cik_nums = pool.map(api_get_cik, tickers_list)
#         pool.close()
#         tickers_info_df['cik'] = cik_nums
#
#         # merge main tickers df with extra info df
#         tickers_industry_info_df = pd.merge(tickers_industry_df, tickers_info_df, on=['ticker'])
#
#         # merge ticker df with industry-sector df
#         combined_df = pd.merge(tickers_industry_info_df, industry_sector_df, on=['industry_id'])
#
#         # write to file
#         combined_df.to_csv(normalize_file_path('data/industry_ticker_info.csv'))
#
#         #########################
#         # get df of US-only tickers
#         us_tickers_file = requests.get('http://www.clwatkins.co/files/us_tickers.csv').content
#         us_tickers_df = pd.read_csv(io.StringIO(us_tickers_file.decode('utf-8')), index_col=0)
#         us_tickers_df.drop('Description', axis=1, inplace=True)
#
#         # get additional info for each ticker, again using chunking
#         us_tickers_list = us_tickers_df['Symbol'].tolist()
#         us_ticker_chunks = [us_tickers_list[i:i + 40] for i in range(0, len(us_tickers_list), 40)]
#         us_ticker_info_list = []
#
#         print('\n')
#
#         with click.progressbar(length=len(us_ticker_chunks), label='Getting US ticker info....'.rjust(50)) as bar:
#             for chunk in us_ticker_chunks:
#                 us_ticker_info_list.extend(api_ticker_info(chunk))
#                 bar.update(1)
#
#         us_tickers_info_df = pd.DataFrame(us_ticker_info_list, columns=['ticker', 'name', 'exchange', 'currency'])
#
#         # get cik number for each ticker, multi-threading to expedite SEC calls
#         print('\nGetting CIK numbers for tickers. May take a minute...'.zfill(50).replace('0', ' '))
#         us_tickers_list = us_tickers_info_df['ticker'].tolist()
#         pool = multiprocessing.Pool(processes=MULTIPROCESSING_NUMBER)
#         cik_nums = pool.map(api_get_cik, us_tickers_list)
#         pool.close()
#
#         # add cik numbers to main info df
#         us_tickers_info_df['cik'] = cik_nums
#
#         # write to file
#         us_tickers_info_df.to_csv(normalize_file_path('data/us_ticker_info.csv'))
#
#         #######################
#         # create big combined df
#         final_df = combined_df.append(us_tickers_info_df, ignore_index=True)
#
#         # replace all our '' values with Pandas-native NaN
#         final_df.replace('', np.nan, inplace=True)
#
#         # remove rows where there is no ticker
#         final_df.dropna(subset=['ticker'], inplace=True)
#
#         # remove any rows where the ticker, company name, or cik number is a duplicate
#         final_df.drop_duplicates(subset=['ticker', 'name', 'cik'], inplace=True)
#
#         # make sure to remove any whitespace around values
#         for column in final_df.columns.tolist():
#             final_df[column] = final_df[column].str.strip
#
#         # write to file
#         final_df.to_csv(normalize_file_path('data/all_ticker_info.csv'))
#         print('\nTicker info CSV written successfully.')
#
#     else:
#         with urllib.request.urlopen('http://www.clwatkins.co/files/all_ticker_info.csv') as \
#                 response, open(normalize_file_path('data/all_ticker_info.csv'), 'wb') as out_file:
#             shutil.copyfileobj(response, out_file)
#         print('\nTicker info CSV downloaded successfully.')


# def create_company_info():
#     """Bulk writes company info to database - called automatically if there's nothing in the information table"""
#
#     # try to find the all_ticker_info.csv file
#     try:
#         companies_info = pd.read_csv(normalize_file_path('data/all_ticker_info.csv'), index_col=0)
#
#     # quit if we can't
#     except OSError:
#         print("\nTried to create company info database table, but all_ticker_info.csv was not found. Please run "
#               "'build_company_info' and try again.\nQuitting...\n")
#         sys.exit(0)
#
#     print('\nInserting pre-built company info...')
#
#     companies_info.dropna(subset=['cik', 'industry_id'], inplace=True)
#     companies_info.cik = companies_info.cik.astype(int)
#     companies_info.cik = companies_info.cik.astype(str)
#     companies_info.cik = companies_info.cik.apply(lambda x: x.zfill(10))
#     companies_info.industry_id = companies_info.industry_id.astype(int)
#     companies_info.industry_id = companies_info.industry_id.astype(str)
#
#     existing_ciks = self.session.query(distinct(CompanyInfo.company_cik)).all()
#
#     filtered_companies_info = companies_info[~companies_info.cik.isin(existing_ciks)]
#     filtered_companies_info.to_sql_table(DB_COMPANY_TABLE, self._db_eng, if_exists='append')
#
#     self.session.commit()
#
#     duplicates = companies_info.shape[0] - filtered_companies_info.shape[0]
#
#     if duplicates > 0:
#         print(f'{duplicates} duplicate entries skipped...')
