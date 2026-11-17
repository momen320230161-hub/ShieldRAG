from dataclasses import dataclass
from typing import Literal

Action=Literal['allow','block','review']


@dataclass(frozen=True)
class Decision:
    decision: Action
    threat_category: str
    reason_code: str
    classifier_version: str='shield-security-v1'
    # Raw signed decision margin, never a calibrated probability or public field.
    risk_score: float | None=None
