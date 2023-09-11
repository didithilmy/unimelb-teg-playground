import copy
from typing import List, Tuple
from collections import defaultdict
from itertools import combinations
from .ifctypes import BuildingElement, Barricade, Wall, Gate
from .utils import find_lines_intersection, find_unbounded_lines_intersection, find, eucledian_distance


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


def join_connected_walls(building_elements: List[BuildingElement]) -> List[BuildingElement]:
    walls = [x for x in building_elements if x.__type__ == 'WallWithOpening']
    for wall in walls:
        for (connected_wall_id, connection_type) in wall.connected_to:
            related_wall = find(
                walls, lambda x: x.object_id == connected_wall_id
            )
            intersection = find_unbounded_lines_intersection(
                (wall.start_vertex, wall.end_vertex),
                (related_wall.start_vertex, related_wall.end_vertex),
            )

            if intersection:
                # Update related wall vertices
                v1_distance = eucledian_distance(
                    related_wall.start_vertex, intersection
                )
                v2_distance = eucledian_distance(
                    related_wall.end_vertex, intersection
                )
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


def split_intersecting_elements(elements: List[BuildingElement]) -> List[BuildingElement]:
    """
    Split intersecting elements to get new vertices.
    Input: Array of BuildingElement
    Output: Array of BuildingElement
    """
    elements_queue = copy.copy(elements)
    output_elements = []
    while len(elements_queue) > 0:
        element = elements_queue.pop(0)
        intersection = _find_first_intersection(element, elements_queue)
        if intersection is None:
            output_elements.append(element)
        else:
            split_elements = _split_element_at_point(intersection, element)
            elements_queue += split_elements

    return output_elements


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

            elements_queue = [Wall(start_vertex=element.start_vertex, end_vertex=element.end_vertex)]
            while len(elements_queue) > 0:
                el = elements_queue.pop(0)
                gate_vertices = get_first_contained_gate(el.start_vertex, el.end_vertex)
                if gate_vertices is None:
                    out_elements.append(el)
                else:
                    gate_vert1, gate_vert2 = gate_vertices
                    wall1 = Wall(start_vertex=el.start_vertex, end_vertex=gate_vert1)
                    wall2 = Wall(start_vertex=gate_vert2, end_vertex=el.end_vertex)
                    gate = Gate(start_vertex=gate_vert1, end_vertex=gate_vert2)
                    elements_queue += [wall1, gate, wall2]
                    gates_vertices.remove(gate_vertices)

        else:
            out_elements.append(element)

    return out_elements


def _find_first_intersection(target_element: BuildingElement, other_elements: List[BuildingElement]) -> Tuple[float, float]:
    for other_element in other_elements:
        target_line = target_element.start_vertex, target_element.end_vertex
        other_line = other_element.start_vertex, other_element.end_vertex
        intersection = find_lines_intersection(target_line, other_line)
        if intersection is not None:
            wall_vertices = [
                target_line[0],
                target_line[1],
                other_line[0],
                other_line[1],
            ]
            # Only add intersections that are T or +
            if wall_vertices.count(intersection) <= 1:
                return intersection
    return None


def _split_element_at_point(point, element: BuildingElement):
    """
    Input:
        point (x, y)
        element: BuildingElement
        (x, y) must fall within the line.
    """
    x, y = point
    (x1, y1), (x2, y2) = element.start_vertex, element.end_vertex

    element1 = BuildingElement(
        type=element.__type__,
        name=f"{element.name}-1",
        start_vertex=(x1, y1),
        end_vertex=(x, y),
    )

    element2 = BuildingElement(
        type=element.__type__,
        name=f"{element.name}-2",
        start_vertex=(x, y),
        end_vertex=(x2, y2),
    )

    out = []
    if element1.length > 0:
        out.append(element1)

    if element2.length > 0:
        out.append(element2)

    return out
