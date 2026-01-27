import importlib.util
import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def setup_plugin_dependencies():
    """
    Sets up and imports plugin dependencies into plugins/lib.
    - Checks if the package is already installed.
    - If not, installs it into plugins/lib using pip --target.
    - Adds plugins/lib to sys.path (if not already present).
    - Imports packages; for RPi.GPIO, creates a GPIO alias.
    """
    # Path to the local plugin library
    lib_path = Path(__file__).parent.parent / "plugins" / "lib"
    lib_path.mkdir(exist_ok=True)
    lib_path_str = str(lib_path)

    # Add lib to sys.path if not already included
    if lib_path_str not in sys.path:
        sys.path.insert(0, lib_path_str)

    # List of required packages
    REQUIRED_PACKAGES = ["RPi.GPIO"]

    for package in REQUIRED_PACKAGES:
        try:
            # Step 1: Check if already imported (in current session)
            if package in sys.modules:
                logger.info(f"[DEP] {package} already loaded in sys.modules. Using it.")
                module = sys.modules[package]
            else:
                # Step 2: Check via importlib (scans sys.path, including lib_path)
                spec = importlib.util.find_spec(package)
                if spec is not None:
                    logger.info(f"[DEP] {package} found via find_spec. Importing...")
                    module = importlib.import_module(package)
                else:
                    # Step 3: Install into plugins/lib
                    logger.info(f"[DEP] Installing {package} into {lib_path}...")
                    subprocess.check_call(
                        [
                            sys.executable,
                            "-m",
                            "pip",
                            "install",
                            "--target",
                            lib_path_str,
                            package,
                        ]
                    )

                    # Step 4: Force reload of package metadata after install
                    # This clears any cached "not found" state
                    importlib.invalidate_caches()

                    # Step 5: Try import again
                    spec = importlib.util.find_spec(package)
                    if spec is None:
                        raise ImportError(
                            f"Failed to locate {package} after installation in {lib_path}"
                        )

                    logger.info(f"[DEP] {package} installed and found. Importing...")
                    module = importlib.import_module(package)

            # Step 6: Save to globals
            if package == "RPi.GPIO":
                globals()["GPIO"] = module
                logger.info(f"[DEP] {package} imported as GPIO")
            else:
                globals()[package] = module
                logger.info(f"[DEP] {package} imported as {package}")

        except Exception as e:
            logger.error(f"[DEP] Fatal error with {package}: {e}", exc_info=True)
            raise  # Re‑raise to prevent silent failure
