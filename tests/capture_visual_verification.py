import os
import sys
import time
import socket
import subprocess
from pathlib import Path

ARTIFACTS_DIR = Path(r"C:\Users\FATHIR\.gemini\antigravity\brain\3f74d584-5787-4a7f-bd20-68c3f8dde703")
SCREENSHOTS_DIR = ARTIFACTS_DIR / "screenshots"
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

def wait_for_port(port, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1):
                return True
        except OSError:
            time.sleep(0.5)
    return False

def main():
    backend_proc = None
    frontend_proc = None
    try:
        print("Starting Flask backend on port 5000...")
        backend_env = os.environ.copy()
        backend_env["PORT"] = "5000"
        backend_env["FLASK_HOST"] = "127.0.0.1"
        backend_proc = subprocess.Popen(
            [sys.executable, "app.py"],
            cwd=str(Path(__file__).resolve().parent.parent),
            env=backend_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if not wait_for_port(5000, 20):
            print("Failed to start Flask backend.")
            return 1
        print("Flask backend ready on http://127.0.0.1:5000")

        print("Starting Next.js frontend on port 3000...")
        frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
        frontend_env = os.environ.copy()
        frontend_env["NEXT_PUBLIC_API_URL"] = "http://127.0.0.1:5000"
        frontend_proc = subprocess.Popen(
            ["npx", "next", "start", "-p", "3000"],
            cwd=str(frontend_dir),
            env=frontend_env,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        if not wait_for_port(3000, 30):
            print("Failed to start Next.js frontend.")
            return 1
        print("Next.js frontend ready on http://127.0.0.1:3000")

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)

            # ── 1. Desktop (1280x800) ──────────────────────────
            print("Capturing 1280px Desktop...")
            desktop_context = browser.new_context(viewport={"width": 1280, "height": 800})
            desktop_page = desktop_context.new_page()
            desktop_page.goto("http://127.0.0.1:3000", wait_until="networkidle")
            time.sleep(1)

            # 1a. Desktop Welcome Screen
            p1 = str(SCREENSHOTS_DIR / "1280_welcome.png")
            desktop_page.screenshot(path=p1)
            print(f"Saved: {p1}")

            # 1b. Desktop Chat active
            textarea = desktop_page.locator('textarea[aria-label="Pesan untuk EchaBot"]')
            textarea.fill("Halo EchaBot, tolong jelaskan kemampuan analisis data kamu.")
            desktop_page.locator('button[aria-label="Kirim pesan"]').click()
            time.sleep(3)
            p2 = str(SCREENSHOTS_DIR / "1280_chat.png")
            desktop_page.screenshot(path=p2)
            print(f"Saved: {p2}")
            desktop_context.close()

            # ── 2. Tablet (768x1024) ───────────────────────────
            print("Capturing 768px Tablet...")
            tablet_context = browser.new_context(viewport={"width": 768, "height": 1024})
            tablet_page = tablet_context.new_page()
            tablet_page.goto("http://127.0.0.1:3000", wait_until="networkidle")
            time.sleep(1)

            # 2a. Tablet Welcome
            p3 = str(SCREENSHOTS_DIR / "768_welcome.png")
            tablet_page.screenshot(path=p3)
            print(f"Saved: {p3}")

            # 2b. Tablet Drawer open (clicking hamburger)
            hamburger = tablet_page.locator('button[aria-label="Buka menu navigasi"]')
            hamburger.click()
            time.sleep(0.5)
            p4 = str(SCREENSHOTS_DIR / "768_drawer.png")
            tablet_page.screenshot(path=p4)
            print(f"Saved: {p4}")

            # Close drawer by pressing Escape
            tablet_page.keyboard.press("Escape")
            time.sleep(0.5)

            # 2c. Tablet Chat active
            textarea = tablet_page.locator('textarea[aria-label="Pesan untuk EchaBot"]')
            textarea.fill("Format file apa saja yang didukung?")
            tablet_page.locator('button[aria-label="Kirim pesan"]').click()
            time.sleep(3)
            p5 = str(SCREENSHOTS_DIR / "768_chat.png")
            tablet_page.screenshot(path=p5)
            print(f"Saved: {p5}")
            tablet_context.close()

            # ── 3. Mobile (375x667) ────────────────────────────
            print("Capturing 375px Mobile...")
            mobile_context = browser.new_context(viewport={"width": 375, "height": 667})
            mobile_page = mobile_context.new_page()
            mobile_page.goto("http://127.0.0.1:3000", wait_until="networkidle")
            time.sleep(1)

            # 3a. Mobile Welcome
            p6 = str(SCREENSHOTS_DIR / "375_welcome.png")
            mobile_page.screenshot(path=p6)
            print(f"Saved: {p6}")

            # 3b. Mobile Drawer open
            hamburger = mobile_page.locator('button[aria-label="Buka menu navigasi"]')
            hamburger.click()
            time.sleep(0.5)
            p7 = str(SCREENSHOTS_DIR / "375_drawer.png")
            mobile_page.screenshot(path=p7)
            print(f"Saved: {p7}")

            # Close drawer
            mobile_page.keyboard.press("Escape")
            time.sleep(0.5)

            # 3c. Mobile Chat active
            textarea = mobile_page.locator('textarea[aria-label="Pesan untuk EchaBot"]')
            textarea.fill("Halo dari mobile screen 375px!")
            mobile_page.locator('button[aria-label="Kirim pesan"]').click()
            time.sleep(3)
            p8 = str(SCREENSHOTS_DIR / "375_chat.png")
            mobile_page.screenshot(path=p8)
            print(f"Saved: {p8}")
            mobile_context.close()

            browser.close()
            print("All screenshots successfully captured!")
            return 0

    except Exception as e:
        print(f"Error during visual capture: {e}")
        return 1
    finally:
        print("Cleaning up processes...")
        if frontend_proc:
            try:
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(frontend_proc.pid)])
            except Exception:
                frontend_proc.kill()
        if backend_proc:
            try:
                subprocess.call(["taskkill", "/F", "/T", "/PID", str(backend_proc.pid)])
            except Exception:
                backend_proc.kill()

if __name__ == "__main__":
    sys.exit(main())
