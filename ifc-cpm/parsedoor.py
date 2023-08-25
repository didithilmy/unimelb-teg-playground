import copy
import numpy as np
from itertools import combinations
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from cpm_writer import CrowdSimulationEnvironment, Level

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
            representations = [x for x in opening_element.Representation.Representations if x.RepresentationIdentifier == 'Box']
            box_representation = representations[0]
            opening_length = box_representation.Items[0].XDim
            print(opening_length)

            opening_location_relative_to_wall = opening_element.ObjectPlacement.RelativePlacement.Location
            print(opening_location_relative_to_wall)
            # print(dir(opening_element))
            # matrix = ifcopenshell.util.placement.get_local_placement(opening_element.ObjectPlacement)
            # print(matrix)
            # print(opening_element.Name, (opening_element.Representation.Representations[1].Items))
            # Opening length can be retrieved from IfcBoundingBox here

        # get_opening_vertices(opening)
        # print("Opening", opening.Name, opening)
