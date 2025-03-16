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

    od: float = 2.2
    axis_to_axis: float = 0.3

    motor_shaft_length: float = 1.2
    motor_shaft_d: float = 0.7

    vertical_travel: float = 1.5

    def __post_init__(self) -> None:
        """Post initialization checks."""
        data = {}

        logger.info(json.dumps(data, indent=2))

    def deep_copy(self) -> "Spec":
        """Copy the current spec."""
        return copy.deepcopy(self)


def motor_screw_cam(spec: Spec) -> bd.Part | bd.Compound:
    """Make the bushing."""
    p = bd.Part(None)

    p += bd.Cylinder(
        radius=spec.od / 2,
        height=spec.motor_shaft_length + spec.vertical_travel,
        align=bde.align.ANCHOR_BOTTOM,
    )

    p -= bd.Cylinder(
        radius=spec.motor_shaft_d / 2,
        height=spec.motor_shaft_length,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # Draw the dot for reference.
    p += bd.Cylinder(
        radius=1.4 / 2,
        height=spec.motor_shaft_length,
        align=bde.align.ANCHOR_BOTTOM,
    ).translate(
        (spec.axis_to_axis, 0, spec.motor_shaft_length + spec.vertical_travel + 0.1)
    )

    return p


if __name__ == "__main__":
    start_time = datetime.now(UTC)
    py_file_name = Path(__file__).name
    logger.info(f"Running {py_file_name}")

    parts = {
        "motor_screw_cam": show(motor_screw_cam(Spec())),
    }

    logger.info("Saving CAD model(s)")

    (
        export_folder := Path(__file__).parent.parent / "build" / Path(__file__).stem
    ).mkdir(exist_ok=True, parents=True)
    for name, part in parts.items():
        bd.export_stl(part, str(export_folder / f"{name}.stl"))
        # bd.export_step(part, str(export_folder / f"{name}.step"))

    logger.info(f"Done running {py_file_name} in {datetime.now(UTC) - start_time}")
