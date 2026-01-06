import glob
import shutil


def on_update_label(self, data:dict):
        self.__console.info(f"Update Label : {data}")
        try:
            moved_count = 0
            for id in range(1,16): # 1~15
                key = f"mea_image{id}"
                labeled_name = data.get(key)
                if not labeled_name:
                    continue

                # split filename
                try:
                    timestamp, mt_stand_norm, mt_no, camera_id, image_idx, defect_label = self._parse_labeled_filename(labeled_name)
                except Exception as e:
                    self.__console.error(f"Label parse failed for {key}: {e}")
                    continue
                date = timestamp[:8]  # YYYYMMDD

                src_pattern = f"/volume1/sdd/{date}/{timestamp}_{mt_stand_norm}/camera_{camera_id}/{camera_id}_{image_idx}_*.jpg"
                dst = f"/volume1/sdd/{date}/{timestamp}_{mt_stand_norm}/camera_{camera_id}/{camera_id}_{image_idx}_{defect_label}.jpg"
                matches = sorted(glob.glob(src_pattern))
                if not matches:
                    self.__console.warning(f"No source file for {key}: {src_pattern}")
                    continue
                if len(matches) > 1:
                    self.__console.warning(f"Multiple source files for {key}, using first: {matches[0]}")

                src = matches[0]
                try:
                    shutil.move(src, dst)
                    moved_count += 1
                except Exception as e:
                    self.__console.error(f"Move failed for {key}: {e}")

            if moved_count == 0:
                self.__console.info("No label updates to apply")
            else:
                self.__console.info(f"Label updated for {moved_count} image file(s)")

        except Exception as e:
            self.__console.error(f"DK Level2 Label Update Error: {e}")
