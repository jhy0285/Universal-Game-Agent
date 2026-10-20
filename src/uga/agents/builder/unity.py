from uga.core.errors import CapabilityUnavailable


class UnityAdapter:
    def generate(self, *args, **kwargs):
        raise CapabilityUnavailable(
            "Unity is an extension boundary: licensed Editor and a verified template are not configured"
        )
