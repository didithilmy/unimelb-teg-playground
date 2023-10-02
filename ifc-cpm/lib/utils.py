from typing import Tuple
import math
import numpy as np
import ifcopenshell.util.element
import ifcopenshell.util.shape
import ifcopenshell.util.placement
import ifcopenshell.geom
from compas.geometry import oriented_bounding_box_xy_numpy


def get_sorted_building_storeys(ifc_building):
    building_elements = ifcopenshell.util.element.get_decomposition(ifc_building)
    storeys = [x for x in building_elements if x.is_a("IfcBuildingStorey")]
    sorted_storeys = sorted(storeys, key=lambda s: s.Elevation)
    return sorted_storeys


def transform_vertex(transformation_matrix, vertex: Tuple[float, float]) -> Tuple[float, float]:
    x, y = vertex

    vertex_matrix = np.array([[x], [y], [0], [1]])
    transformed_matrix = np.dot(transformation_matrix, vertex_matrix)
    transformed_x, transformed_y, _, _ = np.transpose(transformed_matrix)[0]
    return (transformed_x, transformed_y)


def transform_vertex_3d(transformation_matrix, vertex: Tuple[float, float, float]) -> Tuple[float, float, float]:
    x, y, z = vertex

    vertex_matrix = np.array([[x], [y], [z], [1]])
    transformed_matrix = np.dot(transformation_matrix, vertex_matrix)
    transformed_x, transformed_y, transformed_z, _ = np.transpose(transformed_matrix)[0]
    return (transformed_x, transformed_y, transformed_z)


# TODO find permanent solution for rounding error
def truncate(number, digits=4) -> float:
    # Improve accuracy with floating point operations, to avoid truncate(16.4, 2) = 16.39 or truncate(-1.13, 2) = -1.12
    nbDecimals = len(str(number).split('.')[1])
    if nbDecimals <= digits:
        return number
    stepper = 10.0 ** digits
    return math.trunc(stepper * number) / stepper


def find_unbounded_lines_intersection(line1, line2):
    # FIXME this function may output slightly different intersection if the input is swapped, which should NOT happen.
    # This is potentially caused by a rounding error -- more investigation is needed.
    # The consequence of this rounding error is an infinite loop in the _split_intersecting_elements function.
    # Sort line1 and line2 to force a consistent output
    [line1, line2] = sorted([tuple(line1), tuple(line2)])

    (x1, y1), (x2, y2) = line1
    (x3, y3), (x4, y4) = line2

    # Excessive decimal places must be truncated to avoid rounding error
    x1, y1 = truncate(x1), truncate(y1)
    x2, y2 = truncate(x2), truncate(y2)
    x3, y3 = truncate(x3), truncate(y3)
    x4, y4 = truncate(x4), truncate(y4)

    # Calculate the slopes of the two line segments
    m1 = (y2 - y1) / (x2 - x1) if (x2 - x1) != 0 else float('inf')
    m2 = (y4 - y3) / (x4 - x3) if (x4 - x3) != 0 else float('inf')

    # Check if the segments are parallel (the slopes are the same)
    if m1 == m2:
        return None  # No intersection, the lines are parallel

    # Calculate the intersection point
    if m1 == float('inf'):  # First line is vertical
        x = x1
        y = m2 * (x - x3) + y3
    elif m2 == float('inf'):  # Second line is vertical
        x = x3
        y = m1 * (x - x1) + y1
    else:
        x = (m1 * x1 - y1 - m2 * x3 + y3) / (m1 - m2)
        y = m1 * (x - x1) + y1

    x, y = truncate(x), truncate(y)
    return (x, y)


def find_lines_intersection(line1, line2):
    # FIXME this function may output slightly different intersection if the input is swapped, which should NOT happen.
    # This is potentially caused by a rounding error -- more investigation is needed.
    # The consequence of this rounding error is an infinite loop in the _split_intersecting_elements function.
    # Sort line1 and line2 to force a consistent output
    [line1, line2] = sorted([tuple(line1), tuple(line2)])
    (x1, y1), (x2, y2) = line1
    (x3, y3), (x4, y4) = line2

    # Excessive decimal places must be truncated to avoid rounding error
    x1, y1 = truncate(x1), truncate(y1)
    x2, y2 = truncate(x2), truncate(y2)
    x3, y3 = truncate(x3), truncate(y3)
    x4, y4 = truncate(x4), truncate(y4)

    res = find_unbounded_lines_intersection(line1, line2)
    if res is None:
        return None

    x, y = res

    # Check if the intersection point is within both line segments
    if (
        min(x1, x2) <= x <= max(x1, x2) and
        min(y1, y2) <= y <= max(y1, y2) and
        min(x3, x4) <= x <= max(x3, x4) and
        min(y3, y4) <= y <= max(y3, y4)
    ):
        return (x, y)  # Intersection point is within both line segments
    else:
        return None  # Intersection point is outside one or both line segments


def eucledian_distance(v1, v2):
    return math.sqrt(((v1[0] - v2[0]) ** 2) + (v1[1] - v2[1]) ** 2)


def find(list, matcher):
    for element in list:
        if matcher(element):
            return element

    return None


def find_index(list, matcher):
    i = 0
    for element in list:
        if matcher(element):
            return i
        i += 1

    return None


def filter(list, matcher):
    return [x for x in list if matcher(x)]


def calculate_line_angle_relative_to_north(vertex1, vertex2):
    # Extract the coordinates
    x1, y1 = vertex1
    x2, y2 = vertex2

    # Calculate the angle using arctangent (atan2) function
    angle_rad = math.atan2(x2 - x1, y2 - y1)

    # Convert radians to degrees
    angle_deg = math.degrees(angle_rad)

    # Ensure the angle is between 0 and 360 degrees
    if angle_deg < 0:
        angle_deg += 360

    return angle_deg


def rotate_point_around_origin(x, y, angle_degrees):
    # Convert the angle from degrees to radians
    angle_radians = math.radians(angle_degrees)

    # Calculate the new coordinates after rotation
    new_x = x * math.cos(angle_radians) - y * math.sin(angle_radians)
    new_y = x * math.sin(angle_radians) + y * math.cos(angle_radians)

    return new_x, new_y


def rotate_point_around_point(origin, vertex, angle_degrees):
    ax, ay = origin
    bx, by = vertex
    # Translate point B to the origin
    translated_bx = bx - ax
    translated_by = by - ay

    # Rotate the translated point B
    rotated_bx, rotated_by = rotate_point_around_origin(translated_bx, translated_by, angle_degrees)

    # Translate the rotated point B back to its original position
    new_bx = rotated_bx + ax
    new_by = rotated_by + ay

    return new_bx, new_by


def get_composite_verts(ifc_product):
    if ifc_product.Representation is not None:
        settings = ifcopenshell.geom.settings()
        shape = ifcopenshell.geom.create_shape(settings, ifc_product)
        vertices = ifcopenshell.util.shape.get_vertices(shape.geometry)
        matrix = ifcopenshell.util.placement.get_local_placement(ifc_product.ObjectPlacement)
        rel_vertices = [transform_vertex_3d(matrix, x) for x in vertices]
        return list(rel_vertices)

    vertices = []
    products = ifcopenshell.util.element.get_decomposition(ifc_product)
    for product in products:
        vertices += get_composite_verts(product)

    return vertices


def get_edge_from_bounding_box(bbox):
    v1, v2, v3, v4 = bbox
    e1 = (v1, v2)
    e2 = (v2, v3)
    e3 = (v3, v4)
    e4 = (v4, v1)

    e1_dist = eucledian_distance(v1, v2)
    e2_dist = eucledian_distance(v2, v3)

    if e1_dist < e2_dist:
        midpoint_vertex_1 = e1
        midpoint_vertex_2 = e3
    else:
        midpoint_vertex_1 = e2
        midpoint_vertex_2 = e4

    midpoint_x_1 = (midpoint_vertex_1[0][0] + midpoint_vertex_1[1][0]) / 2
    midpoint_y_1 = (midpoint_vertex_1[0][1] + midpoint_vertex_1[1][1]) / 2

    midpoint_x_2 = (midpoint_vertex_2[0][0] + midpoint_vertex_2[1][0]) / 2
    midpoint_y_2 = (midpoint_vertex_2[0][1] + midpoint_vertex_2[1][1]) / 2

    return (midpoint_x_1, midpoint_y_1), (midpoint_x_2, midpoint_y_2)


def shortest_distance_between_two_lines(segment1, segment2):
    # Convert the line segments to numpy arrays for easier calculations
    line1 = np.array(segment1)
    line2 = np.array(segment2)

    def closest_point_on_segment(point, segment):
        # Calculate the vector from the segment's starting point to the point
        vector_to_point = point - segment[0]

        # Calculate the vector representing the segment
        segment_vector = segment[1] - segment[0]

        # Calculate the projection of vector_to_point onto segment_vector
        t = np.dot(vector_to_point, segment_vector) / np.dot(segment_vector, segment_vector)

        # Clamp t to ensure the closest point lies within the segment
        t = max(0, min(1, t))

        # Calculate the closest point on the segment
        closest_point = segment[0] + t * segment_vector

        return closest_point

    # Calculate the closest points on each line segment to the other
    closest_point_segment1_to_segment2 = closest_point_on_segment(line1[0], line2)
    closest_point_segment2_to_segment1 = closest_point_on_segment(line2[0], line1)

    # Calculate the Euclidean distance between these closest points
    distance = np.linalg.norm(closest_point_segment1_to_segment2 - closest_point_segment2_to_segment1)

    return distance


def get_oriented_xy_bounding_box(vertices):
    # Vertices must be non-negative, because there is a bug in the Compas library which causes bbox to be improperly calculated.
    flat_vertices = np.array(vertices).flatten()
    verts_x, verts_y, verts_z = flat_vertices[::3], flat_vertices[1::3], flat_vertices[2::3]
    min_x, min_y = min(verts_x), min(verts_y)
    offset_vertices = [(x - min_x, y - min_y, z) for (x, y, z) in vertices]

    bbox = oriented_bounding_box_xy_numpy(offset_vertices)
    deoffset_bbox = [(x + min_x, y + min_y) for (x, y) in bbox]
    return deoffset_bbox
