import sys
import logging


def get_logger(logger_name='default'):
    """
    Get logging and format
    All logs will be saved into logs/log-DATE (default)
    Default size of log file = 15m
    :param logger_name:
    :return:
    """
    log = logging.getLogger(logger_name)
    log.setLevel(logging.DEBUG)
    log_format = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(log_format)
    log.addHandler(ch)

    return log


def ignore_runtime_error(func, _logger=None, *args, **kwargs):
    if _logger is None:
        logger = get_logger('JFA Issuer')
    else:
        logger = get_logger(_logger)

    def wrapper(*args, **kwargs):
        try:
            rv = func(*args, **kwargs)
        except Exception as err:
            logger.info(f'{func.__repr__()} {err}')
            rv = None
        finally:
            return rv
    
    return wrapper
