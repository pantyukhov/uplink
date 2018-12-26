# Standard library imports
import sys

# Local imports
from uplink import decorators
from uplink.clients.io import RequestTemplate, transitions

__all__ = ["retry"]

# Constants
MAX_VALUE = sys.maxsize


class RetryTemplate(RequestTemplate):
    def __init__(self, back_off_iterator, failure_tester):
        self._back_off_iterator = back_off_iterator
        self._should_retry = failure_tester

    def after_exception(self, request, exc_type, exc_val, exc_tb):
        if self._should_retry(exc_type, exc_val, exc_tb):
            try:
                delay = next(self._back_off_iterator)
            except StopIteration:
                # Fallback to the default behavior
                pass
            else:
                return transitions.sleep(delay)


class _AfterAttemptStopper(object):
    def __init__(self, num):
        self._num = num
        self._attempt = 0

    def __call__(self, *_):
        self._attempt += 1
        return self._num > self._attempt

    @property
    def num(self):
        return self._num

    @property
    def attempt(self):
        return self._attempt

    def __eq__(self, other):
        return (
            isinstance(other, _AfterAttemptStopper)
            and other.num == self.num
            and other.attempt == self.attempt
        )


# noinspection PyPep8Naming
class retry(decorators.MethodAnnotation):
    _DEFAULT_MAX_ATTEMPTS = 5

    @staticmethod
    def exponential_backoff(base=2, multiplier=1, minimum=1, maximum=MAX_VALUE):
        def wait_iterator():
            delay = multiplier
            while minimum > delay:
                delay *= base
            while True:
                yield min(delay, maximum)
                delay *= base

        return wait_iterator

    @staticmethod
    def stop_after_attempt(num):
        def stop():
            return _AfterAttemptStopper(num)

        return stop

    def __init__(self, max_attempts=None, stop=None, wait=None):
        if max_attempts is not None:
            self._stop = self.stop_after_attempt(max_attempts)
        elif stop is None:
            self._stop = self.stop_after_attempt(self._DEFAULT_MAX_ATTEMPTS)
        else:
            self._stop = stop

        self._wait = self.exponential_backoff() if wait is None else wait

    def modify_request(self, request_builder):
        request_builder.add_request_template(self._create_template())

    def _create_template(self):
        return RetryTemplate(self._wait(), self._stop())

    @property
    def stop(self):
        return self._stop

    @property
    def wait(self):
        return self._wait
