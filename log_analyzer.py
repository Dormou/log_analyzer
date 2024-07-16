#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
import sys
from typing import Generator, Optional
from collections import namedtuple
from datetime import datetime
from statistics import mean, median
from string import Template
from json import dumps
import os
import re
import gzip
import argparse
import logging
logger = logging.getLogger(__name__)


# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';

def get_last_logfile_desc(log_dir: str):
    """Find the latest log file with a name matching the format

    :param log_dir:
        directory of log files
    :return:
        description of the file as a namedtuple with fields path, date, extension
        or None if no proper file was found
    """
    Logfile = namedtuple(typename='Logfile', field_names='path date extension')
    res = None
    if os.path.exists(log_dir):
        with os.scandir(log_dir) as entries:
            for entry in entries:
                if entry.is_file():
                    date, extension = parse_logfile_name(entry.name)
                    if date is not None and (not res or res.date < date):
                        res = Logfile(entry.path, date, extension)
    return res


def parse_logfile_name(filename: str) -> tuple[Optional[datetime], Optional[str]]:
    """Check if filename matches the format 'nginx-access-ui.log-YYYYmmdd[.gz]'

    :param filename:
        string with the name of file
    :return:
        tuple of:
        - date from filename as datetime (None if filename format doesn't match the pattern)
        - extension as string (None for plain file or if filename format doesn't match the pattern)
    """
    filename_pattern = re.compile(r"nginx-access-ui\.log-(?P<date>\d{8})(?P<extension>\.gz)?")
    match = filename_pattern.fullmatch(filename)
    date, extension = None, None
    if match is not None:
        try:
            date = datetime.strptime(match.group('date'), '%Y%m%d')
        except ValueError as ex:
            logger.exception(f'Failed to parse log file date (file: {filename}) ({ex.args[0]})')
        extension = match.group('extension')
    return date, extension


def get_report_filename(report_dir: str, report_date: datetime) -> Optional[str]:
    """Generates the path to the report file for the specified date

    :param report_dir:
        directory of reports
    :param report_date:
        date od report
    :return:
        path to the report file as bytes (None if report already exists)
    """
    filename = f'report-{report_date.strftime("%Y.%m.%d")}.html'
    absolute_report_path = os.path.join(report_dir, filename)
    if not os.path.isfile(absolute_report_path):
        os.makedirs(report_dir, exist_ok=True)
        return absolute_report_path
    else:
        logger.info(f'The report file already exists (file: {filename})')
        return


def parse_logfile(file_desc) -> Generator[Optional[dict], None, None]:
    """Generator of parsed strings from the log file provided in the description

    :param file_desc:
        description of the file as a namedtuple with fields path, date, extension
    :yield:
        dictionary with url and request time from log string (None if parsing has been failed)
    """
    opener = gzip.open if file_desc.extension == '.gz' else open
    try:
        with opener(file_desc.path, 'rt', encoding='utf-8') as file:
            for line in file:
                yield parse_logfile_line(line)
    except OSError as ex:
        logger.exception(f'Error while opening log file {file_desc.path}: {ex.strerror}')
        return


def parse_logfile_line(line: str) -> Optional[dict[datetime, Optional[str]]]:
    """Check if log string matches the format below and then extract url and request time

            log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
            '$status $body_bytes_sent "$http_referer" '
            '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
            '$request_time'

    :param line:
        string from log file
    :return:
        dictionary with url as string and request time as float from log string (None if parsing has been failed)
    """
    log_pattern = re.compile(r"^.+?\"\S+\s+(?P<url>\S+).+\"\s+(?P<request_time>\S+)$")
    match = log_pattern.match(line)
    res = None
    if match is not None:
        try:
            res = {'url': match.group('url'), 'request_time': float(match.group('request_time'))}
        except ValueError as ex:
            logger.exception(f'Failed to parse request_time (line: {line}) ({ex.args[0]})')
    else:
        logger.info(f'Failed to parse log file - invalid format (line: {line})')
    return res


def create_statistic_data(parsed_log_lines: Generator[Optional[dict], None, None],
                          error_limit: float,
                          report_size: int):
    """Calculate time statistic for top-(report_size) requests

    :param parsed_log_lines:
        generator of dictionaries with url and request time for every line in log file
    :param error_limit:
        allowed parsing error rate
    :param report_size:
        number of urls for return
    :return:
        list of dictionaries with statistical data:
        url, count, count_perc, time_sum, time_perc, time_avg, time_max, time_med
    """
    total_lines_counter, valid_lines_counter, parsing_error_counter, request_time_counter = 0, 0, 0, 0.0
    urls = {}
    for parsed_line in parsed_log_lines:
        total_lines_counter += 1
        if parsed_line is not None:
            url = parsed_line['url']
            time = parsed_line['request_time']
            if url in urls.keys():
                urls[url].append(time)
            else:
                urls[url] = [time]
            valid_lines_counter += 1
            request_time_counter += time
        else:
            parsing_error_counter += 1

    if total_lines_counter == 0:
        logger.info('Log file was not read. Cannot create statistical report.')
        return

    error_rate = parsing_error_counter / total_lines_counter
    if error_rate >= error_limit:
        logger.info(f'Parsing error limit has been exceeded (error percentage: {round(error_rate * 100, 2)})')
        return

    return [{'url': url,
             'count': len(time_list),
             'count_perc': round(len(time_list) / valid_lines_counter * 100, 3),
             'time_sum': round(sum(time_list), 3),
             'time_perc': round(sum(time_list) / request_time_counter * 100, 3),
             'time_avg': round(mean(time_list), 3),
             'time_max': round(max(time_list), 3),
             'time_med': round(median(time_list), 3)}
            for url, time_list in sorted(urls.items(), key=lambda x: sum(x[1]), reverse=True)[:min(report_size, len(urls.items()))]]


def save_report(report_template_file: str, statistic_data: list[dict], report_filename: str):
    """Create report file by template and save it

    :param report_template_file:
        report template file path
    :param statistic_data:
        list of dictionaries with statistical data to insert into the template:
        url, count, count_perc, time_sum, time_perc, time_avg, time_max, time_med
    :param report_filename:
        report file path
    :return:
        True if report saving is successful, False otherwise
    """
    if not os.path.isfile(report_template_file):
        logger.critical('Report pattern file was not found')
        return False
    with open(report_template_file, 'r', encoding='utf-8') as file:
        pattern = file.read()
    report = Template(pattern).safe_substitute(table_json=dumps(statistic_data))
    with open(report_filename, 'w+', encoding='utf-8') as file:
        file.write(report)
        return True


def update_config(old_config, new_config_path):
    """Get information from config file and replace default configuration

    :param old_config:
        default config
    :param new_config_path:
        config file path
    :return:
        dictionary with updated configuration
    """
    if os.path.isfile(new_config_path):
        with open(new_config_path, 'r', encoding='utf-8') as file:
            try:
                new_config = json.load(file)
            except ValueError:
                logger.critical('Failed to parse config file')
                return
            old_config.update(new_config)
            return old_config
    else:
        logger.critical('Config file does not exist')
        return


def main(config_info):
    """Get log file according to configuration, parse it and create statistical report by template

    :param config_info:
        dictionary with actual configuration
    :return:
        None
    """
    logging.basicConfig(filename=config_info['LOG_FILE'],
                        encoding='utf-8',
                        format='[%(asctime)s] %(levelname).1s %(message)s',
                        datefmt='%Y.%m.%d %H:%M:%S',
                        level=logging.INFO)

    logfile_desc = get_last_logfile_desc(config_info['LOG_DIR'])
    if logfile_desc is None:
        logger.info('No log file for processing')
        return
    logger.info(f'Last log file date: {logfile_desc.date.strftime("%Y.%m.%d")}')

    report_filename = get_report_filename(config_info['REPORT_DIR'], logfile_desc.date)
    if report_filename is None:
        logger.info('Report file was not created')
        return

    parsed_log_lines = parse_logfile(logfile_desc)
    logger.info('Statistical report creation was started')
    statistic_data = create_statistic_data(parsed_log_lines, config_info['ERROR_LIMIT'], config_info['REPORT_SIZE'])
    logger.info('Statistical report creation was ended')
    if statistic_data is not None and save_report(config_info['REPORT_TEMPLATE_FILE'], statistic_data, report_filename):
        logger.info(f'Report file for {logfile_desc.date.strftime("%Y.%m.%d")} was created')
    else:
        logger.critical('Report file was not created')


config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "REPORT_TEMPLATE_FILE": "./report.html",
    "LOG_DIR": "./log",
    "LOG_FILE": None,
    "ERROR_LIMIT": 0.5
}
parser = argparse.ArgumentParser(description='Analyze last nginx log file '
                                             'and create statistical report with longest url requests')
parser.add_argument('--config', nargs='?', const='./config', help='configuration file path')


if __name__ == "__main__":
    args = parser.parse_args()
    actual_config = update_config(config, args.config) if args.config is not None else config
    if actual_config is not None:
        try:
            main(actual_config)
        except KeyboardInterrupt:
            logger.exception('Execution aborted')
            sys.exit(1)
    else:
        sys.exit(1)
