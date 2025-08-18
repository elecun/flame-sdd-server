import os
import glob
import re
import csv
import cv2
import numpy as np
import torch
import torch.nn as nn
import pytorch_ssim
from multiprocessing import Process, Queue, Value, cpu_count
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import time
from xgboost import XGBClassifier

# ===== NEW: onnxruntime =====
try:
    import onnxruntime as ort
except Exception as e:
    ort = None

# =========================
# Index range per camera (inclusive)
# =========================
IDX_FROM = 0
IDX_TO   = 9999

# =========================
# Global config (diff ¡æ mask ÀÏ°ü·ÎÁ÷)
# =========================
DIFF_THRESHOLD    = 70
MIN_AREA          = 100
USE_OPENING       = True
OPEN_KERNEL_SIZE  = (100, 1)
USE_PERCENTILE    = False
PERCENTILE_P      = 95
MIN_THRESH_FLOOR  = 50

USE_HIGHPASS      = False
HP_SIGMA          = 21

# =========================
# °øÅë Â÷¿µ»ó ¡æ ¸¶½ºÅ© ÇÔ¼ö (´ÜÀÏ ¼Ò½º)
# =========================
def diff_to_mask(orig_u8, recon_u8, *,
                 use_percentile=USE_PERCENTILE, percentile_p=PERCENTILE_P,
                 fixed_thr=DIFF_THRESHOLD, opening=USE_OPENING, open_kernel_size=OPEN_KERNEL_SIZE,
                 min_area=None, out_255=True,
                 highpass=USE_HIGHPASS, hp_sigma=HP_SIGMA):
    img_o = orig_u8.astype(np.float32)
    img_r = recon_u8.astype(np.float32)

    if highpass:
        blur_o = cv2.GaussianBlur(img_o, (0, 0), hp_sigma)
        blur_r = cv2.GaussianBlur(img_r, (0, 0), hp_sigma)
        img_o = cv2.addWeighted(img_o, 1.0, blur_o, -1.0, 0)
        img_r = cv2.addWeighted(img_r, 1.0, blur_r, -1.0, 0)

    diff = np.abs(img_o - img_r).astype(np.uint8)

    thr = max(int(np.percentile(diff, percentile_p)), MIN_THRESH_FLOOR) if use_percentile else fixed_thr
    _, mask = cv2.threshold(diff, thr, 255, cv2.THRESH_BINARY)

    if opening:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, open_kernel_size)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k, iterations=1)

    if min_area is not None:
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        clean = np.zeros_like(mask, dtype=np.uint8)
        for i in range(1, num_labels):
            if stats[i, cv2.CC_STAT_AREA] >= min_area:
                clean[labels == i] = 255
        mask = clean

    return mask if out_255 else (mask > 0).astype(np.uint8)

def diff_to_binary(orig_u8, recon_u8):
    return diff_to_mask(orig_u8, recon_u8, min_area=None, out_255=True)

# =========================
# Ä«¸Þ¶ó ±×·ì/¸ðµ¨  (¡Ú ONNX ÆÄÀÏ °æ·Î·Î ¹Ù²ãÁÖ¼¼¿ä)
# =========================
camera_groups = {
    "group_1_10_5_6_part1": {"model": "vae_group_1_10_5_6.onnx", "cams": [1, 5],  "gpu": 0},
    "group_1_10_5_6_part2": {"model": "vae_group_1_10_5_6.onnx", "cams": [6, 10], "gpu": 0},
    "group_2_9_4_7_part1":  {"model": "vae_group_2_9_4_7.onnx",  "cams": [2, 4],  "gpu": 1},
    "group_2_9_4_7_part2":  {"model": "vae_group_2_9_4_7.onnx",  "cams": [7, 9],  "gpu": 1},
    "group_3_8":            {"model": "vae_group_3_8.onnx",      "cams": [3, 8],  "gpu": 0},
}

# =========================
# XGBoost ·Î´õ
# =========================
xgb_model = XGBClassifier()
xgb_model.load_model("xgboost_model.json")

# =========================
# (ÀÌÀü PyTorch VAE Á¤ÀÇ/·Îµå´Â »ç¿ë ¾È ÇÔ) ONNX ¼¼¼Ç ·Î´õ
# =========================
def load_vae_from_onnx(onnx_path: str, gpu_id: int):
    assert ort is not None, "onnxruntime°¡ ¼³Ä¡µÇ¾î ÀÖÁö ¾Ê½À´Ï´Ù. (pip install onnxruntime-gpu ¶Ç´Â onnxruntime)"
    providers = []
    # CUDA °¡´ÉÇÏ¸é ¿ì¼± »ç¿ë
    if torch.cuda.is_available():
        providers.append(('CUDAExecutionProvider', {'device_id': gpu_id}))
    providers.append('CPUExecutionProvider')
    sess = ort.InferenceSession(onnx_path, providers=providers)
    in_name = sess.get_inputs()[0].name
    out_name = sess.get_outputs()[0].name
    return sess, in_name, out_name

# =========================
# Metrics (torch »ç¿ë)
# =========================
def compute_mae(orig, recon):
    return torch.mean(torch.abs(orig - recon)).item()

def compute_ssim(orig4d, recon4d):
    return pytorch_ssim.ssim(orig4d, recon4d).item()

def _make_sobel(device):
    sobel_x = torch.tensor([[-1, 0, 1],
                            [-2, 0, 2],
                            [-1, 0, 1]], dtype=torch.float32, device=device).view(1,1,3,3)
    sobel_y = torch.tensor([[-1, -2, -1],
                            [ 0,  0,  0],
                            [ 1,  2,  1]], dtype=torch.float32, device=device).view(1,1,3,3)
    return sobel_x, sobel_y

def compute_grad_mae(orig4d, recon4d, sobel_x, sobel_y):
    gox = torch.nn.functional.conv2d(orig4d, sobel_x, padding=1)
    goy = torch.nn.functional.conv2d(orig4d, sobel_y, padding=1)
    grx = torch.nn.functional.conv2d(recon4d, sobel_x, padding=1)
    gry = torch.nn.functional.conv2d(recon4d, sobel_y, padding=1)
    grad_orig = torch.sqrt(gox**2 + goy**2 + 1e-12)
    grad_recon = torch.sqrt(grx**2 + gry**2 + 1e-12)
    return torch.mean(torch.abs(grad_orig - grad_recon)).item()

def compute_laplacian_variance_diff_torch(orig2d_t: torch.Tensor, recon2d_t: torch.Tensor):
    device = orig2d_t.device
    lap_k = torch.tensor([[0, 1, 0],
                          [1,-4, 1],
                          [0, 1, 0]], dtype=torch.float32, device=device).view(1,1,3,3)
    o = torch.nn.functional.conv2d(orig2d_t.view(1,1,*orig2d_t.shape), lap_k, padding=1)
    r = torch.nn.functional.conv2d(recon2d_t.view(1,1,*recon2d_t.shape), lap_k, padding=1)
    var_o = torch.var(o)
    var_r = torch.var(r)
    return float(torch.abs(var_o - var_r).item())

def compute_pixel_sum(orig2d_u8, recon2d_u8):
    mask01 = diff_to_mask(orig2d_u8, recon2d_u8, min_area=MIN_AREA, out_255=False)
    return int(mask01.sum())

# =========================
# pth ¼¼¼Ç ¡æ ONNX ¼¼¼Ç (ÀÌ¸§¸¸ À¯Áö È£È¯)
# =========================
def create_session_pth(onnx_path, gpu_id, in_h=300, in_w=480):
    device = torch.device(f"cuda:{gpu_id}" if torch.cuda.is_available() else "cpu")
    sess, in_name, out_name = load_vae_from_onnx(onnx_path, gpu_id)
    return (sess, in_name, out_name), device, in_h, in_w

# =========================
# ÆÄÀÏ¸í¿¡¼­ index ÃßÃâ
# =========================
def extract_idx_from_filename(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    parts = stem.split('_')
    if len(parts) >= 2 and parts[-1].isdigit():
        return int(parts[-1])
    m = re.match(r'^\D*?(\d+)\D+(\d+)\D*$', stem)
    if m:
        return int(m.group(2))
    return None

# =========================
# ¿öÄ¿
# =========================
def infer_worker(cams, model_path, gpu_id, input_root, result_queue, output_csv, save_visual, progress, total):
    # metrics¿ë torch µð¹ÙÀÌ½º
    if torch.cuda.is_available():
        torch.cuda.set_device(gpu_id)
    (sess, in_name, out_name), device, in_h, in_w = create_session_pth(model_path, gpu_id, in_h=300, in_w=480)
    sobel_x, sobel_y = _make_sobel(device)

    image_tasks = []
    for cam_id in cams:
        cam_folder = os.path.join(input_root, f"camera_{cam_id}")
        files = []
        for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG', '*.png', '*.PNG'):
            files.extend(glob.glob(os.path.join(cam_folder, ext)))

        selected = []
        for p in files:
            idx = extract_idx_from_filename(p)
            if idx is None:
                continue
            if IDX_FROM <= idx <= IDX_TO:
                selected.append((idx, p))

        selected.sort(key=lambda x: x[0])
        image_tasks.extend([(cam_id, p) for _, p in selected])

    with ThreadPoolExecutor(max_workers=min(cpu_count(), 8)) as executor:
        futures = []
        for cam_id, img_path in image_tasks:
            futures.append(executor.submit(
                process_image,
                (sess, in_name, out_name), device, cam_id, img_path, result_queue, output_csv, save_visual,
                sobel_x, sobel_y, in_h, in_w, progress
            ))
        for f in futures:
            f.result()

    result_queue.put(None)

def process_image(sess_pack, device, cam_id, img_path, result_queue, output_csv, save_visual,
                  sobel_x, sobel_y, in_h, in_w, progress):
    try:
        sess, in_name, out_name = sess_pack
        img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise RuntimeError("Failed to read image")

        if cam_id in [6, 7, 8, 9, 10]:
            img = cv2.flip(img, 1)

        img = cv2.resize(img, (in_w, in_h)).astype(np.float32) / 255.0

        # ===== ONNX Ãß·Ð =====
        onnx_in = img[np.newaxis, np.newaxis, :, :]  # (1,1,H,W), float32
        onnx_out = sess.run([out_name], {in_name: onnx_in})[0]  # (1,1,H,W)

        # torch ÅÙ¼­·Î º¯È¯(¸ÞÆ®¸¯ °è»ê¿ë)
        recon = torch.from_numpy(onnx_out).to(device=device, dtype=torch.float32)  # (1,1,H,W)
        recon2d = recon[0, 0]
        orig_t = torch.from_numpy(img).to(device=device, dtype=torch.float32)      # (H,W)

        # Metrics
        mae = compute_mae(orig_t, recon2d)
        ssim = compute_ssim(orig_t[None, None], recon2d[None, None])
        grad_mae = compute_grad_mae(orig_t[None, None], recon2d[None, None], sobel_x, sobel_y)
        lap_diff = compute_laplacian_variance_diff_torch(orig_t, recon2d)

        orig_u8  = (orig_t.detach().cpu().numpy()  * 255).astype(np.uint8)
        recon_u8 = (recon2d.detach().cpu().numpy() * 255).astype(np.uint8)
        pix_sum = compute_pixel_sum(orig_u8, recon_u8)

        # XGBoost ¿¹Ãø (+ ÇÈ¼¿ÇÕ 0ÀÌ¸é ¹«Á¶°Ç ¾çÇ°)
        xgb_input = np.array([[mae, ssim, grad_mae, lap_diff, pix_sum]], dtype=np.float32)
        result = int(xgb_model.predict(xgb_input)[0])
        if pix_sum == 0:
            result = 0

        result_queue.put([
            os.path.basename(img_path),
            mae, ssim, grad_mae, lap_diff, pix_sum, result
        ])

    except Exception:
        result_queue.put([
            os.path.basename(img_path) if img_path else "unknown",
            np.nan, np.nan, np.nan, np.nan, np.nan, -1
        ])
    finally:
        with progress.get_lock():
            progress.value += 1

        if save_visual and 'orig_u8' in locals() and 'recon_u8' in locals():
            try:
                mask255 = diff_to_mask(orig_u8, recon_u8, min_area=None, out_255=True)
                orig_v   = cv2.rotate(orig_u8,  cv2.ROTATE_90_CLOCKWISE)
                recon_v  = cv2.rotate(recon_u8, cv2.ROTATE_90_CLOCKWISE)
                binary_v = cv2.rotate(mask255,  cv2.ROTATE_90_CLOCKWISE)
                combined = cv2.hconcat([
                    cv2.cvtColor(orig_v,  cv2.COLOR_GRAY2BGR),
                    cv2.cvtColor(recon_v, cv2.COLOR_GRAY2BGR),
                    cv2.cvtColor(binary_v, cv2.COLOR_GRAY2BGR),
                ])
                vis_out_dir = os.path.join(os.path.dirname(output_csv), f"visual/camera_{cam_id}")
                os.makedirs(vis_out_dir, exist_ok=True)
                cv2.imwrite(os.path.join(vis_out_dir, os.path.basename(img_path)), combined)
            except Exception:
                pass

# =========================
# ¸ÞÀÎ
# =========================
def run_parallel_inference(input_root, output_csv, save_visual):
    start_time = time.time()

    processes = []
    result_queue = Queue()
    total_images = 0

    for config in camera_groups.values():
        for cam_id in config['cams']:
            cam_folder = os.path.join(input_root, f"camera_{cam_id}")
            for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG', '*.png', '*.PNG'):
                total_images += len(glob.glob(os.path.join(cam_folder, ext)))

    progress = Value('i', 0)
    pbar = tqdm(total=total_images, desc="Total Progress", position=0)

    for config in camera_groups.values():
        p = Process(
            target=infer_worker,
            args=(config['cams'], config['model'], config['gpu'], input_root,
                  result_queue, output_csv, save_visual, progress, total_images)
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

# =========================
# Entrypoint
# =========================
if __name__ == '__main__':
    import argparse
    import multiprocessing as mp
    mp.set_start_method('spawn', force=True)
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, required=False, help='Input root folder containing camera_* folders')
    parser.add_argument('--output', type=str, required=False, help='Output CSV path')
    parser.add_argument('--visualize', action='store_true', help='Save visual comparison images')
    args = parser.parse_args()
    #run_parallel_inference(args.input, args.output, args.visualize)
    run_parallel_inference('/home/dk-sdd/nas_storage/20250804/20250804095454_200x200/', './test_old_result_200x200/result.csv', args.visualize)