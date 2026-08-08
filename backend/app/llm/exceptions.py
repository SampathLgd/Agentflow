class ProviderQuotaExceeded(Exception):
    """Provider quota or rate limit was exceeded."""


class ProviderUnavailable(Exception):
    """Provider is temporarily unavailable."""


class ProviderAuthenticationError(Exception):
    """Provider authentication failed."""


class ProviderInvalidRequest(Exception):
    """Provider rejected the request as invalid."""