from typing import List, Tuple
import math
from collections import defaultdict
import xmltodict
from .ifctypes import BuildingElement, Wall, Gate, Barricade, StraightSingleRunStair, DoubleRunStairWithLanding
from .utils import filter, truncate


class Level:
    def __init__(self, index, elements: List[BuildingElement]):
        self.index = index
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
    def __init__(self, offset=(0, 0), dimension=None, unit_scaler=lambda x: x):
        self.highest_id_map = defaultdict(lambda: 0)
        self.levels: List[Level] = []
        self.stairs: List[StraightSingleRunStair] = []
        self.vertices = {}
        self.x_offset, self.y_offset = offset
        self.unit_scaler = unit_scaler
        self.dimension = dimension

    def add_level(self, level):
        self.levels.append(level)

    def add_stair(self, stair: StraightSingleRunStair):
        self.stairs.append(stair)

    def write(self):
        self.map_bounds = self._get_map_bounds()
        levels = [self._get_level(x) for x in self.levels if len(x.elements) > 0]
        stairs = [self._create_stair_json(s) for s in self.stairs]
        stairs = [s for s in stairs if s is not None]
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
        level_id = self._get_id(Level)

        walls = [x for x in [self._create_wall_json(x) for x in level.walls] if x is not None]
        gates = [self._create_gate_json(x) for x in level.gates]
        barricades = [self._create_barricade_json(x) for x in level.barricades]

        if self.dimension is not None:
            width, height = self.dimension
        else:
            width, height = self._get_map_size()

        return {
            "id": level_id,
            "width": math.ceil(width),
            "height": math.ceil(height),
            "wall_pkg": {"walls": {"Wall": walls}},
            "barricade_pkg": {"barricade_walls": {"Wall": barricades}},
            "gate_pkg": {"gates": {"Gate": gates}},
        }

    def _create_wall_json(self, wall: Wall):
        wall_id = self._get_id()
        (x1, y1), (x2, y2) = self._normalize_vertex(wall.start_vertex), self._normalize_vertex(wall.end_vertex)

        length = self.unit_scaler(wall.length)
        if length == 0:
            return None

        return {
            "id": wall_id,
            "name": wall.name,
            "length": length,
            "isLow": False,
            "isTransparent": False,
            "iWlWG": False,
            "vertices": {
                "Vertex": [
                    self._get_vertex((x1, y1)),
                    self._get_vertex((x2, y2))
                ]
            },
        }

    def _create_gate_json(self, gate: Gate):
        gate_id = self._get_id()
        (x1, y1), (x2, y2) = self._normalize_vertex(gate.start_vertex), self._normalize_vertex(gate.end_vertex)
        return {
            "id": gate_id,
            "length": self.unit_scaler(gate.length),
            "angle": 0,  # TODO?
            "destination": False,
            "counter": False,
            "transparent": False,
            "designatedOnly": False,
            "vertices": {
                "Vertex": [
                    self._get_vertex((x1, y1)),
                    self._get_vertex((x2, y2))
                ]
            },
        }

    def _create_barricade_json(self, barricade: Barricade):
        barricade_id = self._get_id()
        (x1, y1), (x2, y2) = barricade.start_vertex, barricade.end_vertex

        return {
            "id": barricade_id,
            "length": self.unit_scaler(barricade.length),
            "isLow": False,
            "isTransparent": False,
            "iWlWG": False,
            "vertices": {
                "Vertex": [
                    self._get_vertex(self._normalize_vertex((x1, y1))),
                    self._get_vertex(self._normalize_vertex((x2, y2)))
                ]
            },
        }

    def _create_stair_json(self, stair):
        if stair.__type__ == 'StraightSingleRunStair':
            return self._create_straight_single_run_stair_json(stair)
        elif stair.__type__ == 'DoubleRunStairWithLanding':
            return self._create_double_run_with_landing_stair_json(stair)

    def _create_straight_single_run_stair_json(self, stair: StraightSingleRunStair):
        stair_id = self._get_id()
        stair_vertex = self._normalize_vertex(stair.vertex)

        return {
            "id": stair_id,
            "x": stair_vertex[0],  # X coordinate of first lower vertex
            "y": stair_vertex[1],  # Y coordinate of first lower vertex
            "speed": -1,  # TODO figure out what
            "spanFloors": stair.end_level_index - stair.start_level_index,
            "length": self.unit_scaler(stair.run_length),  # Run length
            "width": self.unit_scaler(stair.staircase_width),  # Staircase width
            "widthLanding": self.unit_scaler(stair.staircase_width),
            "stands": int(stair.no_of_treads),
            "rotation": stair.rotation,  # Can be inferred from rotation matrix or axis. 0 means facing north
            "type": 1,  # Read from enum
            "direction": 0,
            "upper": {
                "level": stair.end_level_index,
                "gate": {
                        "id": self._get_id(),
                        "length": self.unit_scaler(stair.staircase_width),  # should be the same as width, if stair is STRAIGHT
                        "angle": 90,  # TODO find out what
                        "destination": False,  # let the software figure out I suppose
                        "counter": False,  # TODO find out what
                        "transparent": False,
                        "designatedOnly": False,
                        "vertices": {
                            "Vertex": [
                                self._get_vertex(self._normalize_vertex(stair.upper_gate[0])),
                                self._get_vertex(self._normalize_vertex(stair.upper_gate[1])),
                            ]
                        }
                }
            },
            "lower": {
                "level": stair.start_level_index,
                "gate": {
                    "id": self._get_id(),
                    "length": self.unit_scaler(stair.staircase_width),  # should be the same as width, if stair is STRAIGHT
                    "angle": 90,  # TODO find out what
                    "destination": False,  # let the software figure out I suppose
                    "counter": False,  # TODO find out what
                    "transparent": False,
                    "designatedOnly": False,
                    "vertices": {
                        "Vertex": [
                            self._get_vertex(self._normalize_vertex(stair.lower_gate[0])),
                            self._get_vertex(self._normalize_vertex(stair.lower_gate[1])),
                        ]
                    }
                }
            },
            "walls": {
                "Wall": [
                ]
            }
        }

    def _create_double_run_with_landing_stair_json(self, stair: DoubleRunStairWithLanding):
        stair_id = self._get_id()
        stair_vertex = self._normalize_vertex(stair.vertex)

        return {
            "id": stair_id,
            "x": stair_vertex[0],  # X coordinate of first lower vertex
            "y": stair_vertex[1],  # Y coordinate of first lower vertex
            "speed": -1,  # TODO figure out what
            "spanFloors": stair.end_level_index - stair.start_level_index,
            "length": self.unit_scaler(stair.run_length / 2),  # Run length
            "width": self.unit_scaler(stair.staircase_width / 2),  # Staircase width
            "widthLanding": self.unit_scaler(stair.staircase_width / 2),
            "stands": int(stair.no_of_treads),
            "rotation": stair.rotation,  # Can be inferred from rotation matrix or axis. 0 means facing north
            "type": 2,  # Read from enum
            "direction": 0,
            "upper": {
                "level": stair.end_level_index,
                "gate": {
                        "id": self._get_id(),
                        "length": self.unit_scaler(stair.staircase_width / 2),  # should be the same as width, if stair is STRAIGHT
                        "angle": 90,  # TODO find out what
                        "destination": False,  # let the software figure out I suppose
                        "counter": False,  # TODO find out what
                        "transparent": False,
                        "designatedOnly": False,
                        "vertices": {
                            "Vertex": [
                                self._get_vertex(self._normalize_vertex(stair.upper_gate[0])),
                                self._get_vertex(self._normalize_vertex(stair.upper_gate[1])),
                            ]
                        }
                }
            },
            "lower": {
                "level": stair.start_level_index,
                "gate": {
                    "id": self._get_id(),
                    "length": self.unit_scaler(stair.staircase_width / 2),  # should be the same as width, if stair is STRAIGHT
                    "angle": 90,  # TODO find out what
                    "destination": False,  # let the software figure out I suppose
                    "counter": False,  # TODO find out what
                    "transparent": False,
                    "designatedOnly": False,
                    "vertices": {
                        "Vertex": [
                            self._get_vertex(self._normalize_vertex(stair.lower_gate[0])),
                            self._get_vertex(self._normalize_vertex(stair.lower_gate[1])),
                        ]
                    }
                }
            },
            "walls": {
                "Wall": [
                ]
            }
        }

    def _get_vertex(self, vertex):
        x, y = vertex
        return {"X": x, "Y": y, "id": self._get_vertex_id(vertex)}

    def _get_vertex_id(self, vertex):
        if vertex not in self.vertices:
            self.vertices[vertex] = self._get_id("Vertex")
        return self.vertices[vertex]

    def _get_id(self, entity=None):
        id = self.highest_id_map[entity]
        self.highest_id_map[entity] += 1
        return id

    def _normalize_vertex(self, vertex: Tuple[float, float]) -> Tuple[float, float]:
        x1, y1 = vertex
        x1, y1 = self._scale_to_metric((x1, y1))
        (x_min, y_min), _ = self.map_bounds

        x1, y1 = truncate(x1), truncate(y1)
        x_min, y_min = truncate(x_min), truncate(y_min)

        x1, y1 = x1 + self.x_offset - x_min, y1 + self.y_offset - y_min

        return x1, y1

    def _scale_to_metric(self, length):
        if isinstance(length, tuple):
            new_list = [self.unit_scaler(x) for x in length]
            return tuple(new_list)
        elif isinstance(length, list):
            new_list = [self.unit_scaler(x) for x in length]
            return new_list

        return self.unit_scaler(length)

    def _get_map_size(self):
        (x_min, y_min), (x_max, y_max) = self.map_bounds

        # Account for x and y offset
        w = x_max - x_min + 2 * self.x_offset
        h = y_max - y_min + 2 * self.y_offset

        return w, h

    def _get_map_bounds(self):
        x_max = 0
        x_min = math.inf
        y_max = 0
        y_min = math.inf
        for level in self.levels:
            for element in level.elements:
                x_max = max(x_max, element.start_vertex[0], element.end_vertex[0])
                x_min = min(x_min, element.start_vertex[0], element.end_vertex[0])
                y_max = max(y_max, element.start_vertex[1], element.end_vertex[1])
                y_min = min(y_min, element.start_vertex[1], element.end_vertex[1])

        x_max = math.ceil(x_max)
        y_max = math.ceil(y_max)
        x_min = math.floor(x_min)
        y_min = math.floor(y_min)

        # Scale to metric
        x_max, y_max = self._scale_to_metric((x_max, y_max))
        x_min, y_min = self._scale_to_metric((x_min, y_min))

        return (x_min, y_min), (x_max, y_max)
