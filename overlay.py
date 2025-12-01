import sys
import os
import asyncio
import threading
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QLabel, QFrame
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QColor, QPalette
from dotenv import load_dotenv
from loop import agent_loop, APIProvider, PROVIDER_TO_DEFAULT_MODEL_NAME
from tools.local_actions import handle_local_action
import voice

# Load env
load_dotenv()

# Configuration
API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
PROVIDER = os.getenv("API_PROVIDER", "anthropic") or APIProvider.ANTHROPIC
MODEL = PROVIDER_TO_DEFAULT_MODEL_NAME[APIProvider(PROVIDER)]
SYSTEM_PROMPT_SUFFIX = "User is using a floating overlay. Be EXTREMELY concise. Do not narrate obvious steps. Only speak when necessary or to confirm completion. Max 1 sentence."

class AgentWorker(QObject):
    finished = pyqtSignal()
    status_update = pyqtSignal(str)
    
    def __init__(self, messages):
        super().__init__()
        self.messages = messages
        
    def run(self):
        asyncio.run(self._run_async())
        
    async def _run_async(self):
        def status_callback(content_block):
            if content_block.type == "text":
                text = content_block.text
                self.status_update.emit(f"Agent: {text[:30]}...")
                voice.speak(text)
                
        def tool_cb(tool_output, tool_id):
            self.status_update.emit(f"Tool: {tool_id}")

        try:
            self.status_update.emit("Thinking...")
            await agent_loop(
                model=MODEL,
                provider=PROVIDER,
                system_prompt_suffix=SYSTEM_PROMPT_SUFFIX,
                messages=self.messages,
                output_callback=status_callback,
                tool_output_callback=tool_cb,
                api_response_callback=lambda *args: None,
                api_key=API_KEY,
                only_n_most_recent_images=3
            )
            self.status_update.emit("Ready")
        except Exception as e:
            print(f"Agent error: {e}")
            self.status_update.emit("Error")
        finally:
            self.finished.emit()

class FloatingAssistant(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.messages = []
        self.is_listening = False
        
    def initUI(self):
        self.setWindowTitle("VoiceOS")
        self.setGeometry(100, 100, 400, 100)
        
        # Frameless and Always on Top
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        # Main Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        
        # Background Frame (for styling)
        self.bg_frame = QFrame(self)
        self.bg_frame.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 30, 30, 240);
                border-radius: 10px;
                border: 1px solid #444;
            }
        """)
        layout.addWidget(self.bg_frame)
        
        # Content Layout
        content_layout = QVBoxLayout(self.bg_frame)
        
        # Header (Drag Area + Close)
        header_layout = QHBoxLayout()
        self.title_lbl = QLabel("VoiceOS Assistant")
        self.title_lbl.setStyleSheet("color: #ccc; font-weight: bold;")
        header_layout.addWidget(self.title_lbl)
        
        header_layout.addStretch()
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(20, 20)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #ff5f56;
                border: none;
                font-weight: bold;
            }
            QPushButton:hover { color: #ff3b30; }
        """)
        self.close_btn.clicked.connect(QApplication.instance().quit)
        header_layout.addWidget(self.close_btn)
        
        content_layout.addLayout(header_layout)
        
        # Status
        self.status_lbl = QLabel("Ready")
        self.status_lbl.setStyleSheet("color: #888; font-size: 10pt;")
        content_layout.addWidget(self.status_lbl)
        
        # Input Area
        input_layout = QHBoxLayout()
        
        self.entry = QLineEdit()
        self.entry.setPlaceholderText("Type a command...")
        self.entry.setStyleSheet("""
            QLineEdit {
                background-color: #333;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        self.entry.returnPressed.connect(self.on_submit)
        input_layout.addWidget(self.entry)
        
        self.mic_btn = QPushButton("🎤")
        self.mic_btn.setFixedSize(30, 30)
        self.mic_btn.setStyleSheet("""
            QPushButton {
                background-color: #333;
                color: white;
                border: none;
                border-radius: 15px;
            }
            QPushButton:hover { background-color: #444; }
        """)
        self.mic_btn.clicked.connect(self.toggle_mic)
        input_layout.addWidget(self.mic_btn)
        
        content_layout.addLayout(input_layout)
        
        # Dragging Logic
        self.old_pos = None

    def closeEvent(self, event):
        # Clean up thread on close
        if hasattr(self, 'worker_thread') and self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.old_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.old_pos = None

    def on_submit(self):
        text = self.entry.text().strip()
        if not text:
            return
        self.entry.clear()
        self.process_input(text)

    def toggle_mic(self):
        if self.is_listening:
            # STOP RECORDING
            self.is_listening = False
            self.stop_event.set()
            self.mic_btn.setStyleSheet("""
                QPushButton {
                    background-color: #333;
                    color: white;
                    border: none;
                    border-radius: 15px;
                }
                QPushButton:hover { background-color: #444; }
            """)
            self.status_lbl.setText("Transcribing...")
            return
        
        # START RECORDING
        # Stop any ongoing speech immediately
        voice.stop_speaking()
        
        self.is_listening = True
        self.stop_event = threading.Event()
        
        self.mic_btn.setStyleSheet("background-color: #ff4444; color: white; border-radius: 15px;")
        self.status_lbl.setText("Recording... (Press mic to stop)")
        
        # Run listen in thread
        threading.Thread(target=self.listen_thread, daemon=True).start()

    def listen_thread(self):
        # This will block until stop_event is set
        text = voice.record_until_stopped(self.stop_event)
        
        # Post result
        QApplication.instance().postEvent(self, CustomEvent(lambda: self.finish_listen(text)))

    def customEvent(self, event):
        # Handle custom events for thread safety
        if hasattr(event, 'callback'):
            event.callback()

    def finish_listen(self, text):
        # Reset UI state if not already done (it is done in toggle_mic for button, but status needs update)
        # Actually toggle_mic handles the button color change immediately on click.
        # But we need to handle the text processing here.
        
        if text:
            self.process_input(text)
        else:
            self.status_lbl.setText("Ready")

    def process_input(self, text):
        self.status_lbl.setText(f"Processing: {text[:20]}...")
        
        # Fast path
        system_note = handle_local_action(text)
        
        user_content = [{"type": "text", "text": text}]
        if system_note:
            self.status_lbl.setText("Done (Fast Path)")
            user_content.append({"type": "text", "text": f"\n\n({system_note})"})
        
        # FIX: Prune history if the last message was an assistant message (interrupted turn)
        # The API requires that if an assistant message has tool_use, the next message MUST be tool_result.
        # If we are here, the user has issued a NEW command, interrupting the previous flow.
        # So we should remove the dangling assistant message.
        if self.messages and self.messages[-1]["role"] == "assistant":
            print("Pruning interrupted assistant message to prevent Error 400")
            self.messages.pop()

        
        self.messages.append({
            "role": "user",
            "content": user_content
        })
        
        # Run agent in background thread
        self.worker = AgentWorker(self.messages)
        self.worker_thread = QThread()
        self.worker.moveToThread(self.worker_thread)
        
        # Keep a reference to the thread to prevent GC while it's running
        # We can use the worker itself to hold the thread reference if we want, 
        # or just rely on the fact that we're overwriting self.worker_thread 
        # but we should ensure the OLD one is handled.
        
        # Better approach: Cleanup old thread if it exists
        if hasattr(self, 'worker_thread') and self.worker_thread is not None:
            # If it's still running, we probably shouldn't be here if we want to be strict,
            # but for now let's just ensure we don't lose the reference effectively.
            # Actually, the safe way is to let the cleanup handlers handle it, 
            # but we need to ensure the Python object doesn't die.
            # We can attach the thread to the worker temporarily?
            pass

        self.worker_thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        
        # CRITICAL FIX: Keep a reference to the thread in the worker so it doesn't get GC'd
        # if self.worker_thread is overwritten by a new command.
        # Although self.worker is also overwritten...
        # Let's use a set to hold active threads.
        if not hasattr(self, 'active_threads'):
            self.active_threads = set()
        
        self.active_threads.add(self.worker_thread)
        
        def cleanup_thread(t=self.worker_thread):
            if t in self.active_threads:
                self.active_threads.remove(t)
        
        self.worker_thread.finished.connect(cleanup_thread)
        
        self.worker.status_update.connect(self.status_lbl.setText)
        
        self.worker_thread.start()

# Helper for thread safety
from PyQt6.QtCore import QEvent
class CustomEvent(QEvent):
    def __init__(self, callback):
        super().__init__(QEvent.Type.User)
        self.callback = callback

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = FloatingAssistant()
    window.show()
    sys.exit(app.exec())
