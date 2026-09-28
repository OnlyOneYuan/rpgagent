# 自动化脚本
"""自动生成并校验 requirements.txt"""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run(cmd, check=True):
    print(f"[RUN] {' '.join(cmd)}")
    return subprocess.run(cmd, check=check, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description="生成项目 requirements.txt")
    parser.add_argument("project", nargs="?", default=".", help="项目目录")
    parser.add_argument("-o", "--output", default=None, help="输出文件路径")
    parser.add_argument("--ignore", default="tests,venv,.venv,docs,build,dist")
    parser.add_argument("--encoding", default="utf8")
    parser.add_argument("--no-pin", action="store_true", help="不固定版本号")
    parser.add_argument("--dry-run", action="store_true", help="仅打印不写入")
    args = parser.parse_args()

    project = Path(args.project).resolve()
    output = Path(args.output) if args.output else project / "requirements.txt"

    if not project.is_dir():
        sys.exit(f"[ERROR] 目录不存在：{project}")

    cmd = ["pipreqs", str(project), "--ignore", args.ignore,
           "--encoding", args.encoding, "--force"]
    if args.no_pin:
        cmd.append("--mode=no-pin")
    if args.dry_run:
        cmd.append("--print")
    else:
        cmd += ["--savepath", str(output)]

    try:
        result = run(cmd, check=False)
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr)
            sys.exit(f"[ERROR] pipreqs 执行失败，可用 --debug 定位问题文件")
        if args.dry_run:
            print(result.stdout)
            return
    except FileNotFoundError:
        sys.exit("[ERROR] 未找到 pipreqs，请先 pip install pipreqs")

    # 备份
    # if output.exists():
    #     backup = output.with_suffix(f".bak.{datetime.now():%Y%m%d%H%M%S}")
    #     output.rename(backup)
    #     print(f"[INFO] 旧文件已备份至 {backup}")

    print(f"[OK] 已生成：{output}")
    print("[TIP] 动态导入、Django INSTALLED_APPS 中的第三方 app 可能遗漏，请人工复核。")


if __name__ == "__main__":
    main()