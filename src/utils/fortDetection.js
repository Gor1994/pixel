import { CELL_SIZE } from "../constants/game";

export function detectFort(cells, startCell) {
  const visited = new Set();
  const fortCells = [];
  let minX = startCell.x;
  let maxX = startCell.x;
  let minY = startCell.y;
  let maxY = startCell.y;

  // Depth-first search to collect connected cells
  function isValidCell(cell) {
    return (
      cell &&
      cell.owner === startCell.owner &&
      !visited.has(cell.id)
    );
  }

  function dfs(cell) {
    if (!isValidCell(cell)) return;
    visited.add(cell.id);
    fortCells.push(cell);

    minX = Math.min(minX, cell.x);
    maxX = Math.max(maxX, cell.x);
    minY = Math.min(minY, cell.y);
    maxY = Math.max(maxY, cell.y);

    const directions = [
      { x: 1, y: 0 },
      { x: -1, y: 0 },
      { x: 0, y: 1 },
      { x: 0, y: -1 },
    ];

    for (const dir of directions) {
      const nextCell = cells.find((c) => c.x === cell.x + dir.x && c.y === cell.y + dir.y);
      dfs(nextCell);
    }
  }

  dfs(startCell);

  // Scan for all possible rectangles within the bounding box
  for (let y1 = minY; y1 <= maxY - 2; y1++) {
    for (let x1 = minX; x1 <= maxX - 2; x1++) {
      for (let y2 = y1 + 2; y2 <= maxY; y2++) {
        for (let x2 = x1 + 2; x2 <= maxX; x2++) {
          if (isValidRectangle(cells, x1, y1, x2, y2, startCell.owner)) {
            return {
              cells: collectRectangleCells(x1, y1, x2, y2),
              dimensions: { width: x2 - x1 + 1, height: y2 - y1 + 1 },
              centerPoint: {
                x: ((x1 + x2) / 2) * CELL_SIZE,
                y: ((y1 + y2) / 2) * CELL_SIZE,
              },
              level: startCell.level,
            };
          }
        }
      }
    }
  }

  return null; // No valid fort found
}

function isValidRectangle(cells, x1, y1, x2, y2, owner) {
  let hasEmptyInside = false;

  for (let y = y1; y <= y2; y++) {
    for (let x = x1; x <= x2; x++) {
      const cell = cells.find((c) => c.x === x && c.y === y);
      const isBoundary = x === x1 || x === x2 || y === y1 || y === y2;

      if (isBoundary) {
        // Boundary cells must be owned by the player
        if (!cell || cell.owner !== owner) return false;
      } else {
        // Interior cells: Ensure at least one empty cell exists
        if (!cell || cell.owner !== owner) hasEmptyInside = true;
      }
    }
  }

  return hasEmptyInside; // Valid only if at least one interior cell is empty
}


function collectRectangleCells(x1, y1, x2, y2) {
  const cells = [];
  for (let y = y1; y <= y2; y++) {
    for (let x = x1; x <= x2; x++) {
      cells.push(`${x}-${y}`);
    }
  }
  return cells;
}
