"""VESA MCCS virtual-control-panel feature codes.

These numbers are the same on every DDC/CI monitor. Support is not: a TV
may have volume and no backlight, a cheap panel may have brightness and
nothing else. Callers must probe, never assume a feature exists.
"""

from __future__ import annotations

from enum import IntEnum


class Feature(IntEnum):
    BRIGHTNESS = 0x10
    CONTRAST = 0x12
    AUDIO_SPEAKER_VOLUME = 0x62
    AUDIO_MUTE = 0x8D
    INPUT_SOURCE = 0x60
    POWER_MODE = 0xD6


# Features the UI cares about, in the order sliders should appear.
USER_FEATURES: tuple[Feature, ...] = (
    Feature.BRIGHTNESS,
    Feature.CONTRAST,
    Feature.AUDIO_SPEAKER_VOLUME,
)

FEATURE_LABELS = {
    Feature.BRIGHTNESS: "Brightness",
    Feature.CONTRAST: "Contrast",
    Feature.AUDIO_SPEAKER_VOLUME: "Volume",
    Feature.AUDIO_MUTE: "Mute",
    Feature.INPUT_SOURCE: "Input",
    Feature.POWER_MODE: "Power",
}
