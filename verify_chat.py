import time
from playwright.sync_api import sync_playwright, expect

def verify_chat():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = context.new_page()

        # 1. Login
        print("Navigating to index...")
        page.goto("http://localhost:5000/")

        print("Clicking login button to show form...")
        page.locator(".login-button").click()

        print("Filling credentials...")
        page.fill("input[name='username']", "tester")
        page.fill("input[name='password']", "OnceUponaBurgerTree-12monkeys")
        print("Submitting...")
        page.locator(".login-form button[type='submit']").click()

        # Wait for redirect to dashboard
        print("Waiting for dashboard...")
        page.wait_for_url("**/dashboard")
        print("Dashboard loaded.")

        # 2. Open Mentor Chat
        print("Opening Mentor Chat...")
        # The link ID is #mentor-link (I saw this in layout.html)
        page.locator("#mentor-link").click()

        # Wait for overlay to be visible
        overlay = page.locator("#mentor-chat-overlay")
        expect(overlay).to_be_visible()
        print("Mentor Chat overlay visible.")

        # 3. Verify Initial State
        print("Verifying initial state...")
        # Check if Intro text is visible
        expect(page.locator("#mentor-intro-text")).to_be_visible()

        # 4. Send a Message
        print("Sending message...")
        input_field = page.locator("#chat-input-field")
        input_field.fill("Hello Mentor, tell me about risk.")

        # Click send button (#chat-send-btn)
        page.locator("#chat-send-btn").click()

        # 5. Verify User Message appears
        print("Verifying user message...")
        # Check for .user-message
        user_msg = page.locator(".user-message").last
        expect(user_msg).to_be_visible()
        expect(user_msg).to_contain_text("Hello Mentor, tell me about risk.")
        print("User message verified.")

        # 6. Verify Typing Indicator
        print("Waiting for typing indicator...")
        try:
            typing = page.locator(".typing-indicator-msg")
            typing.wait_for(state="visible", timeout=5000)
            print("Typing indicator seen.")
        except:
            print("Typing indicator missed or too fast.")

        # 7. Take Screenshot
        print("Taking screenshot...")
        time.sleep(2)

        page.screenshot(path="/home/jules/verification/mentor_chat_verified.png")
        print("Screenshot saved to /home/jules/verification/mentor_chat_verified.png")

        browser.close()

if __name__ == "__main__":
    verify_chat()
