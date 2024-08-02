from dataclasses import dataclass

from ..config import StarbearServerPlugin


@dataclass
class Sentry(StarbearServerPlugin):
    dsn: str = None
    traces_sample_rate: float = None
    environment: str = None
    log_level: str = None
    event_log_level: str = None

    def cap_require(self):
        return []

    def cap_export(self):
        return []

    def setup(self, server):
        import logging

        import sentry_sdk

        # Configure sentry to collect log events with minimal level INFO
        # (2023/10/25) https://docs.sentry.io/platforms/python/integrations/logging/
        from sentry_sdk.integrations.logging import LoggingIntegration

        def _get_level(level_name: str) -> int:
            level = logging.getLevelName(level_name)
            return level if isinstance(level, int) else logging.INFO

        sentry_sdk.init(
            dsn=self.dsn,
            traces_sample_rate=self.traces_sample_rate,
            environment=self.environment,
            integrations=[
                LoggingIntegration(
                    level=_get_level(self.log_level or "ERROR"),
                    event_level=_get_level(self.event_log_level or "ERROR"),
                )
            ],
        )
