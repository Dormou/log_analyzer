import json
import os
import shutil
import unittest
import sys
from log_analyzer import *

sys.tracebacklimit = 0


class TestLogFileParsing(unittest.TestCase):
    def setUp(self):
        self.tempdir = 'test_log'
        os.mkdir(self.tempdir)
        self.tempfile_valid_plain_old = 'nginx-access-ui.log-20170629'
        open(os.path.join(self.tempdir, self.tempfile_valid_plain_old), 'a').close()
        self.tempfile_valid_gz_new = 'nginx-access-ui.log-20170630.gz'
        open(os.path.join(self.tempdir, self.tempfile_valid_gz_new), 'a').close()
        self.tempfile_invalid_ext = 'nginx-access-ui.log-20170630.bz2'
        open(os.path.join(self.tempdir, self.tempfile_invalid_ext), 'a').close()
        self.tempfile_invalid_name = 'nginx-access-ui.log-33333333'
        open(os.path.join(self.tempdir, self.tempfile_invalid_name), 'a').close()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_parse_logfile_name(self):
        self.assertTupleEqual(parse_logfile_name(self.tempfile_valid_plain_old), (datetime(2017, 6, 29), None))
        self.assertTupleEqual(parse_logfile_name(self.tempfile_valid_gz_new), (datetime(2017, 6, 30), '.gz'))
        self.assertTupleEqual(parse_logfile_name(self.tempfile_invalid_ext), (None, None))
        self.assertTupleEqual(parse_logfile_name(self.tempfile_invalid_name), (None, None))

    def test_get_last_logfile_desc(self):
        Logfile = namedtuple(typename='Logfile', field_names='path date extension')
        self.assertTupleEqual(get_last_logfile_desc(self.tempdir),
                              Logfile(os.path.join(self.tempdir, self.tempfile_valid_gz_new), datetime(2017, 6, 30),
                                      '.gz'))

    def test_parse_logfile_line(self):
        valid_line = '1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /api/v2/banner/25019354 HTTP/1.1" 200 927 "-" "Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5" "-" "1498697422-2190034393-4708-9752759" "dc7161be3" 0.390\n'
        invalid_format = 'GET /api/1/photogenic_banners/list/?server_name=WIN7RB4 HTTP/1.1 1.99.174.176 3b81f63528 - [29/Jun/2017:03:50:22 +0300] 0.133\n'
        invalid_request_time = '1.169.137.128 -  - [29/Jun/2017:03:50:22 +0300] "GET /api/v2/banner/16852664 HTTP/1.1" 200 19415 "-" "Slotovod" "-" "1498697422-2118016444-4708-9752769" "712e90144abee9" 0.1.99\n'
        self.assertEqual(parse_logfile_line(valid_line), {'url': '/api/v2/banner/25019354', 'request_time': 0.39})
        self.assertIsNone(parse_logfile_line(invalid_format))
        self.assertIsNone(parse_logfile_line(invalid_request_time))


class TestReportCreating(unittest.TestCase):
    def setUp(self):
        self.tempdir = 'test_report'
        os.mkdir(self.tempdir)
        self.report_file = 'report-2017.06.30.html'
        open(os.path.join(self.tempdir, self.report_file), 'a').close()

    def tearDown(self):
        shutil.rmtree(self.tempdir)

    def test_get_report_filename(self):
        self.assertIsNone(get_report_filename(self.tempdir, datetime(2017, 6, 30)))
        self.assertEqual(get_report_filename(self.tempdir, datetime(2017, 6, 29)),
                         os.path.join(self.tempdir, 'report-2017.06.29.html'))

    def test_create_statistic_data(self):
        valid_line = '1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /api/v2/banner/25019354 HTTP/1.1" 200 927 "-" "Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5" "-" "1498697422-2190034393-4708-9752759" "dc7161be3" 0.390\n'
        invalid_format = 'GET /api/1/photogenic_banners/list/?server_name=WIN7RB4 HTTP/1.1 1.99.174.176 3b81f63528 - [29/Jun/2017:03:50:22 +0300] 0.133\n'
        invalid_request_time = '1.169.137.128 -  - [29/Jun/2017:03:50:22 +0300] "GET /api/v2/banner/16852664 HTTP/1.1" 200 19415 "-" "Slotovod" "-" "1498697422-2118016444-4708-9752769" "712e90144abee9" 0.1.99\n'
        parsed_lines = map(parse_logfile_line, [valid_line, invalid_format, invalid_request_time])
        ref_sample = [{'url': '/api/v2/banner/25019354',
                       'count': 1, 'count_perc': 100.0,
                       'time_sum': 0.39,
                       'time_perc': 100.0,
                       'time_avg': 0.39,
                       'time_max': 0.39,
                       'time_med': 0.39}]
        self.assertEqual(create_statistic_data(parsed_lines, 0.8, 10), ref_sample)
        self.assertIsNone(create_statistic_data(parsed_lines, 0.8, 0))
        self.assertIsNone(create_statistic_data([], 0.8, 10))
        self.assertIsNone(create_statistic_data(parsed_lines, 0.1, 10))


class TestConfigUpdating(unittest.TestCase):
    def setUp(self):
        self.valid_config_path = './test_config'
        self.invalid_config_path = './invalid_test_config'
        with open(self.valid_config_path, 'w', encoding='utf-8') as cf:
            test_config = {
                "REPORT_SIZE": 100,
                "ERROR_LIMIT": 0.3
            }
            cf.write(json.dumps(test_config))
        with open(self.invalid_config_path, 'w', encoding='utf-8') as cf:
            invalid_test_config = "REPORT_SIZE: 100, ERROR_LIMIT: 0.3"
            cf.write(invalid_test_config)
        self.config = {
            "REPORT_SIZE": 1000,
            "REPORT_DIR": "./reports",
            "REPORT_TEMPLATE_FILE": "./report.html",
            "LOG_DIR": "./log",
            "LOG_FILE": None,
            "ERROR_LIMIT": 0.5
        }

    def tearDown(self):
        os.remove(self.valid_config_path)
        os.remove(self.invalid_config_path)

    def test_update_config(self):
        new_config = {
            "REPORT_SIZE": 100,
            "REPORT_DIR": "./reports",
            "REPORT_TEMPLATE_FILE": "./report.html",
            "LOG_DIR": "./log",
            "LOG_FILE": None,
            "ERROR_LIMIT": 0.3
        }
        self.assertEqual(update_config(self.config, self.valid_config_path), new_config)
        self.assertIsNone(update_config(self.config, self.invalid_config_path))
        self.assertIsNone(update_config(self.config, './this_file_does_not_exist'))


if __name__ == '__main__':
    unittest.main()
