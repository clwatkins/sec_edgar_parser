import requests
import re
import bs4
import json
from typing import Union, List, Optional, Tuple

from .config import *
from .db import CompanyInfo


def api_tickers_in_industry(industry_id: Union[str, int]) -> Union[bool, List[Tuple[Optional[str], Optional[str]]]]:
    """Queries Yahoo Finance API to return list of stock tickers in industry"""

    url = "http://query.yahooapis.com/v1/public/yql"
    params = {'q': f'select * from yahoo.finance.industry where id={industry_id}', 'format': 'json',
              'env': 'store://datatables.org/alltableswithkeys'}

    r = requests.get(url, params=params, auth=AUTH)

    # try to parse json -- return list of tuples(industry id, ticker) if successful, tuple of (None, None) otherwise
    try:
        r_json = r.json()
        tickers_in_industry = []

        try:
            for ticker in r_json['query']['results']['industry']['company']:
                tickers_in_industry.append((industry_id, ticker['symbol']))
        except (TypeError, IndexError, json.decoder.JSONDecodeError, KeyError):
            try:
                tickers_in_industry.append((industry_id, r_json['query']['results']['industry']['company']['symbol']))
            except (TypeError, IndexError, json.decoder.JSONDecodeError, KeyError):
                return[(None, None)]

        return tickers_in_industry

    except TypeError:
        return [(None, None)]


def api_get_cik(ticker: str) -> Optional[str]:
    """Poll Edgar site for CIK number given a ticker"""

    # extract cik number from page using regex query
    cik_re = re.compile(r'.*CIK=(\d{10}).*')
    url = 'http://www.sec.gov/cgi-bin/browse-edgar?CIK={}&Find=Search&owner=exclude&action=getcompany'

    # find regular expression pattern within page. If ticker contains a ., queries the base ticker
    search_results = cik_re.findall(requests.get(url.format(ticker.split('.')[0])).text)

    if len(search_results):
        return search_results[0]
    else:
        return None


def api_cik_to_name(company_info: CompanyInfo):
    """Queries SEC then Yahoo API to return the stock symbol for a given CIK num"""

    url = f'http://www.sec.gov/cgi-bin/browse-edgar?CIK={company_info.company_cik}&Find=Search&' \
          f'owner=exclude&action=getcompany'
    sec_page = requests.get(url).text

    try:
        company_name_string = bs4.BeautifulSoup(sec_page, 'html.parser').find_all('', class_='companyName')[0].text
    except IndexError:
        print(url)
        return company_info

    company_info.company_name = re.sub("[^a-zA-Z ]+", "", company_name_string[:company_name_string.find(' CIK')])\
        .replace("  ", " ").title()

    return company_info


def api_name_to_ticker(company_info):
    """Return ticker for given company name. Is relatively successful for specific names"""

    url = "http://d.yimg.com/autoc.finance.yahoo.com/autoc"

    params = {'query': company_info.company_name, 'region': 1, 'lang': 'en'}

    try:
        r = requests.get(url, params=params, auth=AUTH)
    except (requests.ConnectTimeout, requests.ConnectionError):
        return company_info

    # try to return the ticker for first result in list of suggestions
    try:
        company_info.company_ticker = r.json()['ResultSet']['Result'][0]['symbol']
        return company_info
    except (TypeError, IndexError, json.decoder.JSONDecodeError, KeyError, ConnectionError, TimeoutError):
        try:
            # try other api to see if we get a hit
            r2 = requests.get(f'http://chstocksearch.herokuapp.com/api/{company_info.company_name}')
            return r2.json()[0]['symbol']
        except (TypeError, IndexError, json.decoder.JSONDecodeError, KeyError, ConnectionError, TimeoutError):
            return company_info


def api_industry_ids_names():
    """Get list of industry ids by parsing links contained within Yahoo Finance Industry-Sector homepage"""

    url = 'https://biz.yahoo.com/ic/ind_index.html'
    r = requests.get(url)
    industries_page = bs4.BeautifulSoup(r.content, 'html.parser')

    industry_directory = {}

    for link in industries_page.find_all('a'):

        if repr(link).find('/industryindex/') > 0:
            industry_id = repr(link)[repr(link).find('industryindex'):].split('/')[1]
            industry_name = link.string.replace('\n', ' ')
            industry_directory[industry_id] = industry_name

    return industry_directory


def api_ticker_info(company_info):
    """Queries Yahoo Finance API to get company information for a list of stock tickers."""

    params = {'q': f"select * from yahoo.finance.quotes where symbol in ('{company_info.company_ticker}')",
              'format': 'json',
              'debug': 'false',
              'env': 'store://datatables.org/alltableswithkeys'}
    url = "https://query.yahooapis.com/v1/public/yql"

    # stupid amount of JSON parsing code again -- nested exception catching for various errors.
    # will return tuple of '' values whenever possible rather than raising exception
    # ideally gets ticker|company name|exchange name|currency
    try:
        r = requests.get(url, params=params, auth=AUTH)
        api_return = r.json()
    except (json.JSONDecodeError, ConnectionError, TimeoutError):
        return company_info

    try:
        company_info.company_ticker = api_return['query']['results']['quote']['symbol']

        # format company name for alpha-only, title case, no double spaces
        company_info.company_name = re.sub("[^a-zA-Z ]+", "", api_return['query']['results']['quote']['Name'])\
            .replace("  ", " ").title()

        company_info.company_exchange = api_return['query']['results']['quote']['StockExchange']

        company_info.company_currency = api_return['query']['results']['quote']['Currency']

    except (TypeError, IndexError, json.decoder.JSONDecodeError, KeyError):
        pass

    finally:
        return company_info
