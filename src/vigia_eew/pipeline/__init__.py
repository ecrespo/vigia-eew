"""Processing pipeline: normalize -> filter -> dedup (RF-07..RF-13).

Consumes the `RawMessage` objects from the ingestion layer and produces `SeismicEvent`
instances ready for notification. Each stage is independent and separately testable
(TECHNICAL-DESIGN §2).
"""

from __future__ import annotations
