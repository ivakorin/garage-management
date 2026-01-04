import logging
import glob
from pathlib import Path
from typing import Dict, Any, List

from .template import DevicePlugin

logger = logging.getLogger(__name__)

BASE_DIR = '/sys/bus/w1/devices/'
DEVICE_FOLDER:List[str] = glob.glob(BASE_DIR + '28*')

class DS18B20Plugin(DevicePlugin):
    def __init__(
            self,
            device_id: str,
            poll_interval: float = 5.0,
    ):
        super().__init__(device_id, poll_interval)
        self.device_id = device_id
        self.plugin_path = Path(__file__).parent.resolve()
        self.poll_interval = max(poll_interval, 0.1)


    async def init_hardware(self) -> None:
        pass

    async def read_data(self) -> Dict[str, Any]:
        data = {'unit': "celsius"}
        if len(DEVICE_FOLDER):
            for sensor in DEVICE_FOLDER:
                file_path = f'/sys/bus/w1/devices/{sensor}/temperature'
                try:
                    with open(file_path, 'r') as f:
                        temp_millicelsius = int(f.read().strip())

                    temperature_celsius = float(temp_millicelsius / 1000.0)
                    data[sensor] = temperature_celsius # type: ignore
                except FileNotFoundError:
                    logger.error(f"The temperature file was not found for the {sensor} sensor. Maybe w1_slave is being used.")
                    return data
                except ValueError:
                    logger.error(f"Incorrect data in temperature for {sensor}")
                    return data
                except Exception as e:
                    logger.error(f"Sensor {sensor}Read error: {e}")
                    return data
        return data




    async def handle_command(self, command: dict[str, Any]):
        pass