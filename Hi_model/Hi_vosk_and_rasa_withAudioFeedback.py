import requests  # Import requests for sending text to Rasa
from vosk import Model, KaldiRecognizer
import pyaudio
import json
import pygame  # Import pygame for audio feedback
import time

# Initialize Pygame Mixer
pygame.mixer.init()

# Rasa NLU API Endpoint
RASA_SERVER = "http://localhost:5005/model/parse"

# Load the Vosk model for speech recognition
MODEL_PATH = "./Vosk_model/vosk-model-small-hi-0.22"  # Update with your Vosk model path
model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, 16000)

# Start audio input
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
stream.start_stream()

# Path for audio feedback files
AUDIO_PATH = "C:/Users/viniy/Documents/Viniya Bhise/Projects/Voice-Controlled Wheelchair/Hi_model/Hi_audio_feedback/"

# Dictionary for intent-to-audio mapping
AUDIO_FEEDBACK = {
    "move_forward": "Hi_forward.wav",
    "move_backward": "Hi_backward.wav",
    "turn_left": "Hi_left.wav",
    "turn_right": "Hi_right.wav",
    "stop": "Hi_stop.wav",
    "speed_up": "Hi_speedUp.wav",
    "slow_down": "Hi_slowDown.wav",
    "out_of_scope": "Hi_unknown.wav",
    "nlu_fallback": "Hi_unknown.wav"
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


def get_intent(text):
    """
    Send recognized text to Rasa NLU, return intent name only if confidence > 0.8,
    and print extracted entities if available.
    """
    response = requests.post(RASA_SERVER, json={"text": text})
    if response.status_code == 200:
        data = response.json()
        
        # Extract intent and confidence
        intent_data = data.get("intent", {})
        intent_name = intent_data.get("name", "nlu_fallback")
        confidence = intent_data.get("confidence", 0.0)

        # Print entities
        entities = data.get("entities", [])
        if entities:
            print("Extracted Entities:")
            for entity in entities:
                print(f" - {entity.get('entity')}: {entity.get('value')}")
        else:
            print("No entities extracted.")

        # Confidence check
        if confidence < 0.8:
            return "nlu_fallback"
        return intent_name

    # If API call fails
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
    """Play corresponding audio feedback for the given intent."""
    if intent in AUDIO_FEEDBACK:
        audio_file = AUDIO_PATH + AUDIO_FEEDBACK[intent]
        try:
            sound = pygame.mixer.Sound(audio_file)
            sound.play()
            while pygame.mixer.get_busy():  # Wait until the audio finishes
                time.sleep(0.1)
        except:
            print(f"Could not play audio file: {audio_file}")

def control_wheelchair(intent):
    """Perform wheelchair actions based on the detected intent and provide audio feedback."""
    
    if intent in INTENT_DISPLAY_MAP:
        hindi_word, english_word = INTENT_DISPLAY_MAP[intent]
        print(f"Detected Intent: {hindi_word} ({english_word})")
    else:
        print("Detected Intent: Unknown")
        intent = "nlu_fallback"

    # Play audio feedback
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
    print("Unknown command, Please Repeat...")

# Main loop: Recognize speech → Get intent from Rasa → Control wheelchair
while True:
    text_command = recognize_speech()
    print(f"Recognized: {text_command}")
    intent = get_intent(text_command)
    control_wheelchair(intent)