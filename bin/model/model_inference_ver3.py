# 병렬 고속화를 위한 ONNX 추론 파이프라인
# 이 코드는 기존 구조를 갈아엎고 멀티 GPU + 멀티 프로세스 + 멀티 스레드 병렬 처리를 갈아넣음
# 핵심 목표: CPU 병목 제거, 디바이스 전송 최소화, 그리고 GPU 노역 강화

import os
import glob
import csv
import cv2
import numpy as np
import torch
import pytorch_ssim
from multiprocessing import Process, Queue, Value, cpu_count  # 병렬 프로세스를 위한 핵심 모듈
from concurrent.futures import ThreadPoolExecutor  # 각 프로세스 안에서 멀티스레드 실행 위함
import onnxruntime as ort
from tqdm import tqdm
import time

# 각 모델이 어떤 카메라 그룹을 담당하는지와 GPU 할당까지 정해놓은 매핑
# 모델 별로 실제로는 같은 파일을 쓰지만, 병렬 분배를 위해 가상의 구간 나눠서 분리 처리함
camera_groups = {
    "vae_group_1_10_5_6.onnx_part1": {"model": "vae_group_1_10_5_6.onnx", "cams": [1, 5], "gpu": 0},
    "vae_group_1_10_5_6.onnx_part2": {"model": "vae_group_1_10_5_6.onnx", "cams": [6, 10], "gpu": 0},
    "vae_group_2_9_4_7.onnx_part1": {"model": "vae_group_2_9_4_7.onnx", "cams": [2, 4], "gpu": 1},
    "vae_group_2_9_4_7.onnx_part2": {"model": "vae_group_2_9_4_7.onnx", "cams": [7, 9], "gpu": 1},
    "vae_group_3_8.onnx": {"model": "vae_group_3_8.onnx", "cams": [3, 8], "gpu": 0}
}

# MAE 계산. 텐서 간 절대값 평균. GPU에서 실행됨
def compute_mae(orig, recon):
    return torch.mean(torch.abs(orig - recon)).item()

# SSIM 계산. pytorch_ssim 사용해서 GPU에서 처리되게 되어 있음
# 시각 품질 평가에서 중요, GPU에게 노역 부여

def compute_ssim(orig, recon):
    return pytorch_ssim.ssim(orig, recon).item()

# 그래디언트 기반 MAE. 경계선 부근 오차 평가용
# Sobel 필터 수동 구현, conv2d로 gradient 뽑아서 MAE 계산

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

# 라플라시안 기반 variance 차이. 시각 품질 및 경계 강조에 민감
# 여긴 GPU보다 OpenCV가 빨랐음. ver3에서 다시 numpy로 내려서 처리

def compute_laplacian_variance_diff(orig, recon):
    var_orig = np.var(cv2.Laplacian(orig.cpu().numpy().astype(np.float64), cv2.CV_64F))
    var_recon = np.var(cv2.Laplacian(recon.cpu().numpy().astype(np.float64), cv2.CV_64F))
    return abs(var_orig - var_recon)

# 픽셀 차이 임계값 넘는 영역 카운트. 이진화된 에러맵 기반

def compute_pixel_sum(orig, recon):
    diff = torch.abs(orig - recon) * 255
    binary = (diff > 30).int()
    return binary.sum().item()

# 로지스틱 회귀 기반 판단 점수. 기계적으로 수동 튜닝된 weight 사용
# 이걸로 최종 OK/NG 판단함 -> 추후 XGBoost로 교체 예정

def logistic_score(metrics):
    mae, ssim, grad_mae, lap_diff, pix_sum = metrics
    score = (
        318.423821 * mae +
        21.601394 * ssim +
        -26.708228 * grad_mae +
        357.830399 * lap_diff +
        -0.000003 * pix_sum +
        -24.372392
    )
    prob = 1 / (1 + np.exp(-score))
    return 1 if prob > 0.5 else 0

# ONNX 세션 초기화. GPU 지정해서 실행될 수 있도록 설정

def create_session(model_path, gpu_id):
    so = ort.SessionOptions()
    so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
    return ort.InferenceSession(model_path, sess_options=so, providers=[("CUDAExecutionProvider", {"device_id": gpu_id})])

# 각 프로세스 단위 병렬 처리 함수. 이 안에서 멀티스레드도 같이 돌림

def infer_worker(cams, model_path, gpu_id, input_root, result_queue, output_csv, save_visual, progress, total):
    session = create_session(model_path, gpu_id)
    input_name = session.get_inputs()[0].name

    # 이미지 경로 수집
    image_tasks = []
    for cam_id in cams:
        cam_folder = os.path.join(input_root, f"camera_{cam_id}")
        for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
            image_tasks.extend([(cam_id, img_path) for img_path in glob.glob(os.path.join(cam_folder, ext))])

    # 이 프로세스 안에서 멀티스레드 돌려서 이미지 개별 처리
    with ThreadPoolExecutor(max_workers=min(cpu_count(), 8)) as executor:
        futures = []
        for cam_id, img_path in image_tasks:
            futures.append(executor.submit(process_image, session, input_name, cam_id, img_path, result_queue, output_csv, save_visual, progress))
        for f in futures:
            f.result()

    result_queue.put(None)  # 처리 끝났다고 알림

# 개별 이미지 처리 함수. 로딩, 추론, 후처리, 결과 전송까지

def process_image(session, input_name, cam_id, img_path, result_queue, output_csv, save_visual, progress):
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if cam_id in [6, 7, 8, 9, 10]:
        img = cv2.flip(img, 1)
    img = cv2.resize(img, (480, 300)).astype(np.float32) / 255.0
    img_tensor = torch.tensor(img).unsqueeze(0).unsqueeze(0).to('cuda')  # GPU 텐서로 올림

    # ONNX는 numpy만 받으므로 다시 CPU 텐서로 전송
    output = session.run(None, {input_name: img_tensor.cpu().numpy()})[0]
    recon = torch.tensor(output[0, 0]).to('cuda')
    orig = img_tensor[0, 0].to(recon.device)

    # 각종 메트릭 계산. GPU에서 가능하면 다 실행
    mae = compute_mae(orig, recon)
    ssim = compute_ssim(orig.unsqueeze(0).unsqueeze(0), recon.unsqueeze(0).unsqueeze(0))
    grad_mae = compute_grad_mae(orig.unsqueeze(0).unsqueeze(0), recon.unsqueeze(0).unsqueeze(0))
    lap_diff = compute_laplacian_variance_diff(orig, recon)
    pix_sum = compute_pixel_sum(orig, recon)
    result = logistic_score([mae, ssim, grad_mae, lap_diff, pix_sum])

    result_queue.put([
        os.path.basename(img_path),
        mae, ssim, grad_mae, lap_diff, pix_sum, result
    ])

    with progress.get_lock():
        progress.value += 1

    if save_visual:
        # 시각화 저장
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

# 메인 실행 함수. 전체 이미지 경로 수집 → 프로세스 생성 및 실행

def run_parallel_inference(input_root, output_csv, save_visual):
    start_time = time.time()

    processes = []
    result_queue = Queue()
    total_images = 0

    # 총 이미지 수 미리 세서 tqdm에 사용
    for config in camera_groups.values():
        for cam_id in config['cams']:
            cam_folder = os.path.join(input_root, f"camera_{cam_id}")
            for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
                total_images += len(glob.glob(os.path.join(cam_folder, ext)))

    progress = Value('i', 0)
    pbar = tqdm(total=total_images, desc="Total Progress", position=0)

    # 카메라 그룹별로 프로세스 생성
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
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, required=True, help='Input root folder containing camera_* folders')
    parser.add_argument('--output', type=str, required=True, help='Output CSV path')
    parser.add_argument('--visualize', action='store_true', help='Save visual comparison images')
    args = parser.parse_args()
    
    #준비-시작을 위해 임의로 넣음. 꼭 필요하지는 않음.
    print("All modules loaded. Type 'yes' or press ENTER to begin inference...")
    user_input = input().strip()
    if user_input == '' or user_input.lower() == 'yes':
        run_parallel_inference(args.input, args.output, args.visualize)
    else:
        print("Aborted by user.")
