import datetime as dt
import dateutil.parser
import re
from numpy import nan

from config import *


def normalize_file_path(file_from_root):
    """Returns full system-contextual file path."""
    return ROOT_DIR.joinpath(file_from_root)


def make_folders():
    """
    Sets up project's folder structure.

    sec_parse_data/
    └── xlsx_data/
    """
    try:
        ROOT_DIR.mkdir()
        print(f'\nDirectory created at: {ROOT_DIR}')
    except FileExistsError:
        pass

    try:
        ROOT_DIR.joinpath("xlsx_data").mkdir()
        print(f'\nDirectory created at: {ROOT_DIR.joinpath("xlsx_data")}')
    except FileExistsError:
        pass


def flatten(deep_list):
    return [item for sublist in deep_list for item in sublist]


def scale_array_val(val, scale_val):
    try:
        return float(str(val).replace(',', '').replace(' ',''))*scale_val
    except (ValueError, IndexError):
        if val == '':
            return nan
        else:
            return val


def user_list(list_to_split=None, user_prompt='Enter a list of values: '):
    """
    Build a list from user input separated by commas.

    :param list_to_split: optional prepared string or list to split
    :param user_prompt: string
    :return: List of strings parsed to leave only alphanumerics + spaces, stripped
    """
    print('\n')
    if list_to_split is not None:
        # regular expression removes any non-alpha characters, outside whitespace
        return [re.sub("[^a-zA-Z0-9 ]+", "", str(x).strip()) for x in list_to_split.split(',')]
    else:
        while True:
            values = [re.sub("[^a-zA-Z0-9 ]+", "", str(x).strip()) for x in input(user_prompt).split(',')]

            if not values[0]:
                print('No values entered.')
                print('Try again...\n')
                continue
            else:
                return values


def user_date_range(dates_to_parse=None):
    """
    Prompts user for a date_from and date_to, parses them using dateutil to make sure datetime object can be extracted.

    :param dates_to_parse: optional list of prepared dates to be parsed
    :return: 2 datetime objects -- if user leaves date_from blank, sets it to datetime.min, if date_to is blank,
    sets it to datetime.now
    """

    if dates_to_parse:
        while True:
            # assume that dates_to_parse is a list containing 2 values
            date_from = dates_to_parse[0].strip()
            date_to = dates_to_parse[1].strip()
            try:
                # use dateutil to try and extract datetime from string
                range_min = dateutil.parser.parse(date_from) if date_from else dt.datetime.min
                range_max = dateutil.parser.parse(date_to) if date_to else dt.datetime.now()

            # if dates can't be parsed will continue to next loop, which prompts user to enter new dates
            except ValueError:
                print('Incorrect date format. Please try again.\n')
                continue
            return range_min, range_max

    # prompt user for dates if object isn't handed to function
    while True:
        date_from = input('Start: ')
        date_to = input('End: ')

        try:
            range_min = dateutil.parser.parse(date_from) if date_from else dt.datetime.min
            range_max = dateutil.parser.parse(date_to) if date_to else dt.datetime.now()

        except ValueError:
            print('Incorrect date format. Please try again.\n')
            continue

        return range_min, range_max