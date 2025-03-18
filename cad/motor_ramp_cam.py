"""Screw-like ramp adapter to go from motor to dot."""

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

    shaft_d: float = 0.55
    shaft_length: float = 22.0  # Nominally 2.0 only.

    general_od: float = 2.2
    travel_distance: float = 1.5

    bottom_block_height: float = 1  # Increase bottom WT.
    upper_stopper_lip_height: float = 1

    def __post_init__(self) -> None:
        """Post initialization checks."""
        data = {
            "shaft_d": self.shaft_d,
            "shaft_length": self.shaft_length,
            "wall_t": (self.general_od - self.shaft_d) / 2,
            "total_height": (
                self.bottom_block_height
                + self.travel_distance
                + self.upper_stopper_lip_height
            ),
        }

        logger.info(json.dumps(data, indent=2))

    def deep_copy(self) -> "Spec":
        """Copy the current spec."""
        return copy.deepcopy(self)


def motor_to_dot_adapter(spec: Spec) -> bd.Part | bd.Compound:
    """Make the adapter."""
    p = bd.Part(None)

    rotation_angle = 270 + 20

    # Create a 270-degree helical path
    _ramp_path = bd.Helix(
        radius=spec.general_od / 2,  # Intentionally way larger.
        pitch=spec.travel_distance / ((rotation_angle + 1) / 360),
        height=spec.travel_distance,
    )
    _ramp_profile = bd.Rectangle(
        spec.general_od / 1,  # Intentionally way larger.
        0.01,
        align=(bd.Align.CENTER, bd.Align.MAX),
    )
    _ramp = bd.sweep(
        _ramp_path.location_at(0) * _ramp_profile,  # type: ignore reportArgumentType
        _ramp_path,
        is_frenet=True,  # Important. Gets wavy otherwise.
    )

    _ramp_support_base = bd.Sketch(
        bd.Circle(radius=spec.general_od / 2)
        - bd.Circle(radius=spec.shaft_d / 2)
        - (
            bd.make_hull(
                bd.Polyline((0, 0), (10, 0)).edges()
                + bd.Polyline((0, 0), (10, 0))
                .rotate(axis=bd.Axis.Z, angle=rotation_angle)
                .edges()
            )
        )
    )
    ramp_support = bd.extrude(
        _ramp_support_base,
        until=bd.Until.NEXT,
        target=_ramp,
    ).rotate(axis=bd.Axis.Z, angle=(270 - rotation_angle))

    p += ramp_support

    # Create a lip at the bottom/top of the top.
    _lip_part = bd.Cylinder(
        radius=spec.general_od / 2 + 0.01,
        height=spec.travel_distance + spec.upper_stopper_lip_height,
        align=bde.align.ANCHOR_BOTTOM,
    ) & bd.Box(
        spec.general_od / 2,
        spec.general_od / 2,
        spec.travel_distance + spec.upper_stopper_lip_height,
        align=(bd.Align.MIN, bd.Align.MAX, bd.Align.MIN),
    )
    p += _lip_part

    # Add thickness on the bottom.
    p += bd.Cylinder(
        radius=spec.general_od / 2,
        height=spec.bottom_block_height,
        align=bde.align.ANCHOR_TOP,
    )

    # Remove the shaft.
    p -= (
        bd.Cylinder(
            radius=spec.shaft_d / 2,
            height=spec.shaft_length,
            align=bde.align.ANCHOR_BOTTOM,
        )
        + bd.Cone(
            bottom_radius=spec.shaft_d / 2,
            top_radius=0.01,
            height=1,
            align=bde.align.ANCHOR_BOTTOM,
        ).translate((0, 0, spec.shaft_length))
    ).translate((0, 0, -spec.bottom_block_height))

    return p


if __name__ == "__main__":
    start_time = datetime.now(UTC)
    py_file_name = Path(__file__).name
    logger.info(f"Running {py_file_name}")

    parts = {
        "motor_to_dot_adapter": show(motor_to_dot_adapter(Spec())),
    }

    logger.info("Saving CAD model(s)")

    (
        export_folder := Path(__file__).parent.parent / "build" / Path(__file__).stem
    ).mkdir(exist_ok=True, parents=True)
    for name, part in parts.items():
        bd.export_stl(part, str(export_folder / f"{name}.stl"))
        bd.export_step(part, str(export_folder / f"{name}.step"))

    logger.info(f"Done running {py_file_name} in {datetime.now(UTC) - start_time}")
