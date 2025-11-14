"""
Voice Assistant - A simple voice-controlled assistant
"""
import speech_recognition as sr
import pyttsx3
import datetime
import requests
import re
import subprocess
import webbrowser
import os
import platform
import shutil


class VoiceAssistant:
    def __init__(self):
        """Initialize the voice assistant with speech recognition and text-to-speech."""
        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        self.tts_engine = pyttsx3.init()
        self.system = platform.system().lower()
        
        # Configure text-to-speech settings
        self._configure_tts()
        
        # Adjust for ambient noise
        print("Adjusting for ambient noise... Please wait.")
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=1)
        print("Ready to listen!")
    
    def _configure_tts(self):
        """Configure text-to-speech engine settings."""
        voices = self.tts_engine.getProperty('voices')
        if voices:
            # Try to set a more natural voice (usually index 1 is female, 0 is male)
            try:
                self.tts_engine.setProperty('voice', voices[1].id)
            except:
                self.tts_engine.setProperty('voice', voices[0].id)
        
        # Set speech rate (words per minute)
        self.tts_engine.setProperty('rate', 150)
        
        # Set volume (0.0 to 1.0)
        self.tts_engine.setProperty('volume', 0.9)
    
    def speak(self, text):
        """Convert text to speech and speak it."""
        print(f"Assistant: {text}")
        try:
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except Exception as e:
            print(f"Error in text-to-speech: {e}")
    
    def listen(self):
        """Listen for voice input and return recognized text."""
        try:
            with self.microphone as source:
                print("Listening...")
                # Listen for audio with timeout
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
            
            print("Processing...")
            # Use Google's speech recognition (requires internet)
            try:
                text = self.recognizer.recognize_google(audio)
                print(f"You said: {text}")
                return text.lower()
            except sr.UnknownValueError:
                print("Sorry, I could not understand the audio.")
                return None
            except sr.RequestError as e:
                print(f"Could not request results from speech recognition service: {e}")
                return None
                
        except sr.WaitTimeoutError:
            print("No speech detected within the timeout period.")
            return None
        except Exception as e:
            print(f"Error listening: {e}")
            return None
    
    def handle_command(self, command):
        """Process and execute voice commands."""
        if not command:
            return False
        
        # Greeting commands
        if any(word in command for word in ['hello', 'hi', 'hey', 'greetings']):
            self.speak("Hello! How can I help you today?")
            return True
        
        # Time commands
        elif any(word in command for word in ['time', 'what time']):
            current_time = datetime.datetime.now().strftime("%I:%M %p")
            self.speak(f"The current time is {current_time}")
            return True
        
        # Date commands
        elif any(word in command for word in ['date', 'what date', 'what day']):
            current_date = datetime.datetime.now().strftime("%A, %B %d, %Y")
            self.speak(f"Today is {current_date}")
            return True
        
        # Search commands
        elif any(word in command for word in ['search', 'find', 'look up', 'what is']):
            query = self._extract_search_query(command)
            if query:
                self.search_web(query)
            else:
                self.speak("What would you like me to search for?")
            return True
        
        # Open application commands
        elif any(word in command for word in ['open', 'launch', 'start']):
            self._handle_open_command(command)
            return True
        
        # Help command
        elif any(word in command for word in ['help', 'what can you do', 'commands', 'what commands']):
            self.show_help()
            return True
        
        # Exit commands
        elif any(word in command for word in ['exit', 'quit', 'goodbye', 'bye']):
            self.speak("Goodbye! Have a great day!")
            return False
        
        # Unknown command
        else:
            self.speak("I'm sorry, I didn't understand that command. Please try again.")
            return True
    
    def _extract_search_query(self, command):
        """Extract search query from command."""
        # Remove command words
        search_keywords = ['search', 'find', 'look up', 'what is', 'who is', 'tell me about']
        query = command
        
        for keyword in search_keywords:
            if keyword in command:
                # Extract text after the keyword
                parts = command.split(keyword, 1)
                if len(parts) > 1:
                    query = parts[1].strip()
                    break
        
        # Clean up the query
        query = re.sub(r'\b(for|about|on)\b', '', query).strip()
        return query if query else None
    
    def search_web(self, query):
        """Search the web for information."""
        try:
            self.speak(f"Searching for {query}")
            
            # Use DuckDuckGo instant answer API (no API key required)
            url = "https://api.duckduckgo.com/"
            params = {
                'q': query,
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1'
            }
            
            response = requests.get(url, params=params, timeout=5)
            data = response.json()
            
            # Check for instant answer
            if data.get('AbstractText'):
                abstract = data['AbstractText']
                # Limit response length
                if len(abstract) > 200:
                    abstract = abstract[:200] + "..."
                self.speak(abstract)
            elif data.get('Answer'):
                self.speak(data['Answer'])
            elif data.get('RelatedTopics') and len(data['RelatedTopics']) > 0:
                # Get first related topic
                first_topic = data['RelatedTopics'][0]
                if isinstance(first_topic, dict) and 'Text' in first_topic:
                    text = first_topic['Text']
                    if len(text) > 200:
                        text = text[:200] + "..."
                    self.speak(text)
                else:
                    self.speak(f"I found information about {query}, but couldn't retrieve a summary. You may want to search manually.")
            else:
                self.speak(f"I couldn't find specific information about {query}. You may want to search manually.")
                
        except requests.exceptions.RequestException as e:
            print(f"Network error during search: {e}")
            self.speak("I'm sorry, I encountered a network error while searching. Please check your internet connection.")
        except Exception as e:
            print(f"Error during web search: {e}")
            self.speak("I'm sorry, I encountered an error while searching.")
    
    def _handle_open_command(self, command):
        """Handle commands to open applications or websites."""
        command_lower = command.lower()
        
        # Website commands
        if any(word in command_lower for word in ['youtube', 'you tube']):
            self.open_website('https://www.youtube.com', 'YouTube')
        
        elif any(word in command_lower for word in ['google']):
            self.open_website('https://www.google.com', 'Google')
        
        elif any(word in command_lower for word in ['spotify']):
            # Try to open Spotify app, fallback to web
            if not self.open_application('spotify'):
                self.open_website('https://open.spotify.com', 'Spotify')
        
        elif any(word in command_lower for word in ['facebook', 'fb']):
            self.open_website('https://www.facebook.com', 'Facebook')
        
        elif any(word in command_lower for word in ['twitter', 'x']):
            self.open_website('https://www.twitter.com', 'Twitter')
        
        elif any(word in command_lower for word in ['instagram', 'insta']):
            self.open_website('https://www.instagram.com', 'Instagram')
        
        elif any(word in command_lower for word in ['github']):
            self.open_website('https://www.github.com', 'GitHub')
        
        elif any(word in command_lower for word in ['netflix']):
            self.open_website('https://www.netflix.com', 'Netflix')
        
        elif any(word in command_lower for word in ['gmail', 'email']):
            self.open_website('https://mail.google.com', 'Gmail')
        
        # Application commands
        elif any(word in command_lower for word in ['notepad', 'text editor']):
            self.open_application('notepad')
        
        elif any(word in command_lower for word in ['calculator', 'calc']):
            self.open_application('calc' if self.system == 'windows' else 'calculator')
        
        elif any(word in command_lower for word in ['paint', 'mspaint']):
            self.open_application('mspaint' if self.system == 'windows' else 'paint')
        
        elif any(word in command_lower for word in ['file explorer', 'explorer', 'files']):
            if self.system == 'windows':
                self.open_application('explorer')
            elif self.system == 'darwin':  # macOS
                subprocess.Popen(['open', '-a', 'Finder'])
                self.speak("Opening file explorer")
            else:  # Linux
                subprocess.Popen(['nautilus'])
                self.speak("Opening file explorer")
        
        elif any(word in command_lower for word in ['command prompt', 'cmd', 'terminal']):
            if self.system == 'windows':
                self.open_application('cmd')
            elif self.system == 'darwin':  # macOS
                subprocess.Popen(['open', '-a', 'Terminal'])
                self.speak("Opening terminal")
            else:  # Linux
                subprocess.Popen(['gnome-terminal'])
                self.speak("Opening terminal")
        
        elif any(word in command_lower for word in ['task manager', 'taskmanager']):
            if self.system == 'windows':
                self.open_application('taskmgr')
            else:
                self.speak("Task manager is only available on Windows")
        
        elif any(word in command_lower for word in ['settings', 'control panel']):
            if self.system == 'windows':
                try:
                    # Try Windows Settings app using os.startfile
                    os.startfile('ms-settings:')
                    self.speak("Opening settings")
                except:
                    try:
                        # Fallback to subprocess
                        subprocess.Popen(['start', 'ms-settings:'], shell=True)
                        self.speak("Opening settings")
                    except:
                        self.speak("I'm sorry, I couldn't open settings. Please try opening it manually.")
            elif self.system == 'darwin':  # macOS
                subprocess.Popen(['open', '-a', 'System Preferences'])
                self.speak("Opening settings")
            else:  # Linux
                self.speak("Please open settings manually")
        
        else:
            self.speak("I'm sorry, I didn't recognize which application or website you want to open. Please try again.")
    
    def show_help(self):
        """Display available commands."""
        help_text = """Here are the commands I can help you with:
        
        Basic Commands:
        - Say "Hello" or "Hi" for a greeting
        - Say "What time is it?" to get the current time
        - Say "What date is it?" to get the current date
        - Say "Help" to see this list
        
        Search:
        - Say "Search for [query]" or "What is [query]?" to search the web
        
        Open Websites:
        - Say "Open YouTube" to open YouTube
        - Say "Open Google" to open Google
        - Say "Open Spotify" to open Spotify
        - Say "Open Facebook", "Open Twitter", "Open Instagram"
        - Say "Open GitHub", "Open Netflix", "Open Gmail"
        
        Open Applications:
        - Say "Open Notepad" or "Open Text Editor"
        - Say "Open Calculator"
        - Say "Open Paint"
        - Say "Open File Explorer" or "Open Files"
        - Say "Open Command Prompt" or "Open Terminal"
        - Say "Open Task Manager"
        - Say "Open Settings"
        
        Exit:
        - Say "Exit" or "Goodbye" to quit
        
        You can also say "Help" anytime to see this list again."""
        
        print(help_text)
        self.speak("I've displayed the available commands in the console. Here's a quick summary: I can greet you, tell you the time and date, search the web, open websites like YouTube and Google, and open applications like Notepad, Calculator, and File Explorer. Just say Help anytime to see all commands.")
    
    def open_website(self, url, name):
        """Open a website in the default browser."""
        try:
            webbrowser.open(url)
            self.speak(f"Opening {name}")
        except Exception as e:
            print(f"Error opening website: {e}")
            self.speak(f"I'm sorry, I couldn't open {name}. Please try again.")
    
    def open_application(self, app_name):
        """Open an application based on the system."""
        try:
            if self.system == 'windows':
                # Try common Windows applications
                apps = {
                    'notepad': 'notepad.exe',
                    'calc': 'calc.exe',
                    'calculator': 'calc.exe',
                    'mspaint': 'mspaint.exe',
                    'paint': 'mspaint.exe',
                    'explorer': 'explorer.exe',
                    'cmd': 'cmd.exe',
                    'taskmgr': 'taskmgr.exe',
                }
                
                # Check if it's a known app
                if app_name.lower() in apps:
                    subprocess.Popen([apps[app_name.lower()]])
                    self.speak(f"Opening {app_name}")
                    return True
                
                # Try to find the application in PATH
                app_path = shutil.which(app_name)
                if app_path:
                    subprocess.Popen([app_path])
                    self.speak(f"Opening {app_name}")
                    return True
                
                # Try common installation paths for Spotify
                if app_name.lower() == 'spotify':
                    spotify_paths = [
                        os.path.expanduser(r'~\AppData\Roaming\Spotify\Spotify.exe'),
                        r'C:\Users\%USERNAME%\AppData\Roaming\Spotify\Spotify.exe',
                        r'C:\Program Files\Spotify\Spotify.exe',
                    ]
                    for path in spotify_paths:
                        expanded_path = os.path.expandvars(path)
                        if os.path.exists(expanded_path):
                            subprocess.Popen([expanded_path])
                            self.speak("Opening Spotify")
                            return True
                    
                    # Try shell command
                    try:
                        subprocess.Popen(['start', 'spotify'], shell=True)
                        self.speak("Opening Spotify")
                        return True
                    except:
                        pass
                
                # Try using 'start' command for Windows
                try:
                    subprocess.Popen(['start', app_name], shell=True)
                    self.speak(f"Opening {app_name}")
                    return True
                except:
                    pass
            
            elif self.system == 'darwin':  # macOS
                # Try to open application using 'open' command
                try:
                    subprocess.Popen(['open', '-a', app_name])
                    self.speak(f"Opening {app_name}")
                    return True
                except:
                    pass
            
            else:  # Linux
                # Try to find and open the application
                app_path = shutil.which(app_name)
                if app_path:
                    subprocess.Popen([app_path])
                    self.speak(f"Opening {app_name}")
                    return True
            
            # If all methods failed
            self.speak(f"I'm sorry, I couldn't find {app_name}. It may not be installed.")
            return False
            
        except Exception as e:
            print(f"Error opening application: {e}")
            self.speak(f"I'm sorry, I encountered an error while trying to open {app_name}.")
            return False
    
    def run(self):
        """Main loop for the voice assistant."""
        self.speak("Hello! I'm your voice assistant. How can I help you?")
        
        running = True
        while running:
            try:
                command = self.listen()
                if command:
                    running = self.handle_command(command)
            except KeyboardInterrupt:
                print("\nInterrupted by user")
                self.speak("Goodbye!")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                self.speak("I encountered an error. Let's try again.")


if __name__ == "__main__":
    assistant = VoiceAssistant()
    assistant.run()

