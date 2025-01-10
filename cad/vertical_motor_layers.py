"""Using a layer of screws (like the `cnc_plotter` branch), make motor holder.

Intended as a proof of concept to see how the motors can fit.

Conclusion: At 2.5mm pitch, Motor OD=4mm, H=8mm motors can't really fit.

Conclusion: At 3mm pitch though, Motor OD=4mm, H=8mm motors can totally fit! Just need
to bend their shafts a bit to make them mate with the screws!
"""

import copy
import json
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import reduce
from itertools import product
from math import sqrt
from pathlib import Path
from typing import Literal

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

    motor_body_od: float = 4.2
    motor_body_length: float = 8.0 + 1.0  # Extra 1mm for fit (esp for bottom).

    # The distance above the top of the motor to not allow the bending `turner_tube`.
    # Best to keep slightly greater than `gap_between_motor_layers`.
    motor_rigid_shaft_len: float = 3

    gap_between_motor_layers: float = 2
    gap_above_top_motor: float = 5

    cell_count_x: int = 4
    cell_count_y: int = 1

    # Width of the wire channel. Also, diameter of the holes out the bottom.
    wire_channel_slot_width: float = 1.5

    # `turner_tube` goes to the surface and connects motor to the dot bolt.
    turner_tube_od: float = 1.4

    total_y: float = 15

    # Distance from outer dots to mounting holes. PCB property.
    x_dist_dots_to_mounting_holes: float = 5.0

    mounting_hole_spacing_y: float = 3
    mounting_hole_diameter: float = 2  # Thread-forming screws from bottom.

    border_x: float = 5

    motor_outline_thickness_z: float = 1.2

    top_plate_thickness: float = 2
    top_plate_tap_hole_diameter: float = 1.25  # For M1.6, drill 1.25mm hole.

    top_plate_dot_hole_thread_diameter: float = 1.6
    top_plate_dot_hole_thread_pitch: float = 0.35

    remove_thin_walls: bool = True

    slice_thickness: float = 4

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
        return (
            self.mounting_hole_spacing_x
            + self.mounting_hole_diameter
            + self.border_x * 2
        )

    @property
    def total_z(self) -> float:
        """Total thickness of the housing."""
        return (
            self.motor_body_length * 2
            + self.gap_between_motor_layers
            + self.gap_above_top_motor
        )

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


def make_motor_placement_demo(spec: HousingSpec) -> bd.Part:
    """Make demo of motor placement."""
    p = bd.Part(None)

    # Create the motor holes.
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
        motor_y = cell_y + offset_y * spec.motor_pitch_x

        layer_num = dot_num % 2  # 0 (bottom) or 1 (top)

        # Create the motor hole.
        p += bd.Cylinder(
            spec.motor_body_od / 2,
            # Add a tiny random amount so you can see the edges clearer.
            spec.motor_body_length + random.random() * 0.2,
            align=bde.align.ANCHOR_BOTTOM,
        ).translate(
            (
                motor_x,
                motor_y,
                (spec.motor_body_length + spec.gap_between_motor_layers) * layer_num,
            ),
        )

        # Create the motor shaft hole.
        p += bd.Cylinder(
            radius=0.25,
            height=(
                (
                    spec.motor_body_length + spec.gap_between_motor_layers
                    if layer_num == 0
                    else 0
                )
                + (spec.motor_body_length + spec.gap_above_top_motor)
            ),
            align=bde.align.ANCHOR_BOTTOM,
        ).translate(
            (
                motor_x,
                motor_y,
                (spec.motor_body_length + spec.gap_between_motor_layers) * layer_num,
            ),
        )

    # Show where the braille dots would be.
    for cell_x, cell_y, offset_x, offset_y in product(
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
        motor_x = cell_x + offset_x
        motor_y = cell_y + offset_y

        # Create the braille dot.
        p += bd.Cylinder(
            radius=0.5,
            height=0.5,
            align=bde.align.ANCHOR_BOTTOM,
        ).translate(
            (
                motor_x,
                motor_y,
                (
                    (spec.motor_body_length * 2)
                    + spec.gap_between_motor_layers
                    + spec.gap_above_top_motor
                ),
            )
        )

    return p


def make_motor_housing(spec: HousingSpec) -> bd.Part:
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
    motor_coords_bottom: list[tuple[float, float]] = []
    motor_coords_top: list[tuple[float, float]] = []
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
        dot_x = cell_x + offset_x * spec.dot_pitch_x
        dot_y = cell_y + offset_y * spec.dot_pitch_y

        layer_num = dot_num % 2  # 0 (bottom) or 1 (top)

        # Store the motor coordinates for later.
        if layer_num == 0:
            motor_coords_bottom.append((motor_x, motor_y))
        elif layer_num == 1:
            motor_coords_top.append((motor_x, motor_y))
        else:
            msg = f"Invalid layer_num: {layer_num}"
            raise ValueError(msg)

        # Create the motor hole.
        p -= bd.Cylinder(
            spec.motor_body_od / 2,
            (
                spec.motor_body_length
                if layer_num == 0
                # Make it stick out on the top
                else spec.motor_body_length + spec.gap_above_top_motor + 1
            ),
            align=bde.align.ANCHOR_BOTTOM,
        ).translate(
            (
                motor_x,
                motor_y,
                (spec.motor_body_length + spec.gap_between_motor_layers) * layer_num,
            ),
        )

        # Remove the hole for the wires.
        if layer_num == 1:  # Top motor layer only.
            # In gap between motor layers.
            p -= (
                bd.extrude(
                    bd.SlotCenterToCenter(
                        center_separation=(
                            spec.motor_body_od - spec.wire_channel_slot_width
                        ),
                        height=spec.wire_channel_slot_width,
                    ),
                    amount=spec.gap_between_motor_layers,
                )
                .rotate(axis=bd.Axis.Z, angle=90)
                .translate(
                    (
                        motor_x,
                        motor_y,
                        spec.motor_body_length + spec.gap_between_motor_layers / 2,
                    )
                )
            )

            # Through to bottom.
            # For non-middle dots (i.e., Dot 4, 6), the wire channel through to the
            # bottom goes toward the center of the housing.
            p -= bd.extrude(
                bd.Circle(radius=spec.wire_channel_slot_width / 2),
                amount=spec.motor_body_length + spec.gap_between_motor_layers,
            ).translate(
                (
                    motor_x,
                    (
                        motor_y
                        + (
                            # Offset it in by 1mm so it is contained in the hull.
                            -offset_y * 0.5
                            if spec.remove_thin_walls
                            # Else: Offset it toward edge.
                            else (
                                offset_y
                                * (
                                    spec.motor_body_od / 2
                                    - spec.wire_channel_slot_width / 2
                                    - 0.2
                                )
                            )
                        )
                    ),
                    0,
                )
            )

        # Create the turner_tube hole, with passage right to the dot.
        if layer_num == 0:  # Bottom only.
            p -= bd.extrude(
                bd.make_hull(
                    bd.Circle(
                        radius=spec.turner_tube_od / 2,
                    )
                    .translate((motor_x, motor_y))
                    .edges()
                    # ----
                    + bd.Circle(
                        radius=spec.turner_tube_od / 2,
                    )
                    .translate((dot_x, dot_y))
                    .edges()
                ),
                amount=spec.motor_body_length + spec.gap_between_motor_layers,
            ).translate((0, 0, spec.motor_body_length + spec.motor_rigid_shaft_len))

            # Bottom part is just a cylinder, from top of bottom motor,
            # up `spec.motor_body_length` amount into/past the gap_between_motor_layers.
            p -= bd.extrude(
                bd.Circle(
                    radius=spec.turner_tube_od / 2,
                ),
                amount=spec.motor_rigid_shaft_len + 0.01,
            ).translate((motor_x, motor_y, spec.motor_body_length))

    if spec.remove_thin_walls:
        # Subtract a hull of the centers of the motor holes (TOP layer).
        # On the top layer, hull all motor holes (top and bottom).
        p -= bd.extrude(
            bd.make_hull(
                reduce(
                    lambda a, b: a + b,
                    [
                        bd.Circle(radius=0.2).translate((motor_x, motor_y)).edges()
                        for motor_x, motor_y in [
                            *motor_coords_top,
                            *motor_coords_bottom,
                        ]
                    ],
                )
            ),
            amount=spec.motor_body_length,
        ).translate(
            (
                0,
                0,
                (
                    spec.motor_body_length
                    + spec.gap_between_motor_layers
                    + spec.motor_outline_thickness_z
                ),
            )
        )

        # Subtract a hull of the centers of the motor holes (BOTTOM layer).
        p -= bd.extrude(
            bd.make_hull(
                reduce(
                    lambda a, b: a + b,
                    [
                        bd.Circle(radius=0.2).translate((motor_x, motor_y)).edges()
                        for motor_x, motor_y in motor_coords_bottom
                    ],
                )
            ),
            amount=spec.motor_body_length,
        ).translate((0, 0, -spec.motor_outline_thickness_z))

    # Subtract the mounting holes.
    for hole_x, hole_y in product(
        bde.evenly_space_with_center(count=2, spacing=spec.mounting_hole_spacing_x),
        bde.evenly_space_with_center(count=3, spacing=spec.mounting_hole_spacing_y),
    ):
        p -= bd.Cylinder(
            spec.mounting_hole_diameter / 2,
            spec.total_z,
            align=bde.align.ANCHOR_BOTTOM,
        ).translate((hole_x, hole_y, 0))

    # Subtract the gap_above_top_motor.
    p -= bd.Box(
        spec.mounting_hole_spacing_x - spec.mounting_hole_diameter - 3,
        spec.total_y,
        spec.gap_above_top_motor,
        align=bde.align.ANCHOR_BOTTOM,
    ).translate((0, 0, spec.motor_body_length * 2 + spec.gap_between_motor_layers))

    return p


def make_motor_housing_slice(
    spec: HousingSpec, *, upper_or_lower: Literal["upper", "lower"]
) -> bd.Part:
    """Create a slice of the motor housing."""
    p = make_motor_housing(spec)

    if upper_or_lower == "upper":
        slice_z_bottom = (
            spec.motor_body_length
            + spec.gap_between_motor_layers
            + spec.motor_outline_thickness_z
            + 0.1
        )
    elif upper_or_lower == "lower":
        slice_z_bottom = 1
    else:
        msg = f"Invalid upper_or_lower: {upper_or_lower}"
        raise ValueError(msg)

    return p & bd.Box(
        spec.total_x * 2,
        spec.total_y * 2,
        spec.slice_thickness,
        align=bde.align.ANCHOR_BOTTOM,
    ).translate((0, 0, slice_z_bottom))


def make_top_plate_for_tapping(
    spec: HousingSpec,
    *,
    tap_holes: bool,
    enable_dot_6_nut_hole: bool = False,
) -> bd.Part:
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
            spec.mounting_hole_diameter / 2,
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
            f"  Diameter: {spec.mounting_hole_diameter}",
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


def make_fake_motor_chunk(spec: HousingSpec) -> bd.Part:
    """Make a fake motor assembly chunk, which 2 motors joined by a plate."""
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


def make_thin_fake_motor(spec: HousingSpec) -> bd.Part:
    """Make a cylinder the size of a thin motor."""
    p = bd.Part(None)

    p += bd.Cylinder(
        radius=(spec.motor_body_od) / 2,
        height=spec.slice_thickness,
        align=bde.align.ANCHOR_BOTTOM,
    )

    return p


def make_fake_thin_motor_block(spec: HousingSpec) -> bd.Part:
    """Make three cylinders the size of thin motors hulled."""
    p = bd.Part(None)

    motor_locations: list[tuple[float, float]] = [
        (-spec.motor_pitch_x, 0),
        (0, -spec.motor_pitch_y),
        (0, spec.motor_pitch_y),
    ]

    p += bd.extrude(
        bd.make_hull(
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


if __name__ == "__main__":
    start_time = datetime.now(UTC)
    py_file_name = Path(__file__).name
    logger.info(f"Running {py_file_name}")

    solve_motor_spacing()

    parts = {
        "fake_thin_motor_block": show(make_fake_thin_motor_block(HousingSpec())),
        "motor_housing_slice_upper": show(
            make_motor_housing_slice(HousingSpec(), upper_or_lower="upper")
        ),
        "motor_housing_slice_lower": show(
            make_motor_housing_slice(HousingSpec(), upper_or_lower="lower")
        ),
        "thin_fake_motor": (make_thin_fake_motor(HousingSpec())),
        "fake_motor_chunk": (make_fake_motor_chunk(HousingSpec())),
        "motor_placement_demo": (make_motor_placement_demo(HousingSpec())),
        "motor_housing": (make_motor_housing(HousingSpec())),
        "motor_housing_thin_walls_fdm": (
            make_motor_housing(HousingSpec(remove_thin_walls=False))
        ),
        "top_plate_untapped": (
            make_top_plate_for_tapping(HousingSpec(), tap_holes=False)
        ),
        "top_plate_with_dot_6_nut": show(
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
