
import os
import glob
import csv
import cv2
import numpy as np
import torch
import pytorch_ssim
from multiprocessing import Process, Queue, Value, cpu_count
from concurrent.futures import ThreadPoolExecutor
import onnxruntime as ort
from tqdm import tqdm
import time
from xgboost import XGBClassifier

# ✅ 사전 학습된 XGBoost 모델 로딩
xgb_model = XGBClassifier()
xgb_model.load_model("xgboost_model.json")  # 경로 조정 가능

camera_groups = {
    "vae_group_1_10_5_6.onnx_part1": {"model": "vae_group_1_10_5_6.onnx", "cams": [1, 5], "gpu": 0},
    "vae_group_1_10_5_6.onnx_part2": {"model": "vae_group_1_10_5_6.onnx", "cams": [6, 10], "gpu": 0},
    "vae_group_2_9_4_7.onnx_part1": {"model": "vae_group_2_9_4_7.onnx", "cams": [2, 4], "gpu": 1},
    "vae_group_2_9_4_7.onnx_part2": {"model": "vae_group_2_9_4_7.onnx", "cams": [7, 9], "gpu": 1},
    "vae_group_3_8.onnx": {"model": "vae_group_3_8.onnx", "cams": [3, 8], "gpu": 0}
}

def compute_mae(orig, recon):
    return torch.mean(torch.abs(orig - recon)).item()

def compute_ssim(orig, recon):
    return pytorch_ssim.ssim(orig, recon).item()

def compute_grad_mae(orig, recon):
    sobel_x = torch.tensor([[[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]], dtype=torch.float32, device=orig.device).unsqueeze(0)
    sobel_y = torch.tensor([[[-1, -2, -1], [0, 0, 0], [1, 2, 1]]], dtype=torch.float32, device=orig.device).unsqueeze(0)
    grad_orig = torch.sqrt(
        torch.nn.functional.conv2d(orig, sobel_x, padding=1)**2 +
        torch.nn.functional.conv2d(orig, sobel_y, padding=1)**2
    )
    grad_recon = torch.sqrt(
        torch.nn.functional.conv2d(recon, sobel_x, padding=1)**2 +
        torch.nn.functional.conv2d(recon, sobel_y, padding=1)**2
    )
    return torch.mean(torch.abs(grad_orig - grad_recon)).item()

def compute_laplacian_variance_diff(orig, recon):
    var_orig = np.var(cv2.Laplacian(orig.cpu().numpy().astype(np.float64), cv2.CV_64F))
    var_recon = np.var(cv2.Laplacian(recon.cpu().numpy().astype(np.float64), cv2.CV_64F))
    return abs(var_orig - var_recon)

def compute_pixel_sum(orig, recon):
    diff = torch.abs(orig - recon) * 255
    binary = (diff > 30).int()
    return binary.sum().item()

def create_session(model_path, gpu_id):
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(model_path, sess_options=so, providers=[("CUDAExecutionProvider", {"device_id": gpu_id})])

def infer_worker(cams, model_path, gpu_id, input_root, result_queue, output_csv, save_visual, progress, total):
    session = create_session(model_path, gpu_id)
    input_name = session.get_inputs()[0].name

    image_tasks = []
    for cam_id in cams:
        cam_folder = os.path.join(input_root, f"camera_{cam_id}")
        for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
            image_tasks.extend([(cam_id, img_path) for img_path in glob.glob(os.path.join(cam_folder, ext))])

    with ThreadPoolExecutor(max_workers=min(cpu_count(), 8)) as executor:
        futures = []
        for cam_id, img_path in image_tasks:
            futures.append(executor.submit(process_image, session, input_name, cam_id, img_path, result_queue, output_csv, save_visual, progress))
        for f in futures:
            f.result()

    result_queue.put(None)

def process_image(session, input_name, cam_id, img_path, result_queue, output_csv, save_visual, progress):
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if cam_id in [6, 7, 8, 9, 10]:
        img = cv2.flip(img, 1)
    img = cv2.resize(img, (480, 300)).astype(np.float32) / 255.0
    img_tensor = torch.tensor(img).unsqueeze(0).unsqueeze(0).to('cuda')

    output = session.run(None, {input_name: img_tensor.cpu().numpy()})[0]
    recon = torch.tensor(output[0, 0]).to('cuda')
    orig = img_tensor[0, 0].to(recon.device)

    mae = compute_mae(orig, recon)
    ssim = compute_ssim(orig.unsqueeze(0).unsqueeze(0), recon.unsqueeze(0).unsqueeze(0))
    grad_mae = compute_grad_mae(orig.unsqueeze(0).unsqueeze(0), recon.unsqueeze(0).unsqueeze(0))
    lap_diff = compute_laplacian_variance_diff(orig, recon)
    pix_sum = compute_pixel_sum(orig, recon)

    # ✅ XGBoost로 예측
    xgb_input = np.array([[mae, ssim, grad_mae, lap_diff, pix_sum]])
    result = int(xgb_model.predict(xgb_input)[0])

    result_queue.put([
        os.path.basename(img_path),
        mae, ssim, grad_mae, lap_diff, pix_sum, result
    ])

    with progress.get_lock():
        progress.value += 1

    if save_visual:
        orig_img = (orig.cpu().numpy() * 255).astype(np.uint8)
        recon_img = (recon.cpu().numpy() * 255).astype(np.uint8)
        diff_img = np.abs(orig_img.astype(np.int16) - recon_img.astype(np.int16)).astype(np.uint8)
        _, binary_diff = cv2.threshold(diff_img, 30, 255, cv2.THRESH_BINARY)
        orig_img = cv2.rotate(orig_img, cv2.ROTATE_90_CLOCKWISE)
        recon_img = cv2.rotate(recon_img, cv2.ROTATE_90_CLOCKWISE)
        binary_diff = cv2.rotate(binary_diff, cv2.ROTATE_90_CLOCKWISE)
        combined = cv2.hconcat([
            cv2.cvtColor(orig_img, cv2.COLOR_GRAY2BGR),
            cv2.cvtColor(recon_img, cv2.COLOR_GRAY2BGR),
            cv2.cvtColor(binary_diff, cv2.COLOR_GRAY2BGR)
        ])
        vis_out_dir = os.path.join(os.path.dirname(output_csv), f"visual/camera_{cam_id}")
        os.makedirs(vis_out_dir, exist_ok=True)
        cv2.imwrite(os.path.join(vis_out_dir, os.path.basename(img_path)), combined)

def run_parallel_inference(input_root, output_csv, save_visual):
    start_time = time.time()

    processes = []
    result_queue = Queue()
    total_images = 0

    for config in camera_groups.values():
        for cam_id in config['cams']:
            cam_folder = os.path.join(input_root, f"camera_{cam_id}")
            for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
                total_images += len(glob.glob(os.path.join(cam_folder, ext)))

    progress = Value('i', 0)
    pbar = tqdm(total=total_images, desc="Total Progress", position=0)

    for config in camera_groups.values():
        p = Process(
            target=infer_worker,
            args=(config['cams'], config['model'], config['gpu'], input_root, result_queue, output_csv, save_visual, progress, total_images)
        )
        processes.append(p)
        p.start()

    end_signals = 0
    results = [['filename', 'MAE', 'SSIM', 'Grad_MAE', 'Laplacian_Diff', 'Pixel_Sum', 'result']]
    while end_signals < len(processes):
        item = result_queue.get()
        if item is None:
            end_signals += 1
        else:
            results.append(item)
            pbar.n = progress.value
            pbar.refresh()

    for p in processes:
        p.join()

    result_queue.close()
    result_queue.join_thread()

    pbar.close()

    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(results)

    elapsed = time.time() - start_time
    print(f"\nTotal Inference Time: {elapsed:.2f} seconds")

if __name__ == '__main__':
    import argparse
    import multiprocessing as mp
    mp.set_start_method('spawn', force=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, required=True, help='Input root folder containing camera_* folders')
    parser.add_argument('--output', type=str, required=True, help='Output CSV path')
    parser.add_argument('--visualize', action='store_true', help='Save visual comparison images')
    args = parser.parse_args()

    print("All modules loaded. Type 'yes' or press ENTER to begin inference...")
    user_input = input().strip()
    if user_input == '' or user_input.lower() == 'yes':
        run_parallel_inference(args.input, args.output, args.visualize)
    else:
        print("Aborted by user.")
