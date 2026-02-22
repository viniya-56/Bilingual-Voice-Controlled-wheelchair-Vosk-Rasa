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
SWITCH_PIN = 22  # Joystick switch button
TRIG = 24         # Ultrasonic TRIG
ECHO = 25         # Ultrasonic ECHO
BUZZER_PIN = 7
RELAY_PIN = 16    # relay 

# === Initialize GPIO with lgpio ===
h = lgpio.gpiochip_open(0)  # Open GPIO chip

lgpio.gpio_claim_output(h, DIR_1_PIN, 0)
lgpio.gpio_claim_output(h, DIR_2_PIN, 0)
lgpio.gpio_claim_output(h, PWM_PIN_1, 0)
lgpio.gpio_claim_output(h, PWM_PIN_2, 0)
lgpio.gpio_claim_output(h, CLUTCH_PIN, 0)
lgpio.gpio_claim_output(h, TRIG)
lgpio.gpio_claim_input(h, ECHO)
lgpio.gpio_claim_input(h, SWITCH_PIN, lgpio.SET_PULL_UP)
lgpio.gpio_claim_output(h, RELAY_PIN, 0)

# PWM Setup
PWM_FREQ = 7000
lgpio.tx_pwm(h, PWM_PIN_1, PWM_FREQ, 0)
lgpio.tx_pwm(h, PWM_PIN_2, PWM_FREQ, 0)

# === OLED Setup ===
serial = i2c(port=1, address=0x3C)
device = sh1106(serial)

# === Status variables ===
current_movement = "Stop"
current_mode = "Joystick"
obstacle_status = "Clear"
prev_movement = ""
prev_mode = ""
prev_obstacle = ""

# Command queue for voice mode
command_queue = Queue()
stop_event = Event()
mode_change_event = Event()

# Define shortcut keywords (in Devanagari for Hindi Vosk model)
JOYSTICK_KEYWORDS = ["जॉयस्टिक", "जोयस्टिक"]
STOP_KEYWORDS = ["रुक जाओ", "रोक दो", "आगे मत बढ़ो", "रुको", "रोक", "रोक दो", "स्टॉप", "रोको", "रोग", "टॉप"]

def show_welcome_message():
    """Display welcome message on OLED for 4 seconds"""
    with canvas(device) as draw:
        draw.rectangle(device.bounding_box, outline="white", fill="black")
        draw.text((10, 10), "Wheelchair Control", fill="white")
        draw.text((20, 30), "System Ready", fill="white")
    time.sleep(4)

def update_display():
    """Update OLED display with current status"""
    global prev_movement, prev_mode, prev_obstacle
    
    if (current_movement != prev_movement or 
        current_mode != prev_mode or 
        obstacle_status != prev_obstacle):
        
        with canvas(device) as draw:
            draw.rectangle(device.bounding_box, outline="white", fill="black")
            draw.text((5, 5), f"Mode: {current_mode}", fill="white")
            draw.text((5, 17), f"Movement: {current_movement}", fill="white")
            draw.text((5, 30), f"Obstacle: {obstacle_status}", fill="white")
        
        prev_movement = current_movement
        prev_mode = current_mode
        prev_obstacle = obstacle_status

# Ultrasonic distance measurement
def get_distance():
    lgpio.gpio_write(h, TRIG, 1)
    time.sleep(10e-6)
    lgpio.gpio_write(h, TRIG, 0)

    start_time = time.time()
    timeout = start_time + 0.04
    while lgpio.gpio_read(h, ECHO) == 0:
        if time.time() > timeout:
            return None
    pulse_start = time.time()

    timeout = time.time() + 0.04
    while lgpio.gpio_read(h, ECHO) == 1:
        if time.time() > timeout:
            return None
    pulse_end = time.time()

    pulse_duration = pulse_end - pulse_start
    distance_cm = (pulse_duration * 34300) / 2
    return distance_cm

# Joystick Setup
i2c_bus = busio.I2C(board.SCL, board.SDA)
ads = ADS.ADS1115(i2c_bus)
x_axis = AnalogIn(ads, ADS.P0)
y_axis = AnalogIn(ads, ADS.P1)

# Clutch control functions
def disengage_clutch():
    print("Clutch disengaged")
    lgpio.gpio_write(h, CLUTCH_PIN, 1)

def engage_clutch():
    print("Clutch engaged")
    lgpio.gpio_write(h, CLUTCH_PIN, 0)

# PWM Control
def setPWM(speed):
    duty = min(max(speed, 0), 100)
    lgpio.tx_pwm(h, PWM_PIN_1, PWM_FREQ, duty)
    lgpio.tx_pwm(h, PWM_PIN_2, PWM_FREQ, duty)
    print(f"Speed set to {duty}%")

# Motor Control Functions
def moveForward(speed):
    global current_movement
    print(f"Forward - गति: {speed:.2f}%")
    current_movement = "Forward"
    lgpio.gpio_write(h, DIR_1_PIN, 0)
    lgpio.gpio_write(h, DIR_2_PIN, 0)
    setPWM(speed)

def moveBackward(speed):
    global current_movement
    print(f"Backward - गति: {speed:.2f}%")
    current_movement = "Backward"
    lgpio.gpio_write(h, DIR_1_PIN, 1)
    lgpio.gpio_write(h, DIR_2_PIN, 1)
    setPWM(speed)

def turnLeft(speed):
    global current_movement
    print(f"Left - गति: {speed:.2f}%")
    current_movement = "Left"
    lgpio.gpio_write(h, DIR_1_PIN, 0)
    lgpio.gpio_write(h, DIR_2_PIN, 1)
    setPWM(speed)

def turnRight(speed):
    global current_movement
    print(f"Right - गति: {speed:.2f}%")
    current_movement = "Right"
    lgpio.gpio_write(h, DIR_1_PIN, 1)
    lgpio.gpio_write(h, DIR_2_PIN, 0)
    setPWM(speed)

def stop():
    global current_movement
    print("व्हीलचेयर रोकी गई है")
    current_movement = "Stop"
    lgpio.tx_pwm(h, PWM_PIN_1, PWM_FREQ, 0)
    lgpio.tx_pwm(h, PWM_PIN_2, PWM_FREQ, 0)
    lgpio.gpio_write(h, DIR_1_PIN, 0)
    lgpio.gpio_write(h, DIR_2_PIN, 0)

# Joystick Logic
def get_direction_and_speed(x, y):
    # === Forward Movement ===
    if 15000 <= x <= 17500:
        return "Forward", 15
    elif 10000 <= x < 15000 and not (11500 <= x <= 13000):
        return "Forward", 20
    elif 5000 <= x < 10000:
        return "Forward", 25
    elif x < 5000:
        return "Forward", 33

    # === Backward Movement ===
    elif 21000 <= x <= 30000 and 20000 <= y <= 21000:
        return "Backward", 15
    elif 11500 < x < 13000 and 21100 <= y <= 23000:
        return "Backward", 20

    # === Right Movement ===
    elif 19700 <= x <= 20000 and 6000 <= y <= 16000:
        return "Right", 10
    elif 19700 <= x <= 20000 and y < 6000:
        return "Right", 15

    # === Left Movement ===
    elif 23000 <= y <= 30000:
        return "Left", 10
    elif y < 13000:
        return "Left", 15

    # === Neutral Zone ===
    elif 19000 <= x <= 20000 and 20000 <= y <= 21000:
        return "Stop", 0

    else:
        return "Unknown", 0

# Voice Control Setup
pygame.mixer.init()
RASA_SERVER = "http://localhost:5005/model/parse"
MODEL_PATH = "./Vosk_model/vosk-model-small-hi-0.22"
model = Model(MODEL_PATH)
recognizer = KaldiRecognizer(model, 16000)
p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
stream.start_stream()

AUDIO_PATH = "/home/viniya/Voice Controlled Wheelchair/Hi_model/Hi_audio_feedback/"
AUDIO_FEEDBACK = {
    "move_forward": "Hi_forward.wav",
    "move_backward": "Hi_backward.wav",
    "turn_left": "Hi_left.wav",
    "turn_right": "Hi_right.wav",
    "stop": "Hi_stop.wav",
    "speed_up": "Hi_speedUp.wav",
    "slow_down": "Hi_slowDown.wav",
    "out_of_scope": "Hi_unknown.wav",
    "nlu_fallback": "Hi_unknown.wav",
    "switch_to_voice": "Hi_voice_mode_activated.wav",
    "switch_to_joystick": "Hi_switch_to_joystick.wav"
}

INTENT_DISPLAY_MAP = {
    "move_forward": ("आगे", "Forward"),
    "move_backward": ("पीछे", "Backward"),
    "turn_left": ("बाएँ मुड़ो", "Turn Left"),
    "turn_right": ("दाएँ मुड़ो", "Turn Right"),
    "stop": ("रुको", "Stop"),
    "speed_up": ("गति बढ़ाओ", "Speed Up"),
    "slow_down": ("गति कम करो", "Slow Down"),
    "nlu_fallback": ("कृपया दोहराएँ", "Please Repeat"),
    "out_of_scope": ("कृपया दोहराएँ", "Please Repeat"),
    "switch_to_joystick": ("जॉयस्टिक मोड", "Joystick Mode"),
    "switch_to_voice": ("वॉइस मोड", "Voice Mode"),
}

speed = 18  # Initial speed percentage

def get_intent(text):
    # First check for fast commands
    if any(keyword in text for keyword in JOYSTICK_KEYWORDS):
        print("Fast matched: switch_to_joystick")
        return "switch_to_joystick"
    elif any(keyword in text for keyword in STOP_KEYWORDS):
        print("Fast matched: stop")
        return "stop"
    
    # If no fast match, use Rasa NLU
    try:
        response = requests.post(RASA_SERVER, json={"text": text}, timeout=1.0)
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
    except requests.exceptions.RequestException:
        print("NLU server timeout")
    return "nlu_fallback"

def recognize_speech(timeout=2):
    print("Listening for commands...")
    start_time = time.time()
    while time.time() - start_time < timeout and not mode_change_event.is_set():
        data = stream.read(4000, exception_on_overflow=False)
        if recognizer.AcceptWaveform(data):
            result = json.loads(recognizer.Result())
            text = result.get("text", "").strip()
            if text:
                print(f"\nRecognized Text: {text}")
                return text
    return ""  # Return empty if nothing detected within timeout

def play_audio_feedback(intent):
    if intent in AUDIO_FEEDBACK and not mode_change_event.is_set():
        audio_file = AUDIO_PATH + AUDIO_FEEDBACK[intent]
        try:
            sound = pygame.mixer.Sound(audio_file)
            sound.play()
            while pygame.mixer.get_busy() and not mode_change_event.is_set():
                time.sleep(0.1)
        except:
            print(f"Could not play audio: {audio_file}")

def ramp_up_motion(direction_func):
    global speed
    print("Ramping up...")
    speed = 15
    disengage_clutch()
    while speed < 22 and not mode_change_event.is_set():
        speed += 2
        print(f"Speed: {speed}%")
        direction_func(speed)
        time.sleep(0.2)

def ramp_down_motion():
    global speed, last_movement_intent

    print("Ramping down...")

    # Map the last movement intent to the corresponding function
    movement_map = {
        "move_forward": moveForward,
        "move_backward": moveBackward,
        "turn_left": turnLeft,
        "turn_right": turnRight,
    }

    direction_func = movement_map.get(last_movement_intent)

    # If direction is known, ramp down in that direction
    if direction_func:
        while speed > 0 and not mode_change_event.is_set():
            speed -= 5
            print(f"Speed: {speed}%")
            direction_func(speed)
            time.sleep(0.2)

    if not mode_change_event.is_set():
        stop()
        engage_clutch()

def speedUp():
    global speed
    speed = min(100, speed + 10)
    print(f"Speed increased: {speed}%")
    return speed

def slowDown():
    global speed
    speed = max(0, speed - 10)
    print(f"Speed decreased: {speed}%")
    return speed

last_movement_intent = None  # Track the last movement direction

def voice_command_processor():
    """Process voice commands in a separate thread"""
    while not stop_event.is_set():
        if current_mode == "Voice" and not mode_change_event.is_set():
            text = recognize_speech()
            if text:
                intent = get_intent(text)
                if intent == "switch_to_joystick":
                    mode_change_event.set()
                    command_queue.put(("switch_mode", "Joystick"))
                else:
                    command_queue.put(("command", intent))
        time.sleep(0.1)

def execute_voice_commands():
    """Execute commands from the queue with priority handling"""
    while not stop_event.is_set():
        try:
            # Get command with short timeout to be responsive to mode changes
            cmd_type, data = command_queue.get(timeout=0.1)
            
            if cmd_type == "switch_mode":
                handle_mode_change(data)
            elif cmd_type == "command" and current_mode == "Voice":
                execute_single_command(data)
                
        except Empty:
            continue
        except Exception as e:
            print(f"Command execution error: {e}")

def execute_single_command(intent):
    global speed, last_movement_intent, current_mode, current_movement
    
    if mode_change_event.is_set():
        return

    # Display intent
    if intent in INTENT_DISPLAY_MAP:
        hindi_word, english_word = INTENT_DISPLAY_MAP[intent]
        print(f"Extracted Intent: {hindi_word} ({english_word})")
    else:
        print("Unknown command")
        intent = "nlu_fallback"

    play_audio_feedback(intent)

    movement_map = {
        "move_forward": moveForward,
        "move_backward": moveBackward,
    }

    # Handle special intents first
    if intent == "switch_to_joystick":
        handle_mode_change("Joystick")
        return
        
    if intent == "switch_to_voice":
        handle_mode_change("Voice")
        return

    # Voice-mode specific: 90° turn for left/right (timed)
    if current_mode == "Voice" and intent == "turn_left":
        disengage_clutch()
        print("Turning left (voice-controlled 90°)...")
        turnLeft(15)  # 15% speed
        time.sleep(1.0)
        stop()
        engage_clutch()
        last_movement_intent = None  # End of motion

    elif current_mode == "Voice" and intent == "turn_right":
        disengage_clutch()
        print("Turning right (voice-controlled 90°)...")
        turnRight(15)
        time.sleep(1.0)
        stop()
        engage_clutch()
        last_movement_intent = None  # End of motion

    elif intent in movement_map:
        if last_movement_intent and intent != last_movement_intent:
            ramp_down_motion()
        ramp_up_motion(movement_map[intent])
        last_movement_intent = intent

    elif intent == "stop":
        ramp_down_motion()
        last_movement_intent = None

    elif intent == "speed_up":
        speed = speedUp()

    elif intent == "slow_down":
        speed = slowDown()

    else:
        print("Unknown or fallback command")

def handle_mode_change(new_mode):
    global current_mode, current_movement, manual_mode
    
    # Clear any pending commands
    with command_queue.mutex:
        command_queue.queue.clear()
    
    # Stop any current movement
    stop()
    
    # Update mode
    if new_mode == "Manual":
        manual_mode = True
        current_mode = "Manual"
        lgpio.gpio_write(h, RELAY_PIN, 0)
        play_audio_feedback("manual_mode")
    else:
        if new_mode == "Joystick":
            play_audio_feedback("switch_to_joystick")
        elif new_mode == "Voice":
            play_audio_feedback("switch_to_voice")
        
        manual_mode = False
        current_mode = new_mode
        lgpio.gpio_write(h, RELAY_PIN, 1)
    
    current_movement = "Stop"
    mode_change_event.clear()
    print(f"Switched to {current_mode} Mode")

# Main Loop Control
last_toggle_time = 0
button_press_start = 0
manual_mode = False
current_speed = 0

def check_mode_toggle():
    global current_mode, last_toggle_time, button_press_start, manual_mode, current_movement

    current_time = time.time()
    button_state = lgpio.gpio_read(h, SWITCH_PIN)

    # Button just pressed
    if button_state == 0 and button_press_start == 0:
        button_press_start = current_time
    
    # Button released
    elif button_state == 1 and button_press_start > 0:
        press_duration = current_time - button_press_start
        
        # Short press (less than 1.5s) - toggle between voice and joystick
        if press_duration < 1.5 and (current_time - last_toggle_time) > 0.5:
            if not manual_mode:
                mode_change_event.set()
                if current_mode == "Joystick":
                    command_queue.put(("switch_mode", "Voice"))
                else:
                    command_queue.put(("switch_mode", "Joystick"))
                last_toggle_time = current_time
        
        # Reset button press tracking
        button_press_start = 0
    
    # Long press (more than 3s) - toggle manual mode
    elif button_state == 0 and button_press_start > 0 and (current_time - button_press_start) > 3:
        mode_change_event.set()
        if manual_mode:
            command_queue.put(("switch_mode", "Joystick"))
        else:
            command_queue.put(("switch_mode", "Manual"))
        
        button_press_start = 0  # Reset after mode change
        last_toggle_time = current_time

# Show welcome message at startup
show_welcome_message()

try:
    # Turn ON relay at start
    lgpio.gpio_write(h, RELAY_PIN, 1)
    print("Relay ON at startup")
    
    # Start voice command processing threads
    voice_thread = Thread(target=voice_command_processor)
    voice_thread.daemon = True
    voice_thread.start()
    
    command_executor = Thread(target=execute_voice_commands)
    command_executor.daemon = True
    command_executor.start()
    
    while True:
        check_mode_toggle()

        # --- Measure distance for obstacle detection ---
        dist = get_distance()
        if dist is not None and dist < 40:
            obstacle_status = "Obstacle!"
            stop()
            engage_clutch()
            current_speed = 0
        else:
            obstacle_status = "Clear"

        if manual_mode:
            # In manual mode, don't process any commands
            continue
            
        elif current_mode == "Joystick":
            print("[JOYSTICK MODE]")
            x_val = x_axis.value
            y_val = y_axis.value
            print(f"X: {x_val}, Y: {y_val}")

            direction, spd = get_direction_and_speed(x_val, y_val)

            if direction in ["Forward", "Backward", "Left", "Right"]:
                disengage_clutch()
                step = 1 if current_speed < spd else -1
                for s in range(current_speed, spd + step, step):
                    if direction == "Forward":
                        moveForward(s)
                    elif direction == "Backward":
                        moveBackward(s)
                    elif direction == "Left":
                        turnLeft(s)
                    elif direction == "Right":
                        turnRight(s)
                    time.sleep(0.07)
                current_speed = spd

            elif direction == "Stop":
                for s in range(current_speed, -1, -1):
                    setPWM(s)
                    time.sleep(0.05)
                current_speed = 0
                stop()
                engage_clutch()

            else:
                print("Unknown direction")
                for s in range(current_speed, -1, -1):
                    setPWM(s)
                    time.sleep(0.07)
                current_speed = 0
                stop()
                engage_clutch()

        # --- Update OLED display every loop iteration ---
        update_display()

except KeyboardInterrupt:
    stop_event.set()
    mode_change_event.set()
    lgpio.gpio_write(h, RELAY_PIN, 0)
    print("Relay OFF at shutdown")
    print("Exiting safely...")
    stop()
    engage_clutch()
    lgpio.gpiochip_close(h)
    stream.stop_stream()
    stream.close()
    p.terminate()
    pygame.mixer.quit()
finally:
    stop()
    engage_clutch()
    lgpio.gpiochip_close(h)