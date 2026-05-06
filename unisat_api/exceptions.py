# exceptions.py

class UnisatAPIError(Exception):
    """Базовое исключение для всех ошибок библиотеки"""
    pass


class ParameterError(UnisatAPIError):
    """Ошибка в параметрах запроса"""
    pass


class MetadataError(UnisatAPIError):
    """Ошибка при получении метаданных"""
    pass


class NetworkError(UnisatAPIError):
    """Ошибка сети (недоступен сервер, таймаут и т.д.)"""
    pass