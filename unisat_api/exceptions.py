# exceptions.py
import sys


class UnisatAPIError(Exception):
    """Base exception for all library errors."""
    pass


class ParameterError(UnisatAPIError):
    """Invalid request parameters."""
    pass


class MetadataError(UnisatAPIError):
    """Error while fetching metadata."""
    pass


class NetworkError(UnisatAPIError):
    """Network error (server unavailable, timeout, etc.)."""
    pass


class StorageError(UnisatAPIError):
    """Storage error (S3 unavailable, missing credentials, etc.)."""
    pass


_previous_excepthook = sys.excepthook


def _excepthook(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, UnisatAPIError):
        print(f"{exc_type.__name__}: {exc_value}", file=sys.stderr)
    else:
        _previous_excepthook(exc_type, exc_value, exc_tb)


sys.excepthook = _excepthook