import contextvars
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import Organization

_current_organization: contextvars.ContextVar[Optional['Organization']] = contextvars.ContextVar(
    'current_organization',
    default=None
)


def get_current_organization() -> Optional['Organization']:
    """
    Retrieves the active tenant organization from thread/task context.
    """
    return _current_organization.get()


def set_current_organization(org: Optional['Organization']):
    """
    Sets the active tenant organization in thread/task context.
    """
    _current_organization.set(org)


def clear_current_organization():
    """
    Clears the active tenant organization.
    """
    _current_organization.set(None)
