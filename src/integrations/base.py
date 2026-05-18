"""Integration exceptions shared across providers."""

from __future__ import annotations


class IntegrationError(RuntimeError):
    """Base class for all integration-side failures."""


class WebhookSignatureError(IntegrationError):
    """Webhook signature did not verify."""


class TemplateMissingError(IntegrationError):
    """A required service-type template (ClickUp, Drive) was not found."""


class SlackChannelCollisionError(IntegrationError):
    """Could not find a free Slack channel name after max_suffix attempts."""
