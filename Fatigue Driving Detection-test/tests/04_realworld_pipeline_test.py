import argparse
import sys
from venv_bootstrap import maybe_reexec_into_project_venv

maybe_reexec_into_project_venv()

from fatigue_test_common import DEFAULT_BASE_URL, DEFAULT_OUTPUT_DIR, run_realworld_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="测试4：真实环境/实车全流程跑通")
    parser.add_argument("--camera", type=int, default=0, help="摄像头索引")
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL, help="后端地址")
    parser.add_argument("--spawn-backend", action="store_true", help="若后端未启动，则自动拉起 app.py")
    parser.add_argument("--python-exec", type=str, default=sys.executable, help="拉起后端时使用的 Python")
    parser.add_argument("--frame-interval-ms", type=int, default=100, help="送帧间隔，默认 100ms")
    parser.add_argument("--duration-sec", type=float, default=60.0, help="采集时长（秒）")
    parser.add_argument("--max-frames", type=int, default=None, help="最多发送多少帧")
    parser.add_argument("--truth", type=str, default=None, help="ground truth JSON 路径")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run_realworld_pipeline(args)


if __name__ == "__main__":
    raise SystemExit(main())
