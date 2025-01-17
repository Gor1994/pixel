import { useState, useEffect, useCallback } from "react";
import { ENERGY_CONFIG } from "../constants/game";

export function useEnergy(initialPlayer) {
  const [player, setPlayer] = useState(initialPlayer);

  // Energy regeneration
  useEffect(() => {
    const interval = setInterval(() => {
      setPlayer((prev) => {
        const now = Date.now();
        const timeSinceLastRecharge = now - prev.energy.lastRechargeTime;
        const newCharges = Math.min(
          prev.energy.charges + Math.floor(timeSinceLastRecharge / ENERGY_CONFIG.RECHARGE_TIME),
          ENERGY_CONFIG.MAX_CHARGES
        );

        if (newCharges === prev.energy.charges) return prev;

        return {
          ...prev,
          energy: {
            ...prev.energy,
            charges: newCharges,
            clicks: newCharges > prev.energy.charges ? ENERGY_CONFIG.CLICKS_PER_CHARGE : prev.energy.clicks,
            lastRechargeTime: now,
          },
        };
      });
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  const consumeEnergy = useCallback(() => {
    const now = Date.now();

    if (now - player.energy.lastClickTime < ENERGY_CONFIG.CLICK_COOLDOWN) {
      return false;
    }

    if (player.energy.clicks <= 0) {
      if (player.energy.charges > 0) {
        setPlayer((prev) => ({
          ...prev,
          energy: {
            ...prev.energy,
            charges: prev.energy.charges - 1,
            clicks: ENERGY_CONFIG.CLICKS_PER_CHARGE,
            lastClickTime: now,
          },
        }));
        return true;
      }
      return false;
    }

    setPlayer((prev) => ({
      ...prev,
      energy: {
        ...prev.energy,
        clicks: prev.energy.clicks - 1,
        lastClickTime: now,
      },
    }));

    return true;
  }, [player]);

  return { player, consumeEnergy };
}
