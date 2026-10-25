"""
External Policy Source Connectors for CoverageGuard.
Enables genuine external insurer policy discovery, SHA-256 fingerprinting,
change detection, and proposal staging.
"""

from app.connectors.base import PolicySourceConnector
from app.connectors.official_policy_source import CMSMedicareConnector
from app.connectors.change_detector import check_source_for_changes
from app.connectors.scheduler import start_source_scheduler, stop_source_scheduler

__all__ = [
    "PolicySourceConnector",
    "CMSMedicareConnector",
    "check_source_for_changes",
    "start_source_scheduler",
    "stop_source_scheduler",
]
