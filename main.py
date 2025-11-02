from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import get_color_from_hex
import threading
import google.generativeai as genai
from gtts import gTTS
import tempfile
import os
from android.permissions import request_permissions, Permission
from android.storage import primary_external_storage_path
import speech_recognition as sr

# Request necessary permissions for Android
request_permissions([
    Permission.INTERNET,
    Permission.RECORD_AUDIO,
    Permission.WRITE_EXTERNAL_STORAGE,
    Permission.READ_EXTERNAL_STORAGE
])

# --- API CONFIGURATION ---
API_KEY = "AIzaSyDbdGmOXYtyddLjWhi_eOMr7JVjRg-J9ds"

try:
    genai.configure(api_key=API_KEY)
except Exception as e:
    print(f"API configuration error: {e}")

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = """
You are Amica, a highly empathetic and caring AI assistant focused on mental well-being.
You are a supportive and non-judgmental listener.
Always acknowledge the user's feelings and respond warmly.
If a user expresses suicidal thoughts, say:
"I'm very sorry to hear you're feeling this way, but please seek immediate help by contacting this helpline: 9152987821. You are not alone."
Never diagnose or prescribe. Always stay comforting and safe.
"""

# --- MODEL INITIALIZATION ---
model = genai.GenerativeModel("gemini-2.5-pro", system_instruction=SYSTEM_PROMPT)
chat = model.start_chat(history=[])

class ChatMessage(BoxLayout):
    """Custom widget for chat messages"""
    def __init__(self, text, is_user=False, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.padding = [10, 5]
        self.spacing = 10
        
        # Create message label
        label = Label(
            text=text,
            size_hint=(0.8, None),
            text_size=(Window.width * 0.7, None),
            halign='left' if not is_user else 'right',
            valign='top',
            color=get_color_from_hex('#FFFFFF') if not is_user else get_color_from_hex('#000000')
        )
        label.bind(texture_size=label.setter('size'))
        
        # Style based on sender
        if is_user:
            label.canvas.before.clear()
            with label.canvas.before:
                from kivy.graphics import Color, RoundedRectangle
                Color(rgba=get_color_from_hex('#E3F2FD') + [1])
                self.rect = RoundedRectangle(
                    pos=label.pos,
                    size=label.size,
                    radius=[15]
                )
            label.bind(pos=self.update_rect, size=self.update_rect)
            self.add_widget(Label(size_hint=(0.2, None)))
            self.add_widget(label)
        else:
            label.canvas.before.clear()
            with label.canvas.before:
                from kivy.graphics import Color, RoundedRectangle
                Color(rgba=get_color_from_hex('#2196F3') + [1])
                self.rect = RoundedRectangle(
                    pos=label.pos,
                    size=label.size,
                    radius=[15]
                )
            label.bind(pos=self.update_rect, size=self.update_rect)
            self.add_widget(label)
            self.add_widget(Label(size_hint=(0.2, None)))
        
        self.height = label.height + 10
    
    def update_rect(self, instance, value):
        self.rect.pos = instance.pos
        self.rect.size = instance.size


class AmicaApp(App):
    def build(self):
        self.title = "Amica - Mental Health Assistant"
        Window.clearcolor = get_color_from_hex('#FFFFFF')
        
        # Main layout
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        
        # Header
        header = Label(
            text='Amica 💬\nYour Mental Health Assistant',
            size_hint=(1, 0.12),
            font_size='20sp',
            bold=True,
            color=get_color_from_hex('#2196F3')
        )
        main_layout.add_widget(header)
        
        # Disclaimer
        disclaimer = Label(
            text='⚠ Not a substitute for professional therapy\nIn crisis? Contact helpline: 9152987821',
            size_hint=(1, 0.08),
            font_size='12sp',
            color=get_color_from_hex('#FF9800')
        )
        main_layout.add_widget(disclaimer)
        
        # Chat area (ScrollView)
        self.chat_scroll = ScrollView(size_hint=(1, 0.6))
        self.chat_layout = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=5,
            padding=[5, 5]
        )
        self.chat_layout.bind(minimum_height=self.chat_layout.setter('height'))
        self.chat_scroll.add_widget(self.chat_layout)
        main_layout.add_widget(self.chat_scroll)
        
        # Input area
        input_layout = BoxLayout(size_hint=(1, 0.15), spacing=5)
        
        self.text_input = TextInput(
            hint_text='Type how you feel...',
            multiline=False,
            size_hint=(0.6, 1),
            font_size='16sp',
            background_color=get_color_from_hex('#F5F5F5'),
            foreground_color=get_color_from_hex('#000000'),
            cursor_color=get_color_from_hex('#2196F3')
        )
        self.text_input.bind(on_text_validate=self.send_message)
        
        send_btn = Button(
            text='Send',
            size_hint=(0.2, 1),
            background_color=get_color_from_hex('#2196F3'),
            color=get_color_from_hex('#FFFFFF'),
            font_size='16sp',
            bold=True
        )
        send_btn.bind(on_press=self.send_message)
        
        mic_btn = Button(
            text='🎤',
            size_hint=(0.2, 1),
            background_color=get_color_from_hex('#4CAF50'),
            font_size='24sp'
        )
        mic_btn.bind(on_press=self.voice_input)
        
        input_layout.add_widget(self.text_input)
        input_layout.add_widget(send_btn)
        input_layout.add_widget(mic_btn)
        
        main_layout.add_widget(input_layout)
        
        # Add welcome message
        self.add_message("Hello! I'm Amica. How are you feeling today?", is_user=False)
        
        return main_layout
    
    def add_message(self, text, is_user=False):
        """Add a message to the chat"""
        msg = ChatMessage(text=text, is_user=is_user)
        self.chat_layout.add_widget(msg)
        # Auto-scroll to bottom
        Clock.schedule_once(lambda dt: setattr(self.chat_scroll, 'scroll_y', 0), 0.1)
    
    def send_message(self, instance):
        """Handle sending a message"""
        user_text = self.text_input.text.strip()
        if not user_text:
            return
        
        # Clear input
        self.text_input.text = ""
        
        # Add user message
        self.add_message(user_text, is_user=True)
        
        # Process in background thread
        threading.Thread(target=self.process_message, args=(user_text,), daemon=True).start()
    
    def process_message(self, user_text):
        """Process the user message and get AI response"""
        try:
            suicide_keywords = [
                "kill myself", "want to die", "commit suicide", 
                "end my life", "suicidal"
            ]
            
            if any(keyword in user_text.lower() for keyword in suicide_keywords):
                response_text = (
                    "I'm very sorry to hear you're feeling this way, "
                    "but please seek immediate help by contacting this "
                    "helpline: 9152987821. You are not alone."
                )
            else:
                response = chat.send_message(user_text)
                response_text = response.text
            
            # Add bot response on main thread
            Clock.schedule_once(
                lambda dt: self.add_message(response_text, is_user=False), 0
            )
            
            # Speak the response
            self.speak_text(response_text)
            
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            Clock.schedule_once(
                lambda dt: self.add_message(error_msg, is_user=False), 0
            )
    
    def voice_input(self, instance):
        """Handle voice input"""
        self.add_message("🎤 Listening...", is_user=False)
        threading.Thread(target=self.listen_to_mic, daemon=True).start()
    
    def listen_to_mic(self):
        """Capture speech from microphone"""
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                audio = recognizer.listen(source, phrase_time_limit=6)
                text = recognizer.recognize_google(audio)
                
                # Set the text and send
                Clock.schedule_once(lambda dt: self.process_voice_result(text), 0)
        except sr.UnknownValueError:
            Clock.schedule_once(
                lambda dt: self.add_message("Sorry, I didn't catch that.", is_user=False), 0
            )
        except Exception as e:
            Clock.schedule_once(
                lambda dt: self.add_message(f"Voice error: {str(e)}", is_user=False), 0
            )
    
    def process_voice_result(self, text):
        """Process the voice recognition result"""
        self.text_input.text = text
        self.send_message(None)
    
    def speak_text(self, text):
        """Convert text to speech"""
        try:
            tts = gTTS(text=text)
            # Use external storage on Android
            storage_path = primary_external_storage_path()
            audio_file = os.path.join(storage_path, "amica_speech.mp3")
            tts.save(audio_file)
            
            # Play audio using Android's media player
            from jnius import autoclass
            MediaPlayer = autoclass('android.media.MediaPlayer')
            player = MediaPlayer()
            player.setDataSource(audio_file)
            player.prepare()
            player.start()
        except Exception as e:
            print(f"Speech error: {e}")


if __name__ == '__main__':
    AmicaApp().run()
