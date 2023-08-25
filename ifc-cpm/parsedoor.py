import copy
import numpy as np
from itertools import combinations
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from cpm_writer import CrowdSimulationEnvironment, Level
from lib.ifctypes import Wall, Gate

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)

model = ifcopenshell.open("house.ifc")
unit_scale = ifcopenshell.util.unit.calculate_unit_scale(model)


def get_opening_vertices(opening):
    matrix = ifcopenshell.util.placement.get_local_placement(opening.ObjectPlacement)

    # Coordinatte of IfcWall origin reference
    position_matrix = matrix[:, 3][:3].reshape(-1, 1)

    # Rotation matrices, from the wall origin reference.
    xyz_rotation_matrix = matrix[:3, :3]

    # Find the rotated wall vertices relative to the wall frame of reference
    representations = opening.Representation.Representations
    print(dir(opening))
    print(opening.ContainedInStructure)
    return
    # print(door.Name, door.OverallWidth)
    origin_vertex_x, origin_vertex_y = (0, 0)
    origin_vertex_matrix = np.array([[origin_vertex_x], [origin_vertex_y], [0]])

    dest_vertex_x, dest_vertex_y = (0, door.OverallWidth)
    dest_vertex_matrix = np.array([[dest_vertex_x], [dest_vertex_y], [0]])

    transformed_origin_vertex = np.dot(xyz_rotation_matrix, origin_vertex_matrix)
    transformed_dest_vertex = np.dot(xyz_rotation_matrix, dest_vertex_matrix)

    # Calculate world coordinate
    absolute_origin_vertex = position_matrix + transformed_origin_vertex
    origin_x, origin_y, _ = np.transpose(absolute_origin_vertex)[0]
    absolute_dest_vertex = position_matrix + transformed_dest_vertex
    dest_x, dest_y, _ = np.transpose(absolute_dest_vertex)[0]

    # Convert to SI unit
    origin_x = unit_scale * origin_x
    origin_y = unit_scale * origin_y
    dest_x = unit_scale * dest_x
    dest_y = unit_scale * dest_y

    return (origin_x, origin_y), (dest_x, dest_y)


for storey in model.by_type("IfcBuildingStorey"):
    elements = ifcopenshell.util.element.get_decomposition(storey)
    walls = [x for x in elements if x.is_a("IfcWall")]
    for wall in walls:
        print(wall.Name)
        for opening in wall.HasOpenings:
            opening_element = opening.RelatedOpeningElement
            representations = [
                x
                for x in opening_element.Representation.Representations
                if x.RepresentationIdentifier == "Box"
            ]
            box_representation = representations[0]
            opening_length = box_representation.Items[0].XDim
            # print(opening_length)

            opening_location_relative_to_wall = (
                opening_element.ObjectPlacement.RelativePlacement.Location.Coordinates
            )
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
            gates_vertices.append(((x, y), (x + opening_length, y), opening_element.Name))
    
    print("Gates vertices", gates_vertices)

    start_vertex, end_vertex = get_relative_wall_vertices(ifc_wall)
    building_elements = [(start_vertex, end_vertex, "Wall", wall.Name)]
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
            wall1 = (vertex1, gate_vert1, "Wall", wall.Name)
            wall2 = (gate_vert2, vertex2, "Wall", wall.Name)
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


for wall in model.by_type("IfcWall"):
    print(wall.Name)
    decomposed = decompose_wall_openings(wall)
    print(decomposed)
    print()
    # transformation_matrix = ifcopenshell.util.placement.get_local_placement(
    #     wall.ObjectPlacement
    # )
    # elements = []
    # i = 0
    # for v1, v2, type in decomposed:
    #     i += 1
    #     v1_transform = transform_vertex(v1, transformation_matrix)
    #     v2_transform = transform_vertex(v2, transformation_matrix)
    #     if type == "Wall":
    #         elements.append(
    #             Wall(
    #                 name=f"{wall.Name} - w{i}",
    #                 start_vertex=v1_transform,
    #                 end_vertex=v2_transform,
    #             )
    #         )
    #     elif type == "Gate":
    #         elements.append(
    #             Gate(
    #                 name=f"{wall.Name} - g{i}",
    #                 start_vertex=v1_transform,
    #                 end_vertex=v2_transform,
    #             )
    #         )

    # print(elements)
