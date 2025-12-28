import time

def _retry(fn, tries=3, base_delay=0.4):
    """지수 백오프 간단 재시도"""
    last_exc = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            last_exc = e

            time.sleep(base_delay * (2 ** i))
    raise last_exc