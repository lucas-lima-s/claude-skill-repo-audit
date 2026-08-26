from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from dataclasses import dataclass

from auditlib.context import CheckContext
from auditlib.severity import CheckResult

RunFn = Callable[[CheckContext], list[CheckResult]]


@dataclass
class CheckSpec:
    name: str
    scope: str
    run: RunFn


CHECKS: dict[str, CheckSpec] = {}


def register(name: str, scope: str = "repo") -> Callable[[RunFn], RunFn]:
    def decorator(fn: RunFn) -> RunFn:
        CHECKS[name] = CheckSpec(name=name, scope=scope, run=fn)
        return fn

    return decorator


def discover(package: str) -> None:
    module = importlib.import_module(package)
    if not hasattr(module, "__path__"):
        return
    for info in pkgutil.iter_modules(module.__path__, prefix=f"{package}."):
        importlib.import_module(info.name)
