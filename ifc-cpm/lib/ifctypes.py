from typing import Tuple
import numpy as np


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
