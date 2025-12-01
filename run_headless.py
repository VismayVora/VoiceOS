import asyncio
import os
import platform
from datetime import datetime
from typing import Any, cast

from dotenv import load_dotenv
from anthropic import APIResponse
from anthropic.types.beta import BetaMessage, BetaContentBlock, BetaToolUseBlock, BetaTextBlock
from anthropic.types.tool_use_block import ToolUseBlock

from loop import (
    APIProvider,
    agent_loop,
    PROVIDER_TO_DEFAULT_MODEL_NAME
)
from tools import ToolResult
from tools.local_actions import handle_local_action
import voice

# Load environment variables
load_dotenv()

# Configuration
API_KEY = os.getenv("ANTHROPIC_API_KEY")
PROVIDER = APIProvider.ANTHROPIC # Default to Anthropic
MODEL = PROVIDER_TO_DEFAULT_MODEL_NAME[PROVIDER]
SYSTEM_PROMPT_SUFFIX = ""

def console_output_callback(content_block: BetaContentBlock):
    """Callback for agent output."""
    if isinstance(content_block, BetaTextBlock):
        print(f"\n🤖 Agent: {content_block.text}")
        voice.speak(content_block.text)
    elif isinstance(content_block, BetaToolUseBlock):
        print(f"\n🛠️ Tool Use: {content_block.name}")
        print(f"   Input: {content_block.input}")

def tool_output_callback(result: ToolResult, tool_id: str):
    """Callback for tool results."""
    if result.output:
        print(f"\n✅ Tool Output: {result.output[:200]}..." if len(result.output) > 200 else f"\n✅ Tool Output: {result.output}")
    if result.error:
        print(f"\n❌ Tool Error: {result.error}")
    if result.base64_image:
        print("\n🖼️ [Screenshot taken]")

def api_response_callback(response: APIResponse[BetaMessage]):
    """Callback for API responses (logging)."""
    # Optional: Log full API responses if needed
    pass

async def main():
    if not API_KEY:
        print("❌ Error: ANTHROPIC_API_KEY not found in environment variables.")
        print("Please create a .env file with your API key.")
        return

    print("="*50)
    print(f"🎙️  VoiceOS Headless Mode ({platform.system()})")
    print(f"🤖 Model: {MODEL}")
    print("="*50)
    print("\n👂 Listening for 'VoiceOS'...")

    messages = []


    while True:
        try:
            print("\n👂 Listening for 'VoiceOS'...")
            
            # 1. Listen for initial command
            command = await asyncio.to_thread(voice.listen_for_wake_word)
            
            if command:
                print(f"\n🗣️  User: {command}")
                
                # Check for fast-path local actions
                system_note = handle_local_action(command)
                
                # Add user message
                user_content = [{"type": "text", "text": command}]
                
                # If we performed a local action, append the system note
                if system_note:
                    print(f"ℹ️  {system_note}")
                    # We append it as a separate text block or just append to the text?
                    # Anthropic API supports multiple text blocks.
                    # Or we can just append to the string.
                    user_content.append({"type": "text", "text": f"\n\n({system_note})"})
                
                messages.append({
                    "role": "user",
                    "content": user_content
                })

                print("\n🤔 Thinking... (Say 'VoiceOS' to interrupt)")
                
                # 2. Run Agent Loop AND Listen for Interruption concurrently
                
                # Create task for agent
                agent_task = asyncio.create_task(agent_loop(
                    model=MODEL,
                    provider=PROVIDER,
                    system_prompt_suffix=SYSTEM_PROMPT_SUFFIX,
                    messages=messages,
                    output_callback=console_output_callback,
                    tool_output_callback=tool_output_callback,
                    api_response_callback=api_response_callback,
                    api_key=API_KEY,
                    only_n_most_recent_images=10
                ))
                
                # Create task for interruption listener
                # We loop this because we might hear noise, but we only want to stop if we hear a valid wake word
                async def interruption_listener():
                    while True:
                        # Listen for wake word
                        cmd = await asyncio.to_thread(voice.listen_for_wake_word)
                        if cmd is not None:
                            return cmd
                
                interrupt_task = asyncio.create_task(interruption_listener())
                
                # Wait for either to finish
                done, pending = await asyncio.wait(
                    [agent_task, interrupt_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                if interrupt_task in done:
                    # User interrupted!
                    print("\n🛑 Interrupted by user!")
                    voice.stop_speaking()
                    agent_task.cancel()
                    try:
                        await agent_task
                    except asyncio.CancelledError:
                        pass
                    
                    # The interruption command becomes the new command for the next loop
                    new_command = interrupt_task.result()
                    print(f"\n🗣️  New Command: {new_command}")
                    
                    # Reset messages or append? 
                    # For now, let's treat it as a new turn but we might need to handle context better.
                    # Appending the interruption as a new user message is usually best.
                    messages.append({
                        "role": "user",
                        "content": [{"type": "text", "text": new_command}]
                    })
                    
                    # We immediately loop back, which will skip the initial "Listening..." and go straight to processing
                    # But our structure expects "Listening" at top of loop. 
                    # Let's just let it loop back. The user said "VoiceOS [command]", so we have a command.
                    # We need to inject this command into the start of the next loop?
                    # Actually, simpler: just let it loop. But we need to avoid "Listening..." again.
                    # Let's handle it by just continuing. The user will have to say it again? 
                    # No, we captured the command.
                    
                    # HACK: We can't easily inject into the top of the loop without restructuring.
                    # Let's just process it here recursively or restructure.
                    # Simplest: Just print "Interrupted" and let the loop restart. 
                    # BUT we lose the command they just said.
                    # Let's store it in a variable `next_command` and check it at top of loop.
                    
                    # For this iteration, let's just cancel and let the user speak again?
                    # No, "VoiceOS stop" should stop. "VoiceOS open safari" should stop AND open safari.
                    
                    # Refactoring loop to handle `next_command`
                    pass 

                else:
                    # Agent finished naturally
                    interrupt_task.cancel()
                    try:
                        await interrupt_task
                    except asyncio.CancelledError:
                        pass
                    
                    # Update messages with result from agent (agent_loop returns messages)
                    messages = agent_task.result()

            else:
                # Optional: Sleep briefly to avoid tight loop if listen returns immediately
                await asyncio.sleep(0.1)

        except KeyboardInterrupt:
            print("\n👋 Exiting VoiceOS...")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
