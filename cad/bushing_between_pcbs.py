"""Bushings for between the PCBs."""

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

    bushing_height: float = 11.0  # 11mm measured.

    hole_id: float = 3.2
    bushing_od: float = 5.8

    pcb_hole_diameter: float = 3.0

    slot_offset_center_to_center: float = 3.0
    pcb_thickness: float = 0.6
    slot_extension_transition_distance_z: float = 5.0

    draw_top_slot: bool = True
    draw_bottom_slot: bool = True

    def __post_init__(self) -> None:
        """Post initialization checks."""
        data = {}

        logger.info(json.dumps(data, indent=2))

    def deep_copy(self) -> "Spec":
        """Copy the current spec."""
        return copy.deepcopy(self)


def bushing_between_pcbs(spec: Spec) -> bd.Part | bd.Compound:
    """Make the bushing."""
    p = bd.Part(None)

    p += bd.Cylinder(
        radius=spec.bushing_od / 2,
        height=spec.bushing_height,
        align=bde.align.ANCHOR_BOTTOM,
    )

    # On the bottom, add a pusher in the slot.
    if spec.draw_bottom_slot:
        p += bd.extrude(
            bd.SlotCenterToCenter(
                center_separation=spec.slot_offset_center_to_center,
                height=spec.pcb_hole_diameter,
            ),
            amount=spec.pcb_thickness + spec.slot_extension_transition_distance_z,
        ).translate(
            (
                -spec.slot_offset_center_to_center / 2,  # Slot starts centered.
                0,
                -spec.pcb_thickness,  # Draw it below.
            )
        ) - bd.Box(spec.hole_id, spec.bushing_od, spec.bushing_height * 4)

        p += bd.extrude(
            bd.SlotCenterToCenter(
                center_separation=spec.slot_offset_center_to_center,
                height=spec.bushing_od,
            ),
            amount=spec.slot_extension_transition_distance_z,
        ).translate(
            (
                -spec.slot_offset_center_to_center / 2,  # Slot starts centered.
                0,
                0,
            )
        )

    # On the top, add a pusher in the slot.
    if spec.draw_top_slot:
        p += bd.extrude(
            bd.SlotCenterToCenter(
                center_separation=spec.slot_offset_center_to_center,
                height=spec.pcb_hole_diameter,
            ),
            amount=spec.pcb_thickness + spec.slot_extension_transition_distance_z,
        ).translate(
            (
                spec.slot_offset_center_to_center / 2,  # Slot starts centered.
                0,
                (
                    spec.bushing_height
                    + spec.pcb_thickness
                    - spec.slot_extension_transition_distance_z
                ),
            )
        ) - bd.Box(spec.hole_id, spec.bushing_od, spec.bushing_height * 4)

        p += bd.extrude(
            bd.SlotCenterToCenter(
                center_separation=spec.slot_offset_center_to_center,
                height=spec.bushing_od,
            ),
            amount=spec.slot_extension_transition_distance_z,
        ).translate(
            (
                spec.slot_offset_center_to_center / 2,  # Slot starts centered.
                0,
                (spec.bushing_height - spec.slot_extension_transition_distance_z),
            )
        )

    # Remove hole.
    p -= bd.Cylinder(
        radius=spec.hole_id / 2,
        height=spec.bushing_height * 4,
    )

    return p


if __name__ == "__main__":
    start_time = datetime.now(UTC)
    py_file_name = Path(__file__).name
    logger.info(f"Running {py_file_name}")

    parts = {
        "bushing_between_pcbs": show(bushing_between_pcbs(Spec())),
    }

    logger.info("Saving CAD model(s)")

    (
        export_folder := Path(__file__).parent.parent / "build" / Path(__file__).stem
    ).mkdir(exist_ok=True, parents=True)
    for name, part in parts.items():
        bd.export_stl(part, str(export_folder / f"{name}.stl"))
        bd.export_step(part, str(export_folder / f"{name}.step"))

    logger.info(f"Done running {py_file_name} in {datetime.now(UTC) - start_time}")
