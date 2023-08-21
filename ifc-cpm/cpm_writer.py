from typing import List
import xmltodict


class Level:
    def __init__(self, width=100, height=100):
        self.walls = []
        self.doors = []
        self.dimension = (width, height)

    def add_wall(self, vertices, length):
        self.walls.append((length, vertices))


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

        walls = []
        for length, vertices in level.walls:
            wall_id = self._get_id()
            (x1, y1), (x2, y2) = vertices

            walls.append(
                {
                    "id": wall_id,
                    "length": length,
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
            )

        return {
            "id": level_id,
            "width": level.dimension[0],
            "height": level.dimension[1],
            "wall_pkg": {"walls": {"Wall": walls}},
        }

    def _get_vertex_id(self, vertex):
        if vertex not in self.vertices:
            self.vertices[vertex] = self._get_id()
        return self.vertices[vertex]

    def _get_id(self):
        self.highest_id += 1
        return self.highest_id
