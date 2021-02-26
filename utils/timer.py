import time


def timer(func, *args, **kwargs):
    """
    Timer decorator
    """
    log = get_logger(logger_name='Timer')

    def wrapper(*args, **kwargs):
        before = time.time()
        print(args)
        rv = func(*args, **kwargs)
        after = time.time()
        log.info(f'{func.__name__} took {round(after - before, 5)}s for execution.')
        return rv
    
    return wrapper