import argparse
import base64
import builtins
import contextlib
import importlib
import io
import json
import os
import types
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
import requests


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:5001"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "test_outputs"


def now_slug() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(path: Path, data: Any) -> None:
    ensure_dir(path.parent)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def print_section(title: str) -> None:
    print(f"\n{'=' * 20} {title} {'=' * 20}")


def open_camera(camera_index: int) -> cv2.VideoCapture:
    if os.name == "nt":
        cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if cap.isOpened():
            return cap
    return cv2.VideoCapture(camera_index)


def encode_frame_to_base64(frame: np.ndarray, quality: int = 80) -> str:
    ok, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), quality])
    if not ok:
        raise RuntimeError("OpenCV JPEG 编码失败")
    return base64.b64encode(buf.tobytes()).decode("utf-8")


def make_dummy_frame() -> np.ndarray:
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(
        frame,
        "fatigue-test",
        (160, 240),
        cv2.FONT_HERSHEY_SIMPLEX,
        1.2,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )
    return frame


def inspect_capture(
    cap: cv2.VideoCapture,
    source_name: str,
    max_frames: int,
    warmup_frames: int = 5,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "source": source_name,
        "opened": cap.isOpened(),
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0),
        "fps": float(cap.get(cv2.CAP_PROP_FPS) or 0.0),
        "frames_attempted": 0,
        "frames_read": 0,
        "success_rate": 0.0,
        "mean_brightness": None,
        "pass": False,
        "message": "",
    }

    if not cap.isOpened():
        result["message"] = "无法打开输入源"
        return result

    brightness_values: List[float] = []
    attempted = 0
    read_ok = 0

    for _ in range(max(0, warmup_frames)):
        cap.read()

    for _ in range(max_frames):
        attempted += 1
        ok, frame = cap.read()
        if not ok or frame is None:
            continue
        read_ok += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness_values.append(float(gray.mean()))

    result["frames_attempted"] = attempted
    result["frames_read"] = read_ok
    result["success_rate"] = round(read_ok / attempted, 4) if attempted else 0.0
    result["mean_brightness"] = round(statistics.mean(brightness_values), 2) if brightness_values else None
    result["pass"] = read_ok > 0 and result["success_rate"] >= 0.6
    result["message"] = "读入正常" if result["pass"] else "可打开但稳定读帧失败"
    return result


def run_io_check(args: argparse.Namespace) -> int:
    print_section("输入链路检查")
    reports: List[Dict[str, Any]] = []

    if args.camera is not None:
        cap = open_camera(args.camera)
        try:
            reports.append(inspect_capture(cap, f"camera:{args.camera}", args.max_frames))
        finally:
            cap.release()

    if args.video:
        video_path = Path(args.video).expanduser().resolve()
        cap = cv2.VideoCapture(str(video_path))
        try:
            report = inspect_capture(cap, f"video:{video_path}", args.max_frames, warmup_frames=0)
            report["exists"] = video_path.exists()
            reports.append(report)
        finally:
            cap.release()

    if not reports:
        raise SystemExit("至少传入 --camera 或 --video 之一")

    overall_pass = all(item.get("pass") for item in reports)
    for item in reports:
        print(json.dumps(item, ensure_ascii=False, indent=2))

    output_dir = ensure_dir(Path(args.output_dir))
    report_path = output_dir / f"io_check_{now_slug()}.json"
    save_json(report_path, {"overall_pass": overall_pass, "reports": reports})
    print(f"\n报告已保存: {report_path}")
    return 0 if overall_pass else 1


def http_get_json(session: requests.Session, url: str, timeout: float = 5.0) -> Dict[str, Any]:
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def http_post_json(
    session: requests.Session,
    url: str,
    payload: Dict[str, Any],
    timeout: float = 15.0,
) -> Dict[str, Any]:
    resp = session.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def wait_for_backend(base_url: str, timeout_sec: float = 30.0) -> bool:
    session = requests.Session()
    deadline = time.time() + timeout_sec
    health_url = f"{base_url.rstrip('/')}/health"
    while time.time() < deadline:
        try:
            data = http_get_json(session, health_url, timeout=2.0)
            if data.get("code") == 200:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def maybe_start_backend(
    base_url: str,
    spawn_backend: bool,
    python_exec: str,
) -> Optional[subprocess.Popen]:
    if wait_for_backend(base_url, timeout_sec=2.0):
        print("后端已在线，复用当前服务。")
        return None

    if not spawn_backend:
        raise RuntimeError("后端未启动。请先运行 python app.py，或使用 --spawn-backend")

    print("后端未在线，开始拉起 app.py ...")
    process = subprocess.Popen(
        [python_exec, "app.py"],
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not wait_for_backend(base_url, timeout_sec=30.0):
        process.kill()
        raise RuntimeError("后端启动失败。")

    print("后端启动成功。")
    return process


def valid_face_box(data: Dict[str, Any]) -> bool:
    box = data.get("face_box") or []
    return isinstance(box, list) and len(box) == 4 and box[2] > 0 and box[3] > 0


def frame_predictions(data: Dict[str, Any], thresholds: Dict[str, Any]) -> Dict[str, Any]:
    fatigue_data = data.get("fatigueData") or {}
    eyelid = fatigue_data.get("eyelidOpening")
    head_angle = fatigue_data.get("headAngle")

    return {
        "face": data.get("status") != "no_face" and valid_face_box(data),
        "eye_closed": isinstance(eyelid, (int, float)) and eyelid < float(thresholds.get("eyelid_threshold", 0.25)),
        "nod": isinstance(head_angle, (int, float)) and abs(head_angle) > float(thresholds.get("head_angle_threshold", 15)),
        "fatigue": data.get("status") == "tired",
        "yawn_supported": "mouthOpening" in fatigue_data or "isYawnTired" in fatigue_data or "yawn" in data,
    }


def summarise_replay_events(events: List[Dict[str, Any]], thresholds: Dict[str, Any]) -> Dict[str, Any]:
    statuses = Counter()
    warning_count = 0
    face_count = 0
    eyelids: List[float] = []
    head_angles: List[float] = []
    request_failures = 0

    for event in events:
        data = event.get("response")
        if not isinstance(data, dict):
            request_failures += 1
            continue

        statuses[data.get("status", "unknown")] += 1
        if data.get("warning"):
            warning_count += 1
        if valid_face_box(data):
            face_count += 1

        fatigue_data = data.get("fatigueData") or {}
        eyelid = fatigue_data.get("eyelidOpening")
        head_angle = fatigue_data.get("headAngle")
        if isinstance(eyelid, (int, float)):
            eyelids.append(float(eyelid))
        if isinstance(head_angle, (int, float)):
            head_angles.append(abs(float(head_angle)))

    supported_yawn = any(
        frame_predictions(event.get("response", {}), thresholds).get("yawn_supported")
        for event in events
        if isinstance(event.get("response"), dict)
    )

    total = len(events)
    return {
        "frames_total": total,
        "request_failures": request_failures,
        "statuses": dict(statuses),
        "warning_count": warning_count,
        "face_detected_frames": face_count,
        "face_detect_rate": round(face_count / total, 4) if total else 0.0,
        "eyelid_opening_avg": round(statistics.mean(eyelids), 4) if eyelids else None,
        "eyelid_opening_min": round(min(eyelids), 4) if eyelids else None,
        "head_angle_abs_avg": round(statistics.mean(head_angles), 4) if head_angles else None,
        "head_angle_abs_max": round(max(head_angles), 4) if head_angles else None,
        "capability_matrix": {
            "face_detection": True,
            "eye_detection": True,
            "nod_detection": True,
            "yawn_detection": supported_yawn,
            "yawn_detection_note": None if supported_yawn else "当前后端返回字段中没有打哈欠/嘴部开合相关输出，测试会标记为 unsupported。",
        },
    }


def confusion_metrics(truths: List[bool], preds: List[bool]) -> Dict[str, Any]:
    tp = sum(1 for t, p in zip(truths, preds) if t and p)
    tn = sum(1 for t, p in zip(truths, preds) if (not t) and (not p))
    fp = sum(1 for t, p in zip(truths, preds) if (not t) and p)
    fn = sum(1 for t, p in zip(truths, preds) if t and (not p))
    total = len(truths)
    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    accuracy = (tp + tn) / total if total else None
    f1 = (2 * precision * recall / (precision + recall)) if (precision is not None and recall is not None and precision + recall) else None
    return {
        "samples": total,
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "accuracy": round(accuracy, 4) if accuracy is not None else None,
        "precision": round(precision, 4) if precision is not None else None,
        "recall": round(recall, 4) if recall is not None else None,
        "f1": round(f1, 4) if f1 is not None else None,
    }


def load_ground_truth(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if not path:
        return None
    truth_path = Path(path).expanduser().resolve()
    return json.loads(truth_path.read_text(encoding="utf-8"))


def label_for_offset(truth: Dict[str, Any], offset_sec: float) -> Optional[Dict[str, Any]]:
    for seg in truth.get("segments", []):
        if seg["start_sec"] <= offset_sec < seg["end_sec"]:
            return seg
    return None


def evaluate_against_ground_truth(
    events: List[Dict[str, Any]],
    thresholds: Dict[str, Any],
    truth: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not truth:
        return None

    buckets: Dict[str, Dict[str, List[bool]]] = {
        "face": {"truth": [], "pred": []},
        "eye_closed": {"truth": [], "pred": []},
        "nod": {"truth": [], "pred": []},
        "fatigue": {"truth": [], "pred": []},
    }
    yawn_requested = False

    for event in events:
        data = event.get("response")
        if not isinstance(data, dict):
            continue

        label = label_for_offset(truth, float(event.get("source_offset_sec", 0.0)))
        if not label:
            continue

        preds = frame_predictions(data, thresholds)
        for key in buckets:
            if key in label:
                buckets[key]["truth"].append(bool(label[key]))
                buckets[key]["pred"].append(bool(preds[key]))

        if "yawn" in label:
            yawn_requested = True

    report = {"metrics": {}}
    for key, bucket in buckets.items():
        if bucket["truth"]:
            report["metrics"][key] = confusion_metrics(bucket["truth"], bucket["pred"])
        else:
            report["metrics"][key] = {"samples": 0, "note": "ground truth 中未提供该标签"}

    report["metrics"]["yawn"] = {
        "supported": False,
        "samples": 0,
        "note": "当前项目未输出打哈欠/嘴部张开检测结果，无法对 yawn 做真值比对。"
        if yawn_requested
        else "ground truth 未要求 yawn，且当前项目也无 yawn 输出。",
    }
    return report


def replay_source(
    source_kind: str,
    source_value: Any,
    base_url: str,
    frame_interval_ms: int,
    duration_sec: Optional[float],
    max_frames: Optional[int],
    output_dir: Path,
) -> Dict[str, Any]:
    session = requests.Session()
    thresholds = http_get_json(session, f"{base_url.rstrip('/')}/get_thresholds").get("thresholds", {})
    http_post_json(session, f"{base_url.rstrip('/')}/start_detection", {"action": "start"})

    if source_kind == "camera":
        cap = open_camera(int(source_value))
    else:
        cap = cv2.VideoCapture(str(source_value))

    if not cap.isOpened():
        raise RuntimeError(f"无法打开输入源: {source_kind}={source_value}")

    events: List[Dict[str, Any]] = []
    capture_started = time.time()
    monotonic_started = time.monotonic()
    last_sent_offset = -999.0
    frame_index = 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break

            frame_index += 1

            if source_kind == "camera":
                source_offset_sec = time.monotonic() - monotonic_started
                shoot_timestamp = time.time()
            else:
                source_offset_sec = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
                shoot_timestamp = capture_started + source_offset_sec

            if duration_sec is not None and source_offset_sec > duration_sec:
                break
            if max_frames is not None and frame_index > max_frames:
                break
            if source_offset_sec - last_sent_offset < frame_interval_ms / 1000.0:
                continue

            last_sent_offset = source_offset_sec
            payload = {
                "image_base64": encode_frame_to_base64(frame),
                "shoot_timestamp": shoot_timestamp,
            }

            t0 = time.perf_counter()
            try:
                data = http_post_json(session, f"{base_url.rstrip('/')}/process_frame", payload, timeout=20.0)
                error = None
            except Exception as exc:
                data = None
                error = str(exc)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0

            events.append(
                {
                    "frame_index": frame_index,
                    "source_offset_sec": round(source_offset_sec, 4),
                    "shoot_timestamp": round(shoot_timestamp, 4),
                    "response_time_ms": round(elapsed_ms, 2),
                    "response": data,
                    "error": error,
                }
            )

            sent_count = len(events)
            if sent_count == 1 or sent_count % 50 == 0:
                status = data.get("status") if isinstance(data, dict) else "request_error"
                print(
                    f"[进度] 已发送 {sent_count} 帧 | 原视频时间 {source_offset_sec:.1f}s | "
                    f"当前状态 {status} | 单帧耗时 {elapsed_ms:.2f} ms"
                )
    finally:
        cap.release()
        with contextlib.suppress(Exception):
            http_post_json(session, f"{base_url.rstrip('/')}/start_detection", {"action": "stop"})

    summary = summarise_replay_events(events, thresholds)
    output_dir = ensure_dir(output_dir)
    raw_path = output_dir / f"replay_events_{now_slug()}.json"
    save_json(
        raw_path,
        {
            "source_kind": source_kind,
            "source_value": str(source_value),
            "thresholds": thresholds,
            "summary": summary,
            "events": events,
        },
    )
    return {"thresholds": thresholds, "summary": summary, "events": events, "raw_report_path": str(raw_path)}


def run_replay(args: argparse.Namespace, force_camera: bool = False) -> int:
    print_section("后端回放/联调测试")
    base_url = args.base_url.rstrip("/")
    backend_proc = maybe_start_backend(base_url, args.spawn_backend, args.python_exec)

    try:
        if force_camera:
            source_kind = "camera"
            source_value = args.camera
        elif args.video:
            source_kind = "video"
            source_value = Path(args.video).expanduser().resolve()
        elif args.camera is not None:
            source_kind = "camera"
            source_value = args.camera
        else:
            raise SystemExit("replay/realworld 需要 --camera 或 --video")

        output_dir = ensure_dir(Path(args.output_dir))
        replay_report = replay_source(
            source_kind=source_kind,
            source_value=source_value,
            base_url=base_url,
            frame_interval_ms=args.frame_interval_ms,
            duration_sec=args.duration_sec,
            max_frames=args.max_frames,
            output_dir=output_dir,
        )

        truth = load_ground_truth(args.truth)
        eval_report = evaluate_against_ground_truth(replay_report["events"], replay_report["thresholds"], truth)

        final_report = {
            "mode": "realworld" if force_camera else "replay",
            "base_url": base_url,
            "source_kind": source_kind,
            "source_value": str(source_value),
            "summary": replay_report["summary"],
            "ground_truth_report": eval_report,
            "raw_report_path": replay_report["raw_report_path"],
        }

        report_path = output_dir / f"{final_report['mode']}_summary_{now_slug()}.json"
        save_json(report_path, final_report)

        print(json.dumps(final_report, ensure_ascii=False, indent=2))
        print(f"\n报告已保存: {report_path}")

        capability = final_report["summary"]["capability_matrix"]
        ok = final_report["summary"]["frames_total"] > 0 and final_report["summary"]["request_failures"] == 0
        if not capability["yawn_detection"]:
            print("\n注意: 当前项目不具备打哈欠检测输出，脚本会明确标记为 unsupported。")
        return 0 if ok else 1
    finally:
        if backend_proc is not None:
            with contextlib.suppress(Exception):
                backend_proc.terminate()
                backend_proc.wait(timeout=10)


def run_detection_accuracy(args: argparse.Namespace) -> int:
    return run_replay(args, force_camera=False)


def run_realworld_pipeline(args: argparse.Namespace) -> int:
    return run_replay(args, force_camera=True)


@dataclass
class ScenarioResult:
    name: str
    passed: bool
    detail: str
    response: Optional[Dict[str, Any]] = None


class FakeFaceMesh:
    def __init__(self, state: Dict[str, Any]):
        self.state = state

    def process(self, _rgb_frame: np.ndarray) -> SimpleNamespace:
        if self.state.get("has_face", True):
            return SimpleNamespace(multi_face_landmarks=[SimpleNamespace(landmark=[])])
        return SimpleNamespace(multi_face_landmarks=None)


class _MediaPipeImportStubFaceMesh:
    def __init__(self, *args, **kwargs):
        pass

    def process(self, _rgb_frame: np.ndarray) -> SimpleNamespace:
        return SimpleNamespace(multi_face_landmarks=None)


def install_mediapipe_stub() -> None:
    for key in list(sys.modules.keys()):
        if key == "mediapipe" or key.startswith("mediapipe."):
            sys.modules.pop(key, None)
    mp_module = types.ModuleType("mediapipe")
    solutions_module = types.SimpleNamespace()
    face_mesh_module = types.SimpleNamespace(FaceMesh=_MediaPipeImportStubFaceMesh)
    solutions_module.face_mesh = face_mesh_module
    mp_module.solutions = solutions_module
    sys.modules["mediapipe"] = mp_module


def import_app_silently():
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return importlib.import_module("app")


def ensure_usable_mediapipe(allow_mediapipe_stub: bool = False) -> None:
    if not allow_mediapipe_stub:
        return

    try:
        import mediapipe as mp  # type: ignore
        if not hasattr(mp, "solutions") or not hasattr(mp.solutions, "face_mesh"):
            install_mediapipe_stub()
    except Exception:
        install_mediapipe_stub()


def import_app_module(allow_mediapipe_stub: bool = False):
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    ensure_usable_mediapipe(allow_mediapipe_stub=allow_mediapipe_stub)
    if "app" in sys.modules:
        return importlib.reload(sys.modules["app"])
    try:
        return import_app_silently()
    except ModuleNotFoundError as exc:
        if allow_mediapipe_stub and exc.name == "mediapipe":
            install_mediapipe_stub()
            return import_app_silently()
        raise


def reset_app_state(app_mod: Any, temp_record_file: Path, temp_export_dir: Path) -> None:
    app_mod.RECORD_FILE_PATH = str(temp_record_file)
    app_mod.EXPORT_DIR = str(temp_export_dir)
    Path(app_mod.RECORD_FILE_PATH).parent.mkdir(parents=True, exist_ok=True)
    Path(app_mod.EXPORT_DIR).mkdir(parents=True, exist_ok=True)
    app_mod.is_detecting = True
    app_mod.last_nod_time = 0.0
    app_mod.close_eye_start_time = 0.0
    app_mod.error_count = 0
    app_mod.last_frame_time = time.time()
    app_mod.last_warning_time = 0.0
    app_mod.warning_active = False
    app_mod.EYELID_THRESHOLD = 0.25
    app_mod.EYE_CLOSE_DURATION = 0.3
    app_mod.HEAD_ANGLE_THRESHOLD = 15
    app_mod.NOD_INTERVAL_THRESHOLD = 0.8
    app_mod.WARNING_COOLDOWN = 3
    app_mod.current_thresholds = {
        "eyelid_threshold": 0.25,
        "eye_close_duration": 0.3,
        "head_angle_threshold": 15,
        "nod_interval_threshold": 0.8,
        "warning_cooldown": 3,
    }


def build_test_payload(ts: float) -> Dict[str, Any]:
    return {
        "image_base64": encode_frame_to_base64(make_dummy_frame()),
        "shoot_timestamp": ts,
    }


def call_process_frame(client: Any, ts: float) -> Tuple[int, Dict[str, Any]]:
    response = client.post("/process_frame", json=build_test_payload(ts))
    return response.status_code, response.get_json()


def run_rule_suite(args: argparse.Namespace) -> int:
    print_section("规则/报警逻辑测试")
    app_mod = import_app_module(allow_mediapipe_stub=True)
    output_dir = ensure_dir(Path(args.output_dir))

    state = {
        "has_face": True,
        "eyelid": 0.6,
        "head_angle": 0.0,
        "face_box": [100, 100, 200, 200],
        "eye_points": [[120, 140], [130, 140], [320, 140], [330, 140]],
        "head_points": [[200, 80], [200, 300]],
    }

    app_mod.face_mesh = FakeFaceMesh(state)
    app_mod.calculate_eyelid_opening = lambda _lm, _shape: state["eyelid"]
    app_mod.calculate_head_angle = lambda _lm, _shape: state["head_angle"]
    app_mod.get_face_box = lambda _lm, _shape: state["face_box"]
    app_mod.get_eye_points = lambda _lm, _shape: state["eye_points"]
    app_mod.get_head_points = lambda _lm, _shape: state["head_points"]
    app_mod.play_warning_sound = lambda: None

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        temp_record_file = tmp_dir_path / "records" / "fatigue_records.txt"
        temp_export_dir = tmp_dir_path / "exports"
        reset_app_state(app_mod, temp_record_file, temp_export_dir)

        client = app_mod.app.test_client()
        results: List[ScenarioResult] = []
        original_print = builtins.print
        builtins.print = lambda *args, **kwargs: None

        try:
            def add(name: str, passed: bool, detail: str, response: Optional[Dict[str, Any]] = None) -> None:
                results.append(ScenarioResult(name=name, passed=passed, detail=detail, response=response))

            stop_resp = client.post("/start_detection", json={"action": "stop"}).get_json()
            start_resp = client.post("/start_detection", json={"action": "start"}).get_json()
            add(
                "start_stop_endpoint",
                stop_resp.get("isDetecting") is False and start_resp.get("isDetecting") is True,
                f"stop={stop_resp}, start={start_resp}",
            )

            update_payload = {
                "eyelid_threshold": 0.28,
                "eye_close_duration": 0.35,
                "head_angle_threshold": 12,
                "nod_interval_threshold": 0.7,
                "warning_cooldown": 4,
            }
            update_resp = client.post("/update_thresholds", json=update_payload).get_json()
            get_resp = client.get("/get_thresholds").get_json()
            threshold_ok = get_resp.get("thresholds") == update_resp.get("thresholds")
            add("threshold_update_endpoint", threshold_ok, f"update={update_resp}, get={get_resp}")

            reset_app_state(app_mod, temp_record_file, temp_export_dir)

            app_mod.is_detecting = False
            code, data = call_process_frame(client, 1.0)
            add(
                "process_frame_stopped",
                code == 200 and data.get("status") == "stopped",
                f"code={code}, data={data}",
                data,
            )

            reset_app_state(app_mod, temp_record_file, temp_export_dir)
            state["has_face"] = False
            code, data = call_process_frame(client, 2.0)
            add(
                "no_face_case",
                code == 200 and data.get("status") == "no_face" and not data.get("warning"),
                f"code={code}, data={data}",
                data,
            )

            reset_app_state(app_mod, temp_record_file, temp_export_dir)
            state["has_face"] = True
            state["eyelid"] = 0.6
            state["head_angle"] = 0.0
            code, data = call_process_frame(client, 3.0)
            add(
                "normal_case",
                code == 200 and data.get("status") == "normal" and valid_face_box(data),
                f"code={code}, data={data}",
                data,
            )

            reset_app_state(app_mod, temp_record_file, temp_export_dir)
            state["eyelid"] = 0.1
            state["head_angle"] = 0.0
            call_process_frame(client, 10.0)
            code, data = call_process_frame(client, 10.35)
            add(
                "eye_fatigue_rule",
                code == 200
                and data.get("status") == "tired"
                and data.get("fatigueData", {}).get("isEyeTired") is True
                and (data.get("warning") or {}).get("type") == "eye",
                f"code={code}, data={data}",
                data,
            )

            reset_app_state(app_mod, temp_record_file, temp_export_dir)
            state["eyelid"] = 0.6
            state["head_angle"] = 20.0
            call_process_frame(client, 20.0)
            code, data = call_process_frame(client, 20.5)
            add(
                "head_fatigue_rule",
                code == 200
                and data.get("status") == "tired"
                and data.get("fatigueData", {}).get("isHeadTired") is True
                and (data.get("warning") or {}).get("type") == "head",
                f"code={code}, data={data}",
                data,
            )

            reset_app_state(app_mod, temp_record_file, temp_export_dir)
            state["eyelid"] = 0.1
            state["head_angle"] = 20.0
            app_mod.close_eye_start_time = 29.6
            app_mod.last_nod_time = 29.7
            code, data = call_process_frame(client, 30.0)
            add(
                "both_fatigue_rule",
                code == 200
                and data.get("status") == "tired"
                and data.get("fatigueData", {}).get("isEyeTired") is True
                and data.get("fatigueData", {}).get("isHeadTired") is True
                and (data.get("warning") or {}).get("type") == "both",
                f"code={code}, data={data}",
                data,
            )

            reset_app_state(app_mod, temp_record_file, temp_export_dir)
            state["eyelid"] = 0.1
            state["head_angle"] = 0.0
            app_mod.close_eye_start_time = 39.6
            app_mod.last_warning_time = time.time()
            code, data = call_process_frame(client, 40.0)
            add(
                "warning_cooldown",
                code == 200 and data.get("status") == "tired" and data.get("warning") is None,
                f"code={code}, data={data}",
                data,
            )

            record_lines = []
            if temp_record_file.exists():
                record_lines = [line.strip() for line in temp_record_file.read_text(encoding="utf-8").splitlines() if line.strip()]
            add(
                "record_write",
                len(record_lines) >= 4,
                f"record_lines={len(record_lines)}, sample={record_lines[:3]}",
                {"record_lines": record_lines[:10]},
            )
        finally:
            builtins.print = original_print

        report = {
            "generated_at": datetime.now().isoformat(),
            "results": [
                {
                    "name": item.name,
                    "passed": item.passed,
                    "detail": item.detail,
                    "response": item.response,
                }
                for item in results
            ],
            "summary": {
                "total": len(results),
                "passed": sum(1 for item in results if item.passed),
                "failed": sum(1 for item in results if not item.passed),
                "unsupported_checks": [
                    {
                        "name": "yawn_detection",
                        "supported": False,
                        "reason": "当前 app.py 没有嘴部关键点/打哈欠阈值/打哈欠报警输出，因此不能做有效自动化判定。",
                    }
                ],
            },
        }

        report_path = output_dir / f"rule_suite_{now_slug()}.json"
        save_json(report_path, report)

        for item in results:
            status = "PASS" if item.passed else "FAIL"
            print(f"[{status}] {item.name}: {item.detail}")

        print(f"\n报告已保存: {report_path}")
        print("注意: yawn_detection 已单独标记为 unsupported（项目本身未实现）。")

        return 0 if all(item.passed for item in results) else 1
