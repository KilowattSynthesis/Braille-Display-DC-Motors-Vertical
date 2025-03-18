"""Bushings for development."""

import copy
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import build123d as bd
import build123d_ease as bde
from bd_warehouse.thread import IsoThread
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

    thread_length: float = 2.0

    top_rod_od: float = 2.2  # Contact surface with the dot.
    top_rod_length: float = 1

    # OD of the part that goes to the spring (out the bottom).
    spring_id: float = 1.5 - 0.2
    spring_rod_length: float = 2.2  # 5mm spring total.

    def __post_init__(self) -> None:
        """Post initialization checks."""
        data = {}

        logger.info(json.dumps(data, indent=2))

    def deep_copy(self) -> "Spec":
        """Copy the current spec."""
        return copy.deepcopy(self)


def motor_screw_cam(spec: Spec, *, draw_dot: bool = False) -> bd.Part | bd.Compound:
    """Make the bushing."""
    p = bd.Part(None)

    thread = IsoThread(
        major_diameter=2.5,
        pitch=1.5,
        length=spec.thread_length,
        end_finishes=("chamfer", "square"),
        align=bde.align.ANCHOR_BOTTOM,
    )
    p += thread

    # Add rod to spring out the bottom.
    p += bd.Cylinder(
        radius=spec.spring_id / 2,
        height=spec.spring_rod_length,
        align=bde.align.ANCHOR_TOP,
    )

    # Add core.
    p += bd.Cylinder(
        radius=thread.min_radius + 0.05,
        height=spec.thread_length,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # Add the top rod.
    p += bd.Cylinder(
        radius=spec.top_rod_od / 2,
        height=spec.top_rod_length,
        align=bde.align.ANCHOR_BOTTOM,
    ).translate((0, 0, spec.thread_length))

    # Draw the dot for reference.
    if draw_dot:
        p += bd.Cylinder(
            radius=1.4 / 2,
            height=spec.motor_shaft_length,
            align=bde.align.ANCHOR_BOTTOM,
        ).translate(
            (spec.axis_to_axis, 0, spec.thread_length + spec.top_rod_length + 0.5)
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
        bd.export_step(part, str(export_folder / f"{name}.step"))

    logger.info(f"Done running {py_file_name} in {datetime.now(UTC) - start_time}")
