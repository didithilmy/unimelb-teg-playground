from typing import Tuple
import numpy as np


class BuildingElement:
    __type__ = "BuildingElement"
    name: str = None
    start_vertex: Tuple[float, float] = None
    end_vertex: Tuple[float, float] = None

    def __init__(
        self, name=None, start_vertex=None, end_vertex=None, type="BuildingElement"
    ):
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


class Wall(BuildingElement):
    __type__ = "Wall"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, type="Wall")


class Barricade(BuildingElement):
    __type__ = "Barricade"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, type="Barricade")


class Gate(BuildingElement):
    __type__ = "Gate"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs, type="Gate")
