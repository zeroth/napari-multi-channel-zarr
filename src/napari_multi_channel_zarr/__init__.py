
try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"
from ._widget import get_metadata

__all__ = (
    "get_metadata"
)
