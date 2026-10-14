"""Skill 标签批量编辑器"""

import re
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

import yaml


SKILL_MD = "SKILL.md"
FRONT_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.S)


def read_skill(path: Path):
    text = path.read_text(encoding="utf-8-sig")
    if not text.startswith("---"):
        return None, text

    m = FRONT_RE.match(text)
    if not m:
        return None, text

    meta = yaml.safe_load(m.group(1)) or {}
    body = m.group(2)
    return meta, body


def write_skill(path: Path, meta: dict, body: str):
    header = yaml.dump(meta, allow_unicode=True, sort_keys=False).rstrip()
    text = f"---\n{header}\n---\n{body}"
    path.write_text(text, encoding="utf-8")


class SkillTagBatchEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Skill 标签批量编辑器")
        self.geometry("1000x640")

        self.skills_dir: Path | None = None
        self.skills: list[dict] = []

        self._build_ui()

    # ---------- UI ----------

    def _build_ui(self):
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)

        ttk.Label(top, text="Skills 目录：").pack(side="left")
        self.dir_var = tk.StringVar()
        dir_entry = ttk.Entry(top, textvariable=self.dir_var, width=50)
        dir_entry.pack(side="left", padx=6)
        ttk.Button(top, text="选择目录", command=self.choose_dir).pack(side="left")
        ttk.Button(top, text="刷新", command=self.refresh).pack(side="left", padx=6)

        columns = ("name", "description", "tags")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=18, selectmode="extended")
        self.tree.heading("name", text="Skill 名称")
        self.tree.heading("description", text="描述")
        self.tree.heading("tags", text="标签")

        self.tree.column("name", width=180)
        self.tree.column("description", width=320)
        self.tree.column("tags", width=400)

        self.tree.pack(fill="both", expand=True, padx=10, pady=6)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=8)

        ttk.Label(bottom, text="标签：").pack(side="left")
        self.tags_var = tk.StringVar()
        tags_entry = ttk.Entry(bottom, textvariable=self.tags_var, width=40)
        tags_entry.pack(side="left", padx=6)

        ttk.Button(bottom, text="追加标签", command=self.batch_append).pack(side="left", padx=4)
        ttk.Button(bottom, text="覆盖标签", command=self.batch_overwrite).pack(side="left", padx=4)
        ttk.Button(bottom, text="清空标签", command=self.batch_clear).pack(side="left", padx=4)
        ttk.Button(bottom, text="保存选中", command=self.save_selected).pack(side="left", padx=12)
        ttk.Button(bottom, text="保存全部", command=self.save_all).pack(side="left", padx=4)

    # ---------- 数据 ----------

    def choose_dir(self):
        d = filedialog.askdirectory(title="选择 Skills 根目录")
        if not d:
            return
        self.skills_dir = Path(d)
        self.dir_var.set(str(self.skills_dir))
        self.refresh()

    def refresh(self):
        if not self.skills_dir or not self.skills_dir.exists():
            messagebox.showwarning("提示", "请先选择有效的 Skills 目录")
            return

        self.skills.clear()
        for item in sorted(self.skills_dir.iterdir()):
            skill_file = item / SKILL_MD
            if not item.is_dir() or not skill_file.exists():
                continue

            meta, body = read_skill(skill_file)
            if not isinstance(meta, dict):
                continue

            name = meta.get("name") or item.name
            desc = meta.get("description") or ""
            tags_raw = meta.get("tags") or []

            if isinstance(tags_raw, str):
                tags = [tags_raw]
            elif isinstance(tags_raw, list):
                tags = [str(t) for t in tags_raw if t]
            else:
                tags = []

            self.skills.append({
                "path": skill_file,
                "name": str(name),
                "description": str(desc),
                "tags": list(tags),
                "meta": meta,
                "body": body,
            })

        self._render_table()

    def _render_table(self):
        for row in self.tree.get_children():
            self.tree.delete(row)

        for s in self.skills:
            tags_text = ", ".join(s["tags"])
            self.tree.insert("", "end", iid=s["name"], values=(s["name"], s["description"], tags_text))

    # ---------- 批量操作 ----------

    def _get_selected_skills(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("提示", "请先选中至少一个 Skill")
            return []

        selected_ids = set(selected)
        return [s for s in self.skills if s["name"] in selected_ids]

    def _parse_tags_input(self):
        raw = self.tags_var.get().strip()
        tags = [t.strip() for t in re.split(r"[,\s]+", raw) if t.strip()]
        if not tags:
            messagebox.showwarning("提示", "请先输入标签，用逗号或空格分隔")
            return []
        return tags

    def batch_append(self):
        new_tags = self._parse_tags_input()
        if not new_tags:
            return

        targets = self._get_selected_skills()
        if not targets:
            return

        for s in targets:
            for t in new_tags:
                if t not in s["tags"]:
                    s["tags"].append(t)
            s["meta"]["tags"] = list(s["tags"])

        self._render_table()

    def batch_overwrite(self):
        new_tags = self._parse_tags_input()
        if not new_tags:
            return

        targets = self._get_selected_skills()
        if not targets:
            return

        for s in targets:
            s["tags"] = list(new_tags)
            s["meta"]["tags"] = list(s["tags"])

        self._render_table()

    def batch_clear(self):
        targets = self._get_selected_skills()
        if not targets:
            return

        for s in targets:
            s["tags"].clear()
            s["meta"]["tags"] = []

        self._render_table()

    # ---------- 保存 ----------

    def save_selected(self):
        targets = self._get_selected_skills()
        if not targets:
            return

        ok = 0
        err = 0
        for s in targets:
            try:
                self._write_one(s)
                ok += 1
            except Exception as e:
                err += 1
                print(f"[保存失败] {s['path']}: {e}")

        messagebox.showinfo("保存结果", f"成功：{ok}\n失败：{err}")

    def save_all(self):
        if not self.skills:
            messagebox.showwarning("提示", "当前没有可保存的 Skill")
            return

        ok = 0
        err = 0
        for s in self.skills:
            try:
                self._write_one(s)
                ok += 1
            except Exception as e:
                err += 1
                print(f"[保存失败] {s['path']}: {e}")

        messagebox.showinfo("保存结果", f"成功：{ok}\n失败：{err}")

    def _write_one(self, skill: dict):
        skill["meta"]["tags"] = skill["tags"]
        write_skill(skill["path"], skill["meta"], skill["body"])


if __name__ == "__main__":
    app = SkillTagBatchEditor()
    app.mainloop()
