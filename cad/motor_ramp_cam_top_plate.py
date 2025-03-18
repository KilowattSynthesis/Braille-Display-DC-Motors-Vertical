"""Holder plates for the `motor_ramp_cam` screw cams."""

import copy
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from itertools import product
from pathlib import Path

import build123d as bd
import build123d_ease as bde
from build123d_ease import show
from loguru import logger


@dataclass(kw_only=True)
class HousingSpec:
    """Specification for braille cell in general."""

    dot_pitch_x: float = 2.5
    dot_pitch_y: float = 2.5

    cell_pitch_x: float = 6
    cell_count_x: int = 4

    dot_count_x: int = 2
    dot_count_y: int = 3

    # Distance from outer dots to mounting holes. PCB property.
    x_dist_dots_to_mounting_holes: float = 5.0

    mounting_hole_spacing_y: float = 3
    mounting_hole_id: float = 1.8  # Thread-forming screws from bottom.
    mounting_hole_peg_od: float = 2
    mounting_hole_peg_length: float = 1.5
    meat_above_peg: float = 3

    border_x: float = 5

    # #####

    bottom_hole_d: float = 1.5
    cam_od: float = 2.5

    bottom_plate_thickness: float = 1.5
    ramp_cam_thickness: float = 3.5 + 0.5

    top_plate_thickness: float = 2.5
    dot_diameter: float = 1.25

    # Assume the cam is R=1.25mm, and dot is R=0.5mm.
    dot_additional_offset_y: float = 1.25 - 0.5

    @property
    def mounting_hole_spacing_x(self) -> float:
        """Spacing between the mounting holes, in X axis."""
        return (
            self.x_dist_dots_to_mounting_holes * 2
            + self.cell_pitch_x * (self.cell_count_x - 1)
            + self.dot_pitch_x
        )

    @property
    def total_x(self) -> float:
        """Total width of the braille housing."""
        return self.mounting_hole_spacing_x + self.mounting_hole_id + self.border_x * 2

    @property
    def total_y(self) -> float:
        """Total height of the braille housing."""
        return 12

    def __post_init__(self) -> None:
        """Post initialization checks."""
        data = {}

        logger.info(json.dumps(data, indent=2))

    def deep_copy(self) -> "HousingSpec":
        """Copy the current spec."""
        return copy.deepcopy(self)


def plate_bottom_part(spec: HousingSpec) -> bd.Part | bd.Compound:
    """Make housing with the placement from the demo.

    Args:
        spec: The specification for the housing.

    """
    p = bd.Part(None)

    p += bd.Box(
        spec.total_x,
        spec.total_y,
        spec.bottom_plate_thickness + spec.ramp_cam_thickness,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # Remove all the holes.
    for cell_x, dot_offset_x, dot_y in product(
        bde.evenly_space_with_center(
            count=spec.cell_count_x,
            spacing=spec.cell_pitch_x,
        ),
        bde.evenly_space_with_center(count=2, spacing=spec.dot_pitch_x),
        bde.evenly_space_with_center(count=3, spacing=spec.dot_pitch_y),
    ):
        dot_x = cell_x + dot_offset_x

        # Remove hole out the bottom.
        p -= bd.Cylinder(
            radius=spec.bottom_hole_d / 2,
            height=spec.bottom_plate_thickness,
            align=bde.align.ANCHOR_BOTTOM,
        ).translate((dot_x, dot_y, 0))

    # Remove the cam area for each cell.
    for cell_x in bde.evenly_space_with_center(
        count=spec.cell_count_x,
        spacing=spec.cell_pitch_x,
    ):
        p -= bd.Box(
            spec.cam_od * spec.dot_count_x,
            spec.cam_od * spec.dot_count_y,
            spec.ramp_cam_thickness,
            align=bde.align.ANCHOR_BOTTOM,
        ).translate((cell_x, 0, spec.bottom_plate_thickness))

    # Remove the mounting holes.
    for x_val, y_val in product(
        bde.evenly_space_with_center(
            count=2,
            spacing=spec.mounting_hole_spacing_x,
        ),
        bde.evenly_space_with_center(
            count=3,
            spacing=spec.mounting_hole_spacing_y,
        ),
    ):
        p -= bd.Pos(
            X=x_val,
            Y=y_val,
            Z=(0 if y_val == 0 else spec.meat_above_peg),  # Leave meat above peg.
        ) * bd.Cylinder(
            radius=spec.mounting_hole_id / 2,
            height=10,
            align=bde.align.ANCHOR_BOTTOM,
        )
    # Add the mounting pegs (corner holes).
    for x_val, y_val in product(
        bde.evenly_space_with_center(
            count=2,
            spacing=spec.mounting_hole_spacing_x,
        ),
        bde.evenly_space_with_center(
            count=2,
            spacing=spec.mounting_hole_spacing_y * 2,
        ),
    ):
        p += bd.Pos(x_val, y_val) * bd.Cylinder(
            radius=spec.mounting_hole_peg_od / 2,
            height=spec.mounting_hole_peg_length,
            align=bde.align.ANCHOR_TOP,
        )

    return p


def plate_top_part(spec: HousingSpec) -> bd.Part | bd.Compound:
    """Make the threaded top plate, with holes for tapping."""
    p = bd.Part(None)

    p += bd.Box(
        spec.total_x,
        spec.total_y,
        spec.top_plate_thickness,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # Create the dots.
    for cell_x, dot_offset_x, dot_offset_y in product(
        bde.evenly_space_with_center(
            count=spec.cell_count_x,
            spacing=spec.cell_pitch_x,
        ),
        bde.evenly_space_with_center(count=2, spacing=spec.dot_pitch_x),
        bde.evenly_space_with_center(count=3, spacing=spec.dot_pitch_y),
    ):
        dot_x = cell_x + dot_offset_x
        dot_y = dot_offset_y + spec.dot_additional_offset_y

        p -= bd.Cylinder(
            spec.dot_diameter / 2,
            spec.top_plate_thickness,
            align=bde.align.ANCHOR_BOTTOM,
        ).translate((dot_x, dot_y, 0))

    # Create the mounting holes.
    for hole_x, hole_y in product(
        bde.evenly_space_with_center(count=2, spacing=spec.mounting_hole_spacing_x),
        bde.evenly_space_with_center(count=3, spacing=spec.mounting_hole_spacing_y),
    ):
        p -= bd.Cylinder(
            spec.mounting_hole_id / 2,
            spec.top_plate_thickness,
            align=bde.align.ANCHOR_BOTTOM,
        ).translate((hole_x, hole_y, 0))

    return p


if __name__ == "__main__":
    start_time = datetime.now(UTC)
    py_file_name = Path(__file__).name
    logger.info(f"Running {py_file_name}")

    parts = {
        "plate_bottom_part": show(plate_bottom_part(HousingSpec())),
        "plate_top_part": show(plate_top_part(HousingSpec())),
    }

    logger.info("Saving CAD model(s)")

    (
        export_folder := Path(__file__).parent.parent / "build" / Path(__file__).stem
    ).mkdir(exist_ok=True, parents=True)
    for name, part in parts.items():
        bd.export_stl(part, str(export_folder / f"{name}.stl"))
        bd.export_step(part, str(export_folder / f"{name}.step"))

    logger.info(f"Done running {py_file_name} in {datetime.now(UTC) - start_time}")
