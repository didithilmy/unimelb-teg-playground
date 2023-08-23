import numpy as np
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


def get_wall_vertices(wall):
    matrix = ifcopenshell.util.placement.get_local_placement(wall.ObjectPlacement)

    # Coordinate of IfcWall origin reference
    position_matrix = matrix[:, 3][:3].reshape(-1, 1)

    # Rotation matrices, from the wall origin reference.
    xyz_rotation_matrix = matrix[:3, :3]

    # Find the rotated wall vertices relative to the wall frame of reference
    representations = wall.Representation.Representations
    axis_representation = [
        x for x in representations if x.RepresentationType == "Curve2D"
    ]
    origin_vertex, dest_vertex = axis_representation[0].Items[0].Points

    origin_vertex_x, origin_vertex_y = origin_vertex.Coordinates
    origin_vertex_matrix = np.array([[origin_vertex_x], [origin_vertex_y], [0]])

    dest_vertex_x, dest_vertex_y = dest_vertex.Coordinates
    dest_vertex_matrix = np.array([[dest_vertex_x], [dest_vertex_y], [0]])

    transformed_origin_vertex = np.dot(xyz_rotation_matrix, origin_vertex_matrix)
    transformed_dest_vertex = np.dot(xyz_rotation_matrix, dest_vertex_matrix)

    # Calculate world coordinate
    absolute_origin_vertex = position_matrix + transformed_origin_vertex
    origin_x, origin_y, _ = np.transpose(absolute_origin_vertex)[0]
    absolute_dest_vertex = position_matrix + transformed_dest_vertex
    dest_x, dest_y, _ = np.transpose(absolute_dest_vertex)[0]

    # Calculate wall length (eucledian distance)
    wall_length = np.sqrt((abs(dest_x - origin_x) ** 2) + abs(dest_y - origin_y) ** 2)

    # Convert to SI unit
    origin_x = unit_scale * origin_x
    origin_y = unit_scale * origin_y
    dest_x = unit_scale * dest_x
    dest_y = unit_scale * dest_y
    wall_length = unit_scale * wall_length

    return (origin_x, origin_y), (dest_x, dest_y), wall_length


cpm = CrowdSimulationEnvironment()

for storey in model.by_type("IfcBuildingStorey"):
    elements = ifcopenshell.util.element.get_decomposition(storey)
    walls = [x for x in elements if x.is_a("IfcWall")]

    level = Level()

    for wall in walls:
        vert1, vert2, wall_length = get_wall_vertices(wall)
        level.add_wall((vert1, vert2), wall_length)
    cpm.add_level(level)

xml = cpm.write()
print(xml)
