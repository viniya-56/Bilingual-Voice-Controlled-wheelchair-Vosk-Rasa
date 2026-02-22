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
MODEL_PATH = "./Vosk_model/vosk-model-small-en-in-0.4"  # Update with your Vosk model path
model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, 16000)

# Start audio input
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
stream.start_stream()

# Path for audio feedback files
AUDIO_PATH = "C:/Users/viniy/Documents/Viniya Bhise/Projects/Voice-Controlled Wheelchair/En_model/En_audio_feedback/" 

AUDIO_FEEDBACK = {
    "move_forward": "En_forward.wav",
    "move_backward": "En_backward.wav",
    "turn_left": "En_left.wav",
    "turn_right": "En_right.wav",
    "stop": "En_stop.wav",
    "speed_up": "En_speedUp.wav",
    "slow_down": "En_slowDown.wav",
    "out_of_scope": "En_unknown.wav",
    "nlu_fallback": "En_unknown.wav"
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
    """Perform wheelchair actions based on the detected intent."""
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
    print("Unknown command, Please repeat...")


# Main loop: Recognize speech → Get intent from Rasa → Control wheelchair
while True:
    text_command = recognize_speech()
    print(f"Recognized: {text_command}")
    intent = get_intent(text_command)
    print(f"Detected Intent: {intent}")
    control_wheelchair(intent)

