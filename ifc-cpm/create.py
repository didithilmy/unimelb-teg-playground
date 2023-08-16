import xmltodict

data = {
    "Model": {
        "@xmlns:xsd": "http://www.w3.org/2001/XMLSchema",
        "@xmlns:xsi": "http://www.w3.org/2001/XMLSchema-instance",
        "version": "2023.1.0",
        "panicMode": False,
        "validatedSuccessfully": False,
        "levelHeight": 2.5,
        "levels": {
            "Level": [
                {
                    "id": 0,
                    "width": 49,
                    "height": 49,
                    "wall_pkg": {
                        "walls": {
                            "Wall": [
                                {
                                    "id": 24,
                                    "length": 1,
                                    "isLow": False,
                                    "isTransparent": False,
                                    "isWlWG": False,
                                    "vertices": {
                                        "Vertex": [
                                            {"X": 28, "Y": 30, "id": 28},
                                            {"X": 28, "Y": 31, "id": 23},
                                        ],
                                    },
                                }
                            ]
                        }
                    },
                }
            ]
        },
        "cameraPos": {"x": 0, "y": 12.325, "z": 0},
        "cameraRot": {"x": 18.306, "y": 45, "z": 0},
    }
}

print(xmltodict.unparse(data, pretty=True))
