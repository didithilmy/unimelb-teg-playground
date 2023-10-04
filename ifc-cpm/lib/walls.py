from typing import Tuple, Any
import logging
import ifcopenshell.util.element
import ifcopenshell.util.placement
import numpy as np
import copy
from typing import List, Tuple
from collections import defaultdict
from itertools import combinations
from skspatial.objects import Line
from .ifctypes import BuildingElement, Barricade, Wall, Gate
from .utils import transform_vertex, find, filter, find_unbounded_lines_intersection, truncate, get_oriented_xy_bounding_box, get_edge_from_bounding_box, eucledian_distance
from .utils import filter, get_composite_verts, get_sorted_building_storeys
from .ifctypes import BuildingElement, WallWithOpening
from .representation_helpers import WallVertices


logger = logging.getLogger("Walls")

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, False)
settings.set(settings.CONVERT_BACK_UNITS, True)


def get_walls_by_storey(ifc_building):
    walls_map = dict()
    ifc_walls = get_all_walls(ifc_building)

    sorted_storeys = get_sorted_building_storeys(ifc_building)
    for i, storey in enumerate(sorted_storeys):
        elevation = ifcopenshell.util.placement.get_storey_elevation(storey)
        walls_in_storey = []
        for (ifc_wall, z_min, z_max) in ifc_walls:
            tolerance = 100  # FIXME scale relative to unit
            wall_contained_within_boundary = (z_min <= elevation + tolerance and z_max >= elevation + 1000 - tolerance)
            if wall_contained_within_boundary:
                walls_in_storey.append(ifc_wall)
        walls_map[storey] = walls_in_storey
    return walls_map


def get_all_walls(ifc_building) -> Tuple[Any, float, float]:
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
