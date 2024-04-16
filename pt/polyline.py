import pandas as pd
import numpy as np
import math

df = pd.read_json("links.json")


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

    return np.array([new_x, new_y])


def line_segment_into_polygon_band(line_segment, band_width=0.0001):
    (x1, y1), (x2, y2) = line_segment
    p1 = np.array([x1, y1])
    p2 = np.array([x2, y2])

    angle_relative_to_north = calculate_line_angle_relative_to_north(p1, p2)

    segment_length = np.linalg.norm(p2 - p1)
    # Line is (0, 0) -> (0, segment_length)
    points = [
        (-band_width, 0),
        (-band_width, segment_length),
        (band_width, segment_length),
        (band_width, 0),
    ]

    rotated_points = [rotate_point_around_origin(*a, -angle_relative_to_north) for a in points]
    translated_points = [(p1 + x) for x in rotated_points]
    return translated_points

