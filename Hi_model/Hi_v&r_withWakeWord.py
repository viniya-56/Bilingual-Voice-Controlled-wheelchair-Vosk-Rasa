import requests
from vosk import Model, KaldiRecognizer
import pyaudio
import json
import pygame
import time
import struct
import pvporcupine

# Initialize Pygame Mixer
pygame.mixer.init()

# ===== Configuration =====
# Rasa NLU API Endpoint
RASA_SERVER = "http://localhost:5005/model/parse"

# VOSK Model Path
VOSK_MODEL_PATH = "./Vosk_model/vosk-model-small-hi-0.22"

# Audio Settings
SAMPLE_RATE = 16000
FRAME_LENGTH = 512  # For wake word detection
CHANNELS = 1
AUDIO_FORMAT = pyaudio.paInt16

# Timeout Settings
MAX_UNKNOWN_COMMAND_TIME = 10  # Seconds of continuous unknown commands before shutdown
MIN_COMMAND_INTERVAL = 1.5     # Minimum time between commands to be considered continuous

# Porcupine Configuration
access_key = "iDTjd1sERAynWYOBzqO6Gi2AnGOV99Tuf2kPHCItJsabKyVTcTMWYA=="
keyword_path = "./wake-up-wheelchair_en_windows_v3_0_0/wake-up-wheelchair_en_windows_v3_0_0.ppn"
WAKE_WORD_SENSITIVITY = 0.5

# Audio Feedback Paths
AUDIO_PATH = "C:/Users/viniy/Documents/Viniya Bhise/Projects/Voice-Controlled Wheelchair/Hi_model/Hi_audio_feedback/"

# Dictionary for intent-to-audio mapping
AUDIO_FEEDBACK = {
    "wakeWord": "Hi_wakeWord.wav",
    "move_forward": "Hi_forward.wav",
    "move_backward": "Hi_backward.wav",
    "turn_left": "Hi_left.wav",
    "turn_right": "Hi_right.wav",
    "stop": "Hi_stop.wav",
    "speed_up": "Hi_speedUp.wav",
    "slow_down": "Hi_slowDown.wav",
    "out_of_scope": "Hi_unknown.wav",
    "nlu_fallback": "Hi_unknown.wav",
    "shutdown": "Hi_shutdown.wav"
}

# Dictionary for intent-to-text mapping
INTENT_DISPLAY_MAP = {
    "move_forward": ("आगे", "Forward"),
    "move_backward": ("पीछे", "Backward"),
    "turn_left": ("बाए मुड़ो", "Turn Left"),
    "turn_right": ("दाए मुड़ो", "Turn Right"),
    "stop": ("रुको", "Stop"),
    "speed_up": ("गति बढ़ाओ", "Speed Up"),
    "slow_down": ("गति कम करो", "Slow Down"),
    "nlu_fallback": ("कृपया दोहराएँ", "Please Repeat"),
    "out_of_scope": ("कृपया दोहराएँ", "Please Repeat")
}

# ===== Initialize Components =====
porcupine = pvporcupine.create(access_key=access_key, keyword_paths=[keyword_path])
model = Model(VOSK_MODEL_PATH)
recognizer = KaldiRecognizer(model, SAMPLE_RATE)
audio_interface = pyaudio.PyAudio()
stream = audio_interface.open(
    rate=SAMPLE_RATE,
    channels=CHANNELS,
    format=AUDIO_FORMAT,
    input=True,
    frames_per_buffer=FRAME_LENGTH
)

# ===== Functions =====
def get_intent(text):
    """Send text to Rasa NLU and return intent with timing information"""
    response = requests.post(RASA_SERVER, json={"text": text})
    if response.status_code == 200:
        data = response.json()
        intent_data = data.get("intent", {})
        intent_name = intent_data.get("name", "nlu_fallback")
        confidence = intent_data.get("confidence", 0.0)
            
        entities = data.get("entities", [])
        if entities:
            print("Extracted Entities:")
            for entity in entities:
                print(f" - {entity.get('entity')}: {entity.get('value')}")
        else:
            print("No entities extracted.")

        if confidence < 0.8:
            return "nlu_fallback"
        return intent_name
        
    return "nlu_fallback"

def recognize_speech():
    """Continuously listen for speech and return recognized text."""
    print("Listening for commands...")
    while True:
        data = stream.read(4000, exception_on_overflow=False)
        if recognizer.AcceptWaveform(data):
            result = json.loads(recognizer.Result())
            text = result.get("text", "").strip()
            if text:
                return text  # Return recognized speech text

def play_audio_feedback(intent):
    """Play audio feedback for the given intent"""
    audio_file = AUDIO_PATH + AUDIO_FEEDBACK[intent]
    try:
        sound = pygame.mixer.Sound(audio_file)
        sound.play()
        while pygame.mixer.get_busy():
            time.sleep(0.1)
    except Exception as e:
        print(f"Audio playback error: {e}")

def is_unknown_intent(intent):
    return intent in ("nlu_fallback", "out_of_scope")

# Function definitions
def moveForward():
    print("Moving forward")

def moveBackward():
    print("Moving backward")

def turnLeft():
    print("Turning left")

def turnRight():
    print("Turning right")

def speedUp():
    print("Increasing speed")

def slowDown():
    print("Decreasing speed")

def stop():
    print("Stopping wheelchair")

def unknown():
    print("Unknown command, Please repeat...")

def control_wheelchair(intent):
    """Execute wheelchair control"""
    if intent in INTENT_DISPLAY_MAP:
        hindi_word, english_word = INTENT_DISPLAY_MAP[intent]
        print(f"Detected Intent: {hindi_word} ({english_word})")
    else:
        print("Detected Intent: Unknown")
    
    play_audio_feedback(intent)
    
    if intent == "move_forward":
        moveForward()
    elif intent == "move_backward":
        moveBackward()
    elif intent == "turn_left":
        turnLeft()
    elif intent == "turn_right":
        turnRight()
    elif intent == "stop":
        stop()
    elif intent == "speed_up":
        speedUp()
    elif intent == "slow_down":
        slowDown()
    elif intent == "out_of_scope":
        unknown()
    elif intent == "nlu_fallback":
        unknown()
    else:
        unknown()
    print()


# ===== Main Loop =====
def main():
    print("System ready. Waiting for wake word...")
    last_command_time = time.time()
    unknown_command_start = None
    
    try:
        while True:
            # Wait for wake word
            pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)
            
            if porcupine.process(pcm) >= 0:
                print("\nWake word detected!")
                play_audio_feedback("wakeWord")
                unknown_command_start = None
                
                # Continuous command processing
                while True:
                    command = recognize_speech()
                                       
                    print(f"Recognized: {command}")
                    intent = get_intent(command)
                    print(f"Raw Intent: {intent}")
                    
                    # Handle unknown commands timeout
                    if is_unknown_intent(intent):
                        if unknown_command_start is None:
                            unknown_command_start = time.time()
                        elif time.time() - unknown_command_start >= MAX_UNKNOWN_COMMAND_TIME:
                            play_audio_feedback("shutdown")
                            print(f"Timeout reached. Shutting down...")
                            time.sleep(2)
                            break
                    else:
                        unknown_command_start = None
                    
                    control_wheelchair(intent)
                    last_command_time = time.time()
    
    except KeyboardInterrupt:
        print("Shutting down...")
    finally:
        stream.stop_stream()
        stream.close()
        audio_interface.terminate()
        porcupine.delete()

if __name__ == "__main__":
    while True:
        main()
        print("System in standby. Waiting for wake word to reactivate...")
           