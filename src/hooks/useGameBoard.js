import { useState, useCallback } from "react";
import { BOARD_WIDTH, BOARD_HEIGHT, VIEWPORT_WIDTH, VIEWPORT_HEIGHT } from "../constants/game";

export function useGameBoard() {
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  const handleMouseDown = useCallback(
    (e) => {
      setIsDragging(true);
      setDragStart({
        x: e.clientX - position.x,
        y: e.clientY - position.y,
      });
    },
    [position]
  );

  const handleMouseMove = useCallback(
    (e) => {
      if (!isDragging) return;

      const newX = e.clientX - dragStart.x;
      const newY = e.clientY - dragStart.y;

      // Add bounds checking
      const boundedX = Math.max(Math.min(newX, 0), -(BOARD_WIDTH - VIEWPORT_WIDTH));
      const boundedY = Math.max(Math.min(newY, 0), -(BOARD_HEIGHT - VIEWPORT_HEIGHT));

      setPosition({ x: boundedX, y: boundedY });
    },
    [isDragging, dragStart]
  );

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  return {
    position,
    isDragging,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
  };
}
