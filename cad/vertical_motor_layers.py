"""Using a layer of screws (like the `cnc_plotter` branch), make motor holder.

Intended as a proof of concept to see how the motors can fit.

Conclusion: At 2.5mm pitch, Motor OD=4mm, H=8mm motors can't really fit.

Conclusion: At 3mm pitch though, Motor OD=4mm, H=8mm motors can totally fit! Just need
to bend their shafts a bit to make them mate with the screws!
"""

import copy
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import reduce
from itertools import product
from math import atan2, degrees, sqrt
from pathlib import Path

import bd_warehouse.thread
import build123d as bd
import build123d_ease as bde
from build123d_ease import show
from loguru import logger


@dataclass(kw_only=True)
class HousingSpec:
    """Specification for braille cell in general."""

    motor_pitch_x: float = 3
    motor_pitch_y: float = 2.64  # Solved below to hold motor tightly.
    dot_pitch_x: float = 2.5
    dot_pitch_y: float = 2.5
    cell_pitch_x: float = 6
    cell_pitch_y: float = 10

    dot_count_x: int = 2
    dot_count_y: int = 3

    motor_body_od: float = 4.5
    motor_body_length: float = 8.0 + 1.0  # Extra 1mm for fit (esp for bottom).

    # Main gap for top motor. 8mm seems workable (with 6mm bolts).
    # 10mm safe for trying springs as couplers.
    gap_above_top_motor: float = 10.0

    cell_count_x: int = 4
    cell_count_y: int = 1

    total_y: float = 15

    # Distance from outer dots to mounting holes. PCB property.
    x_dist_dots_to_mounting_holes: float = 5.0

    mounting_hole_spacing_y: float = 3
    mounting_hole_id: float = 1.8  # Thread-forming screws from bottom.
    mounting_hole_peg_od: float = 2
    mounting_hole_peg_length: float = 1.5
    meat_above_peg: float = 3

    border_x: float = 5

    top_plate_thickness: float = 2
    top_plate_tap_hole_diameter: float = 1.25  # For M1.6, drill 1.25mm hole.

    top_plate_dot_hole_thread_diameter: float = 1.6
    top_plate_dot_hole_thread_pitch: float = 0.35

    remove_thin_walls: bool = True

    slice_thickness: float = 7  # Just under the motor_length.

    @property
    def dist_between_motor_walls(self) -> float:
        """Distance between motor walls in a layer."""
        return self.motor_pitch_x * 2 - self.motor_body_od

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
    def total_z(self) -> float:
        """Total thickness of the housing."""
        return self.motor_body_length + self.gap_above_top_motor

    def __post_init__(self) -> None:
        """Post initialization checks."""
        hypot_len = (self.motor_pitch_x**2 + self.motor_pitch_y**2) ** 0.5

        data = {
            "hypot_len": round(hypot_len, 2),  # Forced to match `motor_od`.
            "total_x": self.total_x,
            "total_y": self.total_y,
            "total_z": self.total_z,
            "dist_between_motor_walls": self.dist_between_motor_walls,
            "threads_in_top_plate": round(
                self.top_plate_thickness / self.top_plate_dot_hole_thread_pitch, 1
            ),
        }

        logger.info(json.dumps(data, indent=2))

    def deep_copy(self) -> "HousingSpec":
        """Copy the current spec."""
        return copy.deepcopy(self)


def motor_housing(spec: HousingSpec) -> bd.Part | bd.Compound:
    """Make housing with the placement from the demo.

    Args:
        spec: The specification for the housing.

    """
    p = bd.Part(None)

    p += bd.Box(
        spec.total_x,
        spec.total_y,
        spec.total_z,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # Create the motor holes.
    motor_coords: list[tuple[float, float]] = []
    for dot_num, (cell_x, cell_y, offset_x, offset_y) in enumerate(
        product(
            bde.evenly_space_with_center(
                count=spec.cell_count_x,
                spacing=spec.cell_pitch_x,
            ),
            bde.evenly_space_with_center(
                count=spec.cell_count_y,
                spacing=spec.cell_pitch_y,
            ),
            bde.evenly_space_with_center(count=2, spacing=1),
            bde.evenly_space_with_center(count=3, spacing=1),
        ),
    ):
        motor_x = cell_x + offset_x * spec.motor_pitch_x
        motor_y = cell_y + offset_y * spec.motor_pitch_y

        is_motor_spot: bool = (dot_num % 2) == 0

        # Skip places where there's not a motor (checkerboard).
        if not is_motor_spot:
            continue

        # Store the motor coordinates for later.
        motor_coords.append((motor_x, motor_y))

        # Create the motor hole.
        p -= bd.Cylinder(
            spec.motor_body_od / 2,
            spec.motor_body_length,
            align=bde.align.ANCHOR_BOTTOM,
        ).translate((motor_x, motor_y, 0))

    if spec.remove_thin_walls:
        # Subtract a hull of the centers of the motor holes.
        p -= bd.extrude(
            bd.make_hull(
                reduce(
                    lambda a, b: a + b,
                    [
                        bd.Circle(radius=0.2).translate((motor_x, motor_y)).edges()
                        for motor_x, motor_y in motor_coords
                    ],
                )
            ),
            amount=spec.motor_body_length,
        )

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
            height=spec.total_z,
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

    # Subtract the gap_above_top_motor.
    p -= bd.Box(
        spec.mounting_hole_spacing_x - spec.mounting_hole_id - 3,
        spec.total_y,
        spec.gap_above_top_motor,
        align=bde.align.ANCHOR_BOTTOM,
    ).translate((0, 0, spec.motor_body_length))

    return p


def make_top_plate_for_tapping(
    spec: HousingSpec,
    *,
    tap_holes: bool,
    enable_dot_6_nut_hole: bool = False,
) -> bd.Part | bd.Compound:
    """Make the threaded top plate, with holes for tapping."""
    p = bd.Part(None)

    p += bd.Box(
        spec.total_x,
        spec.total_y,
        spec.top_plate_thickness,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # Add a border to get to the minimum build size for 3d printing company.
    p += bd.Box(
        spec.total_x,
        spec.total_y,
        2.1,
        align=bde.align.ANCHOR_BOTTOM,
    ) - bd.Box(
        spec.total_x - 4,
        spec.total_y - 4,
        2.1,
        align=bde.align.ANCHOR_BOTTOM,
    )

    internal_thread_for_dots = bd_warehouse.thread.TrapezoidalThread(
        diameter=spec.top_plate_dot_hole_thread_diameter,
        pitch=spec.top_plate_dot_hole_thread_pitch,
        thread_angle=30,  # Standard metric.
        length=spec.top_plate_thickness,
        external=False,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # Create the dots.
    for cell_x, cell_y, dot_offset_x, dot_offset_y in product(
        bde.evenly_space_with_center(
            count=spec.cell_count_x,
            spacing=spec.cell_pitch_x,
        ),
        bde.evenly_space_with_center(
            count=spec.cell_count_y,
            spacing=spec.cell_pitch_y,
        ),
        bde.evenly_space_with_center(count=2, spacing=spec.dot_pitch_x),
        bde.evenly_space_with_center(count=3, spacing=spec.dot_pitch_y),
    ):
        dot_x = cell_x + dot_offset_x
        dot_y = cell_y + dot_offset_y

        if tap_holes:
            p -= bd.Cylinder(
                radius=spec.top_plate_dot_hole_thread_diameter / 2,
                height=spec.top_plate_thickness,
                align=bde.align.ANCHOR_BOTTOM,
            ).translate((dot_x, dot_y, 0))

            p += internal_thread_for_dots.translate((dot_x, dot_y, 0))
        elif not enable_dot_6_nut_hole:
            # Create the braille as just a cylinder.
            p -= bd.Cylinder(
                radius=spec.top_plate_tap_hole_diameter / 2,
                height=spec.top_plate_thickness,
                align=bde.align.ANCHOR_BOTTOM,
            ).translate((dot_x, dot_y, 0))

    if enable_dot_6_nut_hole:
        for cell_x, cell_y in product(
            bde.evenly_space_with_center(
                count=spec.cell_count_x,
                spacing=spec.cell_pitch_x,
            ),
            bde.evenly_space_with_center(
                count=spec.cell_count_y,
                spacing=spec.cell_pitch_y,
            ),
        ):
            # Make coords for dot 6 (for testing).
            dot_x = cell_x + spec.dot_pitch_x / 2
            dot_y = cell_y - spec.dot_pitch_y

            p -= bd.extrude(
                bd.RegularPolygon(
                    radius=3 / 2,  # Nut width of M1.6 is 3mm.
                    side_count=6,
                    major_radius=False,
                ),
                amount=10,
            ).translate((dot_x, dot_y, spec.top_plate_thickness - 1.5))

            # Remove the hole.
            p -= bd.Cylinder(
                radius=spec.top_plate_tap_hole_diameter / 2,
                height=spec.top_plate_thickness,
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


def write_milling_drawing_info(
    spec: HousingSpec, *, include_each_dot: bool = False
) -> str:
    """Write information for how to mill the housing."""
    lines: list[str] = []
    section_break = ["", "=" * 80, ""]

    lines.extend(
        [
            "Braille display milling machine plate dimensions:",
            "",
            "Cut stock to size:",
            f"  Housing total X: {spec.total_x}",
            f"  Housing total Y: {spec.total_y}",
            f"  Housing total Z: {spec.total_z} (not used for milling)",
            "  Stock thickness: 2mm-3mm is probably best.",
            "",
            f"Dot pitch X: {spec.dot_pitch_x}",
            f"Dot pitch Y: {spec.dot_pitch_y}",
            f"Cell pitch X: {spec.cell_pitch_x}",
            f"Cell pitch Y: {spec.cell_pitch_y}",
            f"Cell count X: {spec.cell_count_x}",
            f"Cell count Y: {spec.cell_count_y}",
            f"Total dots: {spec.cell_count_x * spec.cell_count_y * 6}",
            "",
            f"Mounting hole pitch X (2 positions): {spec.mounting_hole_spacing_x}",
            f"Mounting hole pitch Y (3 positions): {spec.mounting_hole_spacing_y}",
            "",
            "Make center of it all be at (0, 0).",
            *section_break,
        ]
    )

    # Mounting hole positions.
    hole_positions = list(
        product(
            bde.evenly_space_with_center(count=2, spacing=spec.mounting_hole_spacing_x),
            bde.evenly_space_with_center(count=3, spacing=spec.mounting_hole_spacing_y),
        )
    )
    lines.extend(
        [
            "Mounting hole positions (X, Y):",
            f"  Diameter: {spec.mounting_hole_id}",
            "",
        ]
    )
    for hole_num, (hole_x, hole_y) in enumerate(hole_positions):
        lines.extend(
            [
                f"Mounting hole {hole_num + 1} position:",
                f"  X: {hole_x}",
                f"  Y: {hole_y}",
                "",
            ]
        )

    lines.extend(section_break)

    dot_positions: list[tuple[float, float]] = []
    for cell_x, cell_y, offset_x, offset_y in product(
        bde.evenly_space_with_center(
            count=spec.cell_count_x,
            spacing=spec.cell_pitch_x,
        ),
        bde.evenly_space_with_center(
            count=spec.cell_count_y,
            spacing=spec.cell_pitch_y,
        ),
        bde.evenly_space_with_center(count=2, spacing=1),
        bde.evenly_space_with_center(count=3, spacing=1),
    ):
        dot_x = cell_x + offset_x * spec.dot_pitch_x
        dot_y = cell_y + offset_y * spec.dot_pitch_y
        dot_positions.append((dot_x, dot_y))

    lines.extend(
        [
            "Dot hole positions (X, Y):",
            "  For M1.6 tap, drill 1.25mm hole [do this].",
            "  For M1.4 tap, drill 1.1mm hole.",
            "  For other sizes, see https://fullerfasteners.com/tech/recommended-tapping-drill-size/.",
            "",
        ]
    )

    if include_each_dot:
        for dot_num, (dot_x, dot_y) in enumerate(dot_positions):
            lines.extend(
                [
                    f"Dot {dot_num + 1} position:",
                    f"  X: {dot_x}",
                    f"  Y: {dot_y}",
                    "",
                ]
            )

        lines.extend(section_break)

    # All dot X positions.
    dot_x_positions: list[float] = sorted({dot_x for dot_x, _ in dot_positions})
    dot_y_positions: list[float] = sorted({dot_y for _, dot_y in dot_positions})
    lines.append("Dot X positions:")
    lines.extend(f"  {dot_x}\n" for dot_x in dot_x_positions)
    lines.append("")

    lines.extend(section_break)

    # All dot Y positions.
    lines.append("Dot Y positions:")
    lines.extend(f"  {dot_y}\n" for dot_y in dot_y_positions)
    lines.extend(["", ""])

    return "\n".join(lines)


def two_mock_motors_joined(spec: HousingSpec) -> bd.Part | bd.Compound:
    """Make a fake motor assembly chunk, with 2 motors joined by a plate."""
    config_bottom_plate_thickness = 2
    config_extra_motor_length = 2  # Extra length so the plate is higher than flush.
    config_slop = 0.4  # Remove from diameter.

    p = bd.Part(None)

    # Add the motors.
    for motor_x in bde.evenly_space_with_center(
        count=2,
        spacing=spec.motor_pitch_x * 2,
    ):
        p += bd.Cylinder(
            radius=(spec.motor_body_od - config_slop) / 2,
            height=spec.motor_body_length + config_extra_motor_length,
            align=bde.align.ANCHOR_BOTTOM,
        ).translate(
            (
                motor_x,
                0,
                config_bottom_plate_thickness,
            ),
        )

    p += bd.Box(
        spec.motor_pitch_x * 2 + spec.motor_body_od + 1.5,
        spec.motor_body_od + 1.5,
        config_bottom_plate_thickness,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # Remove a hole in the middle (wires and/or shaft).
    p -= bd.Cylinder(
        radius=2 / 2,
        height=config_bottom_plate_thickness,
        align=bde.align.ANCHOR_BOTTOM,
    )

    return p


def three_mock_thin_motors_joined(spec: HousingSpec) -> bd.Part | bd.Compound:
    """Make three cylinders the size of thin motors hulled."""
    p = bd.Part(None)

    motor_locations: list[tuple[float, float]] = [
        (-spec.motor_pitch_x, 0),
        (0, -spec.motor_pitch_y),
        (0, spec.motor_pitch_y),
    ]

    p += bd.extrude(
        # TODO(KilowattSynthesis): Open an issue and remove type ignore.
        bd.make_hull(  # type: ignore reportArgumentType
            reduce(
                lambda a, b: a + b,
                [
                    bd.Circle(radius=spec.motor_body_od / 4).translate(coord).edges()
                    for coord in motor_locations
                ],
            )
        )
        + reduce(
            lambda a, b: a + b,
            [
                bd.Circle(radius=spec.motor_body_od / 2).translate(coord)
                for coord in motor_locations
            ],
        ),
        amount=spec.slice_thickness,
    )

    return p


def solve_motor_spacing() -> None:
    """Do calculations about motor spacing."""
    _dot_pitch_x = 2.5
    cell_pitch_x = 6
    motor_od = 4

    motor_pitch_x = cell_pitch_x / 2  # Forced, so motors can hold each other.
    motor_pitch_y = sqrt(motor_od**2 - motor_pitch_x**2)
    logger.info(f"motor_pitch_y: {motor_pitch_y}")


def solve_dot_to_motor_offset_dist(spec: HousingSpec) -> None:
    """Calculate the distance from the dot to the motor."""
    dot_coords = [
        (x, y)
        for x, y in product(
            bde.evenly_space_with_center(
                count=spec.dot_count_x,
                spacing=spec.dot_pitch_x,
            ),
            bde.evenly_space_with_center(
                count=spec.dot_count_y,
                spacing=spec.dot_pitch_y,
            ),
        )
    ]

    motor_coords = [
        (x, y)
        for x, y in product(
            bde.evenly_space_with_center(
                count=spec.dot_count_x,
                spacing=spec.motor_pitch_x,
            ),
            bde.evenly_space_with_center(
                count=spec.dot_count_y,
                spacing=spec.motor_pitch_y,
            ),
        )
    ]

    for dot_num, (dot_coord, motor_coord) in enumerate(
        zip(dot_coords, motor_coords, strict=True), 1
    ):
        dot_x, dot_y = dot_coord
        motor_x, motor_y = motor_coord

        dist = sqrt((dot_x - motor_x) ** 2 + (dot_y - motor_y) ** 2)
        angle_deg = degrees(atan2(dot_y - motor_y, dot_x - motor_x))

        logger.info(
            f"Dot {dot_num} to motor dist ({motor_coord} -> {dot_coord}): "
            f"{dist:.2f} at {angle_deg:.2f}°"
        )


if __name__ == "__main__":
    start_time = datetime.now(UTC)
    py_file_name = Path(__file__).name
    logger.info(f"Running {py_file_name}")

    solve_motor_spacing()
    solve_dot_to_motor_offset_dist(HousingSpec())

    parts = {
        "three_mock_thin_motors_joined": show(
            three_mock_thin_motors_joined(HousingSpec())
        ),
        "two_mock_motors_joined": show(two_mock_motors_joined(HousingSpec())),
        "motor_housing_top_pcb": show(motor_housing(HousingSpec())),
        "motor_housing_bottom_pcb": show(
            motor_housing(
                HousingSpec(
                    motor_body_length=6.0,
                    gap_above_top_motor=0.1,
                )
            )
        ),
        "top_plate_untapped": (
            make_top_plate_for_tapping(HousingSpec(), tap_holes=False)
        ),
        "top_plate_with_dot_6_nut": (
            make_top_plate_for_tapping(
                HousingSpec(
                    top_plate_thickness=3,
                    top_plate_tap_hole_diameter=2.1,  # Clearance for M1.6.
                ),
                tap_holes=False,
                enable_dot_6_nut_hole=True,
            )
        ),
        # "top_plate_pre_tapped": ( # Very slow to generate.
        #     make_top_plate_for_tapping(HousingSpec(), tap_holes=True)
        # ),
    }

    logger.info("Saving CAD model(s)")

    (
        export_folder := Path(__file__).parent.parent / "build" / Path(__file__).stem
    ).mkdir(exist_ok=True, parents=True)
    for name, part in parts.items():
        bd.export_stl(part, str(export_folder / f"{name}.stl"))
        bd.export_step(part, str(export_folder / f"{name}.step"))

    (export_folder / "milling_drawing_info.txt").write_text(
        write_milling_drawing_info(HousingSpec())
    )

    logger.info(f"Done running {py_file_name} in {datetime.now(UTC) - start_time}")
