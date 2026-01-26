
from svgpathtools import svg2paths
import os
import glob

def calculate_bbox(svg_file):
    paths, attributes = svg2paths(svg_file)
    if not paths:
        return None

    min_x, min_y, max_x, max_y = float('inf'), float('inf'), float('-inf'), float('-inf')

    for path in paths:
        xmin, xmax, ymin, ymax = path.bbox()
        min_x = min(min_x, xmin)
        max_x = max(max_x, xmax)
        min_y = min(min_y, ymin)
        max_y = max(max_y, ymax)

    return min_x, min_y, max_x, max_y

def main():
    svg_files = [
        "static/Dashboard_Icon.svg",
        "static/Tracking_Icon.svg",
        "static/Mentor_Chat_Icon.svg",
        "static/Settings_Icon.svg",
        "static/Logout_Icon.svg"
    ]

    for svg_file in svg_files:
        if os.path.exists(svg_file):
            bbox = calculate_bbox(svg_file)
            if bbox:
                min_x, min_y, max_x, max_y = bbox
                width = max_x - min_x
                height = max_y - min_y
                print(f"{svg_file}: x={min_x:.2f}, y={min_y:.2f}, w={width:.2f}, h={height:.2f}")
                print(f"  Proposed viewBox: {min_x:.2f} {min_y:.2f} {width:.2f} {height:.2f}")
            else:
                print(f"{svg_file}: No paths found")
        else:
            print(f"{svg_file}: Not found")

if __name__ == "__main__":
    main()
