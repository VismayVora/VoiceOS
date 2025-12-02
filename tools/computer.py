import asyncio
import base64
import shlex
import pyautogui
from pathlib import Path
from typing import Literal, TypedDict
from uuid import uuid4

from .base import BaseAnthropicTool, ToolError, ToolResult
from .run import run

OUTPUT_DIR = "/tmp/outputs"
TYPING_DELAY_MS = 2
TYPING_GROUP_SIZE = 50

# UPDATED: Added new actions supported by Claude 4.5 (20250124)
Action = Literal[
    "key",
    "type",
    "mouse_move",
    "left_click",
    "left_click_drag",
    "right_click",
    "middle_click",
    "double_click",
    "triple_click", # New
    "screenshot",
    "cursor_position",
    "wait",      # New
    "scroll",    # New
]

class Resolution(TypedDict):
    width: int
    height: int

MAX_SCALING_TARGETS: dict[str, Resolution] = {
    "XGA": Resolution(width=1024, height=768),
    "WXGA": Resolution(width=1280, height=800),
    "FWXGA": Resolution(width=1366, height=768),
}
SCALE_DESTINATION = MAX_SCALING_TARGETS["FWXGA"]

class ComputerTool(BaseAnthropicTool):
    name: Literal["computer"] = "computer"
    api_type: Literal["computer_20250124"] = "computer_20250124"
    width: int
    height: int
    display_num: int | None

    # Reduced delay for zippier performance
    _screenshot_delay = 0.1 
    _scaling_enabled = True

    @property
    def options(self):
        return {
            "display_width_px": self.width,
            "display_height_px": self.height,
            "display_number": self.display_num,
        }

    def to_params(self):
        return {"name": self.name, "type": self.api_type, **self.options}

    def __init__(self):
        super().__init__()
        self.width, self.height = pyautogui.size()
        self.display_num = None

    async def __call__(
        self,
        *,
        action: Action,
        text: str | None = None,
        coordinate: list[int] | None = None,
        duration: int | float | None = None, # New param for 'wait'
        **kwargs,
    ):
        print(f"Action: {action} {text} {coordinate}")
        
        # --- Handle 'wait' ---
        if action == "wait":
            if duration is None:
                # Default wait if not provided
                duration = 1.0 
            await asyncio.sleep(duration)
            return ToolResult(output=f"Waited {duration} seconds")

        # --- Handle Mouse Movements ---
        if action in ("mouse_move", "left_click_drag"):
            if coordinate is None:
                raise ToolError(f"coordinate is required for {action}")
            
            x, y = self.scale_coordinates(coordinate[0], coordinate[1])

            if action == "mouse_move":
                return await self.shell(f"cliclick m:{x},{y}")
            elif action == "left_click_drag":
                return await self.shell(f"cliclick dd:{x},{y}")

        # --- Handle Scroll ---
        if action == "scroll":
            # Move to location first if provided
            if coordinate is not None:
                x, y = self.scale_coordinates(coordinate[0], coordinate[1])
                await self.shell(f"cliclick m:{x},{y}")
            
            # Determine scroll amount and direction
            # Default to down if not specified
            direction = kwargs.get('scroll_direction', 'down')
            amount = kwargs.get('scroll_amount', 10) # Default amount
            
            if not isinstance(amount, int):
                amount = 10
                
            # pyautogui scroll: positive is up, negative is down
            clicks = amount if direction == 'up' else -amount
            
            # Scale for smoother/more noticeable scroll? 
            # pyautogui.scroll unit varies by OS. On Mac it's often small.
            # Let's multiply by 10 to make it significant.
            clicks = clicks * 10
            
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: pyautogui.scroll(clicks)
                )
                # Take screenshot after scroll
                await asyncio.sleep(self._screenshot_delay)
                screenshot_base64 = (await self.screenshot()).base64_image
                return ToolResult(output=f"Scrolled {direction} by {amount}", base64_image=screenshot_base64)
            except Exception as e:
                return ToolResult(error=str(e))

        # --- Handle Key Presses (UPDATED to use cliclick instead of keyboard lib) ---
        if action in ("key", "type"):
            if text is None:
                raise ToolError(f"text is required for {action}")

            if action == "key":
                # Map common key names to pyautogui format
                key_map = {
                    "command": "command", "cmd": "command", "control": "ctrl", "ctrl": "ctrl",
                    "shift": "shift", "alt": "alt", "option": "alt",
                    "return": "enter", "enter": "enter", "escape": "esc", 
                    "space": "space", "tab": "tab", "backspace": "backspace",
                    "up": "up", "down": "down", 
                    "left": "left", "right": "right"
                }

                try:
                    if "+" in text:
                        # Handle combinations like "cmd+space"
                        keys = text.split("+")
                        mapped_keys = [key_map.get(k.strip().lower(), k.strip().lower()) for k in keys]
                        # pyautogui.hotkey handles multiple keys
                        await asyncio.get_event_loop().run_in_executor(
                            None, lambda: pyautogui.hotkey(*mapped_keys)
                        )
                    else:
                        # Handle single keys
                        mapped_key = key_map.get(text.lower(), text.lower())
                        await asyncio.get_event_loop().run_in_executor(
                            None, lambda: pyautogui.press(mapped_key)
                        )
                    
                    # Take screenshot after key press
                    await asyncio.sleep(self._screenshot_delay)
                    screenshot_base64 = (await self.screenshot()).base64_image
                    return ToolResult(output=f"Pressed key: {text}", base64_image=screenshot_base64)
                    
                except Exception as e:
                    return ToolResult(error=str(e))

            elif action == "type":
                # Typing text
                for chunk in chunks(text, TYPING_GROUP_SIZE):
                    cmd = f"cliclick w:{TYPING_DELAY_MS} t:{shlex.quote(chunk)}"
                    await self.shell(cmd, take_screenshot=False)
                
                # Take screenshot after typing
                await asyncio.sleep(self._screenshot_delay)
                screenshot_base64 = (await self.screenshot()).base64_image
                return ToolResult(output=f"Typed: {text}", base64_image=screenshot_base64)

        # --- Handle Clicks and Cursor ---
        if action in ("left_click", "right_click", "double_click", "middle_click", "triple_click", "screenshot", "cursor_position"):
            if action == "screenshot":
                return await self.screenshot()
            
            elif action == "cursor_position":
                result = await self.shell("cliclick p", take_screenshot=False)
                if result.output:
                    x, y = map(int, result.output.strip().split(","))
                    # Scale back if needed, or just return raw
                    return result.replace(output=f"X={x},Y={y}")
                return result
                
            else:
                # Check if coordinates are provided
                if coordinate is not None:
                    x, y = self.scale_coordinates(coordinate[0], coordinate[1])
                    coords = f"{x},{y}"
                else:
                    coords = "."

                click_cmd_map = {
                    "left_click": "c",
                    "right_click": "rc",
                    "middle_click": "mc",
                    "double_click": "dc",
                    "triple_click": "tc", 
                }
                cmd_code = click_cmd_map[action]
                
                # Execute click AND take screenshot
                return await self.shell(f"cliclick {cmd_code}:{coords}", take_screenshot=True)

        raise ToolError(f"Invalid action: {action}")

    async def screenshot(self):
        output_dir = Path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"screenshot_{uuid4().hex}.png"

        screenshot_cmd = f"screencapture -x {path}"
        result = await self.shell(screenshot_cmd, take_screenshot=False)

        if self._scaling_enabled:
            x, y = SCALE_DESTINATION['width'], SCALE_DESTINATION['height']
            await self.shell(f"sips -z {y} {x} {path}", take_screenshot=False)

        if path.exists():
            return result.replace(
                base64_image=base64.b64encode(path.read_bytes()).decode()
            )
        raise ToolError(f"Failed to take screenshot: {result.error}")

    async def shell(self, command: str, take_screenshot=False) -> ToolResult:
        _, stdout, stderr = await run(command)
        base64_image = None
        if take_screenshot:
            await asyncio.sleep(self._screenshot_delay)
            base64_image = (await self.screenshot()).base64_image
        return ToolResult(output=stdout, error=stderr, base64_image=base64_image)

    def scale_coordinates(self, x: int, y: int) -> tuple[int, int]:
        if not self._scaling_enabled:
            return x, y
        x_scaling_factor = SCALE_DESTINATION['width'] / self.width
        y_scaling_factor = SCALE_DESTINATION['height'] / self.height
        return round(x / x_scaling_factor), round(y / y_scaling_factor)

def chunks(s: str, chunk_size: int) -> list[str]:
    return [s[i : i + chunk_size] for i in range(0, len(s), chunk_size)]
