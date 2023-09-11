from typing import List
import xmltodict
from .ifctypes import BuildingElement, Wall, Gate, Barricade, Stair
from .utils import filter


class Level:
    def __init__(self, elements: List[BuildingElement], width=100, height=100):
        self.dimension = (width, height)
        self.elements = elements

    @property
    def walls(self) -> List[Wall]:
        return filter(self.elements, lambda x: x.__type__ == 'Wall')

    @property
    def barricades(self) -> List[Barricade]:
        return filter(self.elements, lambda x: x.__type__ == 'Barricade')

    @property
    def gates(self) -> List[Gate]:
        return filter(self.elements, lambda x: x.__type__ == 'Gate')

    @property
    def stairs(self) -> List[Stair]:
        return filter(self.elements, lambda x: x.__type__ == 'Stair')


class CrowdSimulationEnvironment:
    def __init__(self):
        self.highest_id = 0
        self.levels: List[Level] = []
        self.vertices = {}

    def add_level(self, level):
        self.levels.append(level)

    def write(self):
        levels = [self._get_level(x) for x in self.levels]
        data = {
            "Model": {
                "@xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
                "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                "version": "2023.1.0",
                "panicMode": False,
                "validatedSuccessfully": False,
                "levelHeight": 2.5,
                "levels": {"Level": levels},
                "cameraPos": {"x": 0, "y": 12.325, "z": 0},
                "cameraRot": {"x": 18.306, "y": 45, "z": 0},
            }
        }

        return xmltodict.unparse(data, pretty=True)

    def _get_level(self, level: Level):
        level_id = self._get_id()

        walls = [self._create_wall_json(x) for x in level.walls]
        gates = [self._create_gate_json(x) for x in level.gates]
        barricades = [self._create_barricade_json(x) for x in level.barricades]

        return {
            "id": level_id,
            "width": level.dimension[0],
            "height": level.dimension[1],
            "wall_pkg": {"walls": {"Wall": walls}},
            "barricade_pkg": {"barricade_walls": {"Wall": barricades}},
            "gate_pkg": {"gates": {"Gate": gates}},
        }

    def _create_wall_json(self, wall: Wall):
        wall_id = self._get_id()
        (x1, y1), (x2, y2) = wall.start_vertex, wall.end_vertex

        return {
            "id": wall_id,
            "length": wall.length,
            "isLow": False,
            "isTransparent": False,
            "isWlWG": False,
            "vertices": {
                "Vertex": [
                        {"X": x1, "Y": y1, "id": self._get_vertex_id((x1, y1))},
                        {"X": x2, "Y": y2, "id": self._get_vertex_id((x2, y2))},
                ]
            },
        }

    def _create_gate_json(self, gate: Gate):
        gate_id = self._get_id()
        (x1, y1), (x2, y2) = gate.start_vertex, gate.end_vertex
        return {
            "id": gate_id,
            "length": gate.length,
            "angle": 0,  # TODO?
            "destination": False,
            "counter": False,
            "transparent": False,
            "designatedOnly": False,
            "vertices": {
                "Vertex": [
                        {"X": x1, "Y": y1, "id": self._get_vertex_id((x1, y1))},
                        {"X": x2, "Y": y2, "id": self._get_vertex_id((x2, y2))},
                ]
            },
        }

    def _create_barricade_json(self, barricade: Barricade):
        barricade_id = self._get_id()
        (x1, y1), (x2, y2) = barricade.start_vertex, barricade.end_vertex

        return {
            "id": barricade_id,
            "length": barricade.length,
            "isLow": False,
            "isTransparent": False,
            "isWlWG": False,
            "vertices": {
                "Vertex": [
                        {"X": x1, "Y": y1, "id": self._get_vertex_id((x1, y1))},
                        {"X": x2, "Y": y2, "id": self._get_vertex_id((x2, y2))},
                ]
            },
        }

    def _get_vertex_id(self, vertex):
        if vertex not in self.vertices:
            self.vertices[vertex] = self._get_id()
        return self.vertices[vertex]

    def _get_id(self):
        self.highest_id += 1
        return self.highest_id
