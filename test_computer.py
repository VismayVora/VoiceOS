import asyncio
import pyautogui
import subprocess
import time

async def test_mouse():
    print("Testing Mouse Control...")
    
    # 1. Test PyAutoGUI (Get Size)
    try:
        width, height = pyautogui.size()
        print(f"✅ PyAutoGUI Size: {width}x{height}")
    except Exception as e:
        print(f"❌ PyAutoGUI Error: {e}")

    # 2. Test Cliclick (Move Mouse)
    print("\nAttempting to move mouse to 100, 100 using cliclick...")
    try:
        # Check if cliclick is in path
        which = subprocess.run(["which", "cliclick"], capture_output=True, text=True)
        print(f"Cliclick path: {which.stdout.strip()}")
        
        if not which.stdout.strip():
            print("❌ Cliclick not found in PATH!")
            return

        # Try move
        cmd = "cliclick m:100,100"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Cliclick move command executed successfully.")
        else:
            print(f"❌ Cliclick failed: {result.stderr}")
            
    except Exception as e:
        print(f"❌ Cliclick Exception: {e}")

    # 3. Test PyAutoGUI Move (Fallback)
    print("\nAttempting to move mouse to 200, 200 using PyAutoGUI...")
    try:
        pyautogui.moveTo(200, 200)
        print("✅ PyAutoGUI move executed.")
    except Exception as e:
        print(f"❌ PyAutoGUI Move Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_mouse())
