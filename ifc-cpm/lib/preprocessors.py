import copy
from typing import List, Tuple
from collections import defaultdict
from itertools import combinations
from .ifctypes import BuildingElement, Barricade, Wall, Gate
from .utils import find_lines_intersection, find_unbounded_lines_intersection, find, eucledian_distance, shortest_distance_between_two_lines


def glue_connected_elements(elements: List[BuildingElement], tolerance: float) -> List[BuildingElement]:
    out_elements = copy.deepcopy(elements)
    n = len(out_elements)
    for i1, i2 in combinations(range(n), 2):
        element1 = out_elements[i1]
        element2 = out_elements[i2]

        line1 = element1.start_vertex, element1.end_vertex
        line2 = element2.start_vertex, element2.end_vertex

        # Glue walls when the gap between walls is less than tolerance.
        is_gap_small_enough = shortest_distance_between_two_lines(line1, line2) <= tolerance
        if not is_gap_small_enough:
            continue

        intersection = find_unbounded_lines_intersection(line1, line2)
        if intersection is None:
            continue

        w1_v1_distance_to_intersection = eucledian_distance(element1.start_vertex, intersection)
        w1_v2_distance_to_intersection = eucledian_distance(element1.end_vertex, intersection)
        w2_v1_distance_to_intersection = eucledian_distance(element2.start_vertex, intersection)
        w2_v2_distance_to_intersection = eucledian_distance(element2.end_vertex, intersection)

        if w1_v1_distance_to_intersection <= tolerance:
            element1.start_vertex = intersection
        if w1_v2_distance_to_intersection <= tolerance:
            element1.end_vertex = intersection
        if w2_v1_distance_to_intersection <= tolerance:
            element2.start_vertex = intersection
        if w2_v2_distance_to_intersection <= tolerance:
            element2.end_vertex = intersection

        # Handle walls with near vertices but far away intersection.
        # This indicates that the walls are near parallel, but the vertices are close.
        # In this case, draw a new wall that connects the two.
        intersection_is_nearby = min(w1_v1_distance_to_intersection, w1_v2_distance_to_intersection, w2_v1_distance_to_intersection, w2_v2_distance_to_intersection) <= tolerance
        if not intersection_is_nearby:
            for w1_vertex in line1:
                for w2_vertex in line2:
                    if w1_vertex != w2_vertex:
                        distance = eucledian_distance(w1_vertex, w2_vertex)
                        if distance <= tolerance:
                            print(distance, tolerance)
                            connector_wall = Wall(name=f"Connector-[{element1.name}]-[{element2.name}]", start_vertex=w1_vertex, end_vertex=w2_vertex)
                            out_elements.append(connector_wall)

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
