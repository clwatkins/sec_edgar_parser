from sqlalchemy import create_engine, Column, String, BigInteger, ForeignKey, Float, Index, Boolean, distinct
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import exists

import datetime as dt
import dateutil.parser
import sys
from typing import List

from config import *

Base = declarative_base()


class CompanyInfo(Base):
    __tablename__ = DB_COMPANY_TABLE

    company_cik = Column(String, primary_key=True)
    company_name = Column(String)
    company_ticker = Column(String)
    company_industry_id = Column(String)
    company_industry = Column(String)
    company_sector = Column(String)
    company_exchange = Column(String)
    company_currency = Column(String)


class FilingInfo(Base):
    __tablename__ = DB_FILING_TABLE

    company_cik = Column(String, ForeignKey(CompanyInfo.company_cik))
    filing_accession = Column(String, primary_key=True)
    form = Column(String)
    period = Column(BigInteger)
    filed = Column(BigInteger)
    filing_url = Column(String)
    excel_url = Column(String)
    excel_path = Column(String)
    parsed_data = Column(Boolean)

    Index("FILING_CIK_IDX", "company_cik", "filing_accession")


class FilingData(Base):
    __tablename__ = DB_FILING_DATA_TABLE

    filing_accession = Column(String, ForeignKey(FilingInfo.filing_accession), primary_key=True)
    filing_term = Column(String, primary_key=True)
    filing_type = Column(String)
    filing_value = Column(Float)
    value_period = Column(BigInteger, primary_key=True)


class EdgarDatabase(object):
    def __init__(self):
        self._db_eng = create_engine(f'sqlite:///{DB_FILE_LOC}', echo=False)
        self._sessionmaker = sessionmaker(autocommit=False)
        self._sessionmaker.configure(bind=self._db_eng)
        Base.metadata.create_all(self._db_eng)

    def make_session(self):
        self.session = self._sessionmaker(expire_on_commit=False)

    def close_session(self):
        try:
            self.session.commit()
            self.session.close()
        except ConnectionError as err:
            raise err

    def _check_exists(self, column, value):
        res = self.session.query(distinct(column)).filter(exists().where(column == value)).first()

        if res is None:
            return False
        else:
            return True

    def check_cik_exists(self, cik):
        return self._check_exists(CompanyInfo.company_cik, cik)

    def check_filing_url_exists(self, filing_url):
        return self._check_exists(FilingInfo.filing_url, filing_url)

    def check_accession_exists(self, accession):
        return self._check_exists(FilingInfo.filing_accession, accession)

    def select_all_filings(self):
        return self.session.query(FilingInfo, CompanyInfo).join(CompanyInfo).all()

    def select_single_filing_data_(self, accession_num):
        return self.session.query(FilingData.filing_accession == accession_num).all()

    def select_filings_by_ciks(self, cik_nums) -> List[FilingInfo]:
        return self.session.query(FilingInfo, CompanyInfo).join(CompanyInfo).filter(CompanyInfo.company_cik.in_(cik_nums)).all()

    def select_all_distinct_ciks(self):
        return self.session.query(CompanyInfo.company_cik).all()

    def _select_distinct_ciks(self, query_column, query_term):
        distinct_ciks = self.session.query(CompanyInfo.company_cik).filter(query_column.ilike(query_term)).all()

        if not distinct_ciks:
            print('No results found.\n')
            sys.exit(0)

        return [res.company_cik for res in distinct_ciks]

    def select_ciks_by_exchange(self, exchange_name):
        return self._select_distinct_ciks(CompanyInfo.company_exchange, exchange_name)

    def select_ciks_by_industry(self, industry_name):
        return self._select_distinct_ciks(CompanyInfo.company_industry, industry_name)

    def select_ciks_by_sector(self, sector_name):
        return self._select_distinct_ciks(CompanyInfo.company_sector, sector_name)

    def select_ciks_by_ticker(self, company_ticker):
        return self._select_distinct_ciks(CompanyInfo.company_ticker, company_ticker)

    def select_ciks_by_name(self, company_name):
        return self._select_distinct_ciks(CompanyInfo.company_name, "%"+company_name+"%")

    def update_excel_path(self, excel_path, filing_url):

        for c in self.session.query(FilingInfo).filter(FilingInfo.filing_url == filing_url).all():
            c.excel_path = str(excel_path)

    def insert_objects(self, objects):
        if type(objects) != list:
            objects = [objects]

        self.session.add_all(objects)

    def set_filing_data(self, filing: FilingInfo, data, filing_type) -> bool:
        """Adds parsed excel data to data table from individual filing object"""

        def prep_date(date_str):
            try:
                clean_date_str = date_str.replace('USD ($)', '')
            except AttributeError:
                # print("\n")
                # print(data)
                # print(date_str)
                return False
            return clean_date_str

        # find number of columns in central data range by testing numpy array shape
        num_columns = data.shape[1]

        for column_num in range(1, num_columns):
            # find the time period the data refers to (this is usually cell B1 & C1 for balance sheets)
            try:
                prepped_date = prep_date(data[0, column_num])

                if prepped_date:
                    period = dt.datetime.strftime(dateutil.parser.parse(prepped_date), '%Y%m%d')
                else:
                    return False
            except (TypeError, ValueError, IndexError):
                # print("\n")
                # print(prepped_date)
                # print(data)
                # print(filing.FilingInfo.excel_path)
                self.session.rollback()  # rollback the session so no partially-written data is preserved
                return False

            rows_to_insert = []
            for row in data[1:]:
                # check to see if values field is blank, exclude header row
                if not row[-1]:
                    continue

                rows_to_insert.append(FilingData(
                    filing_accession=filing.FilingInfo.filing_accession,
                    filing_term=row[0],
                    filing_value=row[column_num],
                    value_period=period,
                    filing_type=filing_type))

            try:
                self.session.add_all(rows_to_insert)

                for c in self.session.query(FilingInfo).filter(
                        FilingInfo.filing_accession == filing.FilingInfo.filing_accession).all():
                    c.parsed_data = True

            except (IntegrityError, StatementError):
                self.session.rollback()
                return False

            self.session.commit()

        return True
