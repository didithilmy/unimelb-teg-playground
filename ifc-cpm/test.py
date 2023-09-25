from lib.utils import find_lines_intersection


def find_intersection(line1, line2):
    (x1, y1), (x2, y2) = line1
    (x3, y3), (x4, y4) = line2
    # Calculate the slopes of the two line segments
    m1 = (y2 - y1) / (x2 - x1) if (x2 - x1) != 0 else float('inf')
    m2 = (y4 - y3) / (x4 - x3) if (x4 - x3) != 0 else float('inf')

    # Check if the segments are parallel (the slopes are the same)
    if m1 == m2:
        return None  # No intersection, the lines are parallel

    # Calculate the intersection point
    if m1 == float('inf'):  # First line is vertical
        x = x1
        y = m2 * (x - x3) + y3
    elif m2 == float('inf'):  # Second line is vertical
        x = x3
        y = m1 * (x - x1) + y1
    else:
        x = (m1 * x1 - y1 - m2 * x3 + y3) / (m1 - m2)
        y = m1 * (x - x1) + y1

    # Check if the intersection point is within both line segments
    if (
        min(x1, x2) <= x <= max(x1, x2) and
        min(y1, y2) <= y <= max(y1, y2) and
        min(x3, x4) <= x <= max(x3, x4) and
        min(y3, y4) <= y <= max(y3, y4)
    ):
        return (x, y)  # Intersection point is within both line segments
    else:
        return None  # Intersection point is outside one or both line segments


line1 = (-4073.424439342946, 6067.438619937829), (-4073.424439342919, 22180.290756191764)
line2 = (-1504.1744393429449, 6067.438619937829), (-9848.79943934293, 6067.438619937829)
intr = find_intersection(line1, line2)

intr = find_intersection(((0, 0), (5, 0)), ((0, 1), (0, 5)))
print(intr)
