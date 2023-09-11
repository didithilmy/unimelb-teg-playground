import copy
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
from .preprocessors import convert_disconnected_walls_into_barricades, split_intersecting_elements, decompose_wall_with_openings, join_connected_walls, infer_wall_connections

from .ifctypes import BuildingElement, Barricade, WallWithOpening, Stair
from .stairs import StairBuilder
from .utils import transform_vertex

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
        close_wall_gap_metre=None
    ):
        ifc_building = self.get_ifc_building(building_name)
        return IfcToCpmConverter(
            ifc_building=ifc_building,
            unit_scale=self.unit_scale,
            dimension=dimension,
            origin=origin,
            round_function=round_function,
            close_wall_gap_metre=close_wall_gap_metre
        )


class IfcToCpmConverter:
    def __init__(
        self,
        ifc_building,
        unit_scale,
        dimension: Tuple[int, int] = None,
        origin: Tuple[int, int] = None,
        round_function=None,
        close_wall_gap_metre=None
    ):
        self.dimension = dimension
        if origin is None:
            origin = (0, 0)
        self.x_offset = origin[0]
        self.y_offset = origin[1]

        self.crowd_environment = CrowdSimulationEnvironment()
        self.ifc_building = ifc_building
        self.unit_scale = unit_scale

        building_transformation_matrix = ifcopenshell.util.placement.get_local_placement(ifc_building.ObjectPlacement)
        self.base_transformation_matrix = np.linalg.inv(building_transformation_matrix)

        if round_function is not None:
            self.round = round_function
        else:
            self.round = lambda x: x

        self.close_wall_gap_metre = close_wall_gap_metre

        building_elements = ifcopenshell.util.element.get_decomposition(self.ifc_building)
        self.storeys = [x for x in building_elements if x.is_a("IfcBuildingStorey")]

    def write(self, cpm_out_filepath):
        for storey_id, storey in enumerate(self.storeys):
            building_elements = ifcopenshell.util.element.get_decomposition(storey)
            stairs_in_storey = [x for x in building_elements if x.is_a("IfcStair")]
            for stair_in_storey in stairs_in_storey:
                stair = StairBuilder(storey_id, stair_in_storey, vertex_normalizer=self._normalize_vertex).build()
                self.crowd_environment.add_stair(stair)

        for storey_id, storey in enumerate(self.storeys):
            elements = self._get_storey_elements(storey_id, storey)

            if self.dimension is None:
                width, height = self._get_storey_size(elements)
                width = math.ceil(width)
                height = math.ceil(height)
            else:
                width, height = self.dimension

            normalized_elements = self._normalize_vertices(elements)
            level = Level(index=storey_id, elements=normalized_elements, width=width, height=height)
            self.crowd_environment.add_level(level)

        with open(cpm_out_filepath, "w") as f:
            f.write(self.crowd_environment.write())

    def _get_storey_elements(self, storey_id, storey):
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

        if self.close_wall_gap_metre is not None:
            tolerance = self.close_wall_gap_metre / self.unit_scale
            building_elements = infer_wall_connections(tolerance, building_elements)

        building_elements = join_connected_walls(building_elements)
        building_elements = decompose_wall_with_openings(building_elements)
        building_elements = split_intersecting_elements(building_elements)
        building_elements = convert_disconnected_walls_into_barricades(building_elements)
        # building_elements += self._get_storey_void_barricade_elements(storey)
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

        start_vertex, end_vertex = WallVertices.infer(ifc_wall.Representation.Representations)
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

    def _normalize_vertices(self, elements: List[BuildingElement]) -> List[BuildingElement]:
        out_elements = copy.deepcopy(elements)
        for element in out_elements:
            x1, y1 = self._normalize_vertex(element.start_vertex)
            x2, y2 = self._normalize_vertex(element.end_vertex)

            element.start_vertex = (x1, y1)
            element.end_vertex = (x2, y2)

        return out_elements

    def _normalize_vertex(self, vertex: Tuple[float, float]) -> Tuple[float, float]:
        x1, y1 = vertex
        x1, y1 = self._scale_to_metric((x1, y1))
        x1, y1 = x1 + self.x_offset, y1 + self.y_offset
        return x1, y1

    def _transform_vertex(self, vertex, transformation_matrix):
        # Building location correction
        total_transformation_matrix = np.dot(
            self.base_transformation_matrix, transformation_matrix
        )
        transformed_x, transformed_y = transform_vertex(total_transformation_matrix, vertex)
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
