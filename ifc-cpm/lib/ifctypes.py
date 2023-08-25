from typing import Tuple
import numpy as np


class BuildingElement:
    __type__ = None
    name: str = None
    start_vertex: Tuple[float, float] = None
    end_vertex: Tuple[float, float] = None

    @property
    def length(self):
        (x1, y1), (x2, y2) = self.start_vertex, self.end_vertex
        return np.sqrt((abs(x2 - x1) ** 2) + (abs(y2 - y1) ** 2))


class Wall(BuildingElement):
    __type__ = "Wall"


class Gate(BuildingElement):
    __type__ = "Gate"
