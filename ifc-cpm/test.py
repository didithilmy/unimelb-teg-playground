from lib.ifctypes import WallWithOpening, Wall, Gate
from lib.utils import eucledian_distance

wwo = WallWithOpening(
    start_vertex=(56521.078114, -23332.661381),
    end_vertex=(56521.07811400084, -14931.161381517002),
    opening_vertices=[
        ((56521.08, -30556.46), (56521.08, -20956.46)),
        ((56521.08, -16572.91), (56521.08, -15657.91))
    ])


def decompose_wall_with_opening(wall: WallWithOpening):
    out_elements = []
    edges = set()
    vertices = [wall.start_vertex, wall.end_vertex]

    for i, (opening_v1, opening_v2) in enumerate(wall.opening_vertices):
        gate = Gate(name=f"{wall.name}:gate-{i}", start_vertex=opening_v1, end_vertex=opening_v2)
        out_elements.append(gate)
        edges.add((opening_v1, opening_v2))
        edges.add((opening_v2, opening_v1))
        vertices += [opening_v1, opening_v2]

    vertex = vertices[0]
    while True:
        nearest_vertex = min(vertices, key=lambda v: eucledian_distance(vertex, v))
        if vertex != nearest_vertex:
            if (vertex, nearest_vertex) not in edges:
                connector = Wall(name=wall.name, start_vertex=vertex, end_vertex=nearest_vertex)
                edges.add((vertex, nearest_vertex))
                edges.add((nearest_vertex, vertex))
                out_elements.append(connector)

        vertex = nearest_vertex
        vertices.remove(vertex)

        if len(vertices) == 0:
            break

    return out_elements


el = decompose_wall_with_opening(wwo)
print(el)

"""
[
    Gate(None:gate-0, (56521.08, -30556.46), (56521.08, -20956.46)), 
    Gate(None:gate-1, (56521.08, -16572.91), (56521.08, -15657.91)), 
    Wall(None, (56521.078114, -23332.661381), (56521.08, -20956.46)), 
    Wall(None, (56521.08, -20956.46), (56521.08, -16572.91)), 
    Wall(None, (56521.08, -15657.91), (56521.07811400084, -14931.161381517002)), 
    Wall(None, (56521.07811400084, -14931.161381517002), (56521.08, -30556.46))]
"""