from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Constants
FORT_MIN_SIZE = 3

# Grid dictionary to store only claimed cells
grid = {}

def get_neighbors(row, col):
    """Get neighbors for a given cell."""
    return [
        (row - 1, col), (row + 1, col),  # Vertical neighbors
        (row, col - 1), (row, col + 1)   # Horizontal neighbors
    ]

def detect_and_mark_fort(grid, start_cell=None):
    """Detect and mark forts (rectangles) with a minimum size, allowing for hollow centers."""
    visited = set()  # Track visited cells
    cells_in_forts = set()  # Track cells already part of a fort

    def dfs(row, col):
        """Depth-first search to find all connected cells."""
        stack = [(row, col)]
        component = set()

        while stack:
            r, c = stack.pop()
            if (r, c) in visited or (r, c) not in grid:
                continue
            visited.add((r, c))
            if grid[(r, c)].get("isFort"):  # Skip cells already in a fort
                cells_in_forts.add((r, c))
                continue
            component.add((r, c))
            stack.extend(get_neighbors(r, c))

        return component

    # If a specific cell is provided, start detection only from that cell
    if start_cell:
        start_row, start_col = start_cell
        connected_cells = dfs(start_row, start_col)
    else:
        # Process all cells in the grid
        for (row, col) in grid:
            if (row, col) in visited or grid[(row, col)].get("isFort"):
                continue
            connected_cells = dfs(row, col)

    # Group cells by rows
    rows = {}
    for r, c in connected_cells:
        if r not in rows:
            rows[r] = []
        rows[r].append(c)

    # Sort rows and their columns
    for r in rows:
        rows[r] = sorted(rows[r])

    # Check for rectangles
    row_indices = sorted(rows.keys())
    for start_row_idx in range(len(row_indices)):
        for end_row_idx in range(start_row_idx + FORT_MIN_SIZE - 1, len(row_indices)):
            start_row = row_indices[start_row_idx]
            end_row = row_indices[end_row_idx]

            # Check if all required rows exist
            if not all(row in rows for row in range(start_row, end_row + 1)):
                continue

            # Determine the column range for the rectangle
            start_col = min(min(rows[row]) for row in range(start_row, end_row + 1))
            end_col = max(max(rows[row]) for row in range(start_row, end_row + 1))

            # Ensure the rectangle meets the minimum size requirements
            if (end_row - start_row + 1) < FORT_MIN_SIZE or (end_col - start_col + 1) < FORT_MIN_SIZE:
                continue

            # Validate the borders of the rectangle
            is_valid_rectangle = True

            # Check top and bottom rows (must be fully filled across start_col to end_col)
            if not all((start_row, col) in connected_cells for col in range(start_col, end_col + 1)):
                is_valid_rectangle = False
            if not all((end_row, col) in connected_cells for col in range(start_col, end_col + 1)):
                is_valid_rectangle = False

            # Check left and right columns (must be fully filled from start_row to end_row)
            if not all((row, start_col) in connected_cells for row in range(start_row, end_row + 1)):
                is_valid_rectangle = False
            if not all((row, end_col) in connected_cells for row in range(start_row, end_row + 1)):
                is_valid_rectangle = False

            if is_valid_rectangle:
                print(f"🏰 Detected valid rectangle from ({start_row}, {start_col}) to ({end_row}, {end_col})")
                # Mark the rectangle cells
                for r in range(start_row, end_row + 1):
                    for c in range(start_col, end_col + 1):
                        if r == start_row or r == end_row or c == start_col or c == end_col:
                            # Border cells
                            if (r, c) not in grid:
                                grid[(r, c)] = {"isFort": True, "ownerId": None, "isClickable": False}
                            else:
                                grid[(r, c)]["isFort"] = True
                                grid[(r, c)]["isClickable"] = False
                            cells_in_forts.add((r, c))
                        else:
                            # Inner cells (make them not clickable and mark as part of the fort)
                            if (r, c) not in grid:
                                grid[(r, c)] = {"isInnerCell": True, "isClickable": False, "ownerId": None}
                            else:
                                grid[(r, c)]["isInnerCell"] = True
                                grid[(r, c)]["isClickable"] = False
                return True  # A fort has been detected

    return False  # No fort detected

@app.route("/get-grid", methods=["GET"])
def get_grid():
    """Return the current grid state."""
    return jsonify({f"{r}-{c}": cell for (r, c), cell in grid.items()})

@app.route("/claim-cell", methods=["POST"])
def claim_cell():
    """Handle cell clicks."""
    data = request.json
    row, col = data.get("row"), data.get("col")
    user_id = data.get("userId")

    if (row, col) in grid:
        return jsonify({"error": "Cell already claimed"}), 400

    # Claim the cell
    grid[(row, col)] = {"ownerId": user_id, "isFort": False, "isClickable": True}
    print(f"✅ Cell ({row}, {col}) claimed by user {user_id}")

    # Detect and mark forts starting from this cell
    new_fort_detected = detect_and_mark_fort(grid, start_cell=(row, col))
    if new_fort_detected:
        print(f"🏰 A new fort has been detected starting from cell ({row}, {col})")

    return jsonify({f"{r}-{c}": cell for (r, c), cell in grid.items()})

if __name__ == "__main__":
    app.run(debug=True)