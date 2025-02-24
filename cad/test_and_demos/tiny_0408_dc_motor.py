"""Model of the tiny 0408 DC motor."""

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
    """Specification for the tiny 4008 DC motor."""

    motor_od: float = 4

    motor_length: float = 8

    shaft_lip_od: float = 2.0
    shaft_lip_length: float = 0.5

    shaft_length: float = 2.0
    shaft_od: float = 0.7

    wire_od: float = 0.5
    wire_stub_length: float = 1
    wire_separation: float = 2.6

    def __post_init__(self) -> None:
        """Post initialization checks."""
        data = {}
        logger.info(json.dumps(data, indent=2))

    def deep_copy(self) -> "MainSpec":
        """Copy the current spec."""
        return copy.deepcopy(self)


def make_dc_motor(spec: MainSpec) -> bd.Part | bd.Compound:
    """Make a tiny DC motor.

    Used for test fitting in KiCAD models, mostly.

    For flush-mounting into a PCB. Motor body starts at Z=0.

    Wire stubs are in the +/- X direction.
    """
    p = bd.Part(None)

    # Motor body.
    p += bd.Cylinder(
        spec.motor_od / 2,
        spec.motor_length,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # Draw the wires out tho bottom of the motor body.
    for x_value in bde.evenly_space_with_center(count=2, spacing=spec.wire_separation):
        p += bd.Pos(X=x_value) * bd.Cylinder(
            spec.wire_od / 2,
            spec.wire_stub_length,
            align=bde.align.ANCHOR_TOP,
        )

    # Shaft lip.
    p += bd.Pos(Z=spec.motor_length) * bd.Cylinder(
        spec.shaft_lip_od / 2,
        spec.shaft_lip_length,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # Shaft.
    p += bd.Pos(Z=spec.motor_length + spec.shaft_lip_length) * bd.Cylinder(
        spec.shaft_od / 2,
        spec.shaft_length,
        align=bde.align.ANCHOR_BOTTOM,
    )

    return p


if __name__ == "__main__":
    start_time = datetime.now(UTC)
    py_file_name = Path(__file__).name
    logger.info(f"Running {py_file_name}")

    parts = {
        "dc_motor_0408": show(make_dc_motor(MainSpec())),
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
