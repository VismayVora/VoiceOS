# VoiceOS Computer Use (for Mac)

[VoiceOS Computer Use](https://github.com/VismayVora/VoiceOS) is a powerful tool that runs natively on macOS to provide direct system control through native macOS commands and utilities, now featuring advanced **Gesture Control**.

## Features

- **Gesture Control**: Control the assistant with hand gestures via your webcam.
- **Voice Control**: High-quality Neural TTS.
- **Headless Mode**: Run entirely from the terminal without a browser.
- **Native macOS GUI interaction**: No Docker required.
- **Screen capture**: Using native macOS commands.
- **Keyboard and mouse control**: Through cliclick.
- **Multiple LLM provider support**: Anthropic, Bedrock, Vertex.

## Prerequisites

- macOS Sonoma 15.7 or later
- Python 3.12+
- Homebrew (for installing additional dependencies)
- `cliclick` (`brew install cliclick`) - Required for mouse/keyboard control
- `portaudio` (`brew install portaudio`) - Required for microphone access

## Setup Instructions

1. Clone the repository and navigate to it:

```bash
git clone https://github.com/VismayVora/VoiceOS.git
cd VoiceOS
```

2. Create and activate a virtual environment:

```bash
python3.12 -m venv venv
source venv/bin/activate
```

3. Install Python requirements:

```bash
pip install -r requirements.txt
```

## Configuration

1. In a `.env` file add:

```
API_PROVIDER=anthropic
ANTHROPIC_API_KEY=<key>
WIDTH=800
HEIGHT=600
DISPLAY_NUM=1
```

## Running the App

Run the gesture-controlled assistant:

```bash
source venv/bin/activate
python gesture_control.py
```

### Gesture Controls

The system uses your webcam to detect hand gestures:

- **✋ Open Palm**: Start Listening (The assistant will start listening for your voice command)
- **✊ Closed Fist**: Stop Listening (Finish your command)
- **✌️ Victory (Peace Sign)**: Reset History (Clear the conversation context)

### Voice Interaction

Once listening (Open Palm), say your command. For example:
- "Open Safari and search for weather in New York"
- "Take a screenshot"
- "Close the calculator"

## Screen Size Considerations

We recommend using one of these resolutions for optimal performance:

-   XGA: 1024x768 (4:3)
-   WXGA: 1280x800 (16:10)
-   FWXGA: 1366x768 (~16:9)

Higher resolutions will be automatically scaled down to these targets to optimize model performance.

## Acknowledgements

This project builds upon the excellent work in [mac_computer_use](https://github.com/deedy/mac_computer_use) by [deedy](https://github.com/deedy).

While the core computer use logic is derived from the original repository, this repository introduces significant novel contributions:

-   **Latest Anthropic Integration**: Updated to support the latest Anthropic models (Claude 3.5 Sonnet v2) and API structures (beta 2025-01-24).
-   **Gesture Control**: A completely new camera-based hand gesture recognition system for hands-free interaction.
-   **Voice Integration**: Integration of high-quality Neural TTS and Whisper-based STT for natural voice conversations.
-   **Headless Operation**: Optimized for running without a visible UI overlay, suitable for background operation.
