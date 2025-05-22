'''
test
@auhtor Byunghun Hwang<bh.hwnag@iae.re.kr>
'''

import sys, os
import pathlib
import json

# root directory registration on system environment
ROOT_PATH = pathlib.Path(__file__).parent.parent
APP_NAME = pathlib.Path(__file__).stem
sys.path.append(ROOT_PATH.as_posix())


from util.logger.console import ConsoleLogger


if __name__ == "__main__":
    
    console = ConsoleLogger.get_logger()
    configure = {}

    configure["root_path"] = ROOT_PATH
    configure["app_path"] = (pathlib.Path(__file__).parent / APP_NAME)

    console.info("test")
    console.debug("test")
    console.warning("test")
    console.error("test")
    console.critical("test")

    print(configure)
        
    
        
    