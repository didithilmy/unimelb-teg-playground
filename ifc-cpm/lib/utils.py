from typing import Tuple
import math
import numpy as np
import ifcopenshell.util.element
import ifcopenshell.util.shape
import ifcopenshell.util.placement
import ifcopenshell.geom


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


def find_unbounded_lines_intersection(line1, line2):
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

    return intersection_x, intersection_y


def find_lines_intersection(line1, line2):
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
