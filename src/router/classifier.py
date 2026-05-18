"""Classify a contract as `new` vs `renewal` based on metadata.

Rules are loaded from `config/routing_rules.yaml`. Each rule has a single
`when` predicate. The first matching rule wins; otherwise the configured
default applies. We default to `new` because:

  - A misclassified renewal (treated as new) still has the welcome email
    gated by AM review — the AM catches it before it goes out.
  - A misclassified new client (treated as renewal) would silently skip the
    welcome — much worse.

See `CLAUDE.md` §9 and `tests/test_router.py` for the contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from ..config import CONFIG_DIR
from ..schemas import Contract, ContractType


@dataclass(frozen=True)
class ClassifierResult:
    contract_type: ContractType
    rule_name: str  # "default" if no explicit rule matched


class Classifier:
    def __init__(self, rules_path: Path) -> None:
        with rules_path.open("r", encoding="utf-8") as fh:
            config = yaml.safe_load(fh)
        self._rules: list[dict[str, Any]] = config.get("rules", []) or []
        self._default = ContractType(config.get("default", "new"))

    def classify(self, contract: Contract) -> ClassifierResult:
        """Apply each rule in order; first match wins."""
        metadata = self._normalize(contract)
        for rule in self._rules:
            when = rule.get("when", {})
            if self._match(when, metadata):
                return ClassifierResult(
                    contract_type=ContractType(rule["classify_as"]),
                    rule_name=rule.get("name", "<unnamed>"),
                )
        return ClassifierResult(contract_type=self._default, rule_name="default")

    @staticmethod
    def _normalize(contract: Contract) -> dict[str, Any]:
        """Flatten contract fields + raw_metadata, lowercase string values."""
        merged: dict[str, Any] = dict(contract.raw_metadata)
        for field in ("contract_type", "service_type", "envelope_subject", "existing_client_id"):
            value = getattr(contract, field, None)
            if value is None:
                continue
            merged[field] = value.value if hasattr(value, "value") else value
        return {k: _maybe_lower(v) for k, v in merged.items()}

    @staticmethod
    def _match(when: dict[str, Any], metadata: dict[str, Any]) -> bool:
        field = when.get("field")
        if not field:
            return False
        actual = metadata.get(field)

        if "equals" in when:
            return actual == _maybe_lower(when["equals"])

        if "present" in when:
            wants_present = bool(when["present"])
            is_present = actual is not None and actual != ""
            return is_present == wants_present

        if "contains_any" in when:
            if not isinstance(actual, str):
                return False
            needles = [str(n).lower() for n in when["contains_any"]]
            return any(n in actual for n in needles)

        return False


def _maybe_lower(value: Any) -> Any:
    if isinstance(value, str):
        return value.lower()
    return value


@lru_cache(maxsize=1)
def get_classifier() -> Classifier:
    return Classifier(CONFIG_DIR / "routing_rules.yaml")
