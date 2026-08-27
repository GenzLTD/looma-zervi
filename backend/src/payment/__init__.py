"""Payment module — plans + provider registry + legacy exports."""

from src.payment.plans import (
    DEFAULT_REGION,
    get_plan_for_tier,
    list_plans_for_region,
    normalize_region,
    resolve_region,
)
from src.payment.providers import (
    get_provider,
    list_configured_providers,
    list_registered_providers,
    BaseProvider,
)

__all__ = [
    "DEFAULT_REGION",
    "get_plan_for_tier",
    "list_plans_for_region",
    "normalize_region",
    "resolve_region",
    "get_provider",
    "list_configured_providers",
    "list_registered_providers",
    "BaseProvider",
]
