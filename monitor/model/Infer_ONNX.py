import os
import glob
import numpy as np
import csv
import cv2
from PIL import Image
from tqdm import tqdm
import onnxruntime as ort
from torchvision import transforms

# ----------------------------
# 손실 지표 계산 함수 정의
# ----------------------------

# 평균 절대 오차
def compute_mae(orig, recon):
    return np.mean(np.abs(orig - recon))

# 구조적 유사도(SSIM)
def compute_ssim(orig, recon):
    import pytorch_ssim
    import torch
    orig_tensor = torch.tensor(orig).unsqueeze(0).unsqueeze(0).float()
    recon_tensor = torch.tensor(recon).unsqueeze(0).unsqueeze(0).float()
    return pytorch_ssim.ssim(orig_tensor, recon_tensor).item()

# Gradient 기반 평균 절대 오차
def compute_grad_mae(orig, recon):
    grad_orig = np.sqrt(cv2.Sobel(orig, cv2.CV_64F, 1, 0, ksize=3)**2 + cv2.Sobel(orig, cv2.CV_64F, 0, 1, ksize=3)**2)
    grad_recon = np.sqrt(cv2.Sobel(recon, cv2.CV_64F, 1, 0, ksize=3)**2 + cv2.Sobel(recon, cv2.CV_64F, 0, 1, ksize=3)**2)
    return np.mean(np.abs(grad_orig - grad_recon))

# 라플라시안 기반 경계 선명도 차이
def compute_laplacian_variance_diff(orig, recon):
    orig = orig.astype(np.float64)
    recon = recon.astype(np.float64)
    var_orig = np.var(cv2.Laplacian(orig, cv2.CV_64F))
    var_recon = np.var(cv2.Laplacian(recon, cv2.CV_64F))
    return abs(var_orig - var_recon)

# 차영상 기반 임계 픽셀 개수
def compute_pixel_sum(orig, recon):
    diff = np.abs((orig * 255).astype(np.uint8) - (recon * 255).astype(np.uint8))
    _, binary = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
    return np.sum(binary > 0)

# ----------------------------
# 로지스틱 회귀 기반 결함 판정 함수
# ----------------------------
def logistic_score(metrics):
    mae, ssim, grad_mae, lap_diff, pix_sum = metrics
    score = (
        318.423821 * mae +
        21.601394 * ssim +
        -26.708228 * grad_mae +
        357.830399 * lap_diff +
        -0.000003 * pix_sum +
        -24.372392  # 바이어스 항
    )
    prob = 1 / (1 + np.exp(-score))
    return 1 if prob > 0.5 else 0

# ----------------------------
# ONNX 모델 기반 추론 함수
# ----------------------------
def inference_all(input_root, output_csv):
    # 카메라 ID 그룹별로 사용하는 ONNX 모델 경로 정의
    camera_to_model = {
        (1, 5, 6, 10): 'vae_group_1_10_5_6.onnx',
        (2, 4, 7, 9): 'vae_group_2_9_4_7.onnx',
        (3, 8): 'vae_group_3_8.onnx'
    }

    # PIL 이미지를 텐서로 변환 (크기 고정)
    transform = transforms.Compose([
        transforms.Resize((300, 480)),
        transforms.ToTensor()
    ])

    # 결과 CSV 저장용 배열
    result_rows = [['filename', 'MAE', 'SSIM', 'Grad_MAE', 'Laplacian_Diff', 'Pixel_Sum', 'result']]
    model_cache = {}  # ONNX 세션 캐싱

    # 이미지 파일 전체 수집 (camera_* 폴더 기준)
    all_image_info = []
    for cam_folder in glob.glob(os.path.join(input_root, 'camera_*')):
        cam_id = int(cam_folder.split('_')[-1])
        for ext in ('*.jpg', '*.jpeg', '*.JPG', '*.JPEG'):
            for img_path in glob.glob(os.path.join(cam_folder, ext)):
                all_image_info.append((cam_id, img_path))

    SAVE_IMAGE = False  # ← 결과 이미지 저장 여부 토글 (True 시 저장됨)

    for cam_id, img_path in tqdm(all_image_info, desc="Inference Progress", unit="img"):
        # 해당 카메라에 대응되는 ONNX 모델 찾기
        model_path = None
        for cams, path in camera_to_model.items():
            if cam_id in cams:
                model_path = path
                break
        if model_path is None or not os.path.exists(model_path):
            continue

        # ONNX 세션 캐싱 또는 생성
        if model_path not in model_cache:
            session = ort.InferenceSession(model_path, providers=['CPUExecutionProvider'])
            model_cache[model_path] = session
        else:
            session = model_cache[model_path]

        # 이미지 전처리
        img = Image.open(img_path).convert('L')
        if cam_id in [6, 7, 8, 9, 10]:
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        img_tensor = transform(img).unsqueeze(0).numpy()  # shape: (1, 1, 300, 480)

        # 모델 추론 수행
        input_name = session.get_inputs()[0].name
        output = session.run(None, {input_name: img_tensor})[0]
        recon = output[0, 0]
        orig = img_tensor[0, 0]

        # 지표 계산
        mae = compute_mae(orig, recon)
        ssim = compute_ssim(orig, recon)
        grad_mae = compute_grad_mae(orig, recon)
        lap_diff = compute_laplacian_variance_diff(orig, recon)
        pix_sum = compute_pixel_sum(orig, recon)
        result = logistic_score([mae, ssim, grad_mae, lap_diff, pix_sum])

        # CSV 결과 저장
        result_rows.append([
            os.path.basename(img_path),
            mae,
            ssim,
            grad_mae,
            lap_diff,
            pix_sum,
            result
        ])

        # 시각화 이미지 저장
        if SAVE_IMAGE:
            orig_img = (orig * 255).astype(np.uint8)
            recon_img = (recon * 255).astype(np.uint8)
            diff_img = np.abs(orig_img.astype(np.int16) - recon_img.astype(np.int16)).astype(np.uint8)
            _, binary_diff = cv2.threshold(diff_img, 30, 255, cv2.THRESH_BINARY)

            # 이미지 회전 및 색상 변환
            orig_img = cv2.rotate(orig_img, cv2.ROTATE_90_CLOCKWISE)
            recon_img = cv2.rotate(recon_img, cv2.ROTATE_90_CLOCKWISE)
            binary_diff = cv2.rotate(binary_diff, cv2.ROTATE_90_CLOCKWISE)

            orig_color = cv2.cvtColor(orig_img, cv2.COLOR_GRAY2BGR)
            recon_color = cv2.cvtColor(recon_img, cv2.COLOR_GRAY2BGR)
            diff_color = cv2.cvtColor(binary_diff, cv2.COLOR_GRAY2BGR)

            # 이미지 상단 텍스트 박스 작성
            metrics_text = [
                f"MAE: {mae:.4f}",
                f"SSIM: {ssim:.4f}",
                f"Grad_MAE: {grad_mae:.4f}",
                f"Laplacian_Diff: {lap_diff:.4f}",
                f"Pixel_Sum: {pix_sum}",
                f"Result: {'Defect' if result else 'OK'}"
            ]
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            thickness = 1
            line_height = 20
            header_h = line_height * len(metrics_text) + 10
            header = np.ones((header_h, orig_color.shape[1] * 3, 3), dtype=np.uint8) * 255

            for i, line in enumerate(metrics_text):
                y = 10 + (i + 1) * line_height
                cv2.putText(header, line, (10, y), font, font_scale, (0, 0, 0), thickness)

            combined = cv2.hconcat([orig_color, recon_color, diff_color])
            final_img = cv2.vconcat([header, combined])

            output_vis_dir = os.path.join(os.path.dirname(output_csv), "visual")
            os.makedirs(output_vis_dir, exist_ok=True)
            save_path = os.path.join(output_vis_dir, f"combined_{os.path.basename(img_path)}")
            cv2.imwrite(save_path, final_img)

    # CSV 결과 파일 저장
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(result_rows)

    print(f"Inference results saved to: {output_csv}")

# ----------------------------
# 메인 실행부
# ----------------------------
if __name__ == "__main__":
    input_root = "./test_vector"  # 입력 이미지가 있는 루트 폴더
    output_csv = "./test_vector/result/result.csv"  # 결과 CSV 파일 경로
    inference_all(input_root, output_csv)
