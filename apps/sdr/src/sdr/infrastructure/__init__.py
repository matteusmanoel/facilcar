"""Infrastructure adapters (DB repositories + Evolution client)."""

from sdr.infrastructure.conversation_repository import ConversationRepository
from sdr.infrastructure.customer_repository import CustomerRepository
from sdr.infrastructure.evolution_client import (
    EvolutionClient,
    EvolutionError,
    EvolutionUnauthorizedError,
)
from sdr.infrastructure.followup_repository import (
    FollowUpRepository,
    InMemoryFollowUpRepository,
)
from sdr.infrastructure.lead_repository import LeadRepository

__all__ = [
    "ConversationRepository",
    "CustomerRepository",
    "EvolutionClient",
    "EvolutionError",
    "EvolutionUnauthorizedError",
    "FollowUpRepository",
    "InMemoryFollowUpRepository",
    "LeadRepository",
]
