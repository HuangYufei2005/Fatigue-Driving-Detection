import argparse
from venv_bootstrap import maybe_reexec_into_project_venv

maybe_reexec_into_project_venv()

from fatigue_test_common import DEFAULT_OUTPUT_DIR, run_io_check


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="测试1：摄像头/视频能否正常读入")
    parser.add_argument("--camera", type=int, default=None, help="摄像头索引，例如 0")
    parser.add_argument("--video", type=str, default=None, help="视频文件路径")
    parser.add_argument("--max-frames", type=int, default=30, help="每个输入源最多读取多少帧")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run_io_check(args)


if __name__ == "__main__":
    raise SystemExit(main())
