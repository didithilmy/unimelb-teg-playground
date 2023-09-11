from typing import Tuple
import copy
import numpy as np
from .utils import eucledian_distance


class BuildingElement:
    __type__ = "BuildingElement"
    object_id: str = None
    name: str = None
    start_vertex: Tuple[float, float] = None
    end_vertex: Tuple[float, float] = None

    def __init__(
        self,
        object_id=None,
        name=None,
        start_vertex=None,
        end_vertex=None,
        type="BuildingElement",
    ):
        self.object_id = object_id
        self.name = name
        self.start_vertex = start_vertex
        self.end_vertex = end_vertex
        self.__type__ = type

    @property
    def length(self):
        (x1, y1), (x2, y2) = self.start_vertex, self.end_vertex
        return np.sqrt((abs(x2 - x1) ** 2) + (abs(y2 - y1) ** 2))

    def normalize(self, vertex_normalizer):
        dupl = copy.deepcopy(self)
        dupl.start_vertex = vertex_normalizer(self.start_vertex)
        dupl.end_vertex = vertex_normalizer(self.end_vertex)
        return dupl

    def __repr__(self):
        return f"{self.__type__}({self.name}, {self.start_vertex}, {self.end_vertex})"


class WallWithOpening(BuildingElement):
    __type__ = "WallWithOpening"
    opening_vertices = []
    connected_to = []

    def __init__(self, *args, opening_vertices=[], connected_to=[], **kwargs):
        super().__init__(*args, **kwargs, type="WallWithOpening")
        self.opening_vertices = opening_vertices
        self.connected_to = connected_to


class Wall(BuildingElement):
    __type__ = "Wall"
    connected_to = []

    def __init__(self, *args, connected_to=[], **kwargs):
        super().__init__(*args, **kwargs, type="Wall")
        self.connected_to = connected_to


class Barricade(BuildingElement):
    __type__ = "Barricade"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, type="Barricade")


class Gate(BuildingElement):
    __type__ = "Gate"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, type="Gate")


class Stair(BuildingElement):
    __type__ = "Stair"

    def __init__(self, *args, rotation, start_level_index, end_level_index, lower_gate_edge=None, upper_gate_edge=None, first_wall_edge=None, second_wall_edge=None, **kwargs):
        super().__init__(*args, **kwargs, type="Stair")
        self.rotation = rotation
        self.start_level_index = start_level_index
        self.end_level_index = end_level_index
        self.lower_gate_edge = lower_gate_edge
        self.upper_gate_edge = upper_gate_edge
        self.first_wall_edge = first_wall_edge
        self.second_wall_edge = second_wall_edge

    @property
    def staircase_width(self):
        staircase_width = eucledian_distance(self.lower_gate_edge[0], self.lower_gate_edge[1])
        return staircase_width

    @property
    def staircase_length(self):
        staircase_length = eucledian_distance(self.first_wall_edge[0], self.first_wall_edge[1])
        return staircase_length

    def normalize(self, vertex_normalizer):
        return Stair(
            object_id=self.object_id,
            rotation=self.rotation,
            start_vertex=vertex_normalizer(self.lower_gate_edge[0]),
            end_vertex=vertex_normalizer(self.lower_gate_edge[1]),
            start_level_index=self.start_level_index,
            end_level_index=self.end_level_index,
            lower_gate_edge=(vertex_normalizer(self.lower_gate_edge[0]), vertex_normalizer(self.lower_gate_edge[1])),
            upper_gate_edge=(vertex_normalizer(self.upper_gate_edge[0]), vertex_normalizer(self.upper_gate_edge[1])),
            first_wall_edge=(vertex_normalizer(self.first_wall_edge[0]), vertex_normalizer(self.first_wall_edge[1])),
            second_wall_edge=(vertex_normalizer(self.second_wall_edge[0]), vertex_normalizer(self.second_wall_edge[1])),
        )
