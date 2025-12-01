import subprocess
import re

def handle_local_action(text: str) -> str | None:
    """
    Checks if the user text contains a simple command that can be executed locally
    without the agent loop (e.g. "Open Safari").
    
    Returns a system message describing what was done, or None if no action was taken.
    """
    text_lower = text.lower().strip()
    
    # Pattern: "open [app name]" or "launch [app name]"
    # We want to capture the app name.
    # Examples: "Open Safari", "Launch Google Chrome", "Open the calculator"
    match = re.search(r'^(?:open|launch|start)\s+(?:the\s+)?(.+)$', text_lower)
    
    if match:
        app_name = match.group(1).strip()
        
        # Filter out complex sentences like "Open Safari and search for..." 
        # For now, let's try to handle the "Open X" part even in complex sentences?
        # If we do "Open Safari", we should probably just do it.
        # But if the user says "Open the door", we shouldn't try to open an app named "door".
        # Let's be aggressive for now as requested by user.
        
        # Clean up app name (remove punctuation)
        app_name_clean = re.sub(r'[^\w\s]', '', app_name)
        
        # Heuristic: If app name is too long or contains "and", "then", etc., it's likely a complex command.
        if len(app_name_clean.split()) > 3 or " and " in app_name_clean or " then " in app_name_clean:
            # Let the agent handle complex commands
            return None

        # Try to open it
        try:
            # -g: Do not bring to foreground (we want it to be focused though?)
            # No, we want it focused.
            cmd = ["open", "-a", app_name_clean]
            
            # Run it
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"🚀 Fast-Path: Opened '{app_name_clean}'")
                return f"System Note: I have already opened the application '{app_name_clean}' for you via a fast-path command. You do not need to open it again. Proceed with any subsequent steps."
            else:
                # Silent failure for fast-path to avoid noise
                # print(f"Fast-Path failed for '{app_name_clean}': {result.stderr}")
                return None
                
        except Exception as e:
            # Silent failure
            return None
            
    return None
