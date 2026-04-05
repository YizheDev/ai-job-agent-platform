"""Check BOSS cookies"""
from app.utils.security_util import load_cookie

cookies = load_cookie("boss_zhipin")
if cookies:
    print(f"Found {len(cookies)} BOSS cookies")
    for c in cookies[:3]:
        name = c.get("name", "?")
        val = str(c.get("value", ""))[:20]
        print(f"  {name} = {val}...")
else:
    print("No BOSS cookies found")
