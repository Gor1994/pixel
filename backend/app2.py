from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # Allow all origins for testing

# Grid Configuration
GRID_SIZE = 100
board = [
    [{"owner": None, "level": 0} for _ in range(GRID_SIZE)]
    for _ in range(GRID_SIZE)
]

forts = []  # Persistent list to store detected forts


@app.route("/click", methods=["POST"])
def handle_click():
    global forts
    try:
        data = request.json
        x, y = data["x"], data["y"]
        user_id = data["user_id"]

        # Validate click
        if not (0 <= x < GRID_SIZE and 0 <= y < GRID_SIZE):
            return jsonify({"error": "Invalid coordinates"}), 400
        if board[y][x]["owner"]:
            return jsonify({"error": "Cell already clicked"}), 400

        # Update the grid
        board[y][x]["owner"] = user_id
        board[y][x]["level"] += 1

        # Detect new forts only, without invalidating previous forts
        new_forts = detect_new_forts(user_id)
        forts.extend(new_forts)

        return jsonify({"board": board, "forts": new_forts}), 200

    except Exception as e:
        print(f"Error occurred: {e}")
        return jsonify({"error": str(e)}), 500

def detect_new_forts(user_id):
    """
    Detect new forts, distinguish between boundary and inner cells, 
    and identify interior cells to change their styles.
    """
    visited = set()
    new_forts = []

    def is_valid_cell(x, y):
        return (
            0 <= x < GRID_SIZE
            and 0 <= y < GRID_SIZE
            and board[y][x]["owner"] == user_id
        )

    def explore_rectangle(x, y):
        """Explore a rectangle and return its bounding box and cells."""
        min_x, max_x = x, x
        min_y, max_y = y, y
        stack = [(x, y)]
        cells = []

        while stack:
            cx, cy = stack.pop()
            if (cx, cy) in visited:
                continue
            visited.add((cx, cy))
            cells.append((cx, cy))

            min_x = min(min_x, cx)
            max_x = max(max_x, cx)
            min_y = min(min_y, cy)
            max_y = max(max_y, cy)

            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                if is_valid_cell(cx + dx, cy + dy) and (cx + dx, cy + dy) not in visited:
                    stack.append((cx + dx, cy + dy))

        return min_x, min_y, max_x, max_y, cells

    def is_valid_fort(min_x, min_y, max_x, max_y, cells):
        """
        Validate the fort and identify inner cells:
        - All boundary cells must be owned by the user.
        - Inner cells must not be owned by anyone.
        """
        cell_set = set(cells)
        boundary_cells = set()
        inner_cells = []

        for y in range(min_y, max_y + 1):
            for x in range(min_x, max_x + 1):
                is_boundary = x == min_x or x == max_x or y == min_y or y == max_y

                if is_boundary:
                    # Boundary cells must be part of the connected region
                    if (x, y) not in cell_set:
                        return False, [], []  # Fort is invalid if a boundary cell is missing
                    boundary_cells.add((x, y))
                else:
                    # Inner cells should not be owned by anyone
                    if board[y][x]["owner"] is None:
                        inner_cells.append((x, y))
                    else:
                        # If an inner cell is owned, the fort is invalid
                        return False, [], []

        # Fort is valid if all boundary cells are filled and there are empty inner cells
        if not inner_cells:
            return False, [], []

        return True, boundary_cells, inner_cells


    for y in range(GRID_SIZE):
        for x in range(GRID_SIZE):
            if is_valid_cell(x, y) and (x, y) not in visited:
                min_x, min_y, max_x, max_y, cells = explore_rectangle(x, y)
                is_fort, boundary_cells, inner_cells = is_valid_fort(
                    min_x, min_y, max_x, max_y, cells
                )
                if is_fort:
                    fort = {
                        "boundary_cells": list(boundary_cells),
                        "inner_cells": inner_cells,
                        "dimensions": {"width": max_x - min_x + 1, "height": max_y - min_y + 1},
                    }
                    new_forts.append(fort)

    return new_forts



if __name__ == "__main__":
    app.run(debug=True)
