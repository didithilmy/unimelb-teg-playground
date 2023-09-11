from typing import List
import xmltodict
from .ifctypes import BuildingElement, Wall, Gate, Barricade, Stair
from .utils import filter


class Level:
    def __init__(self, index, elements: List[BuildingElement], width=100, height=100):
        self.index = index
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


class CrowdSimulationEnvironment:
    def __init__(self):
        self.highest_id = 0
        self.levels: List[Level] = []
        self.stairs: List[Stair] = []
        self.vertices = {}

    def add_level(self, level):
        self.levels.append(level)

    def add_stair(self, stair: Stair):
        self.stairs.append(stair)

    def write(self):
        levels = [self._get_level(x) for x in self.levels]
        stairs = [self._create_stair_json(s) for s in self.stairs]
        data = {
            "Model": {
                "@xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
                "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
                "version": "2023.1.0",
                "panicMode": False,
                "validatedSuccessfully": False,
                "levelHeight": 2.5,
                "levels": {"Level": levels},
                "stairs": {"Stair": stairs},
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
            "iWlWG": False,
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
            "iWlWG": False,
            "vertices": {
                "Vertex": [
                        {"X": x1, "Y": y1, "id": self._get_vertex_id((x1, y1))},
                        {"X": x2, "Y": y2, "id": self._get_vertex_id((x2, y2))},
                ]
            },
        }

    def _create_stair_json(self, stair: Stair):
        stair_id = self._get_id()

        return {
            "id": stair_id,
            "x": stair.lower_gate_edge[0][0],  # X coordinate of first lower vertex
            "y": stair.lower_gate_edge[0][1],  # Y coordinate of first lower vertex
            "speed": -1,  # TODO figure out what
            "spanFloors": stair.end_level_index - stair.start_level_index,
            "length": stair.staircase_length,  # Run length
            "width": stair.staircase_width,  # Staircase width
            "widthLanding": stair.staircase_width,
            "stands": 5,  # TODO figure out where to get
            "rotation": stair.rotation,  # Can be inferred from rotation matrix or axis. 0 means facing north
            "type": 1,  # Read from enum
            "direction": 0,
            "upper": {
                "level": stair.end_level_index,
                "gate": {
                        "id": self._get_id(),
                        "length": stair.staircase_width,  # should be the same as width, if stair is STRAIGHT
                        "angle": 90,  # TODO find out what
                        "destination": False,  # let the software figure out I suppose
                        "counter": False,  # TODO find out what
                        "transparent": False,
                        "designatedOnly": False,
                        "vertices": {
                            "Vertex": [
                                self._get_vertex(stair.upper_gate_edge[0]),
                                self._get_vertex(stair.upper_gate_edge[1]),
                            ]
                        }
                }
            },
            "lower": {
                "level": stair.start_level_index,
                "gate": {
                    "id": self._get_id(),
                    "length": stair.staircase_width,  # should be the same as width, if stair is STRAIGHT
                    "angle": 90,  # TODO find out what
                    "destination": False,  # let the software figure out I suppose
                    "counter": False,  # TODO find out what
                    "transparent": False,
                    "designatedOnly": False,
                    "vertices": {
                        "Vertex": [
                            self._get_vertex(stair.lower_gate_edge[0]),
                            self._get_vertex(stair.lower_gate_edge[1]),
                        ]
                    }
                }
            },
            "walls": {
                "Wall": [
                    # Left wall
                    {
                        "id": self._get_id(),
                        "length": stair.staircase_length,
                        "angle": 0,
                        "isLow": False,
                        "isTransparent": False,
                        "iWlWG": False,
                        "vertices": {
                            "Vertex": [
                                self._get_vertex(stair.first_wall_edge[0]),
                                self._get_vertex(stair.first_wall_edge[1]),
                            ]
                        }
                    },
                    # Right wall
                    {
                        "id": self._get_id(),
                        "length": stair.staircase_length,
                        "angle": 180,
                        "isLow": False,
                        "isTransparent": False,
                        "iWlWG": False,
                        "vertices": {
                            "Vertex": [
                                self._get_vertex(stair.second_wall_edge[0]),
                                self._get_vertex(stair.second_wall_edge[1]),
                            ]
                        }
                    },
                    # Back wall = upper gate
                    {
                        "id": self._get_id(),
                        "length": stair.staircase_width,
                        "angle": 270,
                        "isLow": False,
                        "isTransparent": False,
                        "iWlWG": False,
                        "vertices": {
                            "Vertex": [
                                self._get_vertex(stair.upper_gate_edge[0]),
                                self._get_vertex(stair.upper_gate_edge[1]),
                            ]
                        }
                    }
                ]
            }
        }

    def _get_vertex(self, vertex):
        x, y = vertex
        return {"X": x, "Y": y, "id": self._get_vertex_id(vertex)}

    def _get_vertex_id(self, vertex):
        if vertex not in self.vertices:
            self.vertices[vertex] = self._get_id()
        return self.vertices[vertex]

    def _get_id(self):
        self.highest_id += 1
        return self.highest_id
