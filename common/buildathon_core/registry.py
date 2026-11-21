"""Track registry.

His core lets you ``register_profile(DomainProfile(...))`` so every model picks
up a new engineering domain with no code change. The analog here is a track
registry: a package registers its ``TrackSpec`` on import, and the top-level
harness (and ``tools/quality_gate.py``) discovers every track by name without
importing the track packages directly.
"""
from __future__ import annotations

from .protocols import TrackSpec

_REGISTRY: dict[str, TrackSpec] = {}


def register_track(spec: TrackSpec) -> TrackSpec:
    """Register a track by its ``name``. Idempotent; last registration wins."""
    _REGISTRY[spec.name] = spec
    return spec


def get_track(name: str) -> TrackSpec:
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "(none registered)"
        raise KeyError(f"unknown track {name!r}; registered: {known}") from None


def all_tracks() -> list[TrackSpec]:
    return [_REGISTRY[k] for k in sorted(_REGISTRY)]


def track_names() -> list[str]:
    return sorted(_REGISTRY)
