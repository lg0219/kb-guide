"""集中读取 config.json。所有可调参数都在这一个文件里。"""
import json, os
from pathlib import Path

BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def load():
    with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as f:
        return json.load(f)

CFG = load()

def path(rel):
    """把 config.json 里的相对路径转成绝对路径（返回 Path）。"""
    p = Path(rel)
    return p if p.is_absolute() else BASE_DIR / p
