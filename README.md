# Log analyzer

This script is designed to analyze web application logs. It parses the latest log file and creates a statistical report on URL calls time.


## How to use it

Clone the project

```cmd
  git clone https://github.com/Dormou/log_analyzer
```

Go to the project directory

```cmd
  cd log_analyzer
```

Run the script

```cmd
  python log_analyzer.py
```

To customize the script, the following configuration parameters are used:
* REPORT_SIZE - number of URLs to display in the report
* REPORT_DIR - folder to save reports
* REPORT_TEMPLATE_FILE - path to the file with report HTML-template
* LOG_DIR - folder with log files
* LOG_FILE - path to the file for script logging
* ERROR_LIMIT - allowed log parsing error rate

Default configuration:
```json
{
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "REPORT_TEMPLATE_FILE": "./report.html",
    "LOG_DIR": "./log",
    "LOG_FILE": None,
    "ERROR_LIMIT": 0.5
}
```

Run the script with custom configaration
* for default config file path (./config)
```cmd
python log_analyzer.py --config
```
* for custom config file path
```cmd
python log_analyzer.py --config some_config_file.json
```


## Running Tests

To run tests, run the following command

```cmd
  python test_log_analyzer.py
```

