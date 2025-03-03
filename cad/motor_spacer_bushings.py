"""Bushings for development."""

import copy
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import build123d as bd
import build123d_ease as bde
from build123d_ease import show
from loguru import logger


@dataclass(kw_only=True)
class Spec:
    """Specification for the part."""

    bushing_height: float = 2.0

    middle_hole_id: float = 2.2
    outer_hole_id: float = 2.5

    hole_spacing: float = 3.0

    def __post_init__(self) -> None:
        """Post initialization checks."""
        data = {}

        logger.info(json.dumps(data, indent=2))

    def deep_copy(self) -> "Spec":
        """Copy the current spec."""
        return copy.deepcopy(self)


def motor_spacer_bushing(spec: Spec) -> bd.Part | bd.Compound:
    """Make the bushing."""
    p = bd.Part(None)

    p += bd.Box(
        14,
        4,
        spec.bushing_height,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # Remove middle hole.
    p -= bd.Cylinder(
        radius=spec.middle_hole_id / 2,
        height=10,
    )

    # Remove outer holes.
    for x_val in bde.evenly_space_with_center(count=2, spacing=spec.hole_spacing * 2):
        p -= bd.Pos(X=x_val) * bd.Cylinder(
            radius=spec.outer_hole_id / 2,
            height=10,
        )

    return p


def peg(_spec: Spec) -> bd.Part | bd.Compound:
    """Make the adapter."""
    p = bd.Part(None)

    p += bd.Cylinder(
        radius=(2.0) / 2,
        height=2,
        align=bde.align.ANCHOR_BOTTOM,
    )
    return p


if __name__ == "__main__":
    start_time = datetime.now(UTC)
    py_file_name = Path(__file__).name
    logger.info(f"Running {py_file_name}")

    parts = {
        "motor_spacer_bushing_1mm": show(motor_spacer_bushing(Spec(bushing_height=1))),
        "motor_spacer_bushing_2mm": show(motor_spacer_bushing(Spec(bushing_height=2))),
        "motor_spacer_bushing_3mm": show(motor_spacer_bushing(Spec(bushing_height=3))),
        "motor_spacer_bushing_4mm": show(motor_spacer_bushing(Spec(bushing_height=4))),
        "motor_spacer_bushing_5mm": show(motor_spacer_bushing(Spec(bushing_height=5))),
        "peg": (peg(Spec())),
    }

    logger.info("Saving CAD model(s)")

    (
        export_folder := Path(__file__).parent.parent / "build" / Path(__file__).stem
    ).mkdir(exist_ok=True, parents=True)
    for name, part in parts.items():
        bd.export_stl(part, str(export_folder / f"{name}.stl"))
        # bd.export_step(part, str(export_folder / f"{name}.step"))

    logger.info(f"Done running {py_file_name} in {datetime.now(UTC) - start_time}")
