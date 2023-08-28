def find_lines_intersection(line1, line2):
    line1_point1, line1_point2 = line1
    line2_point1, line2_point2 = line2

    x1, y1 = line1_point1
    x2, y2 = line1_point2
    x3, y3 = line2_point1
    x4, y4 = line2_point2

    # Calculate slopes and intercepts of the two lines, if the line is NOT vertical.
    m1, b1 = None, None
    if x1 != x2:
        m1 = (y2 - y1) / (x2 - x1)
        b1 = y1 - m1 * x1

    m2, b2 = None, None
    if x3 != x4:
        m2 = (y4 - y3) / (x4 - x3)
        b2 = y3 - m2 * x3

    if m1 == m2 and m1 is not None and m2 is not None:
        return None

    if m1 is None and m2 is None:
        if x1 == x3:
            return None  # FIXME TODO handle lines occupying the same space.
        return None

    if m1 is None:
        intersection_x = x1
        intersection_y = m2 * intersection_x + b2
    elif m2 is None:
        intersection_x = x3
        intersection_y = m1 * intersection_x + b1
    else:
        intersection_x = (b2 - b1) / (m1 - m2)
        intersection_y = m1 * intersection_x + b1

    # Check if the intersection point is within the bounds of both line segments
    if (
        min(x1, x2) <= intersection_x <= max(x1, x2)
        and min(y1, y2) <= intersection_y <= max(y1, y2)
        and min(x3, x4) <= intersection_x <= max(x3, x4)
        and min(y3, y4) <= intersection_y <= max(y3, y4)
    ):
        return intersection_x, intersection_y
    else:
        return None  # No intersection within bounds
