# Fatigue Driving Detection System Based on Image Capture
Real-time driver fatigue detection using camera, MediaPipe, OpenCV and Flask.

## 📖 Project Introduction
This project is a **college course project** that uses a common USB camera to realize non-contact fatigue driving detection. Based on **MediaPipe** for facial landmark detection and computer vision algorithms, it recognizes eye closure and head nodding in real time. When fatigue behavior is detected, the system automatically triggers an alarm.

It is lightweight, easy to deploy, requires no model training, and is suitable for coursework, demonstration, and learning.

## ✨ Features
- Real-time camera image capture
- Facial landmark detection with MediaPipe
- Real-time eye closure detection
- Head nodding / drowsy behavior recognition
- Fatigue alarm with sound and on-screen alert
- Local log recording of fatigue events
- Simple and clear web interface

## 🛠️ Tech Stack
- Language: Python 3
- Backend: Flask
- Image Processing: OpenCV
- Facial Keypoints: **MediaPipe**
- Frontend: HTML + CSS + JavaScript
- Platform: Windows / macOS

## 📂 Project Structure



## 🚀 Quick Start
### 1. Clone or download the project
cd your-repo-name

### 2. Install dependencies
pip install -r requirements.txt

### 3. Run the system
python app.py

### 4. Open the web page
Visit in your browser:
http://127.0.0.1:5000

Click **Start Detection** to begin.

## 📌 Detection Rules
- Eye aspect ratio below threshold → eye closed
- Sustained eye closure for enough frames → fatigue alarm
- Head pitch angle over threshold → nodding detected
- Multiple nodding behaviors → fatigue alarm

## 🧪 How to Test
1. Keep eyes open and head steady → status: Normal
2. Close eyes for 1–2 seconds → eye closure alarm
3. Nod your head 2–3 times → nodding alarm
4. View fatigue history in the log panel

## 👥 Team Members (6-person team)
- Architecture & Backend Development
- Image Processing & MediaPipe Implementation
- Fatigue Detection Logic
- Frontend UI & Interaction
- Testing & Parameter Tuning
- Documentation & Presentation

## 📝 Notes
- This project is for **educational and coursework use only**.
- NOT intended for real driving scenarios.
- You may modify and extend functions freely.

## 🙏 Acknowledgments
- MediaPipe
- OpenCV
- Flask
- All open-source contributors
