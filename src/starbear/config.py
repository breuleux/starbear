from dataclasses import dataclass, field
from typing import Any

import gifnoc


@dataclass
class StarbearDevConfig:
    debug_mode: bool = False
    inject: list[Any] = field(default_factory=list)


@dataclass
class StarbearConfig(gifnoc.Extensible):
    command: str = "serve"
    dev: StarbearDevConfig = field(default_factory=StarbearDevConfig)


config = gifnoc.define(
    field="starbear",
    model=StarbearConfig,
)
