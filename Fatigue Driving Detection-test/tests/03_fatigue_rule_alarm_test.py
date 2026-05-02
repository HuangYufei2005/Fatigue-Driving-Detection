import argparse
from venv_bootstrap import maybe_reexec_into_project_venv

maybe_reexec_into_project_venv()

from fatigue_test_common import DEFAULT_OUTPUT_DIR, run_rule_suite


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="测试3：疲劳判定规则 + 报警逻辑")
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_OUTPUT_DIR))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return run_rule_suite(args)


if __name__ == "__main__":
    raise SystemExit(main())
