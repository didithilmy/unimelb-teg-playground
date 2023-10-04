import copy
from typing import List, Tuple
from collections import defaultdict
from itertools import combinations
from .ifctypes import BuildingElement, Barricade, Wall, Gate, WallWithOpening
from .utils import find_lines_intersection, find_unbounded_lines_intersection, eucledian_distance, shortest_distance_between_two_lines, filter


def glue_connected_elements(elements: List[BuildingElement], tolerance: float) -> List[BuildingElement]:
    out_elements = copy.deepcopy(elements)

    def intersections_within_tolerance(element1: BuildingElement, point: Tuple[float, float]):
        intersections = []
        for element2 in out_elements:
            line1 = element1.start_vertex, element1.end_vertex
            line2 = element2.start_vertex, element2.end_vertex
            intersection = find_unbounded_lines_intersection(line1, line2)
            if intersection is not None:
                if eucledian_distance(point, intersection) <= tolerance:
                    intersections.append(intersection)
        return intersections

    def glue_two_elements(element1: BuildingElement, element2: BuildingElement, tolerance: float):
        line1 = element1.start_vertex, element1.end_vertex
        line2 = element2.start_vertex, element2.end_vertex

        # Glue walls when the gap between walls is less than tolerance.
        is_gap_small_enough = shortest_distance_between_two_lines(line1, line2) <= tolerance
        if not is_gap_small_enough:
            return

        intersection = find_unbounded_lines_intersection(line1, line2)
        if intersection is None:
            return

        w1_v1_distance_to_intersection = eucledian_distance(element1.start_vertex, intersection)
        w1_v2_distance_to_intersection = eucledian_distance(element1.end_vertex, intersection)
        w2_v1_distance_to_intersection = eucledian_distance(element2.start_vertex, intersection)
        w2_v2_distance_to_intersection = eucledian_distance(element2.end_vertex, intersection)

        if w1_v1_distance_to_intersection <= tolerance:
            w1_v1_intersection_within_tolerance = len(intersections_within_tolerance(element1, element1.start_vertex))
            if w1_v1_intersection_within_tolerance <= 1:
                element1.start_vertex = intersection
            else:
                distance_after_attachment = eucledian_distance(element1.end_vertex, intersection)
                if distance_after_attachment > element1.length:
                    element1.start_vertex = intersection

        if w1_v2_distance_to_intersection <= tolerance:
            w1_v2_intersection_within_tolerance = len(intersections_within_tolerance(element1, element1.end_vertex))
            if w1_v2_intersection_within_tolerance <= 1:
                element1.end_vertex = intersection
            else:
                distance_after_attachment = eucledian_distance(element1.start_vertex, intersection)
                if distance_after_attachment > element1.length:
                    element1.end_vertex = intersection

        if w2_v1_distance_to_intersection <= tolerance:
            w2_v1_distance_to_intersection = len(intersections_within_tolerance(element2, element2.start_vertex))
            if w2_v1_distance_to_intersection <= 1:
                element2.start_vertex = intersection
            else:
                distance_after_attachment = eucledian_distance(element2.end_vertex, intersection)
                if distance_after_attachment > element2.length:
                    element2.start_vertex = intersection

        if w2_v2_distance_to_intersection <= tolerance:
            w2_v2_distance_to_intersection = len(intersections_within_tolerance(element2, element2.end_vertex))
            if w2_v2_distance_to_intersection <= 1:
                element2.end_vertex = intersection
            else:
                distance_after_attachment = eucledian_distance(element2.start_vertex, intersection)
                if distance_after_attachment > element2.length:
                    element2.end_vertex = intersection

    for element1, element2 in combinations(out_elements, 2):
        glue_two_elements(element1, element2, tolerance=tolerance)

    return out_elements


def close_wall_gaps(elements: List[BuildingElement], tolerance):
    # Should only close disconnected vertices (i.e., nearby vertex connected to another vertex does not count)
    vertices_count = defaultdict(lambda: 0)
    for el in elements:
        vertices_count[el.start_vertex] += 1
        vertices_count[el.end_vertex] += 1

    out_elements = copy.deepcopy(elements)
    eligible_elements = filter(out_elements, lambda x: x.length > 0)
    for element1, element2 in combinations(eligible_elements, 2):
        line1 = element1.start_vertex, element1.end_vertex
        line2 = element2.start_vertex, element2.end_vertex

        candidate_edges = []
        for w1_vertex in line1:
            for w2_vertex in line2:
                if w1_vertex != w2_vertex:
                    w1_vertex_disconnected = vertices_count[w1_vertex] <= 1
                    w2_vertex_disconnected = vertices_count[w2_vertex] <= 1
                    if w1_vertex_disconnected and w2_vertex_disconnected:
                        distance = eucledian_distance(w1_vertex, w2_vertex)
                        if distance <= tolerance:
                            candidate_edges.append((w1_vertex, w2_vertex))

        if len(candidate_edges) > 0:
            edge_v1, edge_v2 = min(candidate_edges, key=lambda e: eucledian_distance(e[0], e[1]))
            connector_wall = Wall(name=f"Connector-[{element1.name}]-[{element2.name}]", start_vertex=edge_v1, end_vertex=edge_v2)
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


def decompose_wall_with_opening(wall: WallWithOpening):
    out_elements = []
    edges = set()
    vertices = [wall.start_vertex, wall.end_vertex]

    def opening_within_wall_bounds(v1, v2):
        min_x = min(wall.start_vertex[0], wall.end_vertex[0])
        max_x = max(wall.start_vertex[0], wall.end_vertex[0])
        min_y = min(wall.start_vertex[1], wall.end_vertex[1])
        max_y = max(wall.start_vertex[1], wall.end_vertex[1])

        (x1, y1), (x2, y2) = v1, v2
        return (min_x <= x1 <= max_x and min_x <= x2 <= max_x) and (min_y <= y1 <= max_y and min_y <= y2 <= max_y)

    for i, (opening_v1, opening_v2) in enumerate(wall.opening_vertices):
        if opening_within_wall_bounds(opening_v1, opening_v2):
            gate = Gate(name=f"{wall.name}:gate-{i}", start_vertex=opening_v1, end_vertex=opening_v2)
            out_elements.append(gate)
            edges.add((opening_v1, opening_v2))
            edges.add((opening_v2, opening_v1))
            vertices += [opening_v1, opening_v2]

    vertex = vertices[0]
    while True:
        nearest_vertex = min(vertices, key=lambda v: eucledian_distance(vertex, v))
        if vertex != nearest_vertex:
            if (vertex, nearest_vertex) not in edges:
                connector = Wall(name=wall.name, start_vertex=vertex, end_vertex=nearest_vertex)
                out_elements.append(connector)

        vertex = nearest_vertex
        vertices.remove(vertex)

        if len(vertices) == 0:
            break

    return out_elements


def decompose_wall_with_openings(elements: List[BuildingElement]) -> List[BuildingElement]:
    out_elements = []
    for element in elements:
        if element.__type__ == 'WallWithOpening':
            out_elements += decompose_wall_with_opening(element)
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
