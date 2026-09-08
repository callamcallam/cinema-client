"""Unified entry point for supported cinema providers."""

from .exceptions import CinemaAPIError, CinemaError
from .odeon import OdeonClient
from .vue import VueClient


class Cinema:
    """Provider namespace: ``Cinema.Odeon()`` or ``Cinema.Vue()``."""

    Odeon = OdeonClient
    Vue = VueClient


__all__ = ["Cinema", "CinemaAPIError", "CinemaError", "OdeonClient", "VueClient"]
__version__ = "0.1.0"

