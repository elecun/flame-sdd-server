'''
Surface Defect Detector with Qt GUI
@auhtor Byunghun Hwang<bh.hwnag@iae.re.kr>
'''

import sys, os
import pathlib
import json

try:
    from PyQt5.QtWidgets import QApplication
except ImportError:
    from PyQt6.QtWidgets import QApplication

import argparse

# root directory registration on system environment
ROOT_PATH = pathlib.Path(__file__).parent.parent
APP_NAME = pathlib.Path(__file__).stem
sys.path.append(ROOT_PATH.as_posix())

from surface_defect_monitor.window import AppWindow
from util.logger.console import ConsoleLogger


if __name__ == "__main__":
    
    console = ConsoleLogger.get_logger()

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', nargs='?', required=True, help="Configuration File(*.cfg)", default="default.cfg")
    parser.add_argument('--verbose', nargs='?', required=False, help="Enable/Disable verbose", default=True)
    args = parser.parse_args()

    app = None
    try:
        with open(args.config, "r") as cfile:
            configure = json.load(cfile)

            configure["root_path"] = ROOT_PATH
            configure["app_path"] = (pathlib.Path(__file__).parent / APP_NAME)
            configure["verbose"] = args.verbose
            video_out_dir = (ROOT_PATH / configure["video_out_path"])

            if args.verbose:
                console.info(f"Root Directory : {configure['root_path']}")
                console.info(f"Application Directory : {configure['app_path']}")
                console.info(f"Video Out Directory : {video_out_dir}")

            # check required parameters
            if not all(key in configure for key in ["sdd_model", "sdd_model_name", "camera_id", "camera_fps", "camera_width", "camera_height", "video_extension", "image_extension"]):
                raise Exception(f"some parameters does not set in the {args.config}configuration file")

            app = QApplication(sys.argv)
            app_window = AppWindow(config=configure)
            
            if "app_window_title" in configure:
                app_window.setWindowTitle(configure["app_window_title"])
            app_window.show()
            sys.exit(app.exec())

    except json.JSONDecodeError as e:
        console.critical(f"Configuration File Load Error : {e}")
    except Exception as e:
        console.critical(f"{e}")
        
    
        
    