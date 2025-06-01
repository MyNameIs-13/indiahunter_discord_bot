import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

from dotenv import load_dotenv


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> Optional[bool]:
        # If the log message is a dictionary, mask sensitive fields
        if hasattr(record, 'msg'):
            if isinstance(record.msg, (list, str)):
                # Use regex to find and replace the value of "password"
                if 'TOKEN' in str(record.msg):
                    record.msg = re.sub(r"(TOKEN'?:? ?=?'?)[^\s^']+", r'\1****', str(record.msg))
        return True


def setup_logging(logfile_name: str = __name__) -> None:
    root_logger = logging.getLogger()

    # Prevent duplicate configuration
    if any(isinstance(h, (RotatingFileHandler, logging.StreamHandler)) for h in root_logger.handlers):
        return

    # for debugging purposes when running outside of container
    if os.path.exists('../.env'):
        load_dotenv('../.env')
    log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()
    log_level = getattr(logging, log_level.upper(), logging.DEBUG)

    log_filepath = f'./logs/{logfile_name}.log'
    log_path = os.path.dirname(os.path.abspath(log_filepath))
    if log_level == logging.DEBUG and os.access(log_path, os.W_OK):
        handler = RotatingFileHandler(log_filepath, mode='a', encoding='utf-8', maxBytes=5 * 1024 * 1024, backupCount=3)
    else:
        handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(fmt='[{asctime}] [{levelname:<8}] {funcName}: {message}', datefmt='%Y-%m-%d %H:%M:%S', style='{',)
    handler.setFormatter(formatter)

    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)
    root_logger.addFilter(SensitiveDataFilter())
