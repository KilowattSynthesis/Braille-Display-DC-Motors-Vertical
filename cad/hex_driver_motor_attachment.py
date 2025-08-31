"""Hex driver attachment to a motor."""

import copy
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import build123d as bd
import build123d_ease as bde
from build123d_ease import show
from loguru import logger


@dataclass(kw_only=True)
class Spec:
    """Specification for the part."""

    hex_driver_size: float = 0.65  # Across flats.
    hex_driver_height: float = 2.0

    motor_shaft_d: float = 0.6
    motor_shaft_len: float = 2.0

    shaft_interface_od: float = 1.6

    cone_len: float = 1.0

    def __post_init__(self) -> None:
        """Post initialization checks."""
        data = {}

        logger.info(json.dumps(data, indent=2))

    def deep_copy(self) -> "Spec":
        """Copy the current spec."""
        return copy.deepcopy(self)


def hex_driver(spec: Spec) -> bd.Part | bd.Compound:
    """Make the adapter."""
    p = bd.Part(None)

    p += bd.Cylinder(
        radius=spec.shaft_interface_od / 2,
        height=spec.motor_shaft_len,
        align=bde.align.ANCHOR_TOP,
    )

    p += bd.Cone(
        bottom_radius=spec.shaft_interface_od / 2,
        top_radius=spec.hex_driver_size / 2 * math.sqrt(2),
        height=spec.cone_len,
        align=bde.align.ANCHOR_BOTTOM,
    )

    p += bd.extrude(
        bd.RegularPolygon(
            side_count=6,
            radius=spec.hex_driver_size / 2,
            major_radius=False,  # Flat-to-flat is minor radius.
        ),
        amount=spec.hex_driver_height,
    ).translate((0, 0, spec.cone_len))

    # Remove the motor shaft.
    p -= bd.Cylinder(
        radius=spec.motor_shaft_d / 2,
        height=spec.motor_shaft_len,
        align=bde.align.ANCHOR_TOP,
    )

    return p


def mean(a: float, b: float) -> float:
    """Calculate avg of two numbers."""
    return (a + b) / 2


def hex_driver_grid_printable(spec: Spec) -> bd.Part | bd.Compound:
    """Make a grid of hex_driver parts."""
    single_part = hex_driver(spec)

    spacing = 7
    joiner_bar_width_xy = 1
    joiner_bar_width_z = 1.6

    p = bd.Part(None)
    for x_val, y_val in product(
        bde.evenly_space_with_center(count=3, spacing=spacing),
        bde.evenly_space_with_center(count=3, spacing=spacing),
    ):
        p += bd.Pos((x_val, y_val, 0)) * single_part

    # Join grids in Y.
    for x_val, y_val in product(
        bde.evenly_space_with_center(count=3, spacing=spacing),
        bde.evenly_space_with_center(count=2, spacing=spacing),
    ):
        p += bd.Pos((x_val, y_val, -spec.motor_shaft_len / 2)) * bd.Box(
            joiner_bar_width_xy,
            spacing - mean(spec.shaft_interface_od, spec.motor_shaft_d),
            joiner_bar_width_z,
        )

    # Join grids in X.
    for x_val, y_val in product(
        bde.evenly_space_with_center(count=2, spacing=spacing),
        bde.evenly_space_with_center(count=3, spacing=spacing),
    ):
        p += bd.Pos((x_val, y_val, -spec.motor_shaft_len / 2)) * bd.Box(
            spacing - mean(spec.shaft_interface_od, spec.motor_shaft_d),
            joiner_bar_width_xy,
            joiner_bar_width_z,
        )

    # Add protection (vertical cylinders).
    for x_val, y_val in [
        *product(
            bde.evenly_space_with_center(count=2, spacing=spacing),
            bde.evenly_space_with_center(count=3, spacing=spacing),
        ),
        *product(
            bde.evenly_space_with_center(count=3, spacing=spacing),
            bde.evenly_space_with_center(count=2, spacing=spacing),
        ),
    ]:
        p += bd.Pos(X=x_val, Y=y_val, Z=-2.5) * bd.Cylinder(
            radius=2.5 / 2, height=7, align=bde.align.ANCHOR_BOTTOM
        )

    # Add protection (top plate):
    p += bd.Pos(Z=6.5 - 2.5 + 1) * bd.Box(spacing * 2.6, spacing * 2.6, height=1.8)

    return p


if __name__ == "__main__":
    start_time = datetime.now(UTC)
    py_file_name = Path(__file__).name
    logger.info(f"Running {py_file_name}")

    parts: dict[str, bd.Part | bd.Compound] = {
        "hex_driver": (hex_driver(Spec())),
        "hex_driver_grid_printable": show(hex_driver_grid_printable(Spec())),
    }

    logger.info("Saving CAD model(s)")

    (
        export_folder := Path(__file__).parent.parent / "build" / Path(__file__).stem
    ).mkdir(exist_ok=True, parents=True)
    for name, part in parts.items():
        logger.debug(f"Exporting {name} - {part.bounding_box()}")
        bd.export_stl(part, str(export_folder / f"{name}.stl"))
        bd.export_step(part, str(export_folder / f"{name}.step"))

    logger.info(f"Done running {py_file_name} in {datetime.now(UTC) - start_time}")
