import logging
from pathlib import Path

from pyinstrument import Profiler

logger = logging.getLogger(__name__)


class AppProfiler:
    def __init__(self, enabled: bool):
        self.enabled = enabled
        self.profiler = Profiler()

    async def start(self):
        logger.debug("Method called")
        if self.enabled:
            print("start profiling")
            logger.debug("Start profiler")
            self.profiler.start()

    async def stop_and_save(self):
        logger.debug("Method stop called")
        print("stop profiling")
        if self.enabled:
            logger.debug("Stop profiler")
            self.profiler.stop()
            html_report = self.profiler.output_html()
            path = Path(__file__).parent.parent / "plugins" / "profile_report.html"
            with open(path, "w", encoding="utf-8") as f:
                f.write(html_report)
            logger.info(f"Profiling is complete. The report is saved: {path}")
