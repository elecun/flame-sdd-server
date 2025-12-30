
import csv
import re
import tempfile


class DummyConsole:
    def info(self, message: str):
        print(message)

    def error(self, message: str):
        print(message)


class DummyWorker:
    def __init__(self):
        self.__dict__["__console"] = DummyConsole()


def copy_defect_images_regex(self, output_csv: str, date: str, width: int, height: int, mt_no: str, mt_stand_raw: str) -> int:
    def normalize_mt_stand(value: str) -> str:
        if not value:
            return ""
        raw = re.sub(r"\s+", " ", value.strip())
        if not raw:
            return ""

        if re.search(r"[xX]", raw) is None:
            return raw.replace(" ", "").replace("/", "_")

        parts = re.split(r"\s*[xX]\s*", raw)
        if not parts:
            return raw.replace(" ", "").replace("/", "_")

        first = parts[0].strip()
        rest = [p.strip() for p in parts[1:] if p.strip()]

        match = re.match(r"^([A-Za-z]+)\s*([0-9].*)$", first)
        if match:
            prefix = match.group(1)
            first_dim = match.group(2).strip()
        else:
            prefix = ""
            first_dim = first.replace(" ", "")

        dims = [first_dim] + rest
        if prefix.upper() == "H" and len(dims) >= 2:
            dims = dims[:2]

        joined = "x".join(d.replace(" ", "") for d in dims)
        normalized = f"{prefix}{joined}" if prefix else joined
        return normalized.replace("/", "_").replace(" ", "")

    copy_tasks = []
    n_copied = 0
    mt_stand = normalize_mt_stand(mt_stand_raw)
    # if not mt_stand:
    #     mt_stand = f"H{width}X{height}"
    #     self.__console.info(f"*** mt_stand_raw is empty, defaulting mt_stand to '{mt_stand}'")

    # for test only
    image_filename = f"1_1.jpg".strip()[:-4]
    camera_id = image_filename.split("_")[0]
    new_filename = f"{date}_{mt_stand}_{mt_no}_{image_filename}_x.jpg"
    src = f"/volume1/sdd/{date[0:8]}/{date}_{width}x{height}/camera_{camera_id}/{image_filename}_x.jpg"
    dst = f"/volume1/sdd/defect_images/{new_filename}"
    self.__console.info(f"mt_stand_raw -> mt_stand: '{mt_stand_raw}' -> '{mt_stand}'")
    # self.__console.info(f"new_filename: {new_filename}")
    #self.__console.info(f"copy_task: src='{src}', dst='{dst}'")

    # try:
    #     # Read CSV and gather tasks
    #     with open(output_csv, "r", newline="") as csvfile:
    #         reader = csv.reader(csvfile)
    #         next(reader)  # Skip header
    #         for row in reader:
    #             if len(row) > 0 and row[-1].strip() == "1":  # if defect
    #                 image_filename = row[0].strip()[:-4]  # remove file extension (.jpg)
    #                 camera_id = image_filename.split("_")[0]
    #                 new_filename = f"{date}_{mt_stand}_{mt_no}_{image_filename}_x.jpg"
    #                 src = f"/volume1/sdd/{date[0:8]}/{date}_{width}x{height}/camera_{camera_id}/{image_filename}_x.jpg"
    #                 dst = f"/volume1/sdd/defect_images/{new_filename}"
    #                 self.__console.info(f"mt_stand_raw -> mt_stand: '{mt_stand_raw}' -> '{mt_stand}'")
    #                 self.__console.info(f"new_filename: {new_filename}")
    #                 self.__console.info(f"copy_task: src='{src}', dst='{dst}'")

    #                 copy_tasks.append({"src": src, "dst": dst})

    #     if not copy_tasks:
    #         self.__console.info("No defect images to copy")
    #         return 0

        # SSH connection parameters (keep same behavior as before)
        # host = "192.168.1.52"
        # user = "dksteel"
        # password = "Ehdrnrwprkd1"
        #
        # Allow configurable number of persistent SSH sessions; default to 4
        # pool_size = max(1, min(8, len(copy_tasks)))
        #
        # Prepare a thread-safe queue of tasks
        # task_q = queue.Queue()
        # for t in copy_tasks:
        #     task_q.put(t)
        #
        # lock = threading.Lock()
        #
        # def make_client():
        #     client = paramiko.SSHClient()
        #     client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        #     client.connect(
        #         hostname=host,
        #         username=user,
        #         password=password,
        #         look_for_keys=False,
        #         allow_agent=False,
        #         timeout=10,
        #     )
        #     return client
        #
        # def worker_thread():
        #     nonlocal n_copied
        #     client = None
        #     try:
        #         client = make_client()
        #     except Exception as e:
        #         self.__console.error(f"Failed to create SSH client: {e}")
        #         return
        #
        #     while True:
        #         try:
        #             task = task_q.get_nowait()
        #         except Exception:
        #             break
        #
        #         src = task["src"]
        #         dst = task["dst"]
        #         cmd = f"cp {src} {dst}"
        #         try:
        #             stdin, stdout, stderr = client.exec_command(cmd)
        #             exit_status = stdout.channel.recv_exit_status()
        #             if exit_status == 0:
        #                 with lock:
        #                     n_copied += 1
        #             else:
        #                 err = stderr.read().decode(errors="ignore")
        #                 self.__console.error(f"Remote cp failed ({exit_status}): {cmd} -> {err}")
        #         except Exception as e:
        #             self.__console.error(f"SSH exec error for {src} -> {dst}: {e}")
        #         finally:
        #             task_q.task_done()
        #
        #     try:
        #         client.close()
        #     except Exception:
        #         pass
        #
        # Start worker threads (each maintains its own SSH session)
        # threads = []
        # for _ in range(pool_size):
        #     t = threading.Thread(target=worker_thread, daemon=True)
        #     threads.append(t)
        #     t.start()
        #
        # Wait for all tasks to be processed
        # for t in threads:
        #     t.join()

    # except FileNotFoundError:
    #     self.__console.error(f"File not found: {output_csv}")
    #     return 0
    # except Exception as e:
    #     self.__console.error(f"Error processing {output_csv}: {e}")
    #     return 0

    #self.__console.info(f"Copied {n_copied} defect image(s) to NAS defect_images folder")
    return n_copied


if __name__ == "__main__":
    mt_stand_raw_list = [
        "H 194 x 150 x 6/9    ",
        "H 200 x 200 x 8/12   ",
        "H 200 x 204 x 12/12",
        "H 208 x 202 x 10/16",
        "H 244 x 175 x 7/11",
        "H 244 x 252 x 11/11",
        "H 248 x 249 x 8/13",
        "H 250 x 250 x 9/14",
        "H 250 x 255 x 14/14",
        "H 298 x 149 x 5.5/8",
        "H 300 x 150 x 6.5/9",
        "H 294 x 200 x 8/12",
        "H 298 x 201 x 9/14",
        "H 294 x 302 x 12/12",
        "H 298 x 299 x 9/14",
        "H 300 x 300 x 10/15",
        "H 300 x 305 x 15/15",
        "H 304 x 301 x 11/17",
        "H 310 x 305 x 15/20",
        "H 310 x 310 x 20/20",
        "H 346 x 174 x 6/9",
        "H 350 x 175 x 7/11",
        "H 354 x 176 x 8/13",
        "H 336 x 249 x 8/12",
        "H 340 x 250 x 9/14",
        "H 344 x 348 x 10/16",
        "H 344 x 354 x 16/16",
        "H 350 x 350 x 12/19",
        "H 350 x 357 x 19/19",
        "H 396 x 199 x 7/11",
        "H 400 x 200 x 8/13",
        "H 404 x 201 x 9/15",
        "H 386 x 299 x 9/14",
        "H 390 x 300 x 10/16",
        "H 388 x 402 x 15/15",
        "H 394 x 398 x 11/18",
        "H 394 x 405 x 18/18",
        "H 400 x 400 x 13/21",
        "H 400 x 408 x 21/21",
        "H 406 x 403 x 16/24",
        "H 414 x 405 x 18/28",
        "H 428 x 407 x 20/35",
        "H 458 x 417 x 30/50",
        "H 498 x 432 x 45/70",
        "H 446 x 199 x 8/12",
        "H 450 x 200 x 9/14",
        "H 434 x 299 x 10/15",
        "H 440 x 300 x 11/18",
        "H 496 x 199 x 9/14",
        "H 500 x 200 x 10/16",
        "H 506 x 201 x 11/19",
        "H 482 x 300 x 11/15",
        "H 488 x 300 x 11/18",
        "H 596 x 199 x 10/15",
        "H 600 x 200 x 11/17",
        "H 606 x 201 x 12/20",
        "H 612 x 202 x 13/23",
        "H 582 x 300 x 12/17",
        "H 582 x 300 x 12/17",
        "H 588 x 300 x 12/20",
        "H 594 x 302 x 14/23",
        "H 692 x 300 x 13/20",
        "H 700 x 300 x 13/24",
        "H 708 x 302 x 15/28",
        "W 8 x 31",
        "W 8 x 35",
        "W 8 x 40",
        "W 8 x 48",
        "W 8 x 58",
        "W 10 x 49",
        "W 10 x 60",
        "W 10 x 68",
        "W 10 x 77",
        "W 10 x 88",
        "W 10 x 100",
        "W 12 x 65",
        "W 12 x 72",
        "W 12 x 72",
        "W 12 x 79",
        "W 12 x 87",
        "W 12 x 96",
        "W 12 x 106",
        "W 12 x 120",
        "W 12 x 136",
        "W 12 x 8 x 40",
        "W 12 x 8 x 45",
        "W 12 x 8 x 50",
        "W 14 x 6-3/4 x 30",
        "W 14 x 6-3/4 x 34",
        "W 14 x 6-3/4 x 38",
        "W 14 x 14-1/2 x 90",
        "W 14 x 14-1/2 x 99",
        "W 14 x 14-1/2 x 109",
        "W 14 x 14-1/2 x 120",
        "HP 14 x 73",
        "HP 14 x 89",
        "HP 14 x 102",
        "HP 14 x 117",
        "HP 14 x 117",
        "W 14 x 14-1/2 x 132",
        "UB 203 x 133 x 25",
        "UB 203 x 133 x 30",
        "UB 356 x 171 x 45",
        "UB 356 x 171 x 51",
        "UB 356 x 171 x 57",
        "UB 356 x 171 x 67",
        "UC 356 x 368 x 129",
        "UC 356 x 368 x 153",
        "UC 356 x 368 x 177",
        "UC 203 x 203 x 46",
        "UC 203 x 203 x 52",
        "UC 203 x 203 x 60",
        "UC 203 x 203 x 71",
        "UC 203 x 203 x 86",
        "UC 254 x 254 x 73",
        "UC 254 x 254 x 89",
        "UC 254 x 254 x 107",
        "UC 254 x 254 x 132",
        "UC 305 x 305 x 97",
        "UC 305 x 305 x 118",
        "UC 305 x 305 x 137",
        "UC 305 x 305 x 158",
        "200 UB 22.3",
        "200 UB 25.4",
        "200 UB 29.8",
        "200 UC 46.2",
        "200 UC 52.2",
        "200 UC 59.5",
        "250 UB 25.7",
        "250 UC 72.9",
        "250 UC 89.5",
        "310 UB 32.0",
        "310 UB 40.4",
        "310 UB 46.2",
        "310 UC 96.8",
        "310 UC 118.0",
        "310 UC 137.0",
        "310 UC 158.0",
        "360 UB 44.7",
        "360 UB 50.7",
        "360 UB 56.7",
    ]

    dummy = DummyWorker()
    date = "20250804095316"
    width = 200
    height = 200
    mt_no = "MT000"

    with tempfile.NamedTemporaryFile(mode="w", newline="", delete=False) as temp_csv:
        writer = csv.writer(temp_csv)
        writer.writerow(["filename", "mae", "ssim", "grad_mae", "lap_diff", "pix_sum", "result"])
        output_csv = temp_csv.name

    for raw in mt_stand_raw_list:
        copy_defect_images_regex(dummy, output_csv, date, width, height, mt_no, raw)
