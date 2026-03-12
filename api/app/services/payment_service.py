"""Payment service stub.

Stub -- all content accessible. Implement Stripe integration when ready.
"""


class PaymentService:
    """Placeholder payment gate.

    Every access check returns ``True`` and every user is on the ``"free"``
    tier until a real billing provider is wired up.
    """

    def is_allowed(self, user_id: str, resource_type: str, resource_id: int) -> bool:
        """Check whether a user may access a resource.

        Always returns ``True`` while the stub is in place.
        """
        return True

    def get_user_tier(self, user_id: str) -> str:
        """Return the subscription tier for a user.

        Always returns ``"free"`` while the stub is in place.
        """
        return "free"
