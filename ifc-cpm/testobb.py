import numpy as np
from compas.geometry import oriented_bounding_box_xy_numpy

point_cloud = np.array([
    [0, 1],
    [1, 0],
    [4, 1],
    [3, 0]
])

print("Computing bbox")
box = oriented_bounding_box_xy_numpy(points=point_cloud)
print(box)