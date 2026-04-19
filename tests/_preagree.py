"""预先标记 zhangsan 已同意协议, 跳过 Playwright 协议点击流程."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.db.crud import SysConfigCRUD

SysConfigCRUD.set("agreement_accepted", "true", user_name="zhangsan")
print("zhangsan agreement_accepted = true, 已写入 DB")
print("verify:", SysConfigCRUD.get("agreement_accepted", user_name="zhangsan"))
