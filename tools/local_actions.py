import subprocess
import re

def handle_local_action(text: str) -> str | None:
    """
    Checks if the user text contains a simple command that can be executed locally
    without the agent loop (e.g. "Open Safari" or "Close Calculator").
    
    Returns a system message describing what was done, or None if no action was taken.
    """
    text_lower = text.lower().strip()
    
    # --- OPEN / LAUNCH ---
    # Pattern: "open [app name]" or "launch [app name]"
    match_open = re.search(r'^(?:open|launch|start)\s+(?:the\s+)?(.+)$', text_lower)
    
    if match_open:
        app_name = match_open.group(1).strip()
        
        # Clean up app name (remove punctuation)
        app_name_clean = re.sub(r'[^\w\s]', '', app_name)
        
        # Heuristic: If app name is too long or contains "and", "then", etc., it's likely a complex command.
        if len(app_name_clean.split()) > 3 or " and " in app_name_clean or " then " in app_name_clean:
            return None

        # Try to open it
        try:
            cmd = ["open", "-a", app_name_clean]
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"🚀 Fast-Path: Opened '{app_name_clean}'")
                return f"System Note: I have already opened the application '{app_name_clean}' for you via a fast-path command. You do not need to open it again. Proceed with any subsequent steps."
            else:
                return None
        except Exception:
            return None

    # --- CLOSE / QUIT ---
    # Pattern: "close [app name]" or "quit [app name]"
    match_close = re.search(r'^(?:close|quit|exit|terminate|kill)\s+(?:the\s+)?(.+)$', text_lower)
    
    if match_close:
        app_name = match_close.group(1).strip()
        app_name_clean = re.sub(r'[^\w\s]', '', app_name)
        
        if len(app_name_clean.split()) > 3 or " and " in app_name_clean or " then " in app_name_clean:
            return None
            
        try:
            # Use AppleScript to quit the app gracefully
            # osascript -e 'quit app "AppName"'
            cmd = ["osascript", "-e", f'quit app "{app_name_clean}"']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"🚀 Fast-Path: Closed '{app_name_clean}'")
                return f"System Note: I have already closed the application '{app_name_clean}' for you via a fast-path command. You do not need to close it again."
            else:
                # Fallback: If graceful quit fails, maybe try killall? 
                # For now, let's just let the agent handle it if this fails.
                return None
        except Exception:
            return None
            
    return None
