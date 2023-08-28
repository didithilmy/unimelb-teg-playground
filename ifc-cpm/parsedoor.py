import copy
from typing import List
import numpy as np
from itertools import combinations
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from cpm_writer import CrowdSimulationEnvironment, Level
from lib.ifctypes import Wall, Gate, BuildingElement

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

model = ifcopenshell.open("house.ifc")
unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)


# for storey in model.by_type("IfcBuildingStorey"):
#     elements = ifcopenshell.util.element.get_decomposition(storey)
#     walls = [x for x in elements if x.is_a("IfcWall")]
#     for wall in walls:
#         print(wall.Name)
#         for opening in wall.HasOpenings:
#             opening_element = opening.RelatedOpeningElement
#             representations = [
#                 x
#                 for x in opening_element.Representation.Representations
#                 if x.RepresentationIdentifier == "Box"
#             ]
#             box_representation = representations[0]
#             opening_length = box_representation.Items[0].XDim
#             # print(opening_length)

#             opening_location_relative_to_wall = (
#                 opening_element.ObjectPlacement.RelativePlacement.Location.Coordinates
#             )
            # print((opening_location_relative_to_wall))
            # print(dir(opening_element))
            # matrix = ifcopenshell.util.placement.get_local_placement(opening_element.ObjectPlacement)
            # print(matrix)
            # print(opening_element.Name, (opening_element.Representation.Representations[1].Items))
            # Opening length can be retrieved from IfcBoundingBox here

        # get_opening_vertices(opening)
        # print("Opening", opening.Name, opening)


def get_relative_wall_vertices(ifc_wall):
    representations = ifc_wall.Representation.Representations
    axis_representation = [
        x for x in representations if x.RepresentationType == "Curve2D"
    ]
    origin_vertex, dest_vertex = axis_representation[0].Items[0].Points
    origin_vertex_x, origin_vertex_y = origin_vertex.Coordinates
    dest_vertex_x, dest_vertex_y = dest_vertex.Coordinates

    return (origin_vertex_x, origin_vertex_y), (dest_vertex_x, dest_vertex_y)


def decompose_wall_openings(ifc_wall):
    """
    Input: IfcWall
    Output: Array of [
        Wall, Gate, Wall
    ]
    """
    gates_vertices = []
    openings = ifc_wall.HasOpenings
    for opening in openings:
        opening_element = opening.RelatedOpeningElement
        representations = [
            x
            for x in opening_element.Representation.Representations
            if x.RepresentationIdentifier == "Box"
        ]
        box_representation = representations[0]
        opening_length = box_representation.Items[0].XDim

        # TODO investigate: Wand-Int-ERDG-2 has x+length more than the wall length.
        # This measure may not be entirely accurate?
        opening_location_relative_to_wall = (
            opening_element.ObjectPlacement.RelativePlacement.Location.Coordinates
        )

        x, y, z = opening_location_relative_to_wall
        if z == 0:
            gates_vertices.append(
                ((x, y), (x + opening_length, y), opening_element.Name)
            )

    # print("Gates vertices", gates_vertices)

    start_vertex, end_vertex = get_relative_wall_vertices(ifc_wall)
    building_elements = [(start_vertex, end_vertex, "Wall", ifc_wall.Name)]
    out_building_elements = []

    def get_first_contained_gate(p1, p2):
        p1_x, p1_y = min(p1[0], p2[0]), min(p1[1], p2[1])
        p2_x, p2_y = max(p1[0], p2[0]), min(p1[1], p2[1])
        for gate_vertices in gates_vertices:
            (g1_x, g1_y), (g2_x, g2_y), name = gate_vertices

            # Offset with wall starting vertex
            g1_x += start_vertex[0]
            g1_y += start_vertex[1]
            g2_x += start_vertex[0]
            g2_y += start_vertex[1]

            if g1_x >= p1_x and g2_x <= p2_x and g1_y >= p1_y and g2_y <= p2_y:
                return gate_vertices

    while len(building_elements) > 0:
        vertex1, vertex2, type, name = building_elements.pop(0)
        gate_vertices = get_first_contained_gate(vertex1, vertex2)
        if gate_vertices is None:
            out_building_elements.append((vertex1, vertex2, type, name))
        else:
            gate_vert1, gate_vert2, gate_name = gate_vertices
            wall1 = (vertex1, gate_vert1, "Wall", ifc_wall.Name)
            wall2 = (gate_vert2, vertex2, "Wall", ifc_wall.Name)
            gate = (gate_vert1, gate_vert2, "Gate", gate_name)
            building_elements += [wall1, gate, wall2]
            gates_vertices.remove(gate_vertices)

    return out_building_elements


def transform_vertex(vertex, transformation_matrix):
    x, y = vertex

    # Coordinate of IfcWall origin reference
    position_matrix = transformation_matrix[:, 3][:3].reshape(-1, 1)

    # Rotation matrices, from the wall origin reference.
    xyz_rotation_matrix = transformation_matrix[:3, :3]

    vertex_matrix = np.array([[x], [y], [0]])
    transformed_vertex = np.dot(xyz_rotation_matrix, vertex_matrix)

    # Calculate world coordinate
    absolute_vertex = position_matrix + transformed_vertex
    transformed_x, transformed_y, _ = np.transpose(absolute_vertex)[0]
    return (transformed_x, transformed_y)


def split_element_at_point(point, element: BuildingElement):
    """
    Input:
        point (x, y)
        line: (x1, y1), (x2, y2)
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


def find_intersection(line1, line2):
    line1_point1, line1_point2 = line1
    line2_point1, line2_point2 = line2

    x1, y1 = line1_point1
    x2, y2 = line1_point2
    x3, y3 = line2_point1
    x4, y4 = line2_point2

    # Calculate slopes and intercepts of the two lines, if the line is NOT vertical.
    m1, b1 = None, None
    if x1 != x2:
        m1 = (y2 - y1) / (x2 - x1)
        b1 = y1 - m1 * x1

    m2, b2 = None, None
    if x3 != x4:
        m2 = (y4 - y3) / (x4 - x3)
        b2 = y3 - m2 * x3

    if m1 == m2 and m1 is not None and m2 is not None:
        return None

    if m1 is None and m2 is None:
        if x1 == x3:
            return None  # FIXME TODO handle lines occupying the same space.
        return None

    if m1 is None:
        intersection_x = x1
        intersection_y = m2 * intersection_x + b2
    elif m2 is None:
        intersection_x = x3
        intersection_y = m1 * intersection_x + b1
    else:
        intersection_x = (b2 - b1) / (m1 - m2)
        intersection_y = m1 * intersection_x + b1

    # Check if the intersection point is within the bounds of both line segments
    if (
        min(x1, x2) <= intersection_x <= max(x1, x2)
        and min(y1, y2) <= intersection_y <= max(y1, y2)
        and min(x3, x4) <= intersection_x <= max(x3, x4)
        and min(y3, y4) <= intersection_y <= max(y3, y4)
    ):
        return intersection_x, intersection_y
    else:
        return None  # No intersection within bounds


def find_first_intersection(
    target_element: BuildingElement, other_elements: List[BuildingElement]
):
    for other_element in other_elements:
        target_line = target_element.start_vertex, target_element.end_vertex
        other_line = other_element.start_vertex, other_element.end_vertex
        intersection = find_intersection(target_line, other_line)
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


def split_intersecting_elements(elements: List[BuildingElement]):
    """
    Split intersecting walls to get new vertex.
    Input:
    walls: array of [
        ((x1, y1), (x2, y2))
    ]

    Output:
    walls: array of [
        ((x1, y1), (x2, y2))
    ]
    """
    elements_queue = copy.copy(elements)
    output_elements = []
    while len(elements_queue) > 0:
        element = elements_queue.pop(0)
        intersection = find_first_intersection(element, elements_queue)
        if intersection is None:
            output_elements.append(element)
        else:
            split_elements = split_element_at_point(intersection, element)
            elements_queue += split_elements

    return output_elements


def get_storey_elements(storey):
    elements = ifcopenshell.util.element.get_decomposition(storey)
    walls = [x for x in elements if x.is_a("IfcWall")]
    building_elements = []
    for wall in walls:
        decomposed = decompose_wall_openings(wall)
        transformation_matrix = ifcopenshell.util.placement.get_local_placement(
            wall.ObjectPlacement
        )
        i = 0
        for v1, v2, type, name in decomposed:
            i += 1
            v1_transform = transform_vertex(v1, transformation_matrix)
            v2_transform = transform_vertex(v2, transformation_matrix)
            if type == "Wall":
                building_elements.append(
                    Wall(
                        name=f"{wall.Name} - w{i}",
                        start_vertex=v1_transform,
                        end_vertex=v2_transform,
                    )
                )
            elif type == "Gate":
                building_elements.append(
                    Gate(
                        name=f"{wall.Name} - g{i}",
                        start_vertex=v1_transform,
                        end_vertex=v2_transform,
                    )
                )
    building_elements = split_intersecting_elements(building_elements)
    return building_elements


# for wall in model.by_type("IfcWall"):
#     print(wall.Name)
#     decomposed = decompose_wall_openings(wall)
#     transformation_matrix = ifcopenshell.util.placement.get_local_placement(
#         wall.ObjectPlacement
#     )
#     elements = []
#     i = 0
#     for v1, v2, type, name in decomposed:
#         i += 1
#         v1_transform = transform_vertex(v1, transformation_matrix)
#         v2_transform = transform_vertex(v2, transformation_matrix)
#         if type == "Wall":
#             elements.append(
#                 Wall(
#                     name=f"{wall.Name} - w{i}",
#                     start_vertex=v1_transform,
#                     end_vertex=v2_transform,
#                 )
#             )
#         elif type == "Gate":
#             elements.append(
#                 Gate(
#                     name=f"{wall.Name} - g{i}",
#                     start_vertex=v1_transform,
#                     end_vertex=v2_transform,
#                 )
#             )

#     elements = split_intersecting_elements(elements)
#     print(elements)

cpm = CrowdSimulationEnvironment()

for storey in model.by_type("IfcBuildingStorey"):
    elements = get_storey_elements(storey)
    # print(elements)

    level = Level()
    for element in elements:
        if element.__type__ == "Wall":
            vertices = element.start_vertex, element.end_vertex
            level.add_wall(vertices, element.length)
        elif element.__type__ == "Gate":
            vertices = element.start_vertex, element.end_vertex
            level.add_gate(vertices, element.length)

    cpm.add_level(level)

xml = cpm.write()
print(xml)
