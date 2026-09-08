"""Unified entry point for supported cinema providers."""

from importlib.metadata import PackageNotFoundError, version

from .exceptions import *
from .models import Booking, CinemaLocation, Film, Seat, Showtime, TicketType
from .odeon import OdeonClient
from .vue import VueClient


class Cinema:
    """Provider namespace: ``Cinema.Odeon()`` or ``Cinema.Vue()``."""

    Odeon = OdeonClient
    Vue = VueClient


__all__ = [
    "Booking",
    "Cinema",
    "CinemaLocation",
    "Film",
    "OdeonClient",
    "Seat",
    "Showtime",
    "TicketType",
    "VueClient",
]
try:
    __version__ = version("cinema-client")
except PackageNotFoundError:
    __version__ = "0+unknown"
