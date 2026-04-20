from flask import Flask, request, jsonify
from flask_cors import CORS
import cv2
import numpy as np
import base64
import time
import mediapipe as mp
import warnings
import threading
import os
import json
from datetime import datetime
import sys

# 尝试导入声音库
try:
    import sounddevice as sd
    import soundfile as sf
    SOUND_AVAILABLE = True
    print("✅ 声音模块加载成功")
except ImportError:
    SOUND_AVAILABLE = False
    print("⚠️ 声音模块未安装，将使用系统蜂鸣声")


# ==================== 初始化 ====================
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
warnings.filterwarnings('ignore')

# ==================== 配置 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RECORD_FILE_PATH = os.path.join(BASE_DIR, "records", "fatigue_records.txt")
EXPORT_DIR = os.path.join(BASE_DIR, "exports")

# 确保目录存在
os.makedirs(os.path.dirname(RECORD_FILE_PATH), exist_ok=True)
os.makedirs(EXPORT_DIR, exist_ok=True)

# ==================== 全局状态变量 ====================
is_detecting = False
last_nod_time = 0.0
close_eye_start_time = 0.0

# ==================== 阈值配置 ====================
EYELID_THRESHOLD = 0.25
EYE_CLOSE_DURATION = 0.3
HEAD_ANGLE_THRESHOLD = 15
NOD_INTERVAL_THRESHOLD = 0.8
WARNING_COOLDOWN = 3

current_thresholds = {
    'eyelid_threshold': EYELID_THRESHOLD,
    'eye_close_duration': EYE_CLOSE_DURATION,
    'head_angle_threshold': HEAD_ANGLE_THRESHOLD,
    'nod_interval_threshold': NOD_INTERVAL_THRESHOLD,
    'warning_cooldown': WARNING_COOLDOWN
}

# ==================== 健康检查变量 ====================
error_count = 0
last_frame_time = time.time()

# ==================== MediaPipe初始化 ====================
mp_face_mesh = mp.solutions.face_mesh
face_mesh = mp_face_mesh.FaceMesh(
    static_image_mode=False,
    max_num_faces=1,
    refine_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)


# ==================== 预警声音相关 ====================
warning_active = False
warning_lock = threading.Lock()
last_warning_time = 0
warning_sound = None
sample_rate = None

def load_warning_sound():
    """加载或创建预警音频"""
    global warning_sound, sample_rate
    
    if not SOUND_AVAILABLE:
        print("⚠️ 声音模块不可用，将使用系统蜂鸣声")
        return
    
    try:
        if os.path.exists('warning.wav'):
            warning_sound, sample_rate = sf.read('warning.wav')
            print("✅ 预警音频加载成功: warning.wav")
        else:
            print("⚠️ 未找到warning.wav，创建默认警告音...")
            sample_rate = 22050
            duration = 0.3
            t = np.linspace(0, duration, int(sample_rate * duration))
            sound = 0.3 * np.sin(2 * np.pi * 880 * t)
            warning_sound = sound
            try:
                sf.write('warning.wav', warning_sound, sample_rate)
                print("✅ 已创建默认预警音频: warning.wav")
            except:
                pass
    except Exception as e:
        print(f"加载预警音频失败: {e}")
        warning_sound = None

def play_warning_sound():
    """播放预警声音"""
    global warning_active
    
    with warning_lock:
        if warning_active:
            return
        warning_active = True
    
    try:
        if SOUND_AVAILABLE and warning_sound is not None:
            sd.play(warning_sound, sample_rate)
            sd.wait()
        else:
            # 系统蜂鸣声
            print('\a')
            # Mac 系统语音
            if sys.platform == 'darwin':
                os.system('say "注意疲劳，请休息" 2>/dev/null &')
            time.sleep(0.3)
    except Exception as e:
        print(f"播放声音失败: {e}")
    finally:
        with warning_lock:
            warning_active = False

def trigger_warning(fatigue_type, fatigue_data):
    """触发预警并播放声音"""
    global last_warning_time
    
    current_time = time.time()
    if current_time - last_warning_time < WARNING_COOLDOWN:
        return None
    
    last_warning_time = current_time
    
    # 播放声音
    sound_thread = threading.Thread(target=play_warning_sound)
    sound_thread.daemon = True
    sound_thread.start()
    
    type_map = {'eye': '闭眼疲劳', 'head': '点头疲劳', 'both': '多重疲劳'}
    warning_info = {
        'type': fatigue_type,
        'time': time.strftime('%H:%M:%S'),
        'message': f'检测到{type_map.get(fatigue_type, "疲劳")}',
        'data': fatigue_data
    }
    
    print(f"\n⚠️ {warning_info['message']} | 睁眼度:{fatigue_data.get('eyelidOpening', 0)} | 角度:{fatigue_data.get('headAngle', 0)}°")
    
    return warning_info

# 加载声音
load_warning_sound()

# ==================== 关键点索引 ====================
LEFT_EYE_INDICES = [33, 133, 157, 158, 159, 160, 161, 173]
RIGHT_EYE_INDICES = [362, 382, 381, 380, 374, 373, 390, 249]
FOREHEAD_INDICES = [10, 338, 297, 332]
CHIN_INDICES = [152, 148, 176, 150]

# ==================== 记录管理函数 ====================
def write_fatigue_record(fatigue_type, duration):
    """写入疲劳记录"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        record_line = f"{timestamp}-{fatigue_type}-{duration:.3f}秒\n"
        
        with open(RECORD_FILE_PATH, "a", encoding="utf-8") as f:
            f.write(record_line)
        print(f"📝 记录保存: {fatigue_type} - {duration:.3f}秒")
        return True
    except Exception as e:
        print(f"写入记录失败：{e}")
        return False

def read_fatigue_records():
    """读取所有疲劳记录"""
    records = []
    try:
        if not os.path.exists(RECORD_FILE_PATH):
            return records
        
        with open(RECORD_FILE_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            parts = line.split('-')
            if len(parts) >= 3:
                timestamp = '-'.join(parts[:-2])
                fatigue_type = parts[-2]
                duration = parts[-1]
                records.append({
                    "timestamp": timestamp,
                    "fatigue_type": fatigue_type,
                    "duration": duration
                })
        return records
    except Exception as e:
        print(f"读取记录失败：{e}")
        return []

def reset_fatigue_records():
    """重置疲劳记录"""
    try:
        with open(RECORD_FILE_PATH, "w", encoding="utf-8") as f:
            f.write("")
        return True
    except Exception as e:
        print(f"重置记录失败：{e}")
        return False

def export_fatigue_records():
    """导出疲劳记录"""
    try:
        records = read_fatigue_records()
        if not records:
            return {"success": False, "msg": "暂无记录可导出"}
        
        export_file_name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_fatigue_records.txt"
        export_file_path = os.path.join(EXPORT_DIR, export_file_name)
        
        with open(export_file_path, "w", encoding="utf-8") as f:
            f.write("时间戳\t疲劳类型\t持续时长\n")
            for record in reversed(records):
                f.write(f"{record['timestamp']}\t{record['fatigue_type']}\t{record['duration']}\n")
        
        return {"success": True, "file_name": export_file_name, "msg": "导出成功"}
    except Exception as e:
        return {"success": False, "msg": f"导出失败：{str(e)}"}

# ==================== 检测函数 ====================
def calculate_eyelid_opening(face_landmarks, image_shape):
    try:
        LEFT_EYE_TOP = 159
        LEFT_EYE_BOTTOM = 145
        RIGHT_EYE_TOP = 386
        RIGHT_EYE_BOTTOM = 374
        h, w = image_shape[:2]
        
        left_height = abs(face_landmarks.landmark[LEFT_EYE_TOP].y - face_landmarks.landmark[LEFT_EYE_BOTTOM].y) * h
        right_height = abs(face_landmarks.landmark[RIGHT_EYE_TOP].y - face_landmarks.landmark[RIGHT_EYE_BOTTOM].y) * h
        avg_height = (left_height + right_height) / 2.0
        normalized = min(avg_height / 20.0, 1.0)
        return float(normalized)
    except:
        return 1.0

def calculate_head_angle(face_landmarks, image_shape):
    try:
        FOREHEAD = 10
        NOSE_TIP = 4
        CHIN = 152
        h, w = image_shape[:2]
        
        y_forehead = face_landmarks.landmark[FOREHEAD].y * h
        y_nose = face_landmarks.landmark[NOSE_TIP].y * h
        y_chin = face_landmarks.landmark[CHIN].y * h
        
        vertical_total = abs(y_chin - y_forehead) or 1.0
        pitch_ratio = (abs(y_nose - y_forehead) / vertical_total) - 0.5
        pitch_angle = pitch_ratio * 90.0
        
        if y_nose > (y_forehead + y_chin) / 2:
            pitch_angle = -abs(pitch_angle)
        else:
            pitch_angle = abs(pitch_angle)
        
        return float(max(min(pitch_angle, 45.0), -45.0))
    except:
        return 0.0

def get_face_box(face_landmarks, image_shape):
    try:
        h, w = image_shape[:2]
        x_coords = [lm.x * w for lm in face_landmarks.landmark]
        y_coords = [lm.y * h for lm in face_landmarks.landmark]
        x_min = max(0, int(min(x_coords)))
        x_max = min(w, int(max(x_coords)))
        y_min = max(0, int(min(y_coords)))
        y_max = min(h, int(max(y_coords)))
        return [x_min, y_min, x_max - x_min, y_max - y_min]
    except:
        return [0, 0, 0, 0]

def get_eye_points(face_landmarks, image_shape):
    try:
        h, w = image_shape[:2]
        eye_indices = LEFT_EYE_INDICES + RIGHT_EYE_INDICES
        points = []
        for idx in eye_indices:
            if idx < len(face_landmarks.landmark):
                lm = face_landmarks.landmark[idx]
                points.append([int(lm.x * w), int(lm.y * h)])
        return points
    except:
        return []

def get_head_points(face_landmarks, image_shape):
    try:
        h, w = image_shape[:2]
        points = []
        for idx in FOREHEAD_INDICES + CHIN_INDICES:
            if idx < len(face_landmarks.landmark):
                lm = face_landmarks.landmark[idx]
                points.append([int(lm.x * w), int(lm.y * h)])
        return points
    except:
        return []

# ==================== API 接口 ====================

@app.route("/test", methods=["GET"])
def test():
    return jsonify({"code": 200, "msg": "Backend running"})

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"code": 200, "status": "ok", "detecting": is_detecting})

@app.route("/start_detection", methods=["POST"])
def start_detection():
    global is_detecting
    try:
        data = request.get_json()
        action = data.get("action")
        
        if action == "start":
            is_detecting = True
            print("✅ 检测已启动")
            return jsonify({"code": 200, "msg": "检测已启动", "isDetecting": True})
        elif action == "stop":
            is_detecting = False
            print("⏹️ 检测已停止")
            return jsonify({"code": 200, "msg": "检测已停止", "isDetecting": False})
        else:
            return jsonify({"code": 400, "msg": "参数错误"})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)})

@app.route("/get_thresholds", methods=["GET"])
def get_thresholds():
    return jsonify({"code": 200, "thresholds": current_thresholds})

@app.route("/update_thresholds", methods=["POST"])
def update_thresholds():
    global current_thresholds, EYELID_THRESHOLD, EYE_CLOSE_DURATION
    global HEAD_ANGLE_THRESHOLD, NOD_INTERVAL_THRESHOLD, WARNING_COOLDOWN
    
    try:
        data = request.get_json()
        if 'eyelid_threshold' in data:
            current_thresholds['eyelid_threshold'] = float(data['eyelid_threshold'])
            EYELID_THRESHOLD = current_thresholds['eyelid_threshold']
        if 'eye_close_duration' in data:
            current_thresholds['eye_close_duration'] = float(data['eye_close_duration'])
            EYE_CLOSE_DURATION = current_thresholds['eye_close_duration']
        if 'head_angle_threshold' in data:
            current_thresholds['head_angle_threshold'] = float(data['head_angle_threshold'])
            HEAD_ANGLE_THRESHOLD = current_thresholds['head_angle_threshold']
        if 'nod_interval_threshold' in data:
            current_thresholds['nod_interval_threshold'] = float(data['nod_interval_threshold'])
            NOD_INTERVAL_THRESHOLD = current_thresholds['nod_interval_threshold']
        if 'warning_cooldown' in data:
            current_thresholds['warning_cooldown'] = int(data['warning_cooldown'])
            WARNING_COOLDOWN = current_thresholds['warning_cooldown']
        
        return jsonify({"code": 200, "msg": "阈值更新成功", "thresholds": current_thresholds})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)})
    
# ==================== 记录管理接口 ====================
@app.route("/get_records", methods=["POST"])
def get_records():
    try:
        req_data = request.get_json() or {}
        req_type = req_data.get("type", "").strip()
        
        if req_type == "view":
            records = read_fatigue_records()
            return jsonify({"code": 200, "msg": "查询成功", "data": {"records": records}})
        elif req_type == "export":
            result = export_fatigue_records()
            return jsonify({"code": 200 if result["success"] else 500, "msg": result["msg"], "data": {"file_name": result.get("file_name", "")}})
        elif req_type == "reset":
            result = reset_fatigue_records()
            return jsonify({"code": 200 if result else 500, "msg": "重置成功" if result else "重置失败", "data": {}})
        else:
            return jsonify({"code": 400, "msg": f"不支持的请求类型: {req_type}"})
    except Exception as e:
        return jsonify({"code": 500, "msg": str(e)})
    
# ==================== 导出文件下载接口 ====================
@app.route("/download_export/<filename>", methods=["GET"])
def download_export(filename):
    """下载导出的记录文件"""
    try:
        # 安全检查：防止路径遍历攻击
        if '..' in filename or '/' in filename or '\\' in filename:
            return jsonify({"code": 400, "msg": "非法文件名"}), 400
        
        file_path = os.path.join(EXPORT_DIR, filename)
        
        if not os.path.exists(file_path):
            return jsonify({"code": 404, "msg": "文件不存在"}), 404
        
        # 返回文件
        from flask import send_file
        return send_file(file_path, as_attachment=True, download_name=filename)
    
    except Exception as e:
        print(f"下载文件失败: {e}")
        return jsonify({"code": 500, "msg": str(e)}), 500


@app.route("/process_frame", methods=["POST"])
def process_frame():
    global last_nod_time, close_eye_start_time, last_frame_time, error_count
    
    last_frame_time = time.time()
    
    if not is_detecting:
        return jsonify({
            "code": 200,
            "msg": "检测未启动",
            "status": "stopped",
            "warning": None,
            "fatigueData": {},
            "face_box": [],
            "eye_points": [],
            "head_points": []
        })
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({"code": 400, "msg": "无数据"})
        
        shoot_timestamp = float(data.get("shoot_timestamp", time.time()))
        image_base64 = data.get("image_base64", "")
        
        if not image_base64:
            return jsonify({"code": 400, "msg": "无图像数据"})
        
        if "data:image" in image_base64:
            image_base64 = image_base64.split(",")[1]
        
        image_bytes = base64.b64decode(image_base64)
        image_np = np.frombuffer(image_bytes, dtype=np.uint8)
        frame = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
        
        if frame is None:
            error_count += 1
            return jsonify({"code": 400, "msg": "图像解码失败"})
        
        frame = cv2.resize(frame, (640, 480))
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        results = face_mesh.process(rgb_frame)
        
        if not results.multi_face_landmarks:
            return jsonify({
                "code": 200,
                "status": "no_face",
                "warning": None,
                "fatigueData": {
                    "eyelidOpening": 1.0,
                    "headAngle": 0,
                    "isEyeTired": False,
                    "isHeadTired": False,
                    "closeDuration": 0,
                    "nodInterval": 0
                },
                "face_box": [],
                "eye_points": [],
                "head_points": []
            })
        
        face_landmarks = results.multi_face_landmarks[0]
        
        # 计算指标
        head_angle = calculate_head_angle(face_landmarks, frame.shape)
        eyelid_opening = calculate_eyelid_opening(face_landmarks, frame.shape)
        
        # 获取绘制点
        face_box = get_face_box(face_landmarks, frame.shape)
        eye_points = get_eye_points(face_landmarks, frame.shape)
        head_points = get_head_points(face_landmarks, frame.shape)
        
        current_time = shoot_timestamp
        
        # 疲劳检测
        status = "normal"
        is_eye_tired = False
        is_head_tired = False
        close_duration = 0.0
        nod_interval = 0.0
        
        if eyelid_opening < EYELID_THRESHOLD:
            if close_eye_start_time == 0.0:
                close_eye_start_time = current_time
            else:
                close_duration = current_time - close_eye_start_time
                if close_duration >= EYE_CLOSE_DURATION:
                    is_eye_tired = True
        else:
            close_eye_start_time = 0.0
        
        if abs(head_angle) > HEAD_ANGLE_THRESHOLD:
            nod_interval = current_time - last_nod_time
            if last_nod_time != 0.0 and nod_interval < NOD_INTERVAL_THRESHOLD:
                is_head_tired = True
            last_nod_time = current_time
        
        warning_info = None
        if is_eye_tired or is_head_tired:
            status = "tired"
    
        fatigue_data = {
            "eyelidOpening": round(eyelid_opening, 3),
            "headAngle": round(head_angle, 1),
            "closeDuration": round(close_duration, 3),
            "nodInterval": round(nod_interval, 3)
        }
    
        if is_eye_tired and is_head_tired:
            fatigue_type = "both"
            write_fatigue_record("闭眼", close_duration)
            write_fatigue_record("低头", nod_interval)
        elif is_eye_tired:
            fatigue_type = "eye"
            write_fatigue_record("闭眼", close_duration)
        else:
            fatigue_type = "head"
            write_fatigue_record("低头", nod_interval)
    
        # 触发预警（播放声音）
        warning_info = trigger_warning(fatigue_type, fatigue_data)
        
        error_count = 0
        
        return jsonify({
            "code": 200,
            "status": status,
            "warning": warning_info,
            "fatigueData": {
                "eyelidOpening": round(eyelid_opening, 3),
                "headAngle": round(head_angle, 1),
                "isEyeTired": is_eye_tired,
                "isHeadTired": is_head_tired,
                "closeDuration": round(close_duration, 3),
                "nodInterval": round(nod_interval, 3)
            },
            "face_box": face_box,
            "eye_points": eye_points,
            "head_points": head_points
        })
        
    except Exception as e:
        error_count += 1
        print(f"处理帧错误: {e}")
        return jsonify({"code": 500, "msg": str(e)})

# ==================== 启动服务 ====================
if __name__ == "__main__":
    print("=" * 50)
    print("🚗 疲劳检测后端服务启动")
    print("=" * 50)
    print(f"📊 记录文件: {RECORD_FILE_PATH}")
    print(f"📁 导出目录: {EXPORT_DIR}")
    print(f"🎯 MediaPipe: 已初始化")
    print("=" * 50)
    print("🌐 服务地址: http://localhost:5001")
    print("📡 测试接口: http://localhost:5001/test")
    print("=" * 50)
    
    app.run(host="0.0.0.0", port=5001, debug=False, threaded=True)