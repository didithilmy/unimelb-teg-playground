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

    # Convert to SI unit
    origin_x = unit_scale * origin_x
    origin_y = unit_scale * origin_y
    dest_x = unit_scale * dest_x
    dest_y = unit_scale * dest_y

    return (origin_x, origin_y), (dest_x, dest_y)


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


def is_point_within_line(point, line):
    x, y = point
    (x1, y1), (x2, y2) = line

    x_within_range = min(x1, x2) <= x and x <= max(x1, x2)
    y_within_range = min(y1, y2) <= y and y <= max(y1, y2)

    return x_within_range and y_within_range


def get_wall_length(wall):
    (x1, y1), (x2, y2) = wall
    return np.sqrt((abs(x2 - x1) ** 2) + (abs(y2 - y1) ** 2))


def split_line_at_point(point, line):
    """
    Input:
        point (x, y)
        line: (x1, y1), (x2, y2)
        (x, y) must fall within the line.
    """
    x, y = point
    (x1, y1), (x2, y2) = line

    return ((x1, y1), (x, y)), ((x, y), (x2, y2))


def split_intersecting_walls(walls):
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
    wall_pairs = combinations(walls, 2)
    intersections = set()
    for wall1, wall2 in wall_pairs:
        intersection = find_intersection(wall1, wall2)
        if intersection is not None:
            wall_vertices = [wall1[0], wall1[1], wall2[0], wall2[1]]
            # Only add intersections that are T or +
            if wall_vertices.count(intersection) <= 1:
                intersections.add(intersection)

    print(intersections)


cpm = CrowdSimulationEnvironment()

for storey in model.by_type("IfcBuildingStorey"):
    elements = ifcopenshell.util.element.get_decomposition(storey)
    walls = [x for x in elements if x.is_a("IfcWall")]
    walls_vertices = [get_wall_vertices(x) for x in walls]
    split_intersecting_walls(walls_vertices)

    # level = Level()

    # for wall in walls:
    #     vert1, vert2, wall_length = get_wall_vertices(wall)
    #     level.add_wall((vert1, vert2), wall_length)
    # cpm.add_level(level)

# xml = cpm.write()
# print(xml)
