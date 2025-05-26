import os
import csv
import glob
import numpy as np
import torch
import cv2
from multiprocessing import Process, Queue
import onnxruntime as ort
import pathlib

# OpenCV를 사용하여 이미지를 고속으로 불러오고 전처리하는 함수
# 흑백으로 로딩하고, 필요 시 좌우 반전, 리사이즈, 정규화 수행
# 최종 shape: (1, 1, 300, 480)
def preprocess_image_cv2(img_path, flip=False):
    img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        raise RuntimeError(f"Failed to read image: {img_path}")
    if flip:
        img = cv2.flip(img, 1)
    img = cv2.resize(img, (480, 300))  # (W, H)
    img = img.astype(np.float32) / 255.0
    return img[np.newaxis, np.newaxis, :, :]

# 이미지 로딩 전용 프로세스
# 디스크에서 이미지를 읽고 전처리한 후, 추론 큐에 넣음
def preload_worker(image_info, queue):
    for cam_id, img_path in image_info:
        flip = cam_id in [6, 7, 8, 9, 10]
        tensor = preprocess_image_cv2(img_path, flip)
        queue.put((os.path.basename(img_path), tensor))
    queue.put(None)  # 종료 신호

# GPU에서 추론을 수행하는 작업자
# ONNX 세션 생성 후 큐에서 데이터를 꺼내 추론 수행
def inference_worker(gpu_id, input_queue, result_queue, model_path):
    session = ort.InferenceSession(model_path, providers=[('CUDAExecutionProvider', {'device_id': gpu_id})])
    input_name = session.get_inputs()[0].name

    while True:
        item = input_queue.get()
        if item is None:
            break
        filename, tensor = item
        output = session.run(None, {input_name: tensor})[0]
        recon = output[0, 0]
        orig = tensor[0, 0]
        metrics = compute_metrics(orig, recon)
        result_queue.put([filename] + metrics)

# 성능 지표 계산 함수 (SSIM 포함)
def compute_metrics(orig, recon):
    def mae(o, r):
        return np.mean(np.abs(o - r))

    def grad_mae(o, r):
        grad_o = np.sqrt(cv2.Sobel(o, cv2.CV_64F, 1, 0)**2 + cv2.Sobel(o, cv2.CV_64F, 0, 1)**2)
        grad_r = np.sqrt(cv2.Sobel(r, cv2.CV_64F, 1, 0)**2 + cv2.Sobel(r, cv2.CV_64F, 0, 1)**2)
        return np.mean(np.abs(grad_o - grad_r))

    def lap_var_diff(o, r):
        return abs(np.var(cv2.Laplacian(o, cv2.CV_64F)) - np.var(cv2.Laplacian(r, cv2.CV_64F)))

    def pix_sum(o, r):
        diff = np.abs((o * 255).astype(np.uint8) - (r * 255).astype(np.uint8))
        _, binary = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
        return np.sum(binary > 0)

    def logistic_score(metrics):
        m, s, g, l, p = metrics
        score = 318.423821 * m + 21.601394 * s + -26.708228 * g + 357.830399 * l + -0.000003 * p - 24.372392
        prob = 1 / (1 + np.exp(-score))
        return 1 if prob > 0.5 else 0

    import pytorch_ssim
    t_orig = torch.tensor(orig).unsqueeze(0).unsqueeze(0).float()
    t_recon = torch.tensor(recon).unsqueeze(0).unsqueeze(0).float()
    ssim_val = pytorch_ssim.SSIM(window_size=11)(t_orig, t_recon).item()

    m = mae(orig, recon)
    g = grad_mae(orig, recon)
    l = lap_var_diff(orig, recon)
    p = pix_sum(orig, recon)
    return [m, ssim_val, g, l, p, logistic_score([m, ssim_val, g, l, p])]

# 전체 파이프라인 실행 함수
def run_optimized_pipeline(image_root: str, model_path: str, out_csv_path: str):
    preload_to_infer_queue = Queue(maxsize=50)  # 프리로딩 → 추론 전달 큐
    results = Queue()  # 추론 결과 저장 큐

    # 이미지 파일 목록 수집
    image_info = []
    for cam_folder in glob.glob(os.path.join(image_root, 'camera_*')):
        cam_id = int(cam_folder.split('_')[-1])
        for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
            for img_path in glob.glob(os.path.join(cam_folder, ext)):
                image_info.append((cam_id, img_path))

    print(f"Total images to process: {len(image_info)}")

    # 프리로더 실행
    preload_proc = Process(target=preload_worker, args=(image_info, preload_to_infer_queue))

    # GPU 추론 워커 실행 (0, 1번 GPU)
    infer_proc_0 = Process(target=inference_worker, args=(0, preload_to_infer_queue, results, model_path))
    infer_proc_1 = Process(target=inference_worker, args=(1, preload_to_infer_queue, results, model_path))

    preload_proc.start()
    infer_proc_0.start()
    infer_proc_1.start()

    preload_proc.join()
    preload_to_infer_queue.put(None)
    preload_to_infer_queue.put(None)

    infer_proc_0.join()
    infer_proc_1.join()

    # 결과 수집 및 저장
    all_results = [['filename', 'MAE', 'SSIM', 'Grad_MAE', 'Laplacian_Diff', 'Pixel_Sum', 'result']]
    while not results.empty():
        all_results.append(results.get())

    os.makedirs(os.path.dirname(out_csv_path), exist_ok=True)
    with open(out_csv_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(all_results)

    print(f"Saved results to {out_csv_path}")

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, required=True, help='Root input folder')
    parser.add_argument('--model', type=str, required=True, help='ONNX model path')
    parser.add_argument('--output', type=str, required=True, help='Output CSV path')
    args = parser.parse_args()

    run_optimized_pipeline(args.input, args.model, args.output)
