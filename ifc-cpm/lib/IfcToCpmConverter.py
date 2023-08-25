import copy
import math
from typing import Tuple, List
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from cpm_writer import CrowdSimulationEnvironment, Level

from .ifctypes import BuildingElement, Wall

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)


class IfcToCpmConverter:
    def __init__(self, ifc_filepath, dimension=None):
        self.dimension = dimension
        self.crowd_environment = CrowdSimulationEnvironment()
        self.model = ifcopenshell.open(ifc_filepath)
        self.unit_scale = ifcopenshell.util.unit.calculate_unit_scale(self.model)

    def write(self, cpm_out_filepath):
        for storey in self.model.by_type("IfcBuildingStorey"):
            elements = ifcopenshell.util.element.get_decomposition(storey)
            ifc_walls = [x for x in elements if x.is_a("IfcWall")]
            walls = [self._ifc_wall_to_converter_wall(x) for x in ifc_walls]
            walls = self._split_intersecting_walls(walls)

            if self.dimension is None:
                width, height = self._get_storey_size(walls)
            else:
                width, height = self.dimension

            level = Level(width=width, height=height)
            for wall in walls:
                level.add_wall((wall.start_vertex, wall.end_vertex), wall.length)
            self.crowd_environment.add_level(level)

        with open(cpm_out_filepath, "w") as f:
            f.write(self.crowd_environment.write())

    def _get_storey_size(self, elements: List[BuildingElement]):
        x_max = 0
        y_max = 0
        for element in elements:
            x_max = max(x_max, element.start_vertex[0], element.end_vertex[0])
            y_max = max(y_max, element.start_vertex[1], element.end_vertex[1])

        x_max = math.ceil(x_max)
        y_max = math.ceil(y_max)

        return x_max, y_max

    def _split_intersecting_walls(self, walls: List[Wall]) -> List[Wall]:
        """
        Split intersecting walls to get new vertex.
        """
        walls_queue = copy.copy(walls)
        output_walls = []
        while len(walls_queue) > 0:
            wall = walls_queue.pop(0)
            intersection = self._find_first_intersection(wall, walls_queue)
            if intersection is None:
                output_walls.append(wall)
            else:
                split_walls = self._split_line_at_point(intersection, wall)
                walls_queue += split_walls

        return output_walls

    def _ifc_wall_to_converter_wall(self, ifc_wall):
        point1, point2 = self._get_wall_vertices(ifc_wall)
        wall = Wall()
        wall.name = ifc_wall.Name
        wall.start_vertex = point1
        wall.end_vertex = point2
        return wall

    def _get_wall_vertices(self, ifc_wall):
        matrix = ifcopenshell.util.placement.get_local_placement(
            ifc_wall.ObjectPlacement
        )

        # Coordinate of IfcWall origin reference
        position_matrix = matrix[:, 3][:3].reshape(-1, 1)

        # Rotation matrices, from the wall origin reference.
        xyz_rotation_matrix = matrix[:3, :3]

        # Find the rotated wall vertices relative to the wall frame of reference
        representations = ifc_wall.Representation.Representations
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
        origin_x = self.unit_scale * origin_x
        origin_y = self.unit_scale * origin_y
        dest_x = self.unit_scale * dest_x
        dest_y = self.unit_scale * dest_y

        return (origin_x, origin_y), (dest_x, dest_y)

    def _find_first_intersection(
        self, target_line: BuildingElement, other_lines: List[BuildingElement]
    ):
        for other_line in other_lines:
            intersection = self._find_intersection(target_line, other_line)
            if intersection is not None:
                wall_vertices = [
                    target_line.start_vertex,
                    target_line.end_vertex,
                    other_line.start_vertex,
                    other_line.end_vertex,
                ]
                # Only add intersections that are T or +
                if wall_vertices.count(intersection) <= 1:
                    return intersection

        return None

    def _find_intersection(self, element1: BuildingElement, element2: BuildingElement):
        line1_point1, line1_point2 = element1.start_vertex, element1.end_vertex
        line2_point1, line2_point2 = element2.start_vertex, element2.end_vertex

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

    def _split_line_at_point(
        self, point, element: BuildingElement
    ) -> List[BuildingElement]:
        """
        Input:
            point (x, y)
            line: (x1, y1), (x2, y2)
            (x, y) must fall within the line.
        """
        x, y = point
        (x1, y1), (x2, y2) = element.start_vertex, element.end_vertex
        line1, line2 = ((x1, y1), (x, y)), ((x, y), (x2, y2))

        elements = []

        element_new_1 = copy.copy(element)
        element_new_1.start_vertex = line1[0]
        element_new_1.end_vertex = line1[1]
        if element_new_1.length > 0:
            elements.append(element_new_1)

        element_new_2 = copy.copy(element)
        element_new_2.start_vertex = line2[0]
        element_new_2.end_vertex = line2[1]
        if element_new_2.length > 0:
            elements.append(element_new_2)

        return elements
