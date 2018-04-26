import requests
import re
import bs4
import json
from typing import Optional

from .config import *
from .db import CompanyInfo


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


def api_cik_to_info(company_info: CompanyInfo) -> CompanyInfo:
    """Queries SEC then Yahoo API to return the stock symbol for a given CIK num"""

    url = f'http://www.sec.gov/cgi-bin/browse-edgar?CIK={company_info.company_cik}&Find=Search&' \
          f'owner=exclude&action=getcompany'
    sec_page = requests.get(url).text

    sec_page_parsed = bs4.BeautifulSoup(sec_page, 'html.parser')

    try:
        company_name_string = sec_page_parsed.find_all('', class_='companyName')[0].text
        company_info.company_name = re.sub("[^a-zA-Z ]+", "", company_name_string[:company_name_string.find(' CIK')]) \
            .replace("  ", " ").title()
    except IndexError:
        pass

    try:
        company_sic_string = re.findall(r'SIC=....', str(sec_page_parsed.findAll('', class_='identInfo')[0]))[0][-4:]
        company_info.company_sic = company_sic_string
    except IndexError:
        pass

    try:
        company_state_string = re.findall(r'State=..', str(sec_page_parsed.findAll('', class_='identInfo')[0]))[0][-2:]
        company_info.company_state = company_state_string
    except IndexError:
        pass

    return company_info


def api_name_to_ticker(company_info: CompanyInfo) -> CompanyInfo:
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
