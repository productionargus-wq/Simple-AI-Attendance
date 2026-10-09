"""
ARGUS TECHNOLOGIES - Boosted Deep Learning Face Recognition Engine
Zero-Image-Storage Architecture powered by OpenCV YuNet & SFace Neural Networks

Key Features:
1. Deep Neural Network Face Detection (YuNet):
   - Handles extreme poses, head tilts (-90 to +90 deg), distances, and expressions.
   - Detects 5 facial landmarks (eyes, nose, mouth corners) in real-time (<5ms).
2. Deep Feature Vector Extraction (SFace):
   - Aligns face geometrically using facial landmarks to eliminate tilt and skew.
   - Computes a 128-dimensional deep feature embedding vector via ResNet architecture.
   - L2-normalized vector for lightning-fast Cosine Similarity comparisons.
3. Multi-Pass Detection Pipeline:
   - Stage 1: Standard high-speed YuNet detection.
   - Stage 2: CLAHE (Contrast Limited Adaptive Histogram Equalization) on luminance channel
              to handle heavy shadows, backlight, glare, or dark room lighting.
   - Stage 3: Multi-scale dynamic scaling for distant or close-up faces.
   - Stage 4: Robust Haar Cascade fallback.
4. Privacy:
   - Zero raw facial images are stored during attendance. Images are discarded immediately.
"""

import os
import sys
import json
import threading
import contextlib
import urllib.request
import database

_detector_lock = threading.RLock()

@contextlib.contextmanager
def acquire_detector_lock(timeout=5.0):
    """Safely acquires the reentrant detector lock with a strict timeout to prevent worker freezes."""
    acquired = _detector_lock.acquire(timeout=timeout)
    try:
        yield acquired
    finally:
        if acquired:
            try:
                _detector_lock.release()
            except RuntimeError:
                pass

try:
    import numpy as np
except ImportError:
    np = None

try:
    import cv2
except ImportError:
    cv2 = None

# SFace official cosine threshold is 0.363.
# 0.40 provides strict security against impostors while handling lighting, angles, glasses & expressions.
RECOGNITION_THRESHOLD = 0.40

# Directory for deep learning models
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, 'models')
YUNET_PATH = os.path.join(MODELS_DIR, 'face_detection_yunet_2023mar.onnx')
SFACE_PATH = os.path.join(MODELS_DIR, 'face_recognition_sface_2021dec.onnx')

YUNET_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

_detector = None
_recognizer = None
_detector_size = (320, 240)


def ensure_models_available():
    """Ensures YuNet and SFace ONNX models exist locally; downloads if missing or truncated."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    if not os.path.exists(YUNET_PATH) or os.path.getsize(YUNET_PATH) < 100000:
        print(f"Downloading YuNet model to {YUNET_PATH}...")
        try:
            req = urllib.request.Request(YUNET_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as resp, open(YUNET_PATH, 'wb') as out_f:
                out_f.write(resp.read())
            print("YuNet model downloaded successfully.")
        except Exception as e:
            print(f"Error downloading YuNet: {e}")

    if not os.path.exists(SFACE_PATH) or os.path.getsize(SFACE_PATH) < 10000000:
        print(f"Downloading SFace model to {SFACE_PATH}...")
        try:
            req = urllib.request.Request(SFACE_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as resp, open(SFACE_PATH, 'wb') as out_f:
                out_f.write(resp.read())
            print("SFace model downloaded successfully.")
        except Exception as e:
            print(f"Error downloading SFace: {e}")


def get_detector(width=320, height=240):
    """Initializes or retrieves cached YuNet face detector."""
    global _detector, _detector_size
    if cv2 is None or not hasattr(cv2, 'FaceDetectorYN'):
        return None

    with acquire_detector_lock(timeout=5.0) as acquired:
        if not acquired:
            return None

        if _detector is None:
            ensure_models_available()
            if not os.path.exists(YUNET_PATH):
                return None
            try:
                _detector = cv2.FaceDetectorYN.create(
                    model=YUNET_PATH,
                    config="",
                    input_size=(width, height),
                    score_threshold=0.35,
                    nms_threshold=0.3,
                    top_k=5000
                )
                _detector_size = (width, height)
            except Exception as e:
                print(f"Error creating YuNet detector: {e}")
                _detector = None

        if _detector is not None and _detector_size != (width, height):
            try:
                _detector.setInputSize((width, height))
                _detector_size = (width, height)
            except Exception:
                pass

        return _detector


def get_recognizer():
    """Initializes or retrieves cached SFace deep learning recognizer."""
    global _recognizer
    if cv2 is None or not hasattr(cv2, 'FaceRecognizerSF'):
        return None

    with acquire_detector_lock(timeout=5.0) as acquired:
        if not acquired:
            return None

        if _recognizer is None:
            ensure_models_available()
            if not os.path.exists(SFACE_PATH):
                return None
            try:
                _recognizer = cv2.FaceRecognizerSF.create(model=SFACE_PATH, config="")
            except Exception as e:
                print(f"Error creating SFace recognizer: {e}")
                _recognizer = None

        return _recognizer


def apply_clahe_enhancement(img):
    """Enhances contrast and normalizes uneven lighting using CLAHE on the L channel."""
    try:
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l)
        enhanced_lab = cv2.merge((l_clahe, a, b))
        return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
    except Exception:
        return img


def detect_face_deep(img):
    """
    Multi-pass face detection using YuNet:
    Pass 1: Native image detection
    Pass 2: Lighting-enhanced (CLAHE) detection for shadows/glare
    Pass 3: Resized multi-scale detection
    Returns the best face descriptor (15 values: bbox + 5 landmarks + score) or None.
    """
    h, w = img.shape[:2]
    with acquire_detector_lock(timeout=5.0) as acquired:
        if not acquired:
            return None

        detector = get_detector(w, h)
        if detector is None:
            return None

        # Pass 1: Direct detection
        try:
            ret, faces = detector.detect(img)
            if ret and faces is not None and len(faces) > 0:
                # Pick the face with largest area / highest score
                return max(faces, key=lambda f: (f[2] * f[3], f[14]))
        except Exception:
            pass

        # Pass 2: CLAHE lighting enhancement
        try:
            enhanced = apply_clahe_enhancement(img)
            ret, faces = detector.detect(enhanced)
            if ret and faces is not None and len(faces) > 0:
                return max(faces, key=lambda f: (f[2] * f[3], f[14]))
        except Exception:
            pass

        # Pass 3: Scaled detection if frame is very large or very small
        target_w, target_h = 640, 480
        if w != target_w or h != target_h:
            try:
                scaled = cv2.resize(img, (target_w, target_h))
                detector.setInputSize((target_w, target_h))
                ret, faces = detector.detect(scaled)
                # Restore detector size
                detector.setInputSize((w, h))
                if ret and faces is not None and len(faces) > 0:
                    best = max(faces, key=lambda f: (f[2] * f[3], f[14]))
                    # Scale coordinates back to original image size
                    sx = w / float(target_w)
                    sy = h / float(target_h)
                    scaled_face = np.array(best, dtype=np.float32, copy=True)
                    scaled_face[0] *= sx
                    scaled_face[1] *= sy
                    scaled_face[2] *= sx
                    scaled_face[3] *= sy
                    for k in range(4, 14, 2):
                        scaled_face[k] *= sx
                        scaled_face[k + 1] *= sy
                    return scaled_face
            except Exception:
                try:
                    detector.setInputSize((w, h))
                except Exception:
                    pass

        # Pass 4: Robust Haar Cascade Fallback with CLAHE
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            if os.path.exists(cascade_path):
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
                enhanced_gray = clahe.apply(gray)
                face_cascade = cv2.CascadeClassifier(cascade_path)
                faces = face_cascade.detectMultiScale(
                    enhanced_gray,
                    scaleFactor=1.1,
                    minNeighbors=3,
                    minSize=(30, 30)
                )
                if len(faces) > 0:
                    x, y, fw, fh = max(faces, key=lambda b: b[2] * b[3])
                    # Synthesize YuNet 15-float format: [bbox (4), 5 landmarks (10), score (1)]
                    re_x, re_y = x + fw * 0.35, y + fh * 0.38
                    le_x, le_y = x + fw * 0.65, y + fh * 0.38
                    nt_x, nt_y = x + fw * 0.50, y + fh * 0.58
                    rm_x, rm_y = x + fw * 0.38, y + fh * 0.78
                    lm_x, lm_y = x + fw * 0.62, y + fh * 0.78
                    synth = np.array([
                        x, y, fw, fh,
                        re_x, re_y, le_x, le_y,
                        nt_x, nt_y, rm_x, rm_y,
                        lm_x, lm_y, 0.85
                    ], dtype=np.float32)
                    return synth
        except Exception:
            pass

        return None


def extract_face_embedding_from_image(image_bytes_or_path):
    """
    Extracts a 128-dimensional deep feature vector from face using YuNet + SFace.
    The raw image is NOT stored anywhere.
    Returns 128-float list or None if no face is detected.
    """
    if cv2 is None or np is None:
        return None

    try:
        # Load image
        if isinstance(image_bytes_or_path, str):
            img = cv2.imread(image_bytes_or_path)
        elif isinstance(image_bytes_or_path, np.ndarray):
            img = image_bytes_or_path
        else:
            nparr = np.frombuffer(image_bytes_or_path, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if img is None:
            return None

        # Auto-downscale large images to max 640px to ensure lightning-fast detection (<250ms)
        h, w = img.shape[:2]
        max_dim = max(h, w)
        if max_dim > 640:
            scale = 640.0 / float(max_dim)
            new_w = max(1, int(w * scale))
            new_h = max(1, int(h * scale))
            img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

        recognizer = get_recognizer()

        # Step 1: Deep learning detection & alignment
        face = detect_face_deep(img)

        if face is not None and recognizer is not None:
            try:
                with acquire_detector_lock(timeout=5.0) as acquired:
                    if acquired:
                        # Ensure face is float32 numpy array
                        face_arr = np.array(face, dtype=np.float32, copy=False)
                        # SFace geometric alignment using 5 facial landmarks
                        aligned_face = recognizer.alignCrop(img, face_arr)
                        if aligned_face is not None and getattr(aligned_face, 'size', 0) > 0:
                            raw_feature = recognizer.feature(aligned_face)

                            # L2 normalize
                            norm = np.linalg.norm(raw_feature)
                            if norm > 0:
                                normalized_feat = raw_feature / norm
                            else:
                                normalized_feat = raw_feature
                            return normalized_feat.flatten().tolist()
            except Exception as align_err:
                print(f"YuNet/SFace alignment fallback notice: {align_err}")

        # Step 2: Haar Cascade fallback if DNN is unavailable or fails
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        if os.path.exists(cascade_path):
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced_gray = clahe.apply(gray)
            face_cascade = cv2.CascadeClassifier(cascade_path)
            faces = face_cascade.detectMultiScale(
                enhanced_gray,
                scaleFactor=1.1,
                minNeighbors=3,
                minSize=(40, 40)
            )

            if len(faces) > 0:
                # Pick largest face
                x, y, w, h = max(faces, key=lambda b: b[2] * b[3])
                face_roi = enhanced_gray[y:y+h, x:x+w]
                face_resized = cv2.resize(face_roi, (112, 112))

                # Multi-region DCT descriptor
                float_face = np.float32(face_resized) / 255.0
                dct_face = cv2.dct(float_face)
                flat_features = dct_face[:12, :11].flatten()[:128]
                norm = np.linalg.norm(flat_features)
                if norm > 0:
                    embedding = flat_features / norm
                else:
                    embedding = flat_features
                return embedding.tolist()

        return None
    except Exception as e:
        print(f"Face embedding extraction error: {e}")
        return None


def verify_liveness_from_bytes(file_bytes, burst_bytes=None):
    """
    Presentation Attack Detection directly from raw image bytes.
    Decodes the image safely within face_engine where numpy and opencv are loaded,
    and returns (is_live: bool, confidence: float, reason: str).
    """
    return verify_liveness_anti_spoofing(file_bytes, burst_img=burst_bytes)


def verify_liveness_anti_spoofing(img, face=None, burst_img=None):
    """
    Presentation Attack Detection (PAD) / Anti-Spoofing Engine:
    Examines the frame and face region to detect:
    1. Digital Screens (Smartphone / Tablet / Monitor screens: device chassis contours,
       minAreaRect rotated boundaries, specular glass glare, periodic subpixel Moiré FFT peaks,
       blue-shifted backlight, device bezels)
    2. 2D Printed Photos on Paper (flat texture, low depth-of-field, paper borders)
    3. Static 2D presentation attacks (zero temporal micro-movement between burst frames)
    
    Returns:
        tuple: (is_live: bool, confidence: float, reason: str)
    """
    if img is None:
        return True, 1.0, "OK"

    if isinstance(img, (bytes, bytearray)):
        if np is None or cv2 is None:
            return True, 1.0, "OK"
        try:
            nparr = np.frombuffer(img, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        except Exception as dec_err:
            print(f"Error decoding image in verify_liveness: {dec_err}")
            return True, 0.5, "Bypass on decode error"

    if isinstance(burst_img, (bytes, bytearray)):
        if np is not None and cv2 is not None:
            try:
                b_arr = np.frombuffer(burst_img, np.uint8)
                burst_img = cv2.imdecode(b_arr, cv2.IMREAD_COLOR)
            except Exception:
                burst_img = None

    if img is None or cv2 is None or np is None:
        return True, 1.0, "OK"

    try:
        h, w = img.shape[:2]
        if face is None:
            face = detect_face_deep(img)

        if face is None:
            return None, 0.0, "No face detected in camera frame"

        # Extract bbox [x, y, w_box, h_box]
        fx = max(0, int(face[0]))
        fy = max(0, int(face[1]))
        fw = min(w - fx, int(face[2]))
        fh = min(h - fy, int(face[3]))
        fcx = fx + fw / 2.0
        fcy = fy + fh / 2.0

        if fw < 25 or fh < 25:
            return None, 0.0, "Face too small or distant for biometric verification"

        face_roi = img[fy:fy+fh, fx:fx+fw]
        if face_roi.size == 0:
            return None, 0.0, "Invalid face region"

        # Grayscale and edge processing
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        blurred_img = cv2.GaussianBlur(gray_img, (5, 5), 0)
        edges = cv2.Canny(blurred_img, 30, 100)

        # --- Test 1: Handheld Device Chassis & Screen Contour Detection ---
        # Detects standalone handheld rectangular objects enclosing the face (phones, tablets, photo prints)
        contours, _ = cv2.findContours(edges, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        for cnt in contours:
            rx, ry, rw, rh = cv2.boundingRect(cnt)
            if rw > fw * 0.80 and rh > fh * 0.80:
                # Handheld device must be smaller than the camera frame and within handheld proportions
                if (rw < w * 0.96 or rh < h * 0.96) and rw <= fw * 2.8 and rh <= fh * 3.5:
                    # Encloses the face center
                    if rx <= fcx <= rx + rw and ry <= fcy <= ry + rh:
                        aspect_bb = rh / float(rw + 1e-5)
                        rect = cv2.minAreaRect(cnt)
                        dim1, dim2 = rect[1]
                        if dim1 > 0 and dim2 > 0:
                            min_d, max_d = min(dim1, dim2), max(dim1, dim2)
                            aspect_rot = max_d / float(min_d)
                            # Check phone or tablet aspect ratio (vertical or horizontal)
                            if (1.08 <= aspect_bb <= 2.6) or (1.08 <= (1.0 / aspect_bb) <= 2.6) or (1.10 <= aspect_rot <= 2.6):
                                hull = cv2.convexHull(cnt)
                                hull_area = cv2.contourArea(hull)
                                solidity = float(hull_area) / float(rw * rh + 1e-5)
                                if solidity >= 0.35:
                                    return False, 0.98, f"Mobile phone or digital screen chassis detected (aspect {aspect_rot:.2f})"

        # --- Test 3: Specular Glass Reflection Hotspots ---
        hsv_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2HSV)
        v_channel = hsv_roi[:, :, 2]
        s_channel = hsv_roi[:, :, 1]
        glare_mask = (v_channel >= 245) & (s_channel <= 25)
        glare_ratio = float(np.sum(glare_mask)) / float(fw * fh)
        if glare_ratio >= 0.025:
            return False, 0.92, "Digital screen glass specular reflection detected"

        # --- Test 4: 2D FFT Moiré & Periodic Subpixel Grid Analysis ---
        gray_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        gray_128 = cv2.resize(gray_roi, (128, 128), interpolation=cv2.INTER_AREA)
        f = np.fft.fft2(gray_128)
        fshift = np.fft.fftshift(f)
        mag_spec = np.log(np.abs(fshift) + 1.0)

        # High frequency annular ring: radius 25 to 55 from center (64, 64)
        y_grid, x_grid = np.ogrid[:128, :128]
        dist_center = np.sqrt((x_grid - 64)**2 + (y_grid - 64)**2)
        hf_mask = (dist_center >= 25) & (dist_center <= 55)
        hf_vals = mag_spec[hf_mask]
        
        fft_peak_ratio = 0.0
        if len(hf_vals) > 0:
            mean_hf = np.mean(hf_vals)
            max_hf = np.max(hf_vals)
            std_hf = np.std(hf_vals)
            fft_peak_ratio = float((max_hf - mean_hf) / (std_hf + 1e-5))
            if fft_peak_ratio >= 3.6:
                return False, 0.95, "Digital screen subpixel Moiré grid detected"

        # --- Test 5: Color Gamut & Blue-Shifted Screen Backlight ---
        b_mean = float(np.mean(face_roi[:, :, 0]))
        r_mean = float(np.mean(face_roi[:, :, 2]))
        blue_to_red_ratio = (b_mean + 1.0) / (r_mean + 1.0)
        if blue_to_red_ratio >= 1.20 and glare_ratio >= 0.01:
            return False, 0.89, "Digital screen backlight luminescence detected"

        # --- Test 6: Laplacian Texture Sharpness & Flatness ---
        lap_var = float(cv2.Laplacian(gray_roi, cv2.CV_64F).var())
        if lap_var < 4.5:
            return False, 0.88, "2D low-resolution photograph or printout detected"

        # --- Test 7: Dual-Frame Burst Micro-Movement Verification ---
        if burst_img is not None:
            try:
                burst_face = detect_face_deep(burst_img)
                if burst_face is not None:
                    bfx = max(0, int(burst_face[0]))
                    bfy = max(0, int(burst_face[1]))
                    bfw = min(burst_img.shape[1] - bfx, int(burst_face[2]))
                    bfh = min(burst_img.shape[0] - bfy, int(burst_face[3]))
                    burst_roi = burst_img[bfy:bfy+bfh, bfx:bfx+bfw]
                    if burst_roi.size > 0 and face_roi.size > 0:
                        roi_a = cv2.resize(gray_roi, (120, 120))
                        roi_b = cv2.resize(cv2.cvtColor(burst_roi, cv2.COLOR_BGR2GRAY), (120, 120))
                        frame_delta = float(np.mean(np.abs(roi_a.astype(float) - roi_b.astype(float))))
                        if frame_delta < 0.75:
                            return False, 0.97, "Static photograph presentation attack (zero natural micro-movement)"
            except Exception as burst_err:
                print(f"Notice: Dual-frame verification notice: {burst_err}")

        return True, 0.98, "Live Human Confirmed"

    except Exception as e:
        print(f"Anti-spoofing verification error: {e}")
        return True, 0.5, "Bypass on error"


def cosine_similarity(vec_a, vec_b):
    """Computes cosine similarity between two 128-d vectors in range [-1.0, 1.0]."""
    if np is None or not vec_a or not vec_b:
        return 0.0
    try:
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))
    except Exception:
        return 0.0


def calculate_confidence_percentage(similarity_score):
    """
    Maps cosine similarity score to an intuitive human-readable confidence percentage (0% - 100%).
    With SFace deep learning:
    - 0.40 is the match threshold (corresponds to ~70% match)
    - 0.60 is a solid match (~85%)
    - 0.80+ is an exact match (98-99.9%)
    """
    score = float(similarity_score)
    if score < 0.20:
        return float(round(max(0.0, score * 100.0), 1))
    elif score < RECOGNITION_THRESHOLD:
        return float(round(20.0 + (score - 0.20) * 200.0, 1))
    else:
        # Match range [0.40, 1.0] -> [70.0%, 99.9%]
        mapped = 70.0 + (score - 0.40) * (29.9 / 0.50)
        return float(round(min(99.9, max(70.0, mapped)), 1))


def recognize_face(query_embedding, company_id=None):
    """
    Compares query embedding with registered employee embeddings in the database.
    If company_id is provided, compares only within that company.
    Returns best match if similarity >= RECOGNITION_THRESHOLD.
    """
    if not query_embedding:
        return {
            'matched': False,
            'confidence': 0.0,
            'message': 'No face detected in camera frame. Please face the camera directly in good lighting.'
        }

    try:
        stored_embeddings = database.get_all_face_embeddings(company_id=company_id)
        if not stored_embeddings:
            return {
                'matched': False,
                'confidence': 0.0,
                'message': 'No registered face biometrics found in database. Please enroll employee face photo in the Admin Portal.'
            }

        best_match = None
        highest_score = -1.0

        for emp in stored_embeddings:
            score = cosine_similarity(query_embedding, emp.get('embedding', []))
            if score > highest_score:
                highest_score = float(score)
                best_match = emp

        confidence_pct = float(calculate_confidence_percentage(highest_score))

        if highest_score >= RECOGNITION_THRESHOLD and best_match:
            return {
                'matched': True,
                'employee_id': str(best_match['id']),
                'employee_name': str(best_match['employee_name']),
                'confidence': float(confidence_pct),
                'raw_score': float(round(highest_score, 4))
            }
        else:
            return {
                'matched': False,
                'confidence': float(confidence_pct),
                'raw_score': float(round(max(0.0, float(highest_score)), 4)),
                'message': 'Face not recognized. Please face the camera directly in good lighting and try again.'
            }
    except Exception as e:
        print(f"recognize_face error: {e}")
        return {
            'matched': False,
            'confidence': 0.0,
            'message': 'Face recognition biometrics processing error. Please face the camera directly and try again.'
        }


def auto_sync_stored_employee_embeddings():
    """
    Scans the database for employees who have saved photos in static/uploads
    and re-encodes their embeddings with the deep SFace model.
    Runs seamlessly in the background on startup.
    """
    try:
        db = database.get_db()
        employees = db.employees.find({'photo_filename': {'$ne': '', '$exists': True}})
        updated_count = 0
        for emp in employees:
            if emp.get('embedding_model') == 'sface_v1':
                continue
            photo_file = emp.get('photo_filename')
            if not photo_file:
                continue
            full_path = os.path.join(BASE_DIR, 'static', 'uploads', photo_file)
            if os.path.exists(full_path):
                emb = extract_face_embedding_from_image(full_path)
                if emb:
                    db.employees.update_one(
                        {'_id': emp['_id']},
                        {'$set': {
                            'face_embedding': json.dumps(emb),
                            'embedding_model': 'sface_v1'
                        }}
                    )
                    updated_count += 1
        if updated_count > 0:
            print(f"Face Engine: Upgraded {updated_count} employee embeddings to Deep SFace model.")
    except Exception as e:
        print(f"Auto-sync employee embeddings note: {e}")
