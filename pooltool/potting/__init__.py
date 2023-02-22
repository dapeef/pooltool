from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from pooltool.objects import Ball, Pocket
from pooltool.potting.simple import calc_potting_angle, pick_best_pot


@dataclass
class PottingConfig:
    calculate_angle: Callable[[Ball, Ball, Pocket], float]
    choose_pocket: Callable[[Ball, Ball, Sequence[Pocket]], Pocket]

    @staticmethod
    def default() -> PottingConfig:
        return PottingConfig(
            calculate_angle=calc_potting_angle,
            choose_pocket=pick_best_pot,
        )