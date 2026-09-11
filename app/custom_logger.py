import logging
import os
import re
import sys
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
    if any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        return

    # for debugging purposes when running outside of container
    if os.path.exists('../.env'):
        load_dotenv('../.env')
    log_level = os.getenv('LOG_LEVEL', 'DEBUG').upper()
    log_level = getattr(logging, log_level.upper(), logging.DEBUG)

    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(fmt='[{asctime}] [{levelname:<8}] {funcName}: {message}', datefmt='%Y-%m-%d %H:%M:%S', style='{',)
    handler.setFormatter(formatter)

    root_logger.setLevel(log_level)
    root_logger.addHandler(handler)
    root_logger.addFilter(SensitiveDataFilter())
