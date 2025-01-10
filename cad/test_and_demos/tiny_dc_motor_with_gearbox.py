"""Model of the tiny DC motor with planetary gearbox."""

import copy
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import build123d as bd
import build123d_ease as bde
import git
from build123d_ease import show
from loguru import logger


@dataclass(kw_only=True)
class MainSpec:
    """Specification for a tiny DC motor with planetary gearbox."""

    motor_od: float = 6
    gearbox_od: float = 5.9  # Create a tiny lip.

    motor_length: float = 9

    shaft_lip_od: float = 3.0
    shaft_lip_length: float = 1.1  # 3.6 - 2.5mm

    shaft_length: float = 2.5
    shaft_od: float = 2.0
    shaft_d_size: float = 1.5  # Short dimension on D shape.

    gearbox_length: float = 9.7  # 242 RPM (3 stages) -> 9.7mm

    # Gearbox Length:
    # 47 RPM (4 stages) is 21 - 9 = 12mm
    # 242 RPM (3 stages) is 18.7 - 9 = 9.7mm [selected]
    # 1200 RPM (2 stages) is 16.3 - 9 = 7.3mm

    wire_od: float = 1
    wire_stub_length: float = 0.5

    def __post_init__(self) -> None:
        """Post initialization checks."""
        data = {}
        logger.info(json.dumps(data, indent=2))

    def deep_copy(self) -> "MainSpec":
        """Copy the current spec."""
        return copy.deepcopy(self)


def make_dc_motor_and_gearbox(spec: MainSpec) -> bd.Part:
    """Make a tiny DC motor with planetary gearbox.

    Used for test fitting in KiCAD models, mostly.

    The gearbox output shaft starts right at Z=0.
    Body/gearbox/shaft_lip below (-Z). Shaft above (+Z).

    Wire stubs are in the +/- X direction.

    Product Listings:
        * 6mm OD, with dimensions:
            * https://www.aliexpress.com/item/1005001594735805.html

    """
    p = bd.Part(None)

    # Motor body.
    p += bd.Pos(Z=-spec.gearbox_length - spec.shaft_lip_length) * bd.Cylinder(
        spec.motor_od / 2,
        spec.motor_length,
        align=bde.align.ANCHOR_TOP,
    )

    # Draw the wires out tho bottom of the motor body.
    for x_sign in (1, -1):
        p += bd.Pos(
            X=x_sign * 2,
            Z=-spec.motor_length - spec.gearbox_length - spec.shaft_lip_length,
        ) * bd.Cylinder(
            spec.wire_od / 2,
            spec.wire_stub_length,
            align=bde.align.ANCHOR_TOP,
        )

    # Gearbox body.
    p += bd.Pos(Z=-spec.shaft_lip_length) * bd.Cylinder(
        spec.gearbox_od / 2,
        spec.gearbox_length,
        align=bde.align.ANCHOR_TOP,
    )

    # Shaft lip.
    p += bd.Cylinder(
        spec.shaft_lip_od / 2,
        spec.shaft_lip_length,
        align=bde.align.ANCHOR_TOP,
    )

    # Shaft (D-Shape).
    p += bd.Cylinder(
        spec.shaft_od / 2,
        spec.shaft_length,
        align=bde.align.ANCHOR_BOTTOM,
    ) - bd.Box(
        spec.shaft_od,
        spec.shaft_od,
        spec.shaft_length,
        align=(bd.Align.CENTER, bd.Align.MAX, bd.Align.MIN),
    ).translate((0, -(spec.shaft_od - spec.shaft_d_size), 0))

    return p


if __name__ == "__main__":
    start_time = datetime.now(UTC)
    py_file_name = Path(__file__).name
    logger.info(f"Running {py_file_name}")

    parts = {
        "dc_motor_and_gearbox_6mm_3_stages": show(
            make_dc_motor_and_gearbox(MainSpec())
        ),
    }

    logger.info("Saving CAD model(s)...")

    repo_dir = git.Repo(__file__, search_parent_directories=True).working_tree_dir
    assert repo_dir
    (export_folder := Path(repo_dir) / "build" / Path(__file__).stem).mkdir(
        exist_ok=True, parents=True
    )
    for name, part in parts.items():
        bd.export_stl(part, str(export_folder / f"{name}.stl"))
        bd.export_step(part, str(export_folder / f"{name}.step"))

    logger.info(f"Done running {py_file_name} in {datetime.now(UTC) - start_time}")
