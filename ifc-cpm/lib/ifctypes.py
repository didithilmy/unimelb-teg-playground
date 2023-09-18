from typing import Tuple
import math
import copy
import numpy as np
from .utils import rotate_point_around_point


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


class StraightSingleRunStair(BuildingElement):
    __type__ = "StraightSingleRunStair"

    def __init__(self, *args, vertex, rotation, run_length, staircase_width, no_of_treads, start_level_index, end_level_index, **kwargs):
        super().__init__(*args, **kwargs, type="StraightSingleRunStair")

        self.vertex = vertex
        self.start_level_index = start_level_index
        self.end_level_index = end_level_index
        self.rotation = rotation
        self.run_length = run_length
        self.staircase_width = staircase_width
        self.no_of_treads = no_of_treads
        if no_of_treads is None:
            self.no_of_treads = math.ceil(run_length)

    @property
    def lower_gate(self):
        x1, y1 = self.vertex
        x2, y2 = (x1 + self.staircase_width, y1)
        x2, y2 = rotate_point_around_point(self.vertex, (x2, y2), self.rotation)
        return ((x1, y1), (x2, y2))

    @property
    def upper_gate(self):
        x0, y0 = self.vertex
        x1, y1 = (x0, y0 + self.run_length)
        x2, y2 = (x0 + self.staircase_width, y0 + self.run_length)

        x1, y1 = rotate_point_around_point(self.vertex, (x1, y1), self.rotation)
        x2, y2 = rotate_point_around_point(self.vertex, (x2, y2), self.rotation)
        return ((x1, y1), (x2, y2))

    @property
    def first_wall(self):
        x0, y0 = self.vertex
        x1, y1 = (x0, y0)
        x2, y2 = (x0, y0 + self.run_length)

        x1, y1 = rotate_point_around_point(self.vertex, (x1, y1), self.rotation)
        x2, y2 = rotate_point_around_point(self.vertex, (x2, y2), self.rotation)
        return ((x1, y1), (x2, y2))

    @property
    def second_wall(self):
        x0, y0 = self.vertex
        x1, y1 = (x0 + self.staircase_width, y0)
        x2, y2 = (x0 + self.staircase_width, y0 + self.run_length)

        x1, y1 = rotate_point_around_point(self.vertex, (x1, y1), self.rotation)
        x2, y2 = rotate_point_around_point(self.vertex, (x2, y2), self.rotation)
        return ((x1, y1), (x2, y2))

    def normalize(self, vertex_normalizer):
        x, y = vertex_normalizer(self.vertex)
        x, y = self._round(x), self._round(y)

        return StraightSingleRunStair(
            object_id=self.object_id,
            rotation=self.rotation,
            vertex=(x, y),
            run_length=self._round(self._normalize_scalar(vertex_normalizer, self.run_length)),
            staircase_width=self._round(self._normalize_scalar(vertex_normalizer, self.staircase_width)),
            no_of_treads=self.no_of_treads,
            start_level_index=self.start_level_index,
            end_level_index=self.end_level_index,
        )

    def _normalize_scalar(self, vertex_normalizer, scalar_value):
        _, y1 = vertex_normalizer((0, 0))
        _, y2 = vertex_normalizer((0, scalar_value))
        return y2 - y1

    def _round(self, value):
        return round(value * 1) / 1
