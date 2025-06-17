from typing import List, Tuple
import re

def __parse_filename(filename: str) -> Tuple[int, int]:
        match = re.match(r"(\d+)_(\d+)\.preset$", filename)
        if match:
            width, height = map(int, match.groups())
            return width, height
        return None

def __find_nearest_preset(h:int, b:int, filenames:List[str]) -> str:
        min_distance = float('inf')
        nearest_file = None

        for filename in filenames:
            parsed = __parse_filename(filename)
            if parsed:
                width, height = parsed
                distance = (width - h)**2 + (height - b)**2
                if distance < min_distance:
                    min_distance = distance
                    nearest_file = filename

        return nearest_file

files = ["100_100.preset","200_200.preset","250_250.preset", "300_250.preset",
         "300_300.preset", "350_350.preset", "400_200.preset", "400_250.preset", 
         "400_400.preset", "500_200.preset", "600_300.preset", "700_300.preset"]

print(__find_nearest_preset(409,198,files))