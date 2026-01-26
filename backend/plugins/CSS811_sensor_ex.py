import asyncio
import logging
import random
from datetime import datetime
from typing import Dict, Any

from plugins.template import DevicePlugin

logger = logging.getLogger(__name__)


class CCS811AirQualityPlugin(DevicePlugin):
    """
    Test plugin for virtual TVOC sensor (Total Volatile Organic Compounds).
    Generates realistic TVOC data in μg/m³.
    """

    def __init__(self, device_id: str, poll_interval: float = 10.0):
        super().__init__(device_id, poll_interval)
        # Base TVOC level for residential space (typical: 50–200 μg/m³)
        self.base_tvoc = 150.0
        # Current value with smooth fluctuations
        self.current_tvoc = self.base_tvoc
        # Timestamp of last significant change
        self.last_change = datetime.now()
        # History of peak values (for accumulation simulation)
        self.peak_history = []

    async def init_hardware(self) -> None:
        """Simulates sensor initialization."""
        logger.info(f"Initializing virtual TVOC sensor ({self.device_id})")
        # Simulate calibration delay (typical for VOC sensors)
        await asyncio.sleep(1.5)
        logger.info(f"TVOC sensor {self.device_id} is ready")

    async def read_data(self) -> Dict[str, Any]:
        """
        Generates realistic TVOC readings with smooth dynamics and real-life factors.
        """
        result = {
            "value": None,
            "unit": "μg/m³",
            "status": None,
            "recent_peaks": None,
            "online": False,
        }
        now = datetime.now()

        # Significant change every 3–8 minutes
        if (now - self.last_change).total_seconds() > random.uniform(180, 480):
            # Key influencing factors:
            # - Household cleaning chemicals (+100–300 μg/m³)
            # - Cooking (+50–200 μg/m³)
            # - Ventilation (−50–150 μg/m³)
            # - Printer/copier operation (+30–100 μg/m³)

            # Event probabilities
            is_cleaning = random.random() < 0.1  # cleaning with chemicals
            is_cooking = random.random() < 0.2  # cooking
            is_ventilating = random.random() < 0.15  # venting
            is_printing = random.random() < 0.05  # printer in use

            tvoc_delta = 0

            if is_ventilating:
                tvoc_delta -= random.uniform(50, 150)
            else:
                if is_cleaning:
                    tvoc_delta += random.uniform(100, 300)
                if is_cooking:
                    tvoc_delta += random.uniform(50, 200)
                if is_printing:
                    tvoc_delta += random.uniform(30, 100)

            # Apply change
            self.current_tvoc += tvoc_delta

            # Constrain to realistic range
            self.current_tvoc = max(0, min(3000, self.current_tvoc))  # 0–3000 μg/m³

            self.last_change = now
            # Add to peak history
            self.peak_history.append((now, self.current_tvoc))
            # Keep only last 10 peaks
            if len(self.peak_history) > 10:
                self.peak_history.pop(0)

        # Smooth fluctuations between significant changes
        else:
            # Natural fluctuations ±5–15 μg/m³
            self.current_tvoc += random.uniform(-15, 15)

        # Round to 1 decimal place
        tvoc = round(self.current_tvoc, 1)
        result["value"] = tvoc
        result["status"] = self._get_status(tvoc)
        result["recent_peaks"] = [round(p[1], 1) for p in self.peak_history]
        result["online"] = True
        return result

    def _get_status(self, tvoc: float) -> str:
        """
        Determines air quality status based on TVOC level (WHO/EPA guidelines).
        """
        if tvoc < 200:
            return "good"  # Excellent air quality
        elif tvoc < 600:
            return "moderate"  # Moderate pollution (acceptable for homes)
        elif tvoc < 1000:
            return "poor"  # Elevated level (ventilation recommended)
        else:
            return "hazardous"  # Dangerous level (urgent venting/filtration needed)

    async def handle_command(self, command: Dict[str, Any]) -> None:
        """Command handling (not implemented in test plugin)."""
        logger.debug(f"Command for {self.device_id}: {command}")
