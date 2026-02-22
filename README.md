#  Bilingual Voice Controlled Wheelchair (Vosk + Rasa NLU)

A **bilingual voice-controlled wheelchair system** with **audio feedback**, supporting **English and Hindi** commands.  
This project integrates:

-  **Vosk** – Offline speech recognition  
-  **Rasa NLU** – Intent recognition  
-  **Audio feedback** for user interaction  
-  **Joystick + Manual + Voice modes**  
-  **Obstacle detection using ultrasonic sensor**  
-  Designed for **Raspberry Pi / embedded Linux systems**

---

## ✨ Features

-  Offline voice recognition (no internet needed)
-  Supports **English & Hindi**
-  Mode switching:
  -  Voice mode  
  -  Joystick mode  
  -  Manual mode
-  Audio feedback for commands
-  Wake word detection support
-  Obstacle detection & safety stop
-  OLED display status updates
-  Speed control (increase / decrease)

---

## 📂 Project Structure
<pre>
Bilingual-Voice-Controlled-Wheelchair-Vosk-Rasa/
│
├── En_model/
│ ├── data/
│ ├── tests/
│ ├── config.yml
│ ├── domain.yml
│ ├── En_main.py
│ ├── En_vosk_and_rasa_withAudioFeedback.py
│ ├── En_vosk_rasa_wakeword.py
│ └── Vosk_model/
│
├── Hi_model/
│ ├── data/
│ ├── tests/
│ ├── config.yml
│ ├── domain.yml
│ ├── Hi_main.py
│ ├── Hi_vosk_and_rasa_withAudioFeedback.py
│ ├── Hi_vosk_rasa_wakeword.py
│ └── Vosk_model/
|
├── .gitignore
├── LICENSE
└── README.md
</pre>
---

## ⚙️ Requirements

- Python 3.8+
- Raspberry Pi / Linux PC
- Microphone
- Speaker / Headphones
- Motor driver + DC motors
- Ultrasonic sensor (HC-SR04)
- OLED display (SH1106)
- Joystick module
- Relay module

## Python Libraries

bash
pip install vosk rasa pygame pyaudio lgpio adafruit-circuitpython-ads1x15 luma.oled requests


##  How to Run

- 1️⃣ Train Rasa Models
cd En_model
rasa train

cd ../Hi_model
rasa train

- 2️⃣ Start Rasa Server
rasa run --enable-api

- 3️⃣ Run Wheelchair Program

For English:
python En_main.py

For Hindi:
python Hi_main.py
