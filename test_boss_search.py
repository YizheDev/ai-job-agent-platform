"""Test BOSS crawler search directly"""
import sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from app.utils.boss_crawler import get_crawler

print("=" * 60)
print("BOSS Crawler Search Test")
print("=" * 60)

c = get_crawler()

# Step 1: Launch browser
print("\n[1] Launching browser...")
msg = c.launch(headless=True)
print(f"  Result: {msg}")
print(f"  Running: {c.is_running}")
print(f"  Logged in: {c.is_logged_in}")

if not c.is_running:
    print("  [FAIL] Browser didn't start")
    exit(1)

# Step 2: Check login
if c.is_logged_in:
    print("\n[2] Already logged in via cookies!")
else:
    print("\n[2] Not logged in, checking login...")
    msg = c.check_login()
    print(f"  Check result: {msg}")
    print(f"  Logged in now: {c.is_logged_in}")

if not c.is_logged_in:
    print("  [INFO] Need manual QR scan login, skipping search test")
    c.close()
    exit(0)

# Step 3: Get user profile
print("\n[3] Getting user profile...")
profile = c.get_user_profile()
print(f"  Profile: {profile}")

# Step 4: Search
print("\n[4] Searching for 'Python'...")
jobs = c.search_jobs("Python", city="全国")
print(f"  Found {len(jobs)} jobs")
for i, j in enumerate(jobs[:5]):
    print(f"  [{i+1}] {j['title']} @ {j['company']} | {j['salary']} | {j['area']}")

if not jobs:
    print("  [INFO] No results. Trying 'Java'...")
    jobs = c.search_jobs("Java", city="全国")
    print(f"  Found {len(jobs)} jobs for 'Java'")
    for i, j in enumerate(jobs[:3]):
        print(f"  [{i+1}] {j['title']} @ {j['company']} | {j['salary']}")

# Step 5: Close
print("\n[5] Closing browser...")
msg = c.close()
print(f"  {msg}")

print("\nDone!")
