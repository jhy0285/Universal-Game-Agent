class UGAError(Exception):
    """An expected, reportable failure."""


class CapabilityUnavailable(UGAError):
    pass


class AuthorizationRequired(UGAError):
    pass


class SafetyStop(UGAError):
    pass
