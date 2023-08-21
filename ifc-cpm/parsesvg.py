import xmltodict
from svgpathtools import parse_path
from cpm_writer import CrowdSimulationEnvironment, Level

SCALING_FACTOR = 0.05


def parse_storey(storey):
    parsed_ids = set()
    walls = []
    doors = []
    products = storey["g"]
    for product in products:
        ifc_class = product["@class"]
        if ifc_class in ("IfcWallStandardCase", "IfcWall"):
            walls.append(product)
        elif ifc_class in ("IfcDoor",):
            doors.append(product)

    parsed_walls = []
    for wall in walls:
        object_id = wall["@data-guid"]
        object_name = wall["@data-name"]

        if wall['@id'].endswith('-box'):
            parsed_ids.add(object_id)
            paths = wall["path"]
            if isinstance(paths, dict):
                paths = [paths]

            path = parse_path(paths[0]["@d"])

            # FIXME Warning: Won't work on diagonal walls
            xmin, xmax, ymin, ymax = path.bbox()

            # Determine if this is horz or vertical
            if xmax - xmin < ymax - ymin:
                # Vertical wall
                x1, y1 = (
                    SCALING_FACTOR * (((xmax - xmin) / 2) + xmin),
                    SCALING_FACTOR * ymin,
                )
                x2, y2 = (
                    SCALING_FACTOR * (((xmax - xmin) / 2) + xmin),
                    SCALING_FACTOR * ymax,
                )

                # x1, y1 = round(x1), round(y1)
                # x2, y2 = round(x2), round(y2)
                length = y2 - y1
            elif xmax - xmin >= ymax - ymin:
                # TODO if the wall is square, find a way to determine this.
                # Horizontal wall
                x1, y1 = SCALING_FACTOR * xmin, SCALING_FACTOR * (
                    ((ymax - ymin) / 2) + ymin
                )
                x2, y2 = SCALING_FACTOR * xmax, SCALING_FACTOR * (
                    ((ymax - ymin) / 2) + ymin
                )

                # x1, y1 = round(x1), round(y1)
                # x2, y2 = round(x2), round(y2)
                length = x2 - x1

            parsed_walls.append(
                {
                    "name": object_name,
                    "length": length,
                    "vertices": ((x1, y1), (x2, y2)),
                }
            )

    parsed_doors = []
    # parsed_walls = []
    return parsed_walls, parsed_doors


storeys = []
with open("house.svg") as f:
    svg = xmltodict.parse(f.read())["svg"]
    for group in svg["g"]:
        if group["@class"] == "IfcBuildingStorey":
            storeys.append(group)

cpm = CrowdSimulationEnvironment()

for storey in storeys:
    parsed_walls, parsed_doors = parse_storey(storey)

    level = Level()
    for wall in parsed_walls:
        level.add_wall(wall["vertices"], wall["length"])
    cpm.add_level(level)

xml = cpm.write()
print(xml)
