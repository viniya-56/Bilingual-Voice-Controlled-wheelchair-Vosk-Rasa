import time
import board
import busio
import json
import pygame
import requests
import pyaudio
from vosk import Model, KaldiRecognizer
import lgpio
import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn
from threading import Thread, Event
from queue import Queue, Empty

# OLED imports
from luma.core.interface.serial import i2c
from luma.oled.device import sh1106
from luma.core.render import canvas

# === GPIO Pins ===
DIR_1_PIN = 17
DIR_2_PIN = 27
CLUTCH_PIN = 23
PWM_PIN_1 = 12
PWM_PIN_2 = 18
SWITCH_PIN = 22
TRIG = 24
ECHO = 25
BUZZER_PIN = 7
RELAY_PIN = 16

# === GPIO Init ===
h = lgpio.gpiochip_open(0)
lgpio.gpio_claim_output(h, DIR_1_PIN, 0)
lgpio.gpio_claim_output(h, DIR_2_PIN, 0)
lgpio.gpio_claim_output(h, PWM_PIN_1, 0)
lgpio.gpio_claim_output(h, PWM_PIN_2, 0)
lgpio.gpio_claim_output(h, CLUTCH_PIN, 0)
lgpio.gpio_claim_output(h, TRIG)
lgpio.gpio_claim_input(h, ECHO)
lgpio.gpio_claim_input(h, SWITCH_PIN, lgpio.SET_PULL_UP)
lgpio.gpio_claim_output(h, RELAY_PIN, 0)

PWM_FREQ = 7000
lgpio.tx_pwm(h, PWM_PIN_1, PWM_FREQ, 0)
lgpio.tx_pwm(h, PWM_PIN_2, PWM_FREQ, 0)

# === OLED ===
serial = i2c(port=1, address=0x3C)
device = sh1106(serial)

current_movement = "Stop"
current_mode = "Joystick"
obstacle_status = "Clear"

command_queue = Queue()
stop_event = Event()
mode_change_event = Event()

# === Fast Keywords (English) ===
JOYSTICK_KEYWORDS = ["joystick", "manual mode", "stick mode"]
VOICE_KEYWORDS = ["voice mode", "voice control"]
STOP_KEYWORDS = ["stop", "halt", "freeze", "don’t move", "do not move"]

# === Vosk + Rasa Setup ===
pygame.mixer.init()
RASA_SERVER = "http://localhost:5005/model/parse"
MODEL_PATH = "./Vosk_model/vosk-model-small-en-in-0.4"
model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, 16000)

p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
stream.start_stream()

AUDIO_PATH = "/home/viniya/Voice Controlled Wheelchair/En_model/En_audio_feedback/"
AUDIO_FEEDBACK = {
    "move_forward": "En_forward.wav",
    "move_backward": "En_backward.wav",
    "turn_left": "En_left.wav",
    "turn_right": "En_right.wav",
    "stop": "En_stop.wav",
    "speed_up": "En_speedUp.wav",
    "slow_down": "En_slowDown.wav",
    "out_of_scope": "En_unknown.wav",
    "nlu_fallback": "En_unknown.wav",
    "switch_to_voice": "En_voice_mode_activated.wav",
    "switch_to_joystick": "En_switch_to_joystick.wav"
}

INTENT_DISPLAY_MAP = {
    "move_forward": "Forward",
    "move_backward": "Backward",
    "turn_left": "Left",
    "turn_right": "Right",
    "stop": "Stop",
    "speed_up": "Speed Up",
    "slow_down": "Slow Down",
    "switch_to_joystick": "Joystick Mode",
    "switch_to_voice": "Voice Mode"
}

speed = 18
last_movement_intent = None

def get_intent(text):
    text = text.lower()

    if any(k in text for k in JOYSTICK_KEYWORDS):
        return "switch_to_joystick"
    if any(k in text for k in VOICE_KEYWORDS):
        return "switch_to_voice"
    if any(k in text for k in STOP_KEYWORDS):
        return "stop"

    try:
        r = requests.post(RASA_SERVER, json={"text": text}, timeout=1.0)
        if r.status_code == 200:
            data = r.json()
            intent = data["intent"]["name"]
            conf = data["intent"]["confidence"]
            return intent if conf > 0.8 else "nlu_fallback"
    except:
        pass

    return "nlu_fallback"

def recognize_speech(timeout=2):
    start = time.time()
    while time.time() - start < timeout and not mode_change_event.is_set():
        data = stream.read(4000, exception_on_overflow=False)
        if recognizer.AcceptWaveform(data):
            return json.loads(recognizer.Result()).get("text", "").strip()
    return ""

def play_audio_feedback(intent):
    if intent in AUDIO_FEEDBACK:
        pygame.mixer.Sound(AUDIO_PATH + AUDIO_FEEDBACK[intent]).play()

# === Motor Functions (Same as Hindi) ===
def moveForward(s): print(f"Forward {s}%")
def moveBackward(s): print(f"Backward {s}%")
def turnLeft(s): print(f"Left {s}%")
def turnRight(s): print(f"Right {s}%")
def stop(): print("Stopped")

def voice_command_processor():
    while not stop_event.is_set():
        if current_mode == "Voice":
            text = recognize_speech()
            if text:
                intent = get_intent(text)
                command_queue.put(intent)

def execute_voice_commands():
    while not stop_event.is_set():
        try:
            intent = command_queue.get(timeout=0.2)
            print(f"Intent: {intent}")
            play_audio_feedback(intent)
        except Empty:
            pass

Thread(target=voice_command_processor, daemon=True).start()
Thread(target=execute_voice_commands, daemon=True).start()

while True:
    time.sleep(0.2)