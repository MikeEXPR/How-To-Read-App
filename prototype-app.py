from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from elevenlabs import generate, play, set_api_key
from openai import OpenAI
import threading
import asyncio
import speech_recognition as sr
import edge_tts
import os

openai_client = OpenAI(api_key="API")  # OpenAI API Key for GPT-4 & Whisper
set_api_key("API")  # ElevenLabs API Key for Text-to-Speech

# Welcome Screen
class WelcomeScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        layout.add_widget(Label(text="How to Read a Book", font_size=24))
        layout.add_widget(Button(text="Get Started", size_hint=(1, 0.2), on_press=self.go_to_onboarding))
        layout.add_widget(Button(text="Learn About the App", size_hint=(1, 0.2), on_press=self.show_about))
        self.add_widget(layout)

    def go_to_onboarding(self, instance):
        self.manager.current = "onboarding"

    def show_about(self, instance):
        popup = Popup(title="About the App",
                      content=Label(text="Your guide to mastering reading and comprehension."),
                      size_hint=(0.8, 0.4))
        popup.open()

# Onboarding Screen
class OnboardingScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        layout.add_widget(Label(text="Tell us about yourself", font_size=24))
        self.language_input = TextInput(hint_text="Preferred Language (e.g., English, Spanish, French, German)", multiline=False)
        layout.add_widget(self.language_input)
        self.level_input = TextInput(hint_text="Reading Level (e.g., Basic, Intermediate, Advanced)", multiline=False)
        layout.add_widget(self.level_input)
        layout.add_widget(Button(text="Continue", size_hint=(1, 0.2), on_press=self.save_preferences))
        self.add_widget(layout)

    def save_preferences(self, instance):
        language = self.language_input.text
        level = self.level_input.text
        if not language or not level:
            popup = Popup(title="Error", content=Label(text="Please fill in all fields!"), size_hint=(0.8, 0.4))
            popup.open()
        else:
            self.manager.current = "dashboard"

# Chat with Mentor Screen
class ChatWithMentorScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)

        # Chat log for displaying messages with proper wrapping
        self.chat_log = Label(
            text="Welcome! Ask me anything.",
            size_hint_y=None,
            halign='left',
            valign='top',
            text_size=(0, None),  # Enable dynamic text wrapping
        )
        self.chat_log.bind(
            width=self._update_text_size,  # Adjust wrapping on window resize
            texture_size=self._adjust_scroll  # Auto-scroll when text grows
        )

        # Scroll view for the chat log
        self.scroll_view = ScrollView(size_hint=(1, 0.7))
        self.scroll_view.add_widget(self.chat_log)
        layout.add_widget(self.scroll_view)

        # Input box for typing queries
        self.input_box = TextInput(hint_text="Type your question here", multiline=False)
        layout.add_widget(self.input_box)

        # Send button for text input
        send_button = Button(text="Send", size_hint=(1, 0.2))
        send_button.bind(on_press=self.send_message)
        layout.add_widget(send_button)

        # Speak button for voice input
        speak_button = Button(text="Speak", size_hint=(1, 0.2))
        speak_button.bind(on_press=self.capture_voice_input)
        layout.add_widget(speak_button)

        self.add_widget(layout)

    # Auto-update text wrapping on window resize
    def _update_text_size(self, *args):
        self.chat_log.text_size = (self.chat_log.width - 20, None)  # Adjust width for wrapping

    # Auto-scroll to the latest message
    def _adjust_scroll(self, *args):
        self.chat_log.height = self.chat_log.texture_size[1]
        self.scroll_view.scroll_y = 0  # Scroll to the bottom

    def send_message(self, instance):
        user_message = self.input_box.text
        if user_message:
            self.chat_log.text += f"\n\nYou: {user_message}"
            threading.Thread(target=self.get_gpt_response, args=(user_message,)).start()
            self.input_box.text = ""

    def capture_voice_input(self, instance):
        threading.Thread(target=self._record_and_process_voice_whisper).start()

    def _record_and_process_voice_whisper(self):
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            self.chat_log.text += "\n\nListening..."
            try:
                audio = recognizer.listen(source, timeout=10)
                with open("temp_audio.wav", "wb") as f:
                    f.write(audio.get_wav_data())

                # Use Whisper API to transcribe audio
                with open("temp_audio.wav", "rb") as audio_file:
                    transcription = openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file
                    )

                query = transcription.text
                self.chat_log.text += f"\n\nYou (Voice): {query}"
                self.get_gpt_response(query)

                # Clean up the temporary audio file
                os.remove("temp_audio.wav")

            except Exception as e:
                self.chat_log.text += f"\n\nError with speech recognition: {str(e)}"

    def get_gpt_response(self, prompt):
        try:
            response = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            reply = response.choices[0].message.content
            self.chat_log.text += f"\n\nMentor: {reply}"

            # Speak the response using ElevenLabs
            threading.Thread(target=self.speak_with_elevenlabs, args=(reply,)).start()

        except Exception as e:
            self.chat_log.text += f"\n\nError: {str(e)}"

    def speak_with_elevenlabs(self, text):
        try:
            # Generate speech using ElevenLabs
            audio = generate(
                text=text,
                voice="Jessica",  # Choose the desired voice from ElevenLabs
                model="eleven_multilingual_v2"
            )
            play(audio)
        except Exception as e:
            self.chat_log.text += f"\n\nError with TTS: {str(e)}"

# Dashboard Screen
class DashboardScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=20, spacing=10)
        layout.add_widget(Label(text="Main Dashboard", font_size=24))
        layout.add_widget(Button(text="Start Reading (OCR)", size_hint=(1, 0.2), on_press=self.start_reading))
        layout.add_widget(Button(text="Practice Comprehension", size_hint=(1, 0.2), on_press=self.practice_comprehension))
        layout.add_widget(Button(text="Explore Books", size_hint=(1, 0.2), on_press=self.explore_books))
        layout.add_widget(Button(text="Chat with Your Mentor", size_hint=(1, 0.2), on_press=self.open_chat))
        
        self.add_widget(layout)

    def start_reading(self, instance):
        popup = Popup(title="OCR",
                      content=Label(text="This feature will allow OCR text extraction."),
                      size_hint=(0.8, 0.4))
        popup.open()

    def practice_comprehension(self, instance):
        popup = Popup(title="Comprehension Practice",
                      content=Label(text="This feature will include quizzes and exercises."),
                      size_hint=(0.8, 0.4))
        popup.open()

    def explore_books(self, instance):
        popup = Popup(title="Explore Books",
                      content=Label(text="Browse book summaries and recommendations."),
                      size_hint=(0.8, 0.4))
        popup.open()

    def open_chat(self, instance):
        self.manager.current = "chat"

# App Manager
class ReadingApp(App):
    def build(self):
        sm = ScreenManager()
        sm.add_widget(WelcomeScreen(name="welcome"))
        sm.add_widget(OnboardingScreen(name="onboarding"))
        sm.add_widget(DashboardScreen(name="dashboard"))
        sm.add_widget(ChatWithMentorScreen(name="chat"))
        return sm

if __name__ == "__main__":
    ReadingApp().run()
