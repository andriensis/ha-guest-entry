"""Exceptions for the Guest Entry integration."""


class GuestEntryError(Exception):
    """Base error."""


class GuestEntryConnectionError(GuestEntryError):
    """Cannot reach the Guest Entry app."""


class GuestEntryAuthError(GuestEntryError):
    """Internal secret is wrong."""
