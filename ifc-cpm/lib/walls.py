from typing import Tuple, Any
import ifcopenshell.util.element
import ifcopenshell.util.placement
import numpy as np
from typing import Tuple
from .utils import filter, get_composite_verts, get_sorted_building_storeys
from .logger import logger


def get_walls_by_storey(ifc_building, min_wall_height, wall_offset_tolerance):
    walls_map = dict()
    ifc_walls = get_all_walls(ifc_building)

    sorted_storeys = get_sorted_building_storeys(ifc_building)
    for i, storey in enumerate(sorted_storeys):
        elevation = ifcopenshell.util.placement.get_storey_elevation(storey)
        walls_in_storey = []
        for (ifc_wall, z_min, z_max) in ifc_walls:
            tolerance = wall_offset_tolerance
            wall_contained_within_boundary = (z_min <= elevation + tolerance and z_max >= elevation + min_wall_height - tolerance)
            if wall_contained_within_boundary:
                walls_in_storey.append(ifc_wall)
        walls_map[storey] = walls_in_storey
    return walls_map


def get_all_walls(ifc_building) -> Tuple[Any, float, float]:
    logger.debug("Retrieving walls...")
    building_elements = ifcopenshell.util.element.get_decomposition(ifc_building)
    walls = filter(building_elements, matcher=lambda x: x.is_a("IfcWall") or x.is_a("IfcCurtainWall"))
    out = []
    for ifc_wall in walls:
        try:
            z_min, z_max = _wall_z_extremes(ifc_wall)
            out.append((ifc_wall, z_min, z_max))
        except Exception as exc:
            logger.warning(f"Skipped wall parsing: error parsing wall {ifc_wall.Name}: {exc}")
            logger.error(exc, exc_info=True)
    return out


def _wall_z_extremes(ifc_wall):
    vertices = get_composite_verts(ifc_wall)
    flattened = np.array(vertices).flatten()
    z_verts = flattened[2::3]
    return min(z_verts), max(z_verts)
