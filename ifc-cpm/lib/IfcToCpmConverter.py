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
from .representation_helpers import XYBoundingBox, Extrusion2DVertices, WallVertices

from .ifctypes import BuildingElement, Wall, Gate, Barricade, WallWithOpening
from .utils import (
    find_lines_intersection,
    find,
    filter,
    eucledian_distance,
    find_unbounded_lines_intersection,
)

settings = ifcopenshell.geom.settings()
settings.set(settings.USE_WORLD_COORDS, True)


class IfcToCpmConverterBuilder:
    def __init__(self, ifc_filepath: str):
        self.crowd_environment = CrowdSimulationEnvironment()
        self.model = ifcopenshell.open(ifc_filepath)
        self.unit_scale = ifcopenshell.util.unit.calculate_unit_scale(self.model)

    def get_buildings(self):
        buildings = []
        for ifc_building in self.model.by_type("IfcBuilding"):
            buildings.append(ifc_building.Name)
        return buildings

    def get_ifc_building(self, name=None):
        for ifc_building in self.model.by_type("IfcBuilding"):
            if name is None:
                return ifc_building
            if name == ifc_building.Name:
                return ifc_building

    def build(
        self,
        building_name: str = None,
        dimension: Tuple[int, int] = None,
        origin: Tuple[int, int] = None,
        round_function=None,
    ):
        ifc_building = self.get_ifc_building(building_name)
        return IfcToCpmConverter(
            ifc_building=ifc_building,
            unit_scale=self.unit_scale,
            dimension=dimension,
            origin=origin,
            round_function=round_function,
        )


class IfcToCpmConverter:
    def __init__(
        self,
        ifc_building,
        unit_scale,
        dimension: Tuple[int, int] = None,
        origin: Tuple[int, int] = None,
        round_function=None,
    ):
        self.dimension = dimension
        if origin is None:
            origin = (0, 0)
        self.x_offset = origin[0]
        self.y_offset = origin[1]

        self.crowd_environment = CrowdSimulationEnvironment()
        self.ifc_building = ifc_building
        self.unit_scale = unit_scale

        building_transformation_matrix = (
            ifcopenshell.util.placement.get_local_placement(
                ifc_building.ObjectPlacement
            )
        )
        self.base_transformation_matrix = np.linalg.inv(building_transformation_matrix)

        if round_function is not None:
            self.round = round_function
        else:
            self.round = lambda x: x

    def write(self, cpm_out_filepath):
        building_elements = ifcopenshell.util.element.get_decomposition(
            self.ifc_building
        )
        storeys = [x for x in building_elements if x.is_a("IfcBuildingStorey")]
        for storey in storeys:
            elements = self._get_storey_elements(storey)

            if self.dimension is None:
                width, height = self._get_storey_size(elements)
                width = math.ceil(width)
                height = math.ceil(height)
            else:
                width, height = self.dimension

            level = Level(width=width, height=height)
            for element in elements:
                x1, y1 = element.start_vertex
                x2, y2 = element.end_vertex
                x1, y1, x2, y2 = self._scale_to_metric((x1, y1, x2, y2))
                x1, y1 = x1 + self.x_offset, y1 + self.y_offset
                x2, y2 = x2 + self.x_offset, y2 + self.y_offset

                vertices = ((x1, y1), (x2, y2))
                length = self._scale_to_metric(element.length)

                if element.__type__ == "Wall":
                    level.add_wall(vertices, length)
                elif element.__type__ == "Barricade":
                    level.add_barricade(vertices, length)
                elif element.__type__ == "Gate":
                    level.add_gate(vertices, length)

            self.crowd_environment.add_level(level)

        with open(cpm_out_filepath, "w") as f:
            f.write(self.crowd_environment.write())

    def _get_storey_elements(self, storey):
        elements = ifcopenshell.util.element.get_decomposition(storey)
        walls = [x for x in elements if x.is_a("IfcWall")]
        building_elements = []
        for wall in walls:
            try:
                wall_with_opening = self._get_wall_with_opening(wall)
                building_elements.append(wall_with_opening)
            except Exception as exc:
                print("Error parsing wall", wall.Name, exc)
                raise Exception

        building_elements = self._join_connected_walls(building_elements)
        building_elements = self._decompose_wall_with_openings(building_elements)
        building_elements = self._split_intersecting_elements(building_elements)
        building_elements = self._convert_disconnected_walls_into_barricades(building_elements)
        building_elements += self._get_storey_void_barricade_elements(storey)
        return building_elements

    def _get_wall_with_opening(self, ifc_wall) -> WallWithOpening:
        gates_vertices = []
        openings = ifc_wall.HasOpenings
        for opening in openings:
            opening_element = opening.RelatedOpeningElement
            opening_length = self._get_opening_width(opening_element)
            if opening_length is not None:
                opening_location_relative_to_wall = (
                    opening_element.ObjectPlacement.RelativePlacement.Location.Coordinates
                )

                x, y, z = opening_location_relative_to_wall

                # Opening local placement starts from the middle. See https://standards.buildingsmart.org/IFC/RELEASE/IFC2x3/TC1/HTML/ifcproductextension/lexical/ifcopeningelement.htm
                # "NOTE: Rectangles are now defined centric, the placement location has to be set: IfcCartesianPoint(XDim/2,YDim/2)"
                x = x - opening_length / 2
                y = 0  # FIXME investigate other representations where the y is NOT zero.
                if z == 0:
                    gates_vertices.append(
                        ((x, y), (x + opening_length, y))
                    )

        transformation_matrix = ifcopenshell.util.placement.get_local_placement(
            ifc_wall.ObjectPlacement
        )

        opening_vertices = []
        for (v1, v2) in gates_vertices:
            v1 = self._transform_vertex(v1, transformation_matrix)
            v2 = self._transform_vertex(v2, transformation_matrix)
            opening_vertices.append((v1, v2))

        start_vertex, end_vertex = self._get_relative_ifcwall_vertices(ifc_wall)
        start_vertex = self._transform_vertex(start_vertex, transformation_matrix)
        end_vertex = self._transform_vertex(end_vertex, transformation_matrix)

        connected_to = [(x.RelatedElement.GlobalId, x.RelatingConnectionType) for x in ifc_wall.ConnectedTo]
        return WallWithOpening(object_id=ifc_wall.GlobalId, start_vertex=start_vertex, end_vertex=end_vertex, opening_vertices=opening_vertices, connected_to=connected_to)

    def _get_opening_width(self, opening_element):
        fillings = opening_element.HasFillings
        if len(fillings) == 0:
            # This is just an opening without attached door.
            # Get the width from the shape representations.
            representations = opening_element.Representation.Representations
            try:
                opening_length, _ = XYBoundingBox.infer(representations)
                return opening_length
            except:
                return None

        door_filling = None
        for filling in fillings:
            if filling.RelatedBuildingElement.is_a("IfcDoor"):
                door_filling = filling.RelatedBuildingElement
                break

        if door_filling is not None:
            return door_filling.OverallWidth

    def _join_connected_walls(self, building_elements: List[BuildingElement]) -> List[BuildingElement]:
        walls = [x for x in building_elements if x.__type__ == 'WallWithOpening']
        for wall in walls:
            for (connected_wall_id, connection_type) in wall.connected_to:
                related_wall = find(
                    walls, lambda x: x.object_id == connected_wall_id
                )
                intersection = find_unbounded_lines_intersection(
                    (wall.start_vertex, wall.end_vertex),
                    (related_wall.start_vertex, related_wall.end_vertex),
                )

                if intersection:
                    # Update related wall vertices
                    v1_distance = eucledian_distance(
                        related_wall.start_vertex, intersection
                    )
                    v2_distance = eucledian_distance(
                        related_wall.end_vertex, intersection
                    )
                    if v1_distance < v2_distance:
                        related_wall.start_vertex = intersection
                    else:
                        related_wall.end_vertex = intersection

                    # Update current wall vertices
                    if connection_type != 'ATPATH':
                        wall_v1_distance = eucledian_distance(
                            wall.start_vertex, intersection
                        )
                        wall_v2_distance = eucledian_distance(wall.end_vertex, intersection)
                        if wall_v1_distance < wall_v2_distance:
                            wall.start_vertex = intersection
                        else:
                            wall.end_vertex = intersection

        return building_elements

    def _decompose_wall_with_openings(self, elements: List[BuildingElement]) -> List[BuildingElement]:
        out_elements = []
        for element in elements:
            if element.__type__ == 'WallWithOpening':
                gates_vertices = element.opening_vertices

                def get_first_contained_gate(p1, p2):
                    p1_x, p1_y = min(p1[0], p2[0]), min(p1[1], p2[1])
                    p2_x, p2_y = max(p1[0], p2[0]), max(p1[1], p2[1])
                    for gate_vertices in gates_vertices:
                        (g1_x, g1_y), (g2_x, g2_y) = gate_vertices
                        if g1_x >= p1_x and g2_x <= p2_x and g1_y >= p1_y and g2_y <= p2_y:
                            return gate_vertices

                elements_queue = [Wall(start_vertex=element.start_vertex, end_vertex=element.end_vertex)]
                while len(elements_queue) > 0:
                    el = elements_queue.pop(0)
                    gate_vertices = get_first_contained_gate(el.start_vertex, el.end_vertex)
                    if gate_vertices is None:
                        out_elements.append(el)
                    else:
                        gate_vert1, gate_vert2 = gate_vertices
                        wall1 = Wall(start_vertex=el.start_vertex, end_vertex=gate_vert1)
                        wall2 = Wall(start_vertex=gate_vert2, end_vertex=el.end_vertex)
                        gate = Gate(start_vertex=gate_vert1, end_vertex=gate_vert2)
                        elements_queue += [wall1, gate, wall2]
                        gates_vertices.remove(gate_vertices)

            else:
                out_elements.append(element)

        return out_elements

    def _split_intersecting_elements(self, elements: List[BuildingElement]) -> List[BuildingElement]:
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

    def _find_first_intersection(self, target_element: BuildingElement, other_elements: List[BuildingElement]) -> Tuple[float, float]:
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
    
    def _convert_disconnected_walls_into_barricades(self, elements: List[BuildingElement]):
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
                    object_id=wall.object_id,
                    name=wall.name,
                    start_vertex=wall.start_vertex,
                    end_vertex=wall.end_vertex,
                )
                output_elements.remove(wall)
                output_elements.append(barricade)
        return output_elements
    
    def _get_storey_void_barricade_elements(self, storey):
        elements = ifcopenshell.util.element.get_decomposition(storey)
        slabs = [x for x in elements if x.is_a("IfcSlab")]
        floor_slabs = [x for x in slabs if x.PredefinedType == "FLOOR"]

        elements = []
        if len(floor_slabs) > 0:
            floor_slab = floor_slabs[0]
            floor_openings = floor_slab.HasOpenings
            for floor_opening in floor_openings:
                opening_element = floor_opening.RelatedOpeningElement
                representations = opening_element.Representation.Representations

                transformation_matrix = ifcopenshell.util.placement.get_local_placement(
                    opening_element.ObjectPlacement
                )

                edges = Extrusion2DVertices.infer(representations)

                for i in range(len(edges)):
                    v1, v2 = edges[i]
                    v1_transform = self._transform_vertex(v1, transformation_matrix)
                    v2_transform = self._transform_vertex(v2, transformation_matrix)
                    elements.append(
                        Barricade(
                            name=f"{opening_element.Name}-{i}",
                            start_vertex=v1_transform,
                            end_vertex=v2_transform,
                        )
                    )

        return elements


    def _get_relative_ifcwall_vertices(self, ifc_wall):
        representations = ifc_wall.Representation.Representations
        return WallVertices.infer(representations)

    def _get_storey_size(self, elements: List[BuildingElement]):
        x_max = 0
        y_max = 0
        for element in elements:
            x_max = max(x_max, element.start_vertex[0], element.end_vertex[0])
            y_max = max(y_max, element.start_vertex[1], element.end_vertex[1])

        x_max = math.ceil(x_max)
        y_max = math.ceil(y_max)

        # Scale to metric
        x_max, y_max = self._scale_to_metric((x_max, y_max))

        # Account for x and y offset
        x_max += 2 * self.x_offset
        y_max += 2 * self.y_offset

        return x_max, y_max

    def _transform_vertex(self, vertex, transformation_matrix):
        x, y = vertex

        vertex_matrix = np.array([[x], [y], [0], [1]])

        # Building location correction
        total_transformation_matrix = np.dot(
            self.base_transformation_matrix, transformation_matrix
        )
        transformed_matrix = np.dot(total_transformation_matrix, vertex_matrix)

        transformed_x, transformed_y, _, _ = np.transpose(transformed_matrix)[0]
        transformed_x = self.round(transformed_x)
        transformed_y = self.round(transformed_y)
        return (transformed_x, transformed_y)

    def _scale_to_metric(self, length):
        if isinstance(length, tuple):
            new_list = [self.unit_scale * x for x in length]
            return tuple(new_list)
        elif isinstance(length, list):
            new_list = [self.unit_scale * x for x in length]
            return new_list

        return self.unit_scale * length
