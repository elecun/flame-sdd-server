'''
High resolution image split into lower resolution
@author Byunghun Hwang<bh.hwang@iae.re.kr>
'''

import cv2
import os
import pathlib
from tqdm import tqdm

# Image Splitting
def _split_image(img_from:str, save_to:str, rows:int, cols:int) -> None:
    
    try:
        if os.path.isfile(img_from):
            # create dirs
            os.makedirs(save_to, exist_ok=True)
            
            _img_from = pathlib.Path(img_from)
            _save_to = pathlib.Path(save_to)
            
            # image split
            image = cv2.imread(img_from)
            
            x = image.shape[1] # width
            y = image.shape[0] # height
            for i in range(0, rows):
                for j in range(0, cols):
                    roi = image[int(i*y/rows):int(i*y/rows+y/rows) ,int(j*x/cols):int(j*x/cols+x/cols)]
                    cv2.imwrite((_save_to/_img_from.name).as_posix(), roi)
        else:
            raise Exception(f"{img_from} does not exist")
    except Exception as e:
        print(f"{e}")

# Image Splitting from Directory
def _split_image_dir(img_dir:str, save_to:str, rows:int, cols:int) ->None:
    try:
        if os.path.exists(img_dir):
            # create dirs
            os.makedirs(save_to, exist_ok=True)
            
            _img_from = pathlib.Path(img_dir)
            _save_to = pathlib.Path(save_to)
            
            # list-up images from _img_from
            image_files = os.listdir(_img_from.as_posix())
            
            # image split
            for idx, f in tqdm(enumerate(image_files)):
                image = cv2.imread((_img_from / f).as_posix())
                
                x = image.shape[1] # width
                y = image.shape[0] # height
                for i in range(0, rows):
                    for j in range(0, cols):
                        roi = image[int(i*y/rows):int(i*y/rows+y/rows) ,int(j*x/cols):int(j*x/cols+x/cols)]
                        cv2.imwrite((_save_to / f"{pathlib.Path(f).stem}_{i}{j}.png").as_posix(), roi)
        else:
            raise Exception(f"{img_dir} does not exist")
    except Exception as e:
        print(f"{e}")