// Board configuration
export const CELL_SIZE = 20;
export const BOARD_WIDTH = 2000;
export const BOARD_HEIGHT = 2000;
export const VIEWPORT_WIDTH = window.innerWidth;
export const VIEWPORT_HEIGHT = window.innerHeight;

// Energy configuration
export const ENERGY_CONFIG = {
  MAX_CHARGES: 4,
  CLICKS_PER_CHARGE: 500,
  CLICK_COOLDOWN: 1000, // 1 second
  RECHARGE_TIME: 300000, // 5 minutes
  ENERGY_REGEN_RATE: 1, // energy per second
};

// Fort configuration
export const FORT_CONFIG = {
  MIN_LEVEL: 1,
  MAX_SINGLE_CELL_LEVEL: 2,
  MAX_FORT_LEVEL: 12,
  CAPTURE_LEVEL_DIFFERENCE: 1,
  FORT_COLORS: {
    1: "#4F46E5",
    2: "#7C3AED",
    3: "#DB2777",
    4: "#DC2626",
    5: "#EA580C",
    6: "#D97706",
    7: "#65A30D",
    8: "#059669",
    9: "#0891B2",
    10: "#6366F1",
    11: "#8B5CF6",
    12: "#EC4899",
  },
};
