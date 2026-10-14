"""自动生成并校验 requirements.txt"""
import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def run(cmd, check=True):
    cmd_str = " ".join(cmd) if isinstance(cmd, list) else cmd
    print(f"[RUN] {cmd_str}")
    return subprocess.run(cmd_str, check=check, capture_output=True, text=True, shell=True)

def main():
    parser = argparse.ArgumentParser(description="生成项目 requirements.txt")
    parser.add_argument("project", nargs="?", default=".", help="项目目录")
    parser.add_argument("-o", "--output", default=None, help="输出文件路径")
    parser.add_argument("--ignore", default="tests,venv,.venv,docs,build,dist")
    parser.add_argument("--encoding", default="utf8")
    parser.add_argument("--no-pin", action="store_true", help="不固定版本号")
    parser.add_argument("--dry-run", action="store_true", help="仅打印不写入")
    parser.add_argument("--check-pi", action="store_true", help="检查并输出 pi 的版本号")
    args = parser.parse_args()

    # 1. 处理 pi 版本检查
    pi_version = None
    if args.check_pi:
        try:
            result = run(["pi", "--version"], check=False)
            if result.returncode == 0:
                pi_version = result.stdout.strip()
                print(f"[PI VERSION] {pi_version}")
            else:
                print(f"[WARN] {result.stderr.strip()}", file=sys.stderr)
        except FileNotFoundError:
            print("[WARN] 未找到 pi 命令，请确认已安装并配置环境变量。", file=sys.stderr)

    # 2. 处理项目目录和 requirements.txt 生成
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

    # 3. 如果获取到了 pi 版本，将其追加写入到 requirements.txt
    if pi_version:
        with open(output, "a", encoding="utf8") as f:
            f.write(f"\n# pi version: {pi_version}\n")
        print(f"[OK] pi 版本已追加写入：{output}")

    print(f"[OK] 已生成：{output}")
    print("[TIP] 动态导入、Django INSTALLED_APPS 中的第三方 app 可能遗漏，请人工复核。")


if __name__ == "__main__":
    main()
