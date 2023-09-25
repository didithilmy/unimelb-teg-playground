from typing import Tuple, Any
import logging
import ifcopenshell.util.element
import ifcopenshell.util.placement
import numpy as np
import copy
from typing import List, Tuple
from collections import defaultdict
from itertools import combinations
from .ifctypes import BuildingElement, Barricade, Wall, Gate
from .utils import find_lines_intersection, find_unbounded_lines_intersection, find, eucledian_distance
from .utils import filter, get_composite_verts
from .ifctypes import BuildingElement
from .representation_helpers import WallVertices


logger = logging.getLogger("Walls")


class WallWithOpening(BuildingElement):
    __type__ = "WallWithOpening"
    opening_vertices = []
    connected_to = []

    def __init__(self, *args, opening_vertices=[], connected_to=[], **kwargs):
        super().__init__(*args, **kwargs, type="WallWithOpening")
        self.opening_vertices = opening_vertices
        self.connected_to = connected_to

    @staticmethod
    def from_ifc_wall(ifc_wall):
        # TODO parse opening
        opening_vertices = []

        print("Inferring wall vertices for wall " + ifc_wall.Name)
        matrix = ifcopenshell.util.placement.get_local_placement(ifc_wall.ObjectPlacement)
        wall_v1, wall_v2 = WallVertices.from_product(ifc_wall)
        connected_to = [(x.RelatedElement.GlobalId, x.RelatingConnectionType) for x in ifc_wall.ConnectedTo]
        return WallWithOpening(object_id=ifc_wall.GlobalId, name=ifc_wall.Name, start_vertex=wall_v1, end_vertex=wall_v2, opening_vertices=opening_vertices, connected_to=connected_to)


def get_walls_by_storey(ifc_building):
    walls_map = dict()
    walls = get_all_walls(ifc_building)

    building_elements = ifcopenshell.util.element.get_decomposition(ifc_building)
    storeys = filter(building_elements, matcher=lambda x: x.is_a("IfcBuildingStorey"))
    for storey in storeys:
        elevation = ifcopenshell.util.placement.get_storey_elevation(storey)
        walls_in_storey = []
        for (ifc_wall, wall_with_opening, z_min, z_max) in walls:
            tolerance = 500  # FIXME scale relative to unit
            if z_min <= elevation + tolerance and z_max >= elevation - tolerance:
                walls_in_storey.append((ifc_wall, wall_with_opening))
        walls_map[storey] = walls_in_storey
    return walls_map


def get_all_walls(ifc_building) -> Tuple[Any, WallWithOpening, float, float]:
    building_elements = ifcopenshell.util.element.get_decomposition(ifc_building)
    walls = filter(building_elements, matcher=lambda x: x.is_a("IfcWall") or x.is_a("IfcCurtainWall"))
    out = []
    for ifc_wall in walls:
        try:
            wall_with_opening = WallWithOpening.from_ifc_wall(ifc_wall)
            z_min, z_max = _wall_z_extremes(ifc_wall)
            out.append((ifc_wall, wall_with_opening, z_min, z_max))
        except Exception as exc:
            logger.warning(f"Skipped wall parsing: error parsing wall {ifc_wall.Name}: {exc}")
            logger.error(exc, exc_info=True)
    return out


def infer_wall_connections(tolerance, building_elements: List[BuildingElement]) -> List[BuildingElement]:
    # TODO evaluate if this method is reliable
    walls = [x for x in building_elements if x.__type__ in ('Wall', 'WallWithOpening')]
    for wall1, wall2 in combinations(walls, 2):
        wall1_vertices = (wall1.start_vertex, wall1.end_vertex)
        wall2_vertices = (wall2.start_vertex, wall2.end_vertex)
        intersection = find_unbounded_lines_intersection(wall1_vertices, wall2_vertices)
        if intersection is not None:
            # Wall has intersection
            w1_v1_distance_to_intersection = eucledian_distance(wall1.start_vertex, intersection)
            w1_v2_distance_to_intersection = eucledian_distance(wall1.end_vertex, intersection)
            w2_v1_distance_to_intersection = eucledian_distance(wall2.start_vertex, intersection)
            w2_v2_distance_to_intersection = eucledian_distance(wall2.end_vertex, intersection)

            wall1_near_intersection = w1_v1_distance_to_intersection <= tolerance or w1_v2_distance_to_intersection <= tolerance
            wall2_near_intersection = w2_v1_distance_to_intersection <= tolerance or w2_v2_distance_to_intersection <= tolerance
            if wall1_near_intersection or wall2_near_intersection:
                # Wall 1 and 2 has connections
                if wall2.object_id not in wall1.connected_to:
                    connection_type = "ATSTART" if wall1_near_intersection and wall1_near_intersection else "ATPATH"
                    wall1.connected_to.append((wall2.object_id, connection_type))

    return walls


def glue_connected_walls(building_elements: List[BuildingElement], tolerance=None) -> List[BuildingElement]:
    walls = [x for x in building_elements if x.__type__ in ('WallWithOpening', 'Wall')]
    for wall in walls:
        for (connected_wall_id, connection_type) in wall.connected_to:
            related_wall = find(walls, lambda x: x.object_id == connected_wall_id)
            if related_wall is not None:
                intersection = find_unbounded_lines_intersection(
                    (wall.start_vertex, wall.end_vertex),
                    (related_wall.start_vertex, related_wall.end_vertex),
                )

                if intersection:
                    # Update related wall vertices
                    v1_distance = eucledian_distance(related_wall.start_vertex, intersection)
                    v2_distance = eucledian_distance(related_wall.end_vertex, intersection)

                    if tolerance is None or v1_distance <= tolerance or v2_distance <= tolerance:
                        if v1_distance < v2_distance:
                            related_wall.start_vertex = intersection
                        else:
                            related_wall.end_vertex = intersection

                        # Update current wall vertices
                        if connection_type != 'ATPATH':
                            wall_v1_distance = eucledian_distance(
                                wall.start_vertex, intersection
                            )
                            wall_v2_distance = eucledian_distance(wall.end_vertex, intersection)
                            if wall_v1_distance < wall_v2_distance:
                                wall.start_vertex = intersection
                            else:
                                wall.end_vertex = intersection

    return building_elements


def decompose_wall_with_openings(elements: List[BuildingElement]) -> List[BuildingElement]:
    out_elements = []
    for element in elements:
        if element.__type__ == 'WallWithOpening':
            gates_vertices = element.opening_vertices

            def get_first_contained_gate(p1, p2):
                p1_x, p1_y = min(p1[0], p2[0]), min(p1[1], p2[1])
                p2_x, p2_y = max(p1[0], p2[0]), max(p1[1], p2[1])
                for gate_vertices in gates_vertices:
                    (g1_x, g1_y), (g2_x, g2_y) = gate_vertices
                    if g1_x >= p1_x and g2_x <= p2_x and g1_y >= p1_y and g2_y <= p2_y:
                        return gate_vertices

            elements_queue = [Wall(name=element.name, start_vertex=element.start_vertex, end_vertex=element.end_vertex)]
            while len(elements_queue) > 0:
                el = elements_queue.pop(0)
                gate_vertices = get_first_contained_gate(el.start_vertex, el.end_vertex)
                if gate_vertices is None:
                    out_elements.append(el)
                else:
                    gate_vert1, gate_vert2 = gate_vertices
                    wall1 = Wall(name=element.name, start_vertex=el.start_vertex, end_vertex=gate_vert1)
                    wall2 = Wall(name=element.name, start_vertex=gate_vert2, end_vertex=el.end_vertex)
                    gate = Gate(name=element.name, start_vertex=gate_vert1, end_vertex=gate_vert2)
                    elements_queue += [wall1, gate, wall2]
                    gates_vertices.remove(gate_vertices)

        else:
            out_elements.append(element)

    return out_elements


def convert_disconnected_walls_into_barricades(elements: List[BuildingElement]):
    vertices_count = defaultdict(lambda: 0)
    for el in elements:
        vertices_count[el.start_vertex] += 1
        vertices_count[el.end_vertex] += 1

    output_elements = copy.copy(elements)
    walls = [x for x in output_elements if x.__type__ == "Wall"]
    for wall in walls:
        if (
            vertices_count[wall.start_vertex] < 2
            or vertices_count[wall.end_vertex] < 2
        ):
            barricade = Barricade(
                object_id=wall.object_id,
                name=wall.name,
                start_vertex=wall.start_vertex,
                end_vertex=wall.end_vertex,
            )
            output_elements.remove(wall)
            output_elements.append(barricade)

    return output_elements


def _wall_z_extremes(ifc_wall):
    vertices = get_composite_verts(ifc_wall)
    flattened = np.array(vertices).flatten()
    z_verts = flattened[2::3]
    return min(z_verts), max(z_verts)
