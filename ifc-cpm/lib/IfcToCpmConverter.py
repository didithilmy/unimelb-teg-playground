import copy
from collections import defaultdict
import math
from typing import Tuple, List
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import ifcopenshell.util.element
import ifcopenshell.util.unit
from .cpm_writer import CrowdSimulationEnvironment, Level

from .ifctypes import BuildingElement, Wall, Gate, Barricade
from .utils import find_lines_intersection

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)


class IfcToCpmConverter:
    def __init__(
        self,
        ifc_filepath: str,
        dimension: Tuple[int, int] = None,
        origin: Tuple[int, int] = None,
    ):
        self.dimension = dimension
        if origin is None:
            origin = (0, 0)
        self.x_offset = origin[0]
        self.y_offset = origin[1]

        self.crowd_environment = CrowdSimulationEnvironment()
        self.model = ifcopenshell.open(ifc_filepath)
        self.unit_scale = ifcopenshell.util.unit.calculate_unit_scale(self.model)

    def write(self, cpm_out_filepath):
        for storey in self.model.by_type("IfcBuildingStorey"):
            elements = self._get_storey_elements(storey)

            if self.dimension is None:
                width, height = self._get_storey_size(elements)
            else:
                width, height = self.dimension

            level = Level(width=width, height=height)
            for element in elements:
                x1, y1 = element.start_vertex
                x1, y1 = x1 + self.x_offset, y1 + self.y_offset

                x2, y2 = element.end_vertex
                x2, y2 = x2 + self.x_offset, y2 + self.y_offset

                vertices = ((x1, y1), (x2, y2))

                if element.__type__ == "Wall":
                    level.add_wall(vertices, element.length)
                elif element.__type__ == "Barricade":
                    level.add_barricade(vertices, element.length)
                elif element.__type__ == "Gate":
                    level.add_gate(vertices, element.length)

            self.crowd_environment.add_level(level)

        with open(cpm_out_filepath, "w") as f:
            f.write(self.crowd_environment.write())

    def _get_storey_elements(self, storey):
        elements = ifcopenshell.util.element.get_decomposition(storey)
        walls = [x for x in elements if x.is_a("IfcWall")]
        building_elements = []
        for wall in walls:
            decomposed = self._decompose_wall_openings(wall)
            transformation_matrix = ifcopenshell.util.placement.get_local_placement(
                wall.ObjectPlacement
            )
            i = 0
            for v1, v2, type, name in decomposed:
                i += 1
                v1_transform = self._transform_vertex(v1, transformation_matrix)
                v2_transform = self._transform_vertex(v2, transformation_matrix)
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
        building_elements = self._split_intersecting_elements(building_elements)
        building_elements = self._convert_disconnected_walls_into_barricades(
            building_elements
        )
        return building_elements

    def _decompose_wall_openings(self, ifc_wall) -> List[BuildingElement]:
        """
        Input: IfcWall
        Output: Array of [
            Wall, Gate, Wall (decomposed elements)
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

            opening_location_relative_to_wall = (
                opening_element.ObjectPlacement.RelativePlacement.Location.Coordinates
            )

            x, y, z = opening_location_relative_to_wall

            # Opening local placement starts from the middle. See https://standards.buildingsmart.org/IFC/RELEASE/IFC2x3/TC1/HTML/ifcproductextension/lexical/ifcopeningelement.htm
            # "NOTE: Rectangles are now defined centric, the placement location has to be set: IfcCartesianPoint(XDim/2,YDim/2)"
            x = x - opening_length / 2
            if z == 0:
                gates_vertices.append(
                    ((x, y), (x + opening_length, y), opening_element.Name)
                )

        start_vertex, end_vertex = self._get_relative_ifcwall_vertices(ifc_wall)
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

    def _split_intersecting_elements(
        self, elements: List[BuildingElement]
    ) -> List[BuildingElement]:
        """
        Split intersecting elements to get new vertices.
        Input: Array of BuildingElement
        Output: Array of BuildingElement
        """
        elements_queue = copy.copy(elements)
        output_elements = []
        while len(elements_queue) > 0:
            element = elements_queue.pop(0)
            intersection = self._find_first_intersection(element, elements_queue)
            if intersection is None:
                output_elements.append(element)
            else:
                split_elements = self._split_element_at_point(intersection, element)
                elements_queue += split_elements

        return output_elements

    def _find_first_intersection(
        self, target_element: BuildingElement, other_elements: List[BuildingElement]
    ) -> Tuple[float, float]:
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

    def _split_element_at_point(self, point, element: BuildingElement):
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

    def _convert_disconnected_walls_into_barricades(
        self, elements: List[BuildingElement]
    ):
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
                    name=wall.name,
                    start_vertex=wall.start_vertex,
                    end_vertex=wall.end_vertex,
                )
                output_elements.remove(wall)
                output_elements.append(barricade)
        return output_elements

    def _get_relative_ifcwall_vertices(self, ifc_wall):
        representations = ifc_wall.Representation.Representations
        axis_representation = [
            x for x in representations if x.RepresentationType == "Curve2D"
        ]
        origin_vertex, dest_vertex = axis_representation[0].Items[0].Points
        origin_vertex_x, origin_vertex_y = origin_vertex.Coordinates
        dest_vertex_x, dest_vertex_y = dest_vertex.Coordinates

        return (origin_vertex_x, origin_vertex_y), (dest_vertex_x, dest_vertex_y)

    def _get_storey_size(self, elements: List[BuildingElement]):
        x_max = 0
        y_max = 0
        for element in elements:
            x_max = max(x_max, element.start_vertex[0], element.end_vertex[0])
            y_max = max(y_max, element.start_vertex[1], element.end_vertex[1])

        x_max = math.ceil(x_max)
        y_max = math.ceil(y_max)

        # Account for x and y offset
        x_max += 2 * self.x_offset
        y_max += 2 * self.y_offset

        return x_max, y_max

    def _transform_vertex(self, vertex, transformation_matrix):
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
