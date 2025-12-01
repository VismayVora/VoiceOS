# VoiceOS Computer Use (for Mac)

[VoiceOS Computer Use](https://github.com/VismayVora/VoiceOS) is a powerful tool that runs natively on macOS to provide direct system control through native macOS commands and utilities, now with advanced Voice Control.

## Features

- **Voice Control**: "Always Listening" Wake Word ("VoiceOS") and high-quality Neural TTS.
- **Headless Mode**: Run entirely from the terminal without a browser.
- **Native macOS GUI interaction**: No Docker required.
- **Screen capture**: Using native macOS commands.
- **Keyboard and mouse control**: Through cliclick.
- **Multiple LLM provider support**: Anthropic, Bedrock, Vertex.
- **Streamlit-based interface**: For visual interaction.

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

3. Run the setup script:

```bash
chmod +x setup.sh
./setup.sh
```

4. Install Python requirements:

```bash
pip install -r requirements.txt
```

## Running the App

### Set up your environment and API key

1. In a `.env` file add:

```
API_PROVIDER=anthropic
ANTHROPIC_API_KEY=<key>
WIDTH=800
HEIGHT=600
DISPLAY_NUM=1
```

### Option A: Visual Interface (Streamlit)

Start the visual app:

```bash
streamlit run app.py
```

The interface will be available at http://localhost:8501. You can enable the "Wake Word" toggle in the sidebar to use voice commands.

### Option B: Headless Mode (Terminal)

Run the voice-only background service:

```bash
python run_headless.py
```

Say **"VoiceOS, [command]"** to interact.

## Screen Size Considerations

We recommend using one of these resolutions for optimal performance:

-   XGA: 1024x768 (4:3)
-   WXGA: 1280x800 (16:10)
-   FWXGA: 1366x768 (~16:9)

Higher resolutions will be automatically scaled down to these targets to optimize model performance.
