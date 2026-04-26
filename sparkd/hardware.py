"""Default hardware profiles used when an advisor session has no real target box.

Lets a user generate or optimize recipes against canonical DGX Spark capabilities
without needing to register and SSH-probe an actual box first. When a real box is
selected, BoxService.capabilities() takes precedence.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sparkd.schemas.box import BoxCapabilities


def default_dgx_spark_caps() -> BoxCapabilities:
    return BoxCapabilities(
        gpu_count=1,
        gpu_model="NVIDIA GB10 (DGX Spark, defaults)",
        vram_per_gpu_gb=128,
        cuda_version=None,
        ib_interface=None,
        captured_at=datetime.now(timezone.utc),
    )
