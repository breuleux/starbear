from dataclasses import dataclass, field
from typing import Any

import gifnoc


@dataclass
class StarbearDevConfig:
    # Turn on debug mode
    debug_mode: bool = False

    # Dev code to inject
    inject: list[Any] = field(default_factory=list)


@dataclass
class StarbearConfig:
    dev: StarbearDevConfig = field(default_factory=StarbearDevConfig)


config = gifnoc.define(
    field="starbear",
    model=StarbearConfig,
    defaults={},
)
