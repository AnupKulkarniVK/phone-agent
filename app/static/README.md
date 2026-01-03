Static Audio Files
This directory contains audio files used by the phone agent.
Sounds
writing-on-a-laptop-keyboard.wav

Purpose: Typing sound played after Claude speaks, before listening for user input
Duration: ~0.5-1 second
Format: WAV (can also use MP3 if converted)
Usage: Creates natural conversation rhythm and signals the system is ready to listen

Adding New Sounds

Add sound file to static/sounds/
Update app/main.py to reference the new sound
Commit the file to git (files in this directory ARE tracked)

File Size Guidelines

Keep sounds under 100KB for fast loading
WAV or MP3 format
Mono audio is fine (stereo not necessary for phone calls)
16kHz or 8kHz sample rate is sufficient for phone quality