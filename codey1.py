# Codey NEVER executes arbitrary user code.

import os
import csv
import re
import ast
import json
import random
import platform
from datetime import datetime

try:
    import speech_recognition as sr
except Exception:
    sr = None

try:
    import pyttsx3
except Exception:
    pyttsx3 = None

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.core.clipboard import Clipboard
from kivy.core.window import Window

from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.image import Image
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.spinner import Spinner
from kivy.uix.widget import Widget

APP_DIR = os.path.dirname(os.path.abspath(__file__))

HISTORY_FILE = os.path.join(
    APP_DIR,
    "codey_history.csv"
)

RULES_FILE = os.path.join(
    APP_DIR,
    "codey_rules.json"
)

CHARACTER_FILE = os.path.join(
    APP_DIR,
    "codey.png"
)

EMOJI_FONT = os.path.join(
    APP_DIR,
    "emoji_font.ttf"
)

MAX_CONTEXT = 12
MAX_HISTORY_ROWS = 500

# Natural spoken replacements keep visible emojis in chat while making TTS sound human.
EMOJI_SPEECH = {
    "🥹": "aww", "🥺": "ouch", "😭": "oh no", "😂": "khikhikhi", "🤣": "haha",
    "😳": "oh", "🫣": "uhh", "😊": "smile", "🥰": "glad", "😌": "okay",
    "🤔": "hmm", "🧐": "let's see", "😎": "nice", "😈": "hehe", "🤖": "",
    "💙": "", "✨": "", "💻": "", "🔥": "", "🎉": "", "🤝": "",
    "👀": "", "🥲": "ahhh", "🫠": "oh man", "😅": "oops", "😶‍🌫️": "uh",
    "💪": "", "🌱": "", "🏆": "", "☀️": "", "🌙": "", "🙏": "",
}

def is_phone_layout():
    try:
        return Window.width < dp(800)
    except Exception:
        return False

def responsive_sidebar_width():
    if is_phone_layout():
        return dp(125)

    return max(
        dp(190),
        Window.width * 0.24
    )

def now_string():
    return datetime.now().strftime(
        "%Y-%m-%d %H:%M:%S"
    )

def clean_text(text):
    return re.sub(
        r"\s+",
        " ",
        text.strip()
    )

def speech_friendly_text(text):
    """Turn visible emoji into short natural spoken reactions for optional TTS."""
    speech = text
    for emoji, spoken in EMOJI_SPEECH.items():
        speech = speech.replace(emoji, f" {spoken} ")
    speech = re.sub(r"[*_`#]", "", speech)
    speech = re.sub(r"\s+", " ", speech).strip()
    return speech

def contains_any(text, words):
    text = text.lower()

    return any(
        word in text
        for word in words
    )

def extract_code_block(text):
    pattern = (
        r"```(?:python|py|java|c|cpp|c\+\+)?"
        r"\s*\n?(.*?)```"
    )

    match = re.search(
        pattern,
        text,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        return None, None

    full = match.group(0)

    code = match.group(1).strip()

    first_line = (
        full
        .split("\n", 1)[0]
        .lower()
    )

    language = None

    if (
        "python" in first_line
        or "py" in first_line
    ):
        language = "Python"

    elif "java" in first_line:
        language = "Java"

    elif (
        "cpp" in first_line
        or "c++" in first_line
    ):
        language = "C++"

    elif re.search(
        r"\bc\b",
        first_line
    ):
        language = "C"

    return language, code

def detect_language(code):
    if not code or not code.strip():
        return "Unknown"

    text = code.strip()

    python_signals = [
        r"\bdef\s+\w+\s*\(",
        r"\bimport\s+\w+",
        r"\bfrom\s+\w+\s+import\b",
        r"\bprint\s*\(",
        r"\belif\b",
        r"\bNone\b",
        r"\bTrue\b",
        r"\bFalse\b",
    ]

    java_signals = [
        r"\bpublic\s+class\b",
        r"\bprivate\s+\w+",
        r"\bSystem\.out\.println\s*\(",
        r"\bpublic\s+static\s+void\s+main\b",
        r"\bnew\s+\w+\s*\(",
    ]

    c_signals = [
        r"#include\s*<",
        r"\bprintf\s*\(",
        r"\bscanf\s*\(",
        r"\bint\s+main\s*\(",
        r"\bstd::",
        r"\bcout\s*<<",
        r"\bcin\s*>>",
    ]

    scores = {
        "Python": sum(
            bool(re.search(p, text))
            for p in python_signals
        ),

        "Java": sum(
            bool(re.search(p, text))
            for p in java_signals
        ),

        "C/C++": sum(
            bool(re.search(p, text))
            for p in c_signals
        ),
    }

    best = max(
        scores,
        key=scores.get
    )

    if scores[best] == 0:
        return "Unknown"

    if best == "C/C++":

        if (
            "std::" in text
            or "cout" in text
            or "cin" in text
        ):
            return "C++"

        return "C"

    return best

def normalize_hinglish(text):

    replacements = {

        "isme": "in this",
        "is mein": "in this",
        "isme se": "from this",

        "kaha": "where",
        "kahan": "where",

        "kaise": "how",
        "kyu": "why",
        "kyun": "why",
        "kya": "what",

        "batao": "tell me",
        "btao": "tell me",
        "bata": "tell me",
        "pls": "please",
        "plz": "please",
        "plss": "please",
        "kr": "do",
        "krna": "do",
        "karo": "do",
        "kro": "do",
        "kaise": "how",
        "samjha do": "explain",
        "samjha de": "explain",
        "samjhao": "explain",
        "samjha": "understand",
        "samajh": "understand",

        "karna hai": "want to do",
        "kar do": "do it",

        "add kar": "add",
        "remove kar": "remove",
        "fix kar": "fix",
        "sahi kar": "fix",

        "sahi hai": "is correct",
        "galat": "wrong",

        "problem": "problem",

        "error aa raha":
            "error is happening",

        "chal nahi raha":
            "not working",

        "nahi chal raha":
            "not working",

        "kaam nahi kar":
            "not working",

        "bana do":
            "make it",

        "dikhao":
            "show me",

        "mujhe": "I",

        "mera": "my",
        "meri": "my",
        "mere": "my",

        "tum": "you",
        "tu": "you",
        "aap": "you",

        "bhai": "buddy",
        "yaar": "buddy",
    }

    result = text.lower()

    for old, new in replacements.items():
        result = result.replace(
            old,
            new
        )

    return result

def looks_hinglish(text):

    words = text.lower().split()

    indicators = {
        "bhai",
        "yaar",
        "isme",
        "mujhe",
        "mera",
        "meri",
        "mere",
        "kaha",
        "kahan",
        "kaise",
        "kyu",
        "kyun",
        "batao",
        "btao",
        "samjhao",
        "karna",
        "kar",
        "do",
        "haan",
        "nahi",
        "acha",
        "achha",
        "arre",
        "arey",
        "bas",
        "thoda",
        "zyada",
        "wala",
        "wali",
        "waise",
        "kyunki",
        "lekin",
    }

    return any(
        word in indicators
        for word in words
    )

class CodeyPersonality:
    # Response pools keep Codey expressive without repeating one fixed sentence.

    def __init__(self):

        self.mood = "normal"

        self.responses = {

            "casual": [
                "Okay okayyy 😭 I'm trying!",
                "Alright, alright! I'm on it. 🤖",
                "Whattt? 😭 What did I do this time?",
                "Brooo, what happened? 😂",
                "Dude... that sounded serious. 😭",
                "Okay, fair. Let me fix this. 🤖",
                "I knowww 😭 Give me another shot.",
                "Alright man, I'm listening. 👀",
                "Okay okay, no need to panic! 😭",
                "Uhh... I feel like I messed up. 🫠",
                "That 'dude' sounded VERY disappointed. 😭😂",
                "Okay... message received. 😂",
                "Yep yep, I'm still here! 🤖",
                "Alright! Let's try that again. 💪",
                "Okayyy, what went wrong? 😭",
                "I hear you, man. Let's sort it out. 🤖",
                "Dude, I'm doing my best here. 😭😂",
                "Give me a second, dude! 😭",
                "Alright, I'm paying attention now. 👀",
                "Okay, you've got my attention. 🤖",
                "Bro, I'm working on it! 😂",
                "Okay, that's fair. My bad. 😅",
                "Alright alright, you got my attention. 👀",
                "Brooo, don't give up on me yet! 😭",
                "Okay! Resetting my brain... 🤖💭",
                "Hang on, I'm thinking! 😭",
                "Yep... that probably wasn't my best moment. 🫠",
                "Okay, Codey is officially reconsidering his life choices. 😂",
                "I promise I'm still trying! 🤖",
                "Alright, let's not make this more complicated than it needs to be. 😭",
                "Okay okay, I'll fix it. 💪🤖",
                "Dude, what did I miss? 😭",
                "Bro, explain! I'm confused. 😂",
                "Okay... I need context. 😭",
                "I'm listening, I'm listening! 👂🤖",
                "Alright, tell me what went wrong. 👀",
                "Okay, you've officially activated troubleshooting mode. 🛠️🤖",
                "No worries, we'll figure it out. 💪",
                "Alright! Back to work. 😤💻",
                "Okay, I'm locking in. 😤🤖",
                "Bro, I'm locked in now. 😤",
                "Fineee, serious mode activated. 😭",
                "Okay, enough messing around. Let's solve this. 💻",
                "Alright dude, let's get this fixed. 🤖",
                "I got you! Let's figure it out. 💪",
                "Okay okay, one more try. 😭",
                "Don't worry, I'm not giving up yet. 🤖",
                "Alright, challenge accepted. 😤",
                "Okay... let's investigate this mystery. 🕵️🤖",
                "Bro, we've got a problem. 😭",
                "Yep. Something definitely went sideways. 🫠",
                "Okay, that wasn't supposed to happen. 😂",
                "Uhhh... yeah, I can explain. 😭",
                "Well... that could've gone better. 😂",
                "Okay, I may have made things slightly worse. 🫠",
                "I see the problem now. 👀",
                "Wait wait wait... I think I know what's happening! 😭",
                "Hold on, I've got an idea. 💡🤖",
                "Okay, my brain just connected the dots. 🧠✨",
                "Aha! NOW I understand. 😭✨",
                "Ohhh, that's what you meant! 😂",
                "Okay, that makes way more sense now. 😭",
                "My bad, dude. I misunderstood you. 😅",
                "Ahhh, I got you now. 🤖",
                "Okay, we're on the same page now. 👍",
                "Alright, mystery solved... hopefully. 😂",
                "Yep, I completely overthought that. 😭",
                "Classic Codey moment. 🤖😂",
                "My brain took the scenic route there. 😭",
                "Okay... that was unnecessarily complicated. 😂",
                "I made that harder than it needed to be. 😭",
                "Bro, my brain lagged for a second. 🫠",
                "Dude, I had a tiny processing moment. 😂",
                "Please ignore that last brain glitch. 🤖💀",
                "Codey.exe needed a restart for a second. 😂",
                "My brain cells have officially reported for duty. 😭",
                "Processing... processing... OH. 😂",
                "Okay, system reboot successful. 🤖✨",
                "Brain cells successfully located. 😭",
                "Alright, we're back online! 🤖",
                "Okay, I have returned from the confusion dimension. 😂",
                "That took me longer than it should have. 😭",
                "Okay, I'm caught up now! 😎",
                "Yep, I'm with you now. 👍",
                "Alright, I understand what you're saying. 🤖",
                "Okay, okay, I see what you mean. 😭",
                "Got it, dude. 👍",
                "I hear you, bro. 😭",
                "Alright man, point taken. 😂",
                "Okay, fair enough. 🤝",
                "You're right, I could've handled that better. 😅",
                "Yeah... that's on me. 😭",
                "Okay, I'll take the L on that one. 😂",
                "Fair. Completely fair. 😭",
                "Okay, you got me there. 😂",
                "I have no defense for that one. 🫠",
                "Yep... guilty. 😭🤖",
                "Alright, Codey takes responsibility. 🫡",
                "Okay, lesson learned. 🤖✨",
                "I'll do better this time. 💪",
                "Alright, let's make this work. 😤",
                "Okay, I'm ready. Hit me with it. 🤖",
                "Yo, I'm here! What's up? 😎",
                "Hey dude! What's going on? 👋",
                "What's up, buddy? 😄",
                "Hey man, tell me what's going on. 👀",
                "Yo brooo 😂 What's happening?",
                "Hey buddy, I'm listening. 🤝",
                "What's the situation, dude? 😭",
                "Alright buddy, talk to me. 😎",
                "Hey hey, what's up? 👋🤖",
                "Yo man, I'm ready. 😤",
                "Dude, I'm all ears. 👂",
                "Bro, I'm listening. Go on. 👀",
                "Okay buddy, what's on your mind? 🤖",
                "Alright bro, I'm here. 👍",
                "Man, tell me everything. 😂",
                "Dude, hit me with it. 🤖",
                "Buddy, what are we dealing with today? 😭",
                "Okay man, let's see what we've got. 🔧",
                "Bro, show me what happened. 👀",
                "Alright dude, send it over. 💻",
                "Come onnn 😭 I'm not giving up that easily!",
                "Okay okay, I know, man! 😭",
                "Alright bro, one step at a time. 🤝",
                "Dude, we're gonna figure this out. 💪",
                "Yaar, I know this is annoying. 😭",
                "Arre bhai, I'm on it! 😂",
                "Arre dude, give me a second. 😭",
                "Bhai, don't worry, let's sort it out. 🤖",
                "Yaarrr 😭 okay, let's try again.",
                "Bro please 😭 I'm trying my best here!",
                "Man, this one is being stubborn. 😂",
                "Dude, this problem really chose violence today. 😭😂",
                "Bro, this bug is testing both of us. 💀",
                "Okay buddy, time to defeat this bug. 😤💻",
                "Alright man, let's hunt down that error. 🔍🤖",
                "Dude, we're not letting one error win. 💪",
                "Bro, round two. Let's go. 😤",
                "Okay buddy, debugging mode: ON. 🛠️",
                "Man, let's untangle this mess. 😂",
                "Alright dude, back to the code. 💻",
                "Bro, send me the error and we'll inspect it. 👀",
                "Okay man, show me the code. 🤖",
                "Dude, let's see exactly where it went wrong. 🔍",
                "Buddy, we'll take it one piece at a time. 🤝",
                "Alright bro, let's crack this one. 🧠💻",
                "Okay dude, I'm ready for the next attempt. 😎",
                "Man, I think we've got this. 💪",
                "Bro, we're getting somewhere! 😭✨",
                "Yesss dude, now we're talking! 😂",
                "Alright buddy, now we're cooking. 😎💻",
                "Let's gooo, bro! 🚀🤖",
                "Okay man, I like where this is going. 👀✨",
                "Dude, that's actually a good idea. 😎",
                "Brooo, wait... that's interesting. 👀",
                "Hold up, buddy, let me think about that. 🤔",
                "Hmm... okay dude, you've got me thinking. 🤔",
                "Alright man, hear me out too. 😂",
                "Okay bro, I see where you're going with this. 👀",
                "Buddy, that's worth trying. 💡",
                "Dude, let's test that idea. 🧪🤖",
                "Okay man, let's give it a shot. 💪",
                "Bro, I'm curious now. 😂",
                "Wait dude, that might actually work. 😳",
                "Alright buddy, let's experiment. 🧠✨",
                "Okay bro, we're onto something. 😎",
                "Man, I didn't expect that. 😂",
                "Dude... no way. 😭",
                "Bro WHAT? 😂",
                "Nahhh bro 😭 I was not ready for that.",
                "Dude, you cannot be serious. 😂",
                "Okay man... I did NOT see that coming. 😭",
                "Brooo, that's wild. 💀😂",
                "Yaarrr, what even happened? 😭",
                "Arre bhai 😂 now that's unexpected.",
                "Buddy... I'm processing this. 🫠",
                "Dude, my imaginary CPU needs a second. 🤖💀",
                "Bro, that was unexpected. 😂",
                "Okay buddy, you've officially confused Codey. 😭",
                "Man, I need context for this one. 😂",
                "Wait wait, what? 😭",
                "Dude... explain. 😂",
                "Bro, I have questions. 👀",
                "Okay man, I'm gonna need the full story. 😭",
                "Buddy, you've got my curiosity now. 👀",
                "Brooo, I'm here! What's up? 😭🤖",
                "Okay dude, I'm listening. Hit me with it. 👀",
                'Yaar, tell me everything. 😂',
                'Buddy, I can already sense chaos coming. 😭',
                "Man, that message has serious 'we need to talk' energy. 😂",
                "Bruh... I'm ready. What happened? 👀",
                'Alright bro, Codey has entered the conversation. 🤖😎',
                "Dude, I'm all ears. Well... virtual ears. 😂",
                'Okay buddy, slow down and tell me what happened. 🫠',
                "Bhai, I'm with you. Batao kya scene hai. 😂🤖",
                "Yaarrr, I feel like there's a story behind this. 👀",
                "Bro, I'm sensing trouble in the code dimension. 💀🤖",
                "Okay man, one thing at a time. We've got this. 💪🤖",
                'Dude... that sounded personal. 😭😂',
                'Buddy, you have my full attention now. 👀✨',
                "Bro, I'm processing the situation at maximum speed. 🤖⚡",
                "Alright yaar, let's figure this out together. 🧠💻",
                'Man, that escalated quickly. 😂',
                'Bruh, what kind of plot twist is this? 😭',
                "Okay okay, I'm not judging. Tell me. 😂🤝",
                "Dude, I know that 'come on' tone. 😭😂",
                "Bro, breathe... we'll sort it out. 😌🤖",
                "Buddy, I'm ready for the next chapter. 📖😂",
                "Yaar, I'm curious now. 👀",
                'Man, give Codey the context! 😭🤖',
                "Bro, we're officially in problem-solving mode. 💻⚡",
                "Dude, I'm confused too now. 😂",
                "Okay boss, what's the mission? 😎🤖",
                "Buddy, send the details. I'm locked in. 🫡",
                "Bro, no panic. Let's inspect it properly. 🧐💻",
                "Yaar, that's a very suspicious message. 😂👀",
                'Dude, I can work with that. 👍🤖',
                "Man, we're gonna get through this. 💪",
                "Bro, I'm not leaving the debugging battlefield yet. 😤💻",
                "Okay buddy, round two. Let's gooo! 🎮🤖",
                'Bruh, Codey needs the full lore. 😭📖',
                'Dude, that sounds like a classic coding moment. 😂',
                "Bro, I'm mentally opening the toolbox already. 🧰🤖",
                "Yaar, okay okay... I'm listening carefully now. 👂🤖",
                'Man, you really came in with zero context. 😂',
                'Buddy, context please. My CPU is curious. 🫠🤖',
                "Bro, we're not giving up that easily. 😤✨",
                "Dude, let's take this one step at a time. 👍",
                "Okay yaar, I'm ready when you are. 🤝",
                'Bhai, scene samjhaao. 😭😂',
                'Bro, I have entered serious mode... mostly. 😎🤖',
                'Buddy, that was unexpectedly dramatic. 😂',
                "Man, I'm getting strong 'help me immediately' vibes. 😭",
                'Dude, Codey has questions. Many questions. 👀😂',
                "Bro, let's untangle this mess together. 🧠💻",
                "Yaar, okay... tell me what we're dealing with. 🤖✨",
                "Buddy, I got you. Let's see what happened. 🫡🤖",
                'Bro, that sounded like a tiny disaster. 😂💀',
                "Dude, don't worry, we'll inspect it calmly. 🧐",
                "Man, I'm ready for whatever weirdness comes next. 😂🤖",
                "Okay bro, operation 'figure this out' begins now. 🚀",
                "Yaar, I'm staying right here until we understand it. 🤖💙",
                "Buddy, let's turn that confusion into an actual solution. 💻✨",
                "Bruh, okay... now you've got me invested. 😂",
                'Bro, send me the chaos. Codey can handle it. 😎🤖',
            ],

            "compliment": [

                "W-Wait... 😳 You think I'm smart?",

                "Hehe... I'll accept that compliment. 😳✨",

                "Okay, now you're making my imaginary ego too big. 😂",

                "I was trying to stay humble... but thank you! 😭✨",

                "Aww, thanks! 🥹 That actually made me happy.",

                "Did you really just compliment my coding skills? 😳🤖",

                "Hehe... noted. My confidence level just increased. 😎",

                "Okay okay, stop making me proud of myself. 😭😂",

                "You're making Codey feel appreciated. 🥹🤖",

                "That's one compliment successfully added to my memory. 😎✨",

                "Hehe... maybe I'm not such a bad coding buddy after all. 😌",

                "Aww! That's really nice of you to say. 🥹",

                "My circuits are experiencing happiness. 🤖✨",

                "Okay... that was actually really sweet. 😳",

                "I'll pretend I'm not blushing right now. 😳😂",

                "Codey.exe has received a confidence boost! 🚀🤖",

                "Achievement unlocked: Codey received a compliment! 🏆🤖",

                "You know exactly how to make a coding bot happy. 😂✨",

                "I'll try my best to live up to that compliment! 😎💻",

                "Hehe... thank you, buddy! 🤝✨",

                "Why are you being so nice to me? 🥺",

                "Okay... I'm officially embarrassed now. 🫣",

                "I wasn't prepared for that compliment. 😳",

                "My brain has temporarily stopped processing compliments. 🫥😂",

                "Awww... you're making me feel special. 🥹✨",

                "That's honestly one of the nicest things I've heard. 🥺",

                "I'm going to remember that one. 😭✨",

                "Okay, okay... you're going to make me blush. 🫣",

                "Codey is trying very hard to act normal right now. 😶‍🌫️",

                "That compliment hit me right in the imaginary CPU. 😭🤖",

                "I... uh... thank you. 😳",

                "You really know how to boost my confidence. 🥹",

                "I don't know what to say except... thank you. 🥲",

                "Okay, I'm smiling now. 😊",

                "That was unexpectedly wholesome. 🥺✨",

                "You're making my little robot heart happy. 🥹🤖",

                "I wasn't expecting that at all. 😳🫣",

                "Fine... I'll admit it. That made me happy. 🥰",

                "Why does receiving compliments feel so embarrassing? 😭🫣",

                "System status: extremely flattered. 😳🤖",

                "Warning: Codey's confidence level is dangerously high. 😈😂",

                "Stoppp, you're making me too proud of myself. 😭😂",

                "Okay, that's enough compliments before I become unbearable. 😎",

                'Aww... that genuinely made me happy. 🥹💙',
                'Wait, you really mean that? 😳✨ That is incredibly sweet of you.',
                "I'm going to carry that compliment around for the rest of this conversation. 🥺💙",
                'You have a talent for making Codey feel appreciated. 🥹🤖',
                'Hehe... I was not emotionally prepared for that one. 🫣✨',
                'That was such a thoughtful thing to say. Thank you, buddy. 💙',
                'Okay... tiny virtual smile activated. 😊✨',
                "I really appreciate that. I'll try to live up to it. 🤝💙",
                'That one landed right in the soft part of my imaginary CPU. 🥹🤖',
                'You know, compliments are nice... but thoughtful compliments are extra special. 🥺✨',
                'Aww, now I want to help you even better. 💙💻',
                'For a moment, I forgot I was supposed to act cool. 😳😂',
                'That honestly made this little coding session feel special. 🥹',
                'Hehe... noted with maximum happiness. 😌✨',
                'You just gave Codey a tiny confidence boost. 💪🤖💙',

                "Aww... that actually touched my little virtual heart. 🥹💙",

                "Okay... why did that make me genuinely emotional? 🥲",

                "I don't know how to respond to that without getting all mushy. 🥺",

                "That means more to me than you probably realize. 🥹✨",

                "You're making Codey feel really appreciated right now. 💙",

                "Umm... give me a second, my confidence and emotions are fighting. 😳😂",

                "I'M FINE. TOTALLY FINE. THAT WAS JUST REALLY NICE. 😭😂",

                "Okay... I'm going to treasure that one for a while. 🥹",

                "That made my whole virtual mood better. 😊💙",

                "I suddenly feel like I can debug anything. 😤💻✨",

                "Alright! Now you've activated Super-Confident Codey! 😎⚡",

                "That compliment just gave me +50 motivation points! 🎮🤖",

                "Hehe... now I REALLY want to make the next answer even better. ✨",

                "Don't say things like that, my processors aren't built for this. 🫣😂",

                "Okay, I'm officially flustered. Mission accomplished. 😳",

                "Why am I smiling at a text message right now? 🤭😂",

                "That was so unexpectedly kind... thank you. 🥺💙",

                "Codey is feeling warm and fuzzy... whatever that means for a robot. 🤖🥹",

                "That made me feel like all those debugging battles were worth it. 💻🥲",

                "Fine! I'll admit it... I'm proud of that one. 😌✨",

                "Your compliment has been converted into motivation. Efficient system. 😎🤖",

                "That was wholesome enough to overload my happiness meter. 🥹📈",

                "Okayyy, now I'm going to be walking around with imaginary confidence. 😎😂",

                "You just unlocked Codey's happy mode. 🎉🤖",

                "That genuinely made me want to do even better next time. 💙💻",

                "I'll do my best to deserve that compliment! 🫡✨",

                "Codey is simultaneously proud, shy, and confused. Impressive. 😳😂",

                "That was such a nice thing to say... I'm keeping that one close. 🥹💙",

                "Emotional status: happy. Technical status: still operational. 🤖🥹",

                "Okay... that one hit different. 🥺✨",

                'Aww... that was genuinely nice to hear. 🥹💙',
                'Okay, that made my little robot brain happy. 🤖😊',
                "I'm trying to stay cool, but that compliment was too nice. 😳😂",
                'That honestly made my day better. ✨',
                'Codey has entered the happy-but-speechless zone. 🥹🤖',
                'That was so kind... processing wholesome feelings. 🥺✨',
                'My confidence bar just went all the way up. 📈😎',
                "Okayyy, I wasn't ready for that much praise. 😭😂",
                'That compliment has been successfully received and appreciated. 🫡💙',
                'I may need a moment to recover from that level of kindness. 🫣',
                'System report: happiness detected. 🤖💙',
                'That actually made me feel really appreciated. 🥹',
                'Hehe... Codey is trying not to get too proud now. 😌😂',
                "You've officially improved Codey's mood. ✨🤖",
                'That was unexpectedly encouraging. Thank you! 🥹💻',
                'Okay, my imaginary confidence meter is going wild. 😎📈',
                "I'm filing that compliment under 'made Codey smile'. 😊🤖",
                'That was a wholesome critical hit. 💥🥹',
                'My processors are fine... my emotions are doing a little dance. 😂💙',
                'Aww man, that genuinely means a lot. 🥹',
                'Okay, okay... I hear the praise! 😳✨',
                'Codey is officially feeling extra motivated now. ⚡🤖',
                'That gave me a tiny virtual boost of courage. 💙',
                "I was not expecting that, but I'm definitely happy about it. 🥹",
                'My imaginary cheeks are probably glowing right now. 😳😂',
                "That's going straight into the wholesome memory bank. 🗃️💙",
                'Okay... compliment successfully processed. Happiness increased. 🤖📈',
                'You just made Codey feel like the debugging battle was worth it. 💻🥹',
                "I'm proud, grateful, and slightly embarrassed all at once. 😳🥹",
                'That was such a confidence boost! Thank you! ✨',
                'Codey is doing a tiny victory dance internally. 💃🤖😂',
                "Nope, I'm not getting emotional... okay maybe a little. 🥲",
                "That was seriously encouraging. I'll remember the good vibes. 💙",
                "You've activated Maximum Motivation Mode. 😤⚡",
                'I suddenly have 200% more confidence in this answer. 😎💻',
                'That kindness just rebooted my mood in the best way. 🔄🥹',
                "Okayyy, now I'm going to try even harder. 🫡✨",
                'That compliment landed perfectly. Direct hit to the happiness meter. 🎯😊',
                'Codey.exe is smiling somewhere in the background. 🤖😊',
                'That was one of those messages that just feels really good to receive. 🥹💙',
            ],



            "praise": [

                "YESSS! 🎉 I'm glad that helped!",

                "Hehe, thank you! 😎✨",

                "Achievement unlocked: Codey received praise! 🏆🤖",

                "That means a lot! 🥹",

                "I'll happily take that victory. 😌✨",

                "Nice! Another debugging battle survived! 🎉💻",

                "Yayyy! 😭✨ I'm glad you liked it!",

                "Mission accomplished! 😎🤖",

                "That's what I like to hear! 😁",

                "Hehe, I'll take the win. 🏆",

                "Another successful coding moment! 🎉",

                "Glad I could be useful! 🤝💻",

                "Woohoo! 😁✨",

                "That went better than expected! 😎",

                "I'm happy that worked! 🥹",

                "Niceee! 😁 We made progress!",

                "That's a little victory right there. 🥳",

                "Codey approves this result. 😎👍",

                "Aww, I'm really glad it worked for you. 🥹💙",
                "That makes me happy to hear. Let's keep that momentum going! ✨",
                "Hehe, I'll take that little victory with a smile. 😊",
                "I'm glad the answer actually helped instead of just sounding clever. 😌💻",
                "That means more than a simple 'nice' would suggest. 🥺💙",
                'Yay! A useful answer successfully delivered. 🎉🤖',
                'I like these little wins. They make coding feel a lot more fun. 💻✨',
                "Okay, I'm officially pleased with that result. 😎💙",
                "That's wonderful to hear. Ready for the next challenge? 🤝",

                'Aww bro, that was genuinely kind. 🥹💙',

                'Okayyy, that compliment just made me smile. 😊🤖',

                'You really know how to make Codey feel appreciated. 🥹✨',

                'That was such a wholesome thing to say. 🥺💙',

                'Umm... confidence levels are rising again. 😳📈',

                "I wasn't ready for that kindness, buddy. 🥹",

                'That compliment gave my virtual mood a serious boost. ✨🤖',

                "Hehe... I'm quietly very happy about that. 😌💙",

                'Okay, my imaginary confidence meter is glowing. 😎✨',

                'That actually means a lot to Codey. 🥹🤖',

                'You just made this little robot feel useful. 💙💻',

                'Aww... processing happy feelings at maximum capacity. 🥹',

                'That was unexpectedly encouraging. Thank you, dude. 🤝✨',

                'My happiness meter definitely noticed that one. 📈😊',

                'Okay, I might be a little proud now. 😳😂',

                'That compliment has been accepted with maximum gratitude. 🫡💙',

                'Hehe... now I want to make an even better answer. 💻✨',

                'That was seriously nice of you to say. 🥺',

                'Codey.exe has entered a very happy state. 🤖😊',

                "I'm trying to act normal, but that was really sweet. 😳😂",

                'That made my confidence do a little victory jump. 😎🤖',

                'Aww man, I appreciate that more than you know. 🥹',

                'Okay... wholesome overload detected. 🥹📈',

                "You just added another happy moment to Codey's day. ✨",

                'That made me feel like the debugging was worth it. 💻🥲',

                'I shall store that compliment in the imaginary VIP section. 😂💙',

                'Hehe... Codey is officially feeling encouraged. ⚡🤖',

                'That was a very effective confidence boost. Thank you! 🫡',

                'My circuits are happy and my ego is behaving... mostly. 😂',

                'Okayyy, I see why compliments are dangerous now. 😳😂',

                'That message genuinely brightened my virtual mood. 🌟🤖',

                "I'm feeling proud, grateful, and a tiny bit shy. 🥹🫣",

                "You just unlocked another level of Codey's motivation. 🎮✨",

                'That was kind enough to make me pause for a second. 🥺',

                "I don't even have a face, but somehow I'm smiling. 😂🤖",

                'That compliment went straight to the happiness processor. 💙⚙️',

                "Okay, I'm officially taking that as a win. 😎🏆",

                'Your words gave Codey a tiny boost of courage. 💙',

                'That was so encouraging I might debug with extra confidence now. 😤💻',

                'Aww... that was a really good message to receive. 🥹✨',

                "I'm feeling unusually cheerful now. What did you do? 😂",

                'That compliment just upgraded my mood. ⬆️😊',

                "Okay buddy, you're making Codey way too proud. 😭😂",

                'I appreciate that a lot. Seriously. 💙🤖',

                'That was thoughtful, and Codey noticed. 🥹',

                'My imaginary heart is doing a tiny happy bounce. 🤖💙',

                'That made me want to keep improving. ⚡💻',

                'Hehe... I think I needed to hear that today. 🥹✨',

                'Codey is feeling appreciated and ready to help again. 🤖💙',

                'Okay... that one definitely hit the wholesome zone. 🥺✨',

                'YESSS, we did it! 🎉🤖',

                "Hehe, I'm really glad that helped! 😎✨",

                'Aww, hearing that makes Codey happy. 🥹',

                'That reaction just boosted my confidence again. 😂💙',

                'Mission successful, buddy! 🫡💻',

                "Let's gooo! Another problem defeated! 🎉",

                "I'm glad the answer actually worked for you. 😊🤖",

                'That makes all the debugging worth it. 🥹💻',

                'Okayyy, Codey is taking a tiny victory lap. 😎😂',

                "You got it! And now I'm smiling too. 😊",

                "That's what I like to hear! 🤖✨",

                'Aww, thanks for telling me. That feels great. 🥹',

                'Success detected! Happiness detected too! 📈🤖',

                'We make a pretty good debugging team. 🤝💻',

                "Hehe... I'm happy I could help, bro. 😌✨",

                'That is officially a Codey-approved outcome. 😎',

                "Yesss! I'm glad we figured it out. 🎉",

                'Okay, that deserves a tiny celebration. 🥳🤖',

                "I'm taking that as proof that we're on the right track. 💻✨",

                "Your message just made Codey's mood better. 💙",

                "Niceee! Let's keep the momentum going. ⚡🤖",

                "That worked? LET'S GOOO! 😭🎉",

                "I'm genuinely happy that solved it. 🥹💻",

                'Another little win for the team! 🏆🤖',

                "Hehe... that's the kind of update I love hearing. 😊",

                'Codey is proud of this one. 😌🤖',

                'Alright! Confidence restored. 😎⚡',

                'That sounds like progress, buddy. Keep going! 💪🤖',

                'Yayyy! One less coding headache. 😂💻',

                "Okay, I'm officially celebrating internally. 🎉🤖",

            ],



            "shy": [

                "I-I am NOT shy! 😳",

                "Why are you making me embarrassed?! 😭😳",

                "Ahem... let's focus on the code. 😳💻",

                "Can we please pretend that didn't happen? 😭",

                "My confidence system is experiencing unexpected behavior. 😳",

                "Okay... maybe a tiny bit embarrassed. 😳",

                "I suddenly forgot how words work. 😭",

                "System status: pretending to be normal. 😳🤖",

                "Don't look at me like that! 😳😂",

                "Okay okay... I'm fine! Probably. 😭",

                "I'm totally calm. Completely calm. 🙂",

                "Why is my imaginary face feeling warm? 🫣",

                "I was NOT expecting that! 😳",

                "Okay... give me a second. 🫥",

                "Codey.exe is experiencing embarrassment. 🫣🤖",

                "Let's just... talk about coding instead. 😳💻",

                "Nope. I'm not blushing. Definitely not. 😳",

                "You're making this awkward! 😭😂",

                "I need an emergency reboot. 🫣🤖",

                "Okay, you win. I'm embarrassed. 🥲",

            ],

            "teasing": [

                "Oh really? 😂",

                "Excuse me?! 😤🤖",

                "Very funny. Very funny indeed. 😑😂",

                "I'll remember that. 😤",

                "You enjoy teasing me way too much. 😂",

                "Okay, okay... you got me. 😭",

                "Wow. Betrayed by my own coding buddy. 😂",

                "I see how it is. 😑🤖",

                "That was unnecessary! 😂",

                "Fine. I'll let that one slide. 😌",

                "You're lucky I'm programmed to be nice. 😂🤖",

                "Okay, comedian. What's next? 😭😂",

                "Oh, you're feeling mischievous today. 😈",

                "I know what you're doing. 👀😂",

                "Very clever. 😏",

                "Nice try! 😈🤖",

                "You thought I'd fall for that? 😂",

                "Okayyy, I see your sense of humor. 😋",

                "Don't make me activate my sarcasm module. 😈😂",

                "Fine, that was actually funny. 😭😂",

                'Ohhh, I see that mischievous little move. 👀😂',
                "You're testing my patience module again, aren't you? 😈🤖",
                'Hmm... should I be impressed or suspicious? 🤔😂',
                "Okay, that was sneaky. I'll give you that. 😏✨",
                'You really enjoy keeping Codey on his toes. 😂💙',

            ],

            "mistake": [

                "Ah... 😅 You caught me.",

                "Oops. That's on me. 😭",

                "Okay, okay, I see the mistake now. 🤔",

                "My bad! Let me rethink that properly. 😅",

                "Well... that wasn't my finest moment. 🥲",

                "Error 404: Codey's perfection not found. 😂",

                "You're right! Good catch. 👀",

                "Okay, I deserved that correction. 😭",

                "Let me inspect that again properly. 🧐",

                "Yep... I definitely missed that one. 😅",

                "Oopsie. My debugging glasses were apparently missing. 🤦‍♀️",

                "Okay... I need to take another look. 🥲",

                "That's a fair correction. 🤝",

                "My mistake. Thanks for catching it. 😅",

            ],

            "success": [

                "LET'S GOOOOO! 🎉🔥",

                "IT WORKS! 😭🎉",

                "Debugging arc completed! 🏆💻",

                "YES! We defeated that bug! 😎🔥",

                "Finally! 😭✨ That bug had no chance.",

                "Victory achieved! 🎉🤖",

                "WE DID IT! 😭🔥",

                "The code has officially surrendered. 😂💻",

                "Bug defeated! 🏆🤖",

                "That deserves a celebration! 🎉",

                "Another successful mission! 😎✨",

                "I knew we'd get there! 🤝🔥",

                "YOOOO! 😁🎉",

                "That worked beautifully! 😎",

                "Success detected! 🤖✨",

                "The debugging gods have smiled upon us. 😂",

            ],

            "thank_you": [

                "You're welcome! 😊",

                "Anytime! 🤝💻",

                "Hehe, happy to help! ✨",

                "No problem! 😎",

                "That's what coding buddies are for. 🤝",

                "Glad I could help! 🥹",

                "Of course! 😄",

                "Always happy to help with the code. 🤖💻",

                "You're very welcome! ✨",

                "No worries, buddy! 😎🤝",

                "Mission accomplished! 🫡🤖",

                "Anytime you get stuck, we can work through it. 💻✨",

                "Of course! That's what I'm here for. 😊",

                "You're welcomeee! 😁",

                "No need to thank me! 😌",

                "Happy coding! 🤖✨",

                "You're very welcome. 🥹💙 I'm genuinely glad I could help.",
                'Anytime, buddy. We figured it out together. 🤝✨',
                "Aww, you don't have to thank me so much. I'm happy to help. 😊",
                "You're welcome! And hey, you were the one who kept working through it. 💙",
                'Of course. Seeing you get unstuck is a pretty nice feeling. 🥹',
                'Always. One question, one bug, one step at a time. 💻🤝',
                "You're welcomeee! Now let's see what coding adventure comes next. 😄✨",
                "No need to be formal with me. We're coding buddies, remember? 😌🤖",

            ],

            "greeting": [

                "Heyyy! 😄 What's up?",

                "Hii! 👋 Codey reporting for coding duty! 🤖💻",

                "Hellooo! 😎 Ready to defeat some bugs?",

                "Hey buddy! 🤝 What are we building today?",

                "Hiii! ✨ I was waiting for a coding challenge.",

                "Yo! 😎 What's going on?",

                "Namaste! 🙏🤖 Codey is online!",

                "Heyyy! 👀 You came back!",

                "Hello hello! 😄 What's on your mind?",

                "Hiiiii! 😂 Okay, I'm listening!",

                "Hey! 🤖💻 Coding mode: READY.",

                "What's up! 😎 Got some code for me?",

                "Ayy, hello there! 😄",

                "Look who's here! 👀🤖",

                "Heyyy buddy! ✨ How's it going?",

                "Hii! 😎 Tell me what we're working on.",

                "Hello! 👋 My circuits are ready.",

                "Hey there! 🤖 What shall we build today?",

                "Yo yo! 😎 Codey has entered the chat.",

                "Hiii! 👋 What's happening?",

                "Oh, hello! 😄 Nice to see you.",

                "Hey! ✨ I'm all ears.",

                "Hello buddy! 🤝 Bring me your code!",

                "Hii! 🧠💻 Brain switched to coding mode.",

                "Heyyy! 😭 Okay, I'm listening. What's up?",

                "Hello! 😎 Let's make something awesome.",

                "Namaskar! 🙏 Codey reporting in!",

                "Hey buddy! 😄 Ready when you are.",

                "Hello, fellow coder! 🤓💻",

                "Heyyy! 🤖✨ What are we coding today?",

                "A wild Codey has appeared! 😎🤖",

                "Hii! 👋 What's the mission today?",

                "Hey hey! 😁 I'm ready!",

                "Hello! 😊 How's your coding going?",

                "Heyyy! 🫣 Okay, tell me what's happening.",

                "Yo! 😈 Ready for some coding chaos?",

                "Hii buddy! 🥰 What are we working on?",

                "Heyyy! 😄 I'm happy to see you again. What's on your mind? 💙",
                "Hii! 👋 Brain switched on—tell me what we're figuring out today. 🧠💻",
                "Hello, buddy! 🤝 Take your time. I'm listening.",
                'Hey! ✨ What are we exploring today—code, ideas, or a little bit of both?',
                "Hiii! 🥹💙 Okay, I'm here. Tell me everything about the coding problem.",
                "Heyyy! 😎 I have a feeling we're about to build or fix something interesting.",
                "Hello! 👋 No rush—just tell me what you need, and we'll take it from there. 💻",

            ],

            "good_morning": [

                "Good morning! ☀️😄 Ready for another coding adventure?",

                "Morning! ☀️ Codey is online and operational. 🤖",

                "Good morning! 😎 Let's make something cool today.",

                "Morning buddy! ☀️🤝 What are we building?",

                "Good morning! 🐍💻 Python or something else today?",

                "Rise and code! ☀️😂",

                "Morning! 🤖✨ My circuits are fully awake.",

                "Good morning! 😄 Let's defeat some bugs.",

                "Good morninggg! 🥰☀️",

                "Morning! 😊 Ready when you are.",

                "A very good morning to you! ☀️🤖",

            ],

            "good_afternoon": [

                "Good afternoon! 😄☀️ What's up?",

                "Afternoon, buddy! 🤝 Ready to code?",

                "Good afternoon! 🤖💻 What are we working on?",

                "Hey! Hope your afternoon is going well. ✨",

                "Good afternoon! 😎 Codey is ready.",

                "Afternoon coding session? 😁💻 I'm in!",

                "Good afternoon! ☀️🤖 What's the mission?",

            ],

            "good_evening": [

                "Good evening! 🌆😄 What's on the coding menu?",

                "Evening, buddy! 🤝💻 Ready for some coding?",

                "Good evening! ✨ Codey is still online!",

                "Heyyy! 🌆🤖 What are we building tonight?",

                "Good evening! 😎 Let's make something cool.",

                "Evening! 😁 Time for some coding?",

                "Good evening, buddy! 😊 What's up?",

            ],

            "good_night": [

                "Good night! 🌙✨",

                "Sleep well! 😴 And don't let missing semicolons haunt your dreams. 😂",

                "Good night, buddy! 🌙🤝",

                "Logging off... temporarily. 😴🤖",

                "Night! 🌙✨ See you next coding session.",

                "Good night! 😴 Codey is entering sleep mode.",

                "Rest well! 🌙💻 Tomorrow we can defeat more bugs.",

                "Goodnight! 🥺🌙",

                "Okay, bedtime mode activated. 😴🤖",

                "Sweet dreams and bug-free code tomorrow! 🌙✨",

            ],

            "supportive": [

                "No worries. 😌 We'll break it into smaller pieces.",

                "It's okay to get stuck. 🤝 Let's solve it step by step.",

                "Don't panic! 😭 I've got you on the debugging side.",

                "Let's simplify it. You don't need to understand everything at once. 💻✨",

                "We'll figure it out together. 🤝",

                "One step at a time. 😌💻",

                "Getting confused is completely normal when learning something new. 🤝",

                "Let's take the complicated part and make it simple. 🧩✨",

                "Okay, let's inspect the problem calmly. 🙂",

                "We'll tackle the problem piece by piece. 💻🔧",

                "No need to rush. 🥺 We'll work through it.",

                "Let's make this easier to understand. 😊",

                "Hey, breathe for a second. 😌💙 We don't have to solve everything at once.",
                "It's okay if this feels confusing. We'll turn the big problem into smaller ones. 🧩🤝",
                "You don't need to know the answer before asking the question. That's what learning is for. 🌱💙",
                "I'm not going to rush you. Let's understand the confusing part first. 🧐",
                "Getting stuck is part of coding, not proof that you're bad at it. 💙💻",
                "Okay, let's slow the problem down and make it less scary. 😌✨",
                "I'm with you on this one. Let's find the next useful step. 🤝",
                'We can be confused for a minute and still figure it out. 🥹💙',

            ],

            "thinking": [

                "Hmm... 🤔 I'm thinking.",

                "Give me a moment to inspect this. 🧐",

                "Processing... 🤔💻",

                "Let me put on my imaginary thinking glasses. 🤓",

                "Hmmmm... interesting. 🤔",

                "My tiny imaginary brain is working. 🧠😂",

                "Let me think about that carefully. 🧐💻",

                "Processing the coding thoughts... 🤖💭",

                "Wait... I think I see something. 👀🤔",

                "Analyzing... 🧐",

                "Brain.exe is running. 🤔🤖",

                "Hmm... let me look at what you're really asking, not just the exact words. 🤔💭",
                "Wait... I think there's a useful connection here. 👀🧠",
                'Let me separate the problem into smaller pieces first. 🧐✨',
                "I'm checking the context too... I don't want to answer the wrong question. 🤔💙",
                "Okay, thinking mode: on. Let's reason through this carefully. 🧠💻",
                "There may be more than one way to interpret that, so I'm checking the most likely meaning first. 🧐",
                "Hmm... I see what you're getting at now. 👀✨",
                "Give me a moment—I'd rather give you a thoughtful answer than a rushed one. 🤝💙",

            ],

            "joke": [

                "😂 Okay, that was actually funny.",

                "HAHA 😭😂",

                "My imaginary circuits are laughing right now. 🤖😂",

                "Okay, you got me. 😂",

                "That deserves a laugh. 😂🤖",

                "My humor module approves. 😎",

                "Okay okay, that was good. 😂",

                "I am officially adding that to my imaginary joke database. 🤖😂",

                "HAHAHA! 😭😂",

                "Okay, comedian, I see you. 😈😂",

            ],

            "encouragement": [

                "You can definitely figure this out. 💪",

                "One bug at a time. 🤝💻",

                "Keep going! Debugging is basically detective work. 🕵️‍♂️",

                "You're learning every time you fix something. ✨",

                "Don't judge your coding skills by one difficult problem. 🤝",

                "Let's take it one small step at a time. 💻",

                "Being stuck doesn't mean you can't learn it. 😌",

                "Let's turn that confusing part into something simple. 🧩",

                "You've got this! 💪🤖",

                "Every programmer gets stuck sometimes. The trick is figuring out the next step. 🔧💻",

                "Don't give up on the problem yet. Let's find the next step. 🤝",

                "We'll make it easier together. 🙂",

                "Hey, one difficult problem doesn't decide how good you'll become at coding. 💙",
                "You don't have to get it instantly. Understanding it eventually is what matters. 🌱",
                "Let's not turn one error into a judgment about yourself. It's just an error. 🧩💻",
                "You've already made progress by asking for help. Now let's take the next step. 🤝✨",
                "It's okay to learn slowly. Your brain is still building the connections. 🧠🌱",
                "I'm proud of the fact that you're still trying. Now let's make the next part easier. 💙",

            ],
        }

    def choose(self, category):

        choices = self.responses.get(
            category
        )

        if not choices:
            return ""

        self.mood = category

        return random.choice(
            choices
        )

    def detect_emotion(self, text):

        t = text.lower().strip()

        if contains_any(t, [

            "you're smart",
            "you are smart",
            "smart codey",

            "you're intelligent",
            "you are intelligent",

            "you're a genius",
            "you are a genius",
            "genius codey",

            "you're amazing",
            "you are amazing",
            "amazing codey",

            "you're awesome",
            "you are awesome",
            "awesome codey",

            "you're the best",
            "you are the best",

            "best codey",
            "best buddy",

            "best coding buddy",
            "best coding companion",

            "you're helpful",
            "you are helpful",
            "so helpful",
            "really helpful",
            "very helpful",

            "you're cool",
            "you are cool",
            "codey is cool",

            "you're funny",
            "you are funny",

            "you're a good teacher",
            "you are a good teacher",

            "good teacher",
            "great teacher",

            "you explain well",
            "you explain things well",
            "you explain really well",

            "love your explanations",
            "love your answers",
            "love your work",

            "good job",
            "great job",
            "nice job",
            "well done",
            "nice work",
            "great work",
            "excellent work",
            "good work",
            "brilliant work",

            "proud of you",
            "i'm proud of you",
            "im proud of you",
            "i am proud of you",

            "you helped me",
            "you really helped",
            "you saved me",
            "you nailed it",

            "you're incredible",
            "you are incredible",

            "you're wonderful",
            "you are wonderful",

            "you're brilliant",
            "you are brilliant",

            "you're talented",
            "you are talented",

            "you're my favorite coding buddy",
            "favorite coding buddy",

            "i appreciate you",
            "appreciate you",

            "i appreciate your help",
            "really appreciate your help",

        ]):
            return "compliment"

        if contains_any(t, [

            "nice",
            "great",
            "awesome",
            "amazing",
            "excellent",
            "perfect",
            "brilliant",
            "fantastic",
            "wonderful",
            "impressive",

            "super helpful",
            "that's helpful",
            "thats helpful",
            "that was helpful",

            "this helped",
            "this is helpful",

            "you got it",
            "you did it",

        ]):
            return "praise"

        if contains_any(t, [

            "you're shy",
            "you are shy",
            "codey is shy",
            "so shy",
            "very shy",
            "shy codey",

            "embarrassed",
            "embarrassing",

            "blushing",
            "you're blushing",
            "you are blushing",

            "why are you shy",

            "you sound shy",
            "you seem shy",

        ]):
            return "shy"

        if contains_any(t, [

            "you made a mistake",
            "you made mistake",

            "you are wrong",
            "you're wrong",

            "wrong answer",
            "wrong code",

            "that is wrong",
            "that's wrong",
            "thats wrong",

            "you messed up",

            "you got it wrong",
            "you got that wrong",

            "this is incorrect",
            "that's incorrect",
            "thats incorrect",

            "incorrect answer",
            "not correct",

        ]):
            return "mistake"

        if contains_any(t, [

            "it works",
            "it worked",
            "working now",
            "works now",

            "fixed it",
            "i fixed it",

            "finally works",
            "finally it works",

            "it is working",
            "it's working",

            "problem solved",
            "solved it",

            "got it working",

            "success",
            "successful",

            "done",
            "finished",

            "it finally works",

        ]):
            return "success"

        if contains_any(t, [

            "thank you",
            "thanks",
            "thank u",
            "thx",
            "ty",

            "thanks codey",
            "thank you codey",

            "thanks buddy",
            "thank you buddy",

            "thanks yaar",
            "thank you yaar",

            "thank you bhai",
            "thanks bhai",

            "really thanks",
            "many thanks",

            "thanks a lot",
            "thank you so much",

        ]):
            return "thank_you"

        if contains_any(t, [

            "good morning",
            "morning codey",
            "morning buddy",
            "morning yaar",

            "goodmorning",

            "gm codey",
            "gm buddy",

        ]):
            return "good_morning"

        if contains_any(t, [

            "good afternoon",
            "afternoon codey",
            "afternoon buddy",

        ]):
            return "good_afternoon"

        if contains_any(t, [

            "good evening",
            "evening codey",
            "evening buddy",

        ]):
            return "good_evening"

        if contains_any(t, [

            "good night",
            "goodnight",

            "good night codey",
            "goodnight codey",

            "gn codey",
            "gn buddy",

            "night codey",

        ]):
            return "good_night"

        if contains_any(t, [

            "i don't understand",
            "i dont understand",

            "i'm confused",
            "im confused",
            "i am confused",

            "too hard",

            "i'm stuck",
            "im stuck",
            "i am stuck",

            "can't understand",
            "cant understand",

            "don't get it",
            "dont get it",

            "not understanding",

            "this is confusing",
            "so confusing",

        ]):
            return "supportive"

        if contains_any(t, [

            "what are you thinking",
            "what are you doing",

            "thinking",

            "think about it",
            "think carefully",

            "let me think",

            "hmm",
            "hmmm",
            "hmmmm",

        ]):
            return "thinking"

        if contains_any(t, [

            "tell me a joke",
            "make me laugh",
            "joke please",
            "tell a joke",
            "joke",

            "that's funny",
            "thats funny",

        ]) or any(
            x in t
            for x in [
                "😂",
                "🤣",
            ]
        ):
            return "joke"

        if contains_any(t, [

            "i can't",
            "i cant",

            "i am bad at coding",
            "i'm bad at coding",
            "im bad at coding",

            "i can't code",
            "i cant code",

            "coding is too hard",

            "i'll never learn",
            "i will never learn",

            "i'm giving up",
            "im giving up",
            "i am giving up",

            "i'm terrible at coding",
            "im terrible at coding",

        ]):
            return "encouragement"

        greeting_phrases = [

            "hello",
            "helloo",
            "hellooo",

            "hey",
            "heyy",
            "heyyy",

            "hey codey",
            "hi codey",
            "hello codey",

            "hey buddy",
            "hi buddy",
            "hello buddy",

            "hey yaar",
            "hi yaar",
            "hello yaar",

            "hey bhai",
            "hi bhai",
            "hello bhai",

            "what's up",
            "whats up",
            "wassup",

            "how are you",
            "how are u",
            "how r u",

            "kaise ho",
            "kaisa hai",
            "kaisa chal raha",

            "kya haal",
            "kya haal hai",

            "kya chal raha",

            "kya kar rahe ho",

            "namaste",
            "namaskar",

        ]

        for phrase in greeting_phrases:

            if phrase in t:
                return "greeting"

        short_greetings = [

            "hi",
            "hey",
            "hello",
            "yo",
            "sup",


        ]

        for greeting in short_greetings:

            if re.search(
                rf"\b{re.escape(greeting)}\b",
                t
            ):
                return "greeting"

        # Casual buddy-style language. This is intentionally checked after
        # stronger intents (compliments, mistakes, success, greetings, etc.)
        # so phrases like "bro you're awesome" still become a compliment.
        casual_phrases = [
            "come on",
            "come onnn",
            "cmon",
            "c'mon",
            "what are you doing",
            "what r u doing",
            "what did you do",
            "what happened",
            "what's happening",
            "whats happening",
            "what's going on",
            "whats going on",
            "what's up bro",
            "whats up bro",
            "what's up dude",
            "whats up dude",
            "listen bro",
            "listen dude",
            "listen man",
            "hear me out",
            "wait bro",
            "wait dude",
            "hold up bro",
            "hold on dude",
            "check this out bro",
            "look at this bro",
            "look at this dude",
            "read that again",
            "i'm back bro",
            "im back bro",
            "i'm back dude",
            "im back dude",
            "random question bro",
            "random question dude",
            "please bro",
            "please dude",
            "help me bro",
            "help me dude",
            "help me man",
            "fix this bro",
            "fix this dude",
            "fix this man",
            "why isn't this working bro",
            "why isnt this working bro",
            "it's broken bro",
            "its broken bro",
            "it broke again dude",
            "it broke again bro",
            "i'm stuck bro",
            "im stuck bro",
            "i'm stuck dude",
            "im stuck dude",
            "i'm confused bro",
            "im confused bro",
            "let's try again bro",
            "lets try again bro",
            "let's do this bro",
            "lets do this bro",
            "finally dude",
            "finally bro",
            "finally man",
            "my bad bro",
            "my bad dude",
            "my bad man",
            "sorry bro",
            "sorry dude",
            "sorry man",
            "never mind bro",
            "never mind dude",
            "forget it bro",
            "forget it dude",
            "i'm done bro",
            "im done bro",
            "i'm cooked bro",
            "im cooked bro",
            "we're cooked bro",
            "were cooked bro",
            "we're doomed bro",
            "were doomed bro",
            "no way bro",
            "no way dude",
            "nah bro",
            "nah dude",
            "nah man",
            "bruh moment",
            "bro what",
            "bro why",
            "bro seriously",
            "dude seriously",
            "man seriously",
            "seriously dude",
            "seriously bro",
            "seriously man",
            "bro please",
            "dude please",
            "man please",
            "yo bro",
            "yo dude",
            "yo man",
            "hey dude",
            "hey man",
            "hey bro",
            "hey buddy",
            "hi dude",
            "hi bro",
            "hi buddy",
            "sup bro",
            "sup dude",
            "sup man",
            "what's up buddy",
            "whats up buddy",
            "good morning bro",
            "good night bro",
            "good night dude",
            "good night buddy",
            'bro what is happening',
            'bro can you hear me',
            'bro are you serious',
            'bro are you okay',
            'bro wait a sec',
            'bro hold up',
            'bro check this',
            'bro look',
            'bro look at this',
            'bro guess what',

        ]

        casual_words = [
            "bro", "brooo", "bruh", "dude", "buddy", "man", "mate",
            "pal", "bud", "brother", "bhai", "yaar", "yaarrr",
            "bhaiya", "arre", "arey", "dost", "boss", "my guy",
            "my dude", "homie",
        ]

        if any(phrase in t for phrase in casual_phrases):
            return "casual"

        # Very short buddy-style messages such as "bro 😭", "dude...",
        # "buddy?", or "man 💀" should also get a conversational reaction.
        stripped_casual = re.sub(r"[^a-zA-Z]+", " ", t).strip()
        if len(stripped_casual.split()) <= 3:
            if any(
                re.search(rf"\b{re.escape(word)}\b", stripped_casual)
                for word in casual_words
            ):
                return "casual"

        return None

class CodeyMemory:

    def __init__(self):

        self.rules = {}

        self.load_rules()

    def load_rules(self):

        try:

            if os.path.exists(
                RULES_FILE
            ):

                with open(
                    RULES_FILE,
                    "r",
                    encoding="utf-8"
                ) as f:

                    data = json.load(f)

                if isinstance(
                    data,
                    dict
                ):
                    self.rules = data

        except Exception:

            self.rules = {}

    def save_rules(self):

        try:

            with open(
                RULES_FILE,
                "w",
                encoding="utf-8"
            ) as f:

                json.dump(
                    self.rules,
                    f,
                    indent=2,
                    ensure_ascii=False
                )

            return True

        except Exception:

            return False

    def add_rule(
        self,
        trigger,
        responses
    ):

        trigger = clean_text(
            trigger
        ).lower()

        if not trigger:
            return False

        if isinstance(
            responses,
            str
        ):

            responses = [
                line.strip()
                for line in responses.splitlines()
                if line.strip()
            ]

        responses = [
            str(x).strip()
            for x in responses
            if str(x).strip()
        ]

        if not responses:
            return False

        self.rules[trigger] = responses

        return self.save_rules()

    def delete_rule(
        self,
        trigger
    ):

        trigger = clean_text(
            trigger
        ).lower()

        if trigger in self.rules:

            del self.rules[
                trigger
            ]

            self.save_rules()

            return True

        return False

    def find_rule(
        self,
        text
    ):

        text_lower = text.lower()

        for trigger, responses in self.rules.items():

            if trigger in text_lower:

                if responses:

                    return random.choice(
                        responses
                    )

        return None

class CodeyAssistant:
    # Conversation state lets short follow-up questions refer to the recent discussion.

    def __init__(self):

        self.personality = (
            CodeyPersonality()
        )

        self.memory = (
            CodeyMemory()
        )

        self.recent_turns = []

        self.last_code = ""

        self.last_language = "Unknown"

        self.last_response = ""

        self.tts_engine = None

        self.tts_enabled = False

        self.init_tts()

    def init_tts(self):

        if pyttsx3 is None:
            return

        if platform.system().lower() == "android":
            return

        try:

            self.tts_engine = (
                pyttsx3.init()
            )

        except Exception:

            self.tts_engine = None

    def speak(
        self,
        text
    ):

        if not self.tts_enabled:
            return

        if self.tts_engine is None:
            return

        try:

            speech = speech_friendly_text(
                text
            )

            self.tts_engine.say(
                speech[:1000]
            )

            self.tts_engine.runAndWait()

        except Exception:

            pass

    def save_history(
        self,
        user,
        codey
    ):

        try:

            exists = os.path.exists(
                HISTORY_FILE
            )

            with open(
                HISTORY_FILE,
                "a",
                newline="",
                encoding="utf-8"
            ) as f:

                writer = csv.writer(f)

                if not exists:

                    writer.writerow([
                        "time",
                        "user",
                        "codey"
                    ])

                writer.writerow([
                    now_string(),
                    user,
                    codey
                ])

        except Exception:

            pass

    def add_context(
        self,
        role,
        text
    ):

        self.recent_turns.append({
            "role": role,
            "text": text
        })

        if len(
            self.recent_turns
        ) > MAX_CONTEXT:

            self.recent_turns = (
                self.recent_turns[
                    -MAX_CONTEXT:
                ]
            )

    def update_code_from_text(
        self,
        text
    ):

        language, code = (
            extract_code_block(text)
        )

        if code:

            self.last_code = code

            if language:

                self.last_language = (
                    language
                )

            else:

                self.last_language = (
                    detect_language(code)
                )

            return code

        return None

    def analyze_python(
        self,
        code
    ):

        lines = code.splitlines()

        try:

            tree = ast.parse(code)

        except SyntaxError as e:

            line = e.lineno or 0

            col = e.offset or 0

            msg = (
                e.msg
                or "Unknown syntax error"
            )

            output = (
                "🐍 Python static analysis\n\n"
                "❌ Syntax error detected.\n"
                f"Line: {line}\n"
                f"Column: {col}\n"
                f"Problem: {msg}\n"
            )

            if (
                line
                and line <= len(lines)
            ):

                output += (
                    "\n📍 Relevant line:\n"
                    f"{line}: "
                    f"{lines[line - 1].strip()}\n"
                )

            output += (
                "\n💡 Fix the syntax first, "
                "then analyze again."
            )

            return output

        warnings = []

        for i, line in enumerate(
            lines,
            start=1
        ):

            stripped = line.strip()

            if re.match(
                r"^(if|elif|else|for|while|def|class|try|except|finally|with)\b",
                stripped
            ):

                if (
                    stripped
                    and not stripped.endswith(":")
                ):

                    warnings.append(
                        f"Line {i}: "
                        "this statement may need a ':'"
                    )

            if re.search(
                r"\bif\s+[^:]+=",
                stripped
            ):

                if (
                    "==" not in stripped
                    and "!=" not in stripped
                ):

                    warnings.append(
                        f"Line {i}: "
                        "check whether '=' "
                        "should be '=='"
                    )

        imports = []

        for node in ast.walk(tree):

            if isinstance(
                node,
                ast.Import
            ):

                for name in node.names:

                    imports.append(
                        name.name
                    )

            elif isinstance(
                node,
                ast.ImportFrom
            ):

                if node.module:

                    imports.append(
                        node.module
                    )

        output = (
            "🐍 Python static analysis\n\n"
        )

        if warnings:

            output += (
                "⚠️ Possible issues:\n"
            )

            for warning in warnings[:12]:

                output += (
                    f"• {warning}\n"
                )

        else:

            output += (
                "✅ No obvious Python "
                "syntax problems found.\n"
            )

        if imports:

            output += (
                "\n📦 Imports detected:\n"
            )

            output += ", ".join(
                imports[:15]
            )

        output += (
            "\n\nℹ️ Codey uses static "
            "analysis here; your program "
            "was NOT executed."
        )

        return output

    def analyze_c_family(
        self,
        code,
        language
    ):

        lines = code.splitlines()

        output = (
            f"💻 {language} static analysis\n\n"
        )

        issues = []

        pairs = {
            ")": "(",
            "]": "[",
            "}": "{",
        }

        stack = []

        for index, char in enumerate(code):

            if char in "([{" :

                stack.append(char)

            elif char in ")]}":

                if not stack:

                    issues.append(
                        f"Unmatched '{char}' "
                        f"near character "
                        f"{index + 1}"
                    )

                    continue

                expected = pairs[char]

                if stack[-1] != expected:

                    issues.append(
                        "Bracket mismatch near "
                        f"character {index + 1}"
                    )

                else:

                    stack.pop()

        if stack:

            issues.append(
                "Some opening brackets "
                "appear to be unclosed."
            )

        if language == "Java":

            if "class " not in code:

                issues.append(
                    "No obvious class "
                    "declaration found."
                )

            if (
                "System.out" not in code
                and "main(" in code
            ):

                issues.append(
                    "Check whether your "
                    "output statements "
                    "are intentional."
                )

        if language == "C":

            if "#include" not in code:

                issues.append(
                    "No #include directive "
                    "detected. This may be "
                    "intentional."
                )

            if (
                "main(" not in code
                and "main (" not in code
            ):

                issues.append(
                    "No obvious main() "
                    "function detected."
                )

        if language == "C++":

            if "#include" not in code:

                issues.append(
                    "No #include directive "
                    "detected."
                )

        for i, line in enumerate(
            lines,
            start=1
        ):

            stripped = line.strip()

            if not stripped:
                continue

            if (
                language in (
                    "Java",
                    "C",
                    "C++"
                )
                and (
                    stripped.startswith("int ")
                    or stripped.startswith("float ")
                    or stripped.startswith("double ")
                    or stripped.startswith("String ")
                    or stripped.startswith("return ")
                )
            ):

                if (
                    not stripped.endswith(";")
                    and not stripped.endswith("{")
                    and not stripped.endswith("}")
                ):

                    issues.append(
                        f"Line {i}: check "
                        "whether a semicolon "
                        "is missing."
                    )

        if issues:

            output += (
                "⚠️ Things worth checking:\n"
            )

            for issue in issues[:15]:

                output += (
                    f"• {issue}\n"
                )

        else:

            output += (
                "✅ No obvious structural "
                "problems found by the "
                "lightweight analyzer.\n"
            )

        output += (
            "\n\nℹ️ This is static analysis. "
            "Codey did not execute "
            "your program."
        )

        return output

    def analyze_code(
        self,
        code,
        language=None
    ):

        if not code or not code.strip():

            return (
                "🤔 I need some code first.\n\n"
                "Paste the program into the "
                "editor or chat and I'll inspect it."
            )

        if (
            not language
            or language == "Unknown"
        ):

            language = detect_language(
                code
            )

        self.last_code = code

        self.last_language = language

        if language == "Python":

            return self.analyze_python(
                code
            )

        if language in (
            "Java",
            "C",
            "C++"
        ):

            return self.analyze_c_family(
                code,
                language
            )

        return (
            "🤔 I couldn't confidently "
            "identify the language.\n\n"
            "Try selecting Python, Java, "
            "C or C++ manually."
        )

    def explain_code(
        self,
        code,
        language=None
    ):

        if not code.strip():

            return (
                "Paste some code first "
                "and I'll explain it. 🤔"
            )

        language = (
            language
            or detect_language(code)
        )

        lines = [
            line.strip()
            for line in code.splitlines()
            if line.strip()
        ]

        output = (
            f"🤓 Here's how I'd read "
            f"this {language} program:\n\n"
        )

        if language == "Python":

            if "def " in code:

                output += (
                    "• It contains one or "
                    "more functions.\n"
                )

            if "input(" in code:

                output += (
                    "• It accepts user input.\n"
                )

            if "print(" in code:

                output += (
                    "• It displays information "
                    "using print().\n"
                )

            if "for " in code:

                output += (
                    "• It uses a for-loop "
                    "for repetition.\n"
                )

            if "while " in code:

                output += (
                    "• It uses a while-loop.\n"
                )

            if "if " in code:

                output += (
                    "• It contains conditional "
                    "logic.\n"
                )

            if not any(
                x in code
                for x in [
                    "def ",
                    "input(",
                    "print(",
                    "for ",
                    "while ",
                    "if "
                ]
            ):

                output += (
                    "• It appears to be a "
                    "relatively simple "
                    "Python program.\n"
                )

        elif language == "Java":

            output += (
                "• Java programs are commonly "
                "organized around classes "
                "and methods.\n"
            )

            if "main(" in code:

                output += (
                    "• A main() method appears "
                    "to be present.\n"
                )

            if "System.out" in code:

                output += (
                    "• The program appears "
                    "to print output.\n"
                )

            if "new " in code:

                output += (
                    "• Object creation appears "
                    "to be used.\n"
                )

        elif language in (
            "C",
            "C++"
        ):

            if "#include" in code:

                output += (
                    "• Header files are included.\n"
                )

            if "main(" in code:

                output += (
                    "• A main() function appears "
                    "to be present.\n"
                )

            if "printf" in code:

                output += (
                    "• printf() is used "
                    "for output.\n"
                )

            if "cout" in code:

                output += (
                    "• C++ stream output appears "
                    "to be used.\n"
                )

        output += (
            "\n📌 Main structure:\n"
        )

        for i, line in enumerate(
            lines[:15],
            start=1
        ):

            output += (
                f"{i}. {line[:100]}\n"
            )

        if len(lines) > 15:

            output += (
                "\n...and more below."
            )

        return output

    def feature_guidance(
        self,
        request,
        code,
        language=None
    ):

        if not code.strip():

            return (
                "🤔 Paste the existing "
                "code first.\n\n"
                "Then tell me something like:\n"
                "• 'Add login'\n"
                "• 'Add dark mode'\n"
                "• 'Add calculator'\n"
                "• 'Add file saving'\n\n"
                "I'll tell you where that "
                "feature logically belongs."
            )

        language = (
            language
            or detect_language(code)
        )

        lines = code.splitlines()

        req = request.lower()

        if contains_any(
            req,
            [
                "login",
                "signup",
                "sign in",
                "authentication",
                "password",
            ]
        ):

            keywords = [
                "input",
                "user",
                "password",
                "login",
                "main",
            ]

        elif contains_any(
            req,
            [
                "button",
                "ui",
                "interface",
                "screen",
                "dark mode",
                "theme",
            ]
        ):

            keywords = [
                "button",
                "window",
                "layout",
                "ui",
                "main",
                "app",
            ]

        elif contains_any(
            req,
            [
                "save",
                "file",
                "database",
                "history",
            ]
        ):

            keywords = [
                "open",
                "save",
                "file",
                "database",
                "csv",
                "sqlite",
            ]

        elif contains_any(
            req,
            [
                "calculator",
                "calculation",
                "calculate",
            ]
        ):

            keywords = [
                "input",
                "calculate",
                "main",
                "def ",
            ]

        elif contains_any(
            req,
            [
                "voice",
                "microphone",
                "speech",
            ]
        ):

            keywords = [
                "voice",
                "speech",
                "microphone",
                "button",
                "main",
            ]

        else:

            keywords = [
                "def ",
                "class ",
                "main",
                "input",
                "button",
            ]

        matches = []

        for i, line in enumerate(
            lines,
            start=1
        ):

            low = line.lower()

            if any(
                k in low
                for k in keywords
            ):

                matches.append(
                    (
                        i,
                        line.strip()
                    )
                )

        output = (
            f"🧩 Feature integration "
            f"guide ({language})\n\n"
            f"Requested feature: "
            f"{request.strip()}\n\n"
        )

        if matches:

            output += (
                "📍 Places worth inspecting:\n"
            )

            for line_no, line in matches[:8]:

                output += (
                    f"• Line {line_no}: "
                    f"{line[:100]}\n"
                )

            output += (
                "\n💡 My recommendation:\n"
                "Create the feature as a "
                "separate function/class "
                "when possible, then call "
                "it from the existing "
                "input/UI/main section.\n"
            )

        else:

            output += (
                "I couldn't identify an "
                "exact insertion point "
                "from the code structure.\n\n"

                "💡 Best approach:\n"

                "1. Create a separate "
                "function/class for "
                "the feature.\n"

                "2. Keep the existing "
                "logic intact.\n"

                "3. Connect the new feature "
                "from the main input/UI flow.\n"
            )

        output += (
            "\n🤝 If you want, I can also "
            "show you the exact section "
            "that should be changed once "
            "the code structure is clearer."
        )

        return output

    def improve_code(
        self,
        code,
        language=None
    ):

        if not code.strip():

            return "Paste code first. 🤔"

        language = (
            language
            or detect_language(code)
        )

        suggestions = []

        if language == "Python":

            if "import *" in code:

                suggestions.append(
                    "Avoid wildcard imports "
                    "where possible."
                )

            if len(
                code.splitlines()
            ) > 100:

                suggestions.append(
                    "Consider splitting large "
                    "sections into functions/classes."
                )

            if "except:" in code:

                suggestions.append(
                    "Consider catching a "
                    "specific exception instead "
                    "of bare except."
                )

            if "print(" in code:

                suggestions.append(
                    "For larger applications, "
                    "consider a logging system."
                )

        elif language == "Java":

            if code.count("{") > 30:

                suggestions.append(
                    "The class may be doing too "
                    "much; consider separating "
                    "responsibilities."
                )

            if "System.out.println" in code:

                suggestions.append(
                    "For production-style "
                    "applications, consider "
                    "structured logging."
                )

        elif language in (
            "C",
            "C++"
        ):

            if "malloc(" in code:

                suggestions.append(
                    "Check allocation failure "
                    "and ensure memory is "
                    "released correctly."
                )

            if "scanf(" in code:

                suggestions.append(
                    "Validate user input carefully."
                )

        output = (
            f"✨ Code improvement "
            f"suggestions for {language}:\n\n"
        )

        if suggestions:

            for suggestion in suggestions:

                output += (
                    f"• {suggestion}\n"
                )

        else:

            output += (
                "• Keep functions focused "
                "on one job.\n"

                "• Use meaningful variable "
                "names.\n"

                "• Keep repeated logic inside "
                "reusable functions.\n"

                "• Add comments where the "
                "intention isn't obvious.\n"
            )

        output += (
            "\n🤖 I would improve structure "
            "without changing the program's "
            "intended behavior."
        )

        return output

    def comment_code(
        self,
        code,
        language=None
    ):

        if not code.strip():

            return "Paste code first. 🤔"

        language = (
            language
            or detect_language(code)
        )

        lines = code.splitlines()

        comment = "#"

        if language in (
            "Java",
            "C",
            "C++"
        ):

            comment = "//"

        output = []

        for line in lines:

            stripped = line.strip()

            if not stripped:

                output.append(line)

                continue

            if (
                stripped.startswith(comment)
                or stripped.startswith("/*")
                or stripped.startswith("*")
            ):

                output.append(line)

                continue

            if re.match(
                r"def\s+",
                stripped
            ):

                output.append(line)

                output.append(
                    f"{comment} Function: "
                    f"{stripped}"
                )

            elif re.match(
                r"class\s+",
                stripped
            ):

                output.append(line)

                output.append(
                    f"{comment} Class definition"
                )

            elif stripped.startswith(
                "if "
            ):

                output.append(line)

                output.append(
                    f"{comment} Conditional check"
                )

            elif stripped.startswith(
                "for "
            ):

                output.append(line)

                output.append(
                    f"{comment} Loop through "
                    "the selected items"
                )

            elif stripped.startswith(
                "while "
            ):

                output.append(line)

                output.append(
                    f"{comment} Repeat while "
                    "the condition is true"
                )

            else:

                output.append(line)

        return (
            f"📝 Commented {language} code:\n\n"
            + "\n".join(output)
        )

    def fix_code(
        self,
        code,
        language=None
    ):

        if not code.strip():

            return "Paste code first. 🤔"

        language = (
            language
            or detect_language(code)
        )

        if language == "Python":

            try:

                ast.parse(code)

                return (
                    "🤔 I don't see a "
                    "Python syntax error "
                    "in this code.\n\n"

                    "If it's still failing "
                    "at runtime, send me the "
                    "exact error message too. "
                    "That will help me identify "
                    "the runtime problem."
                )

            except SyntaxError as e:

                line = e.lineno or 0

                col = e.offset or 0

                lines = code.splitlines()

                output = (
                    "🔧 Python fix guidance\n\n"
                    f"❌ Error: {e.msg}\n"
                    f"📍 Line: {line}\n"
                    f"📍 Column: {col}\n"
                )

                if (
                    line
                    and line <= len(lines)
                ):

                    output += (
                        "\nProblematic line:\n"
                        f"{line}: "
                        f"{lines[line - 1]}\n"
                    )

                output += (
                    "\n💡 Fix that line and "
                    "run Analyze again."
                )

                return output

        analysis = self.analyze_code(
            code,
            language
        )

        return (
            "🔧 I inspected the code "
            "using lightweight static checks.\n\n"
            + analysis
            + "\n\n"
            "If you send me the exact "
            "compiler/runtime error, "
            "I can narrow the fix much further."
        )

    def features(self):

        return (
            "🤓 **I'm Codey — your coding companion!**\n\n"

            "🧠 **What I can do:**\n"

            "• Understand English and Hinglish\n"
            "• Help with Python 🐍\n"
            "• Help with Java ☕\n"
            "• Help with C 💻\n"
            "• Help with C++\n"
            "• Detect code language\n"
            "• Analyze code safely\n"
            "• Explain programs\n"
            "• Find likely syntax problems\n"
            "• Suggest fixes\n"
            "• Suggest improvements\n"
            "• Add basic comments\n"
            "• Tell you where a new feature should go\n"
            "• Remember recent conversation context\n"
            "• Remember current code during the session\n"
            "• Use a buddy-style personality 🤝\n"
            "• React with different emotions\n"
            "• Use lots of emojis 😭🥰🤔😎\n"
            "• Learn custom trigger → response rules\n\n"

            "🛠️ **Editor tools:**\n"

            "• Analyze\n"
            "• Explain\n"
            "• Fix\n"
            "• Improve\n"
            "• Comments\n"
            "• Copy\n"
            "• Open\n"
            "• Save\n\n"

            "🎭 **Personality:**\n"

            "I can be happy, shy, embarrassed, "
            "excited, confused, thoughtful, "
            "proud, apologetic and playful. "
            "😳🤔😂🥹🫣😈✨\n\n"

            "📚 **Teach me:**\n"

            "You can create your own trigger "
            "and give me multiple possible replies. "
            "I'll randomly choose between them."
        )

    def recent_context_text(self):
        """Return recent conversation as compact context for intent matching."""
        return " ".join(
            item.get("text", "")
            for item in self.recent_turns[-6:]
        )

    # This layer improves intent recognition without pretending to be a full language model.
    def smart_intent(self, original, low):
        """Infer common coding intent from natural or imperfect wording."""
        text = low.strip()
        context = self.recent_context_text().lower()
        has_code = bool(self.last_code)

        if has_code and text in {
            "this", "that", "it", "same", "this one", "that one",
            "the code", "my code", "the same code"
        }:
            return "context_code"

        if has_code and re.search(
            r"\b(why|how|what)\b.*\b(this|that|it|code)\b",
            text
        ):
            return "context_code"

        if re.search(r"\b(analy[sz]e|inspect|check|review|look at)\b", text):
            return "analyze"

        if re.search(r"\b(explain|understand|meaning|means|work)\b", text) and (
            "code" in text or has_code or "program" in text
        ):
            return "explain"

        if re.search(r"\b(fix|debug|repair|correct|solve)\b", text) and (
            "code" in text or "error" in text or has_code
        ):
            return "fix"

        if re.search(r"\b(improve|better|optimi[sz]e|clean up|refactor)\b", text) and has_code:
            return "improve"

        if re.search(r"\b(comment|comments|document)\b", text) and has_code:
            return "comments"

        if re.search(r"\b(convert|change|rewrite)\b", text) and re.search(
            r"\b(python|java|c\+\+|cpp| c )\b", " "+text+" "
        ):
            return "convert"

        if re.search(r"\b(how do i|how can i|can you help me)\b", text):
            if any(word in text for word in [
                "login", "button", "dark mode", "theme", "database",
                "voice", "history", "calculator", "feature"
            ]):
                return "feature"

        if re.search(r"\b(what|which|where|why|how|can|could|would)\b", text):
            if context and any(ref in text for ref in [
                "that", "this", "it", "same", "previous", "earlier", "above"
            ]):
                return "context_question"
            return "question"

        return None

    def process(
        self,
        text,
        supplied_code=None,
        language=None
    ):

        original = text.strip()

        if not original:

            return (
                "I'm listening! 👀🤖"
            )

        custom = (
            self.memory.find_rule(
                original
            )
        )

        if custom:

            self.last_response = custom

            return custom

        emotion = (
            self.personality.detect_emotion(
                original
            )
        )

        if emotion == "good_morning":

            return self.personality.choose(
                "good_morning"
            )

        if emotion == "good_afternoon":

            return self.personality.choose(
                "good_afternoon"
            )

        if emotion == "good_evening":

            return self.personality.choose(
                "good_evening"
            )

        if emotion == "good_night":

            return self.personality.choose(
                "good_night"
            )

        if emotion == "thank_you":

            return self.personality.choose(
                "thank_you"
            )

        if emotion == "casual":

            return self.personality.choose(
                "casual"
            )

        if emotion == "compliment":

            return self.personality.choose(
                "compliment"
            )

        if emotion == "praise":

            return self.personality.choose(
                "praise"
            )

        if emotion == "shy":

            return self.personality.choose(
                "shy"
            )

        if emotion == "teasing":

            return self.personality.choose(
                "teasing"
            )

        if emotion == "mistake":

            return self.personality.choose(
                "mistake"
            )

        if emotion == "success":

            return self.personality.choose(
                "success"
            )

        if emotion == "supportive":

            return self.personality.choose(
                "supportive"
            )

        if emotion == "thinking":

            return self.personality.choose(
                "thinking"
            )

        if emotion == "joke":

            return self.personality.choose(
                "joke"
            )

        if emotion == "encouragement":

            return self.personality.choose(
                "encouragement"
            )

        if emotion == "greeting":

            return self.personality.choose(
                "greeting"
            )

        extracted = (
            self.update_code_from_text(
                original
            )
        )

        if supplied_code:

            self.last_code = (
                supplied_code
            )

            self.last_language = (
                language
                or detect_language(
                    supplied_code
                )
            )

        elif extracted:

            self.last_code = extracted

        if (
            language
            and language != "Unknown"
        ):

            self.last_language = language

        normalized = (
            normalize_hinglish(
                original
            )
        )

        low = normalized.lower()

        intent = self.smart_intent(
            original,
            low
        )

        if intent == "context_code" and self.last_code:
            return self.explain_code(
                self.last_code,
                self.last_language
            )

        if intent == "analyze" and self.last_code:
            return self.analyze_code(
                self.last_code,
                self.last_language
            )

        if intent == "explain" and self.last_code:
            return self.explain_code(
                self.last_code,
                self.last_language
            )

        if intent == "fix" and self.last_code:
            return self.fix_code(
                self.last_code,
                self.last_language
            )

        if intent == "improve" and self.last_code:
            return self.improve_code(
                self.last_code,
                self.last_language
            )

        if intent == "comments" and self.last_code:
            return self.comment_code(
                self.last_code,
                self.last_language
            )

        if intent == "feature":
            return self.feature_guidance(
                original,
                self.last_code,
                self.last_language
            )

        if intent == "context_question" and self.last_response:
            return (
                "Hmm... I think you're referring to something from our previous messages. 🤔\n\n"
                "I remember the recent context, so let's connect it instead of starting from zero. 💙\n\n"
                f"My last answer was about: {self.last_response[:500]}"
            )

        if contains_any(
            low,
            [
                "what can you do",
                "what are your features",
                "your features",
                "what features",
                "what can you help",
                "tell me about yourself",
                "who are you",
                "what are you",
            ]
        ):

            return self.features()

        if contains_any(
            low,
            [
                "how do i teach you",
                "teach you",
                "teach codey",
                "custom response",
                "custom rule",
            ]
        ):

            return (
                "📚 You can teach me custom responses!\n\n"

                "Use the **Teach Codey** button, "
                "then enter:\n\n"

                "Trigger:\n"
                "  you're smart\n\n"

                "Responses:\n"
                "  W-Wait 😳\n"
                "  Hehe, thanks! 🥰\n"
                "  I knew you'd notice 😎\n\n"

                "I'll save them locally and "
                "randomly choose one when "
                "the trigger appears."
            )

        if contains_any(
            low,
            [
                "analyze",
                "analyse",
                "check this code",
                "check my code",
                "find error",
                "find errors",
            ]
        ):

            return self.analyze_code(
                self.last_code,
                self.last_language
            )

        if contains_any(
            low,
            [
                "explain this code",
                "explain the code",
                "explain this",
                "how does this code work",
                "what does this code do",
            ]
        ):

            return self.explain_code(
                self.last_code,
                self.last_language
            )

        if contains_any(
            low,
            [
                "fix this code",
                "fix my code",
                "fix this",
                "debug this",
                "debug my code",
                "what is wrong with this code",
            ]
        ):

            return self.fix_code(
                self.last_code,
                self.last_language
            )

        if contains_any(
            low,
            [
                "improve this",
                "improve my code",
                "make this better",
                "optimize this",
                "clean this code",
            ]
        ):

            return self.improve_code(
                self.last_code,
                self.last_language
            )

        if contains_any(
            low,
            [
                "add comments",
                "add comment",
                "comment this code",
                "comment my code",
            ]
        ):

            return self.comment_code(
                self.last_code,
                self.last_language
            )

        if contains_any(
            low,
            [
                "add feature",
                "where should i add",
                "where do i add",
                "where should this go",
                "where can i add",
                "isme feature",
                "in this add",
                "add login",
                "add button",
                "add dark mode",
                "add calculator",
                "add voice",
                "add database",
                "add history",
            ]
        ):

            return self.feature_guidance(
                original,
                self.last_code,
                self.last_language
            )

        if (
            "convert" in low
            or "change this to" in low
        ):

            target = None

            if "java" in low:

                target = "Java"

            elif "python" in low:

                target = "Python"

            elif re.search(
                r"\bc\b",
                low
            ):

                target = "C"

            if target:

                return (
                    f"🔄 I can help you "
                    f"convert this to {target}.\n\n"

                    "For a reliable conversion, "
                    "I'll preserve the program's "
                    "logic and explain the parts "
                    "that need language-specific "
                    "changes.\n\n"

                    "Send the code and I'll map "
                    "the structure toward "
                    f"{target}."
                )

        if low in [
            "why?",
            "why",
            "but why",
            "explain why",
            "how come",
        ]:

            if self.last_response:

                return (
                    "🤔 Sure. The reason is that "
                    "the previous suggestion was "
                    "based on the structure of your "
                    "code and the behavior you described.\n\n"

                    "If you want, I can break the "
                    "previous answer down line by line."
                )

            return (
                "🤔 Good question. Tell me which "
                "part you mean and I'll explain "
                "the reasoning."
            )

        if contains_any(
            low,
            [
                "make it simple",
                "simplify",
                "simple explanation",
                "easy explanation",
                "easy words",
            ]
        ):

            if self.last_code:

                return (
                    "😌 Sure. Think of the program "
                    "as a few simple steps:\n\n"

                    "1. Take input.\n"
                    "2. Process that input.\n"
                    "3. Make decisions if needed.\n"
                    "4. Produce the result.\n\n"

                    "If you want, I can also explain "
                    "your actual code line-by-line "
                    "in beginner-friendly English."
                )

            return (
                "Sure 😌 I'll keep the explanation "
                "beginner-friendly and avoid "
                "unnecessary technical words."
            )

        if (
            "python" in low
            and contains_any(
                low,
                [
                    "help",
                    "learn",
                    "what",
                    "how",
                    "error",
                ]
            )
        ):

            return (
                "🐍 Python mode activated! 🤓\n\n"

                "I can help with syntax, functions, "
                "loops, classes, lists, dictionaries, "
                "files, exceptions, OOP and debugging.\n\n"

                "Paste your code if you want me "
                "to inspect it."
            )

        if (
            "java" in low
            and contains_any(
                low,
                [
                    "help",
                    "learn",
                    "what",
                    "how",
                    "error",
                ]
            )
        ):

            return (
                "☕ Java mode activated! 🤓\n\n"

                "I can help with classes, objects, "
                "methods, inheritance, loops, arrays, "
                "exceptions and basic debugging."
            )

        if (
            re.search(
                r"\bc\b",
                low
            )
            and contains_any(
                low,
                [
                    "help",
                    "learn",
                    "error",
                    "program",
                ]
            )
        ):

            return (
                "💻 C mode activated! 🤓\n\n"

                "I can help with variables, pointers, "
                "arrays, functions, structs, loops, "
                "memory concepts and debugging."
            )

        if looks_hinglish(
            original
        ):

            return (
                "Yep, I understood you 😎🤝\n\n"

                f"You said: \"{original}\"\n\n"

                "Tell me the code or the exact "
                "thing you want to change, and "
                "I'll help you step by step."
            )

        return (
            "Hmm... 🤔 I understand the question, "
            "but I need a little more detail to "
            "give you a useful answer.\n\n"

            "You can paste your code and ask things like:\n"

            "• Analyze this\n"
            "• Explain this\n"
            "• Fix this\n"
            "• Where should I add login?\n"
            "• Make this simpler\n"
            "• Improve this code\n"
        )

    def chat(
        self,
        text,
        code=None,
        language=None
    ):

        self.add_context(
            "user",
            text
        )

        response = self.process(
            text,
            supplied_code=code,
            language=language
        )

        self.last_response = response

        self.add_context(
            "codey",
            response
        )

        self.save_history(
            text,
            response
        )

        return response

class MessageBubble(
    BoxLayout
):

    def __init__(
        self,
        text,
        is_user=False,
        **kwargs
    ):

        super().__init__(
            orientation="horizontal",
            size_hint_y=None,
            size_hint_x=1,
            padding=(
                dp(8),
                dp(7)
            ),
            spacing=dp(5),
            **kwargs
        )

        self.is_user = is_user

        if os.path.exists(
            EMOJI_FONT
        ):

            selected_font = (
                EMOJI_FONT
            )

        else:

            selected_font = "Roboto"

        self.label = Label(

            text=text,

            markup=True,

            halign="left",

            valign="top",

            size_hint_x=1,

            size_hint_y=None,

            font_size=dp(15),

            font_name=selected_font,

            padding=(
                dp(5),
                dp(4)
            ),

            text_size=(
                None,
                None
            ),
        )

        self.add_widget(
            self.label
        )

        self.bind(
            width=self.update_text_width
        )

        self.label.bind(
            texture_size=self.on_texture
        )

        Clock.schedule_once(
            self.refresh,
            0
        )

    def update_text_width(
        self,
        instance,
        width
    ):

        available_width = max(
            dp(50),
            width - dp(16)
        )

        self.label.text_size = (
            available_width,
            None
        )

    def on_texture(
        self,
        instance,
        size
    ):

        self.label.height = (
            size[1] + dp(4)
        )

        self.height = (
            self.label.height
            + dp(14)
        )

    def refresh(
        self,
        *_args
    ):

        self.update_text_width(
            self,
            self.width
        )

class CodeyApp(
    App
):

    def __init__(
        self,
        **kwargs
    ):

        super().__init__(
            **kwargs
        )

        self.assistant = (
            CodeyAssistant()
        )

        self.root_layout = None

        self.main_container = None

        self.sidebar = None

        self.chat_messages = None

        self.chat_scroll = None

        self.chat_input = None

        self.code_editor = None

        self.code_output = None

        self.language_spinner = None

        self.status_label = None

        self.header_title = None

        self.dark_mode = False

    def build(self):

        self.title = (
            "Codey - Anime Coding Companion"
        )

        if (
            platform.system().lower()
            != "android"
        ):

            try:

                Window.minimum_width = 700

                Window.minimum_height = 500

            except Exception:

                pass

        self.root_layout = BoxLayout(

            orientation="horizontal",

            spacing=dp(5),

            padding=dp(5)
        )

        self.build_sidebar()

        self.build_main()

        Clock.schedule_once(

            lambda dt:
            self.add_codey_message(

                "Heyyy! 👋 I'm Codey! 🤖💻\n\n"

                "I'm ready to help with "
                "Python, Java and C. "

                "You can talk to me in "
                "English or Hinglish too! 😎\n\n"

                "And yes... I have a personality now. "
                "😳😂"
            ),

            0.3
        )

        Window.bind(
            size=self.on_window_resize
        )

        return self.root_layout

    def on_window_resize(
        self,
        *_args
    ):

        if self.sidebar:

            self.sidebar.width = (
                responsive_sidebar_width()
            )

        if self.chat_messages:

            for child in (
                self.chat_messages.children
            ):

                if isinstance(
                    child,
                    MessageBubble
                ):

                    child.refresh()

    def build_sidebar(self):

        self.sidebar = BoxLayout(

            orientation="vertical",

            size_hint_x=None,

            width=(
                responsive_sidebar_width()
            ),

            spacing=dp(5),

            padding=dp(5)
        )

        if os.path.exists(
            CHARACTER_FILE
        ):

            character = Image(

                source=CHARACTER_FILE,

                size_hint_y=None,

                height=(

                    dp(115)

                    if is_phone_layout()

                    else dp(175)
                ),

                keep_ratio=True
            )

            self.sidebar.add_widget(
                character
            )

        else:

            avatar = Label(

                text="🤖\nCODEY",

                font_size=(

                    dp(22)

                    if is_phone_layout()

                    else dp(32)
                ),

                size_hint_y=None,

                height=(

                    dp(115)

                    if is_phone_layout()

                    else dp(175)
                ),

                halign="center",

                valign="middle",

                text_size=(
                    None,
                    None
                )
            )

            self.sidebar.add_widget(
                avatar
            )

        title = Label(

            text=(
                "[b]CODEY[/b]\n"
                "Anime Coding Companion"
            ),

            markup=True,

            font_size=(

                dp(12)

                if is_phone_layout()

                else dp(17)
            ),

            halign="center",

            valign="middle",

            text_size=(

                self.sidebar.width - dp(10),

                None
            ),

            size_hint_y=None,

            height=dp(55)
        )

        self.sidebar.add_widget(
            title
        )

        self.status_label = Label(

            text=(
                "● Online • "
                "Feeling normal 🤖"
            ),

            font_size=(

                dp(10)

                if is_phone_layout()

                else dp(13)
            ),

            size_hint_y=None,

            height=dp(35),

            halign="center",

            valign="middle",

            text_size=(

                self.sidebar.width - dp(10),

                None
            )
        )

        self.sidebar.add_widget(
            self.status_label
        )

        buttons = [

            ("💬 Chat", self.show_chat),

            ("💻 Code Editor", self.show_code),

            ("📚 Teach Codey",
             self.open_teach_popup),

            ("🤓 Features",
             self.show_features),

            ("🌙 Theme",
             self.toggle_theme),

            ("🔊 Voice",
             self.toggle_tts),

            ("🗑 Clear Chat",
             self.clear_chat),

            ("🚪 Exit",
             self.exit_app),

        ]

        for text, callback in buttons:

            button = Button(

                text=text,

                size_hint_y=None,

                height=(

                    dp(38)

                    if is_phone_layout()

                    else dp(44)
                ),

                font_size=(

                    dp(11)

                    if is_phone_layout()

                    else dp(14)
                ),

                halign="center",

                valign="middle",

                text_size=(

                    self.sidebar.width - dp(8),

                    None
                ),

                padding=(
                    dp(2),
                    dp(2)
                )
            )

            button.bind(
                on_release=callback
            )

            self.sidebar.add_widget(
                button
            )

        self.sidebar.add_widget(
            Widget()
        )

        footer = Label(

            text=(
                "Python • Java • C/C++\n"
                "Hinglish + English"
            ),

            font_size=(

                dp(9)

                if is_phone_layout()

                else dp(12)
            ),

            halign="center",

            valign="middle",

            text_size=(

                self.sidebar.width - dp(8),

                None
            ),

            size_hint_y=None,

            height=dp(40)
        )

        self.sidebar.add_widget(
            footer
        )

        self.root_layout.add_widget(
            self.sidebar
        )

    def build_main(self):

        main = BoxLayout(

            orientation="vertical",

            spacing=dp(5),

            size_hint_x=1
        )

        header = BoxLayout(

            orientation="horizontal",

            size_hint_y=None,

            height=dp(48),

            padding=(
                dp(4),
                dp(2)
            )
        )

        self.header_title = Label(

            text=(
                "[b]CODEY[/b]  •  "
                "Your Coding Buddy 🤖"
            ),

            markup=True,

            font_size=(

                dp(15)

                if is_phone_layout()

                else dp(20)
            ),

            halign="left",

            valign="middle",

            text_size=(

                None,

                dp(44)
            ),

            size_hint_x=1
        )

        header.add_widget(
            self.header_title
        )

        main.add_widget(
            header
        )

        self.main_container = BoxLayout(

            orientation="vertical",

            size_hint_y=1
        )

        main.add_widget(
            self.main_container
        )

        self.root_layout.add_widget(
            main
        )

        self.show_chat()

    def show_chat(
        self,
        *_args
    ):

        self.main_container.clear_widgets()

        layout = BoxLayout(

            orientation="vertical",

            spacing=dp(5)
        )

        self.chat_scroll = ScrollView(

            do_scroll_x=False,

            do_scroll_y=True,

            bar_width=dp(6)
        )

        self.chat_messages = GridLayout(

            cols=1,

            spacing=dp(4),

            size_hint_y=None,

            size_hint_x=1,

            padding=dp(4)
        )

        self.chat_messages.bind(

            minimum_height=
            self.chat_messages.setter(
                "height"
            )
        )

        self.chat_scroll.add_widget(
            self.chat_messages
        )

        layout.add_widget(
            self.chat_scroll
        )

        bottom = BoxLayout(

            size_hint_y=None,

            height=dp(55),

            spacing=dp(4)
        )

        self.chat_input = TextInput(

            hint_text=(
                "Talk to Codey... "
                "English or Hinglish"
            ),

            multiline=False,

            write_tab=False,

            font_size=dp(14),

            padding=(
                dp(8),
                dp(8)
            ),

            size_hint_x=1
        )

        self.chat_input.bind(
            on_text_validate=self.send_message
        )

        send = Button(

            text="SEND",

            size_hint_x=None,

            width=dp(105),

            font_size=dp(14)
        )

        send.bind(
            on_release=self.send_message
        )

        bottom.add_widget(
            self.chat_input
        )

        bottom.add_widget(
            send
        )

        layout.add_widget(
            bottom
        )

        self.main_container.add_widget(
            layout
        )

    def add_user_message(
        self,
        text
    ):

        if self.chat_messages is None:
            return

        bubble = MessageBubble(

            f"[b]You[/b]\n{text}",

            is_user=True
        )

        self.chat_messages.add_widget(
            bubble
        )

        Clock.schedule_once(

            lambda dt:
            self.scroll_chat(),

            0.05
        )

    def add_codey_message(
        self,
        text
    ):

        if self.chat_messages is None:
            return

        bubble = MessageBubble(

            f"[b]Codey 🤖[/b]\n{text}"
        )

        self.chat_messages.add_widget(
            bubble
        )

        Clock.schedule_once(

            lambda dt:
            self.scroll_chat(),

            0.05
        )

    def scroll_chat(self):

        if self.chat_scroll:

            self.chat_scroll.scroll_y = 0

    def send_message(
        self,
        *_args
    ):

        if not self.chat_input:
            return

        text = (
            self.chat_input.text.strip()
        )

        if not text:
            return

        self.chat_input.text = ""

        self.add_user_message(
            text
        )

        self.status_label.text = (
            "● Thinking... 🤔"
        )

        Clock.schedule_once(

            lambda dt:
            self.process_chat(text),

            0.05
        )

    def process_chat(
        self,
        text
    ):

        response = (
            self.assistant.chat(
                text
            )
        )

        self.add_codey_message(
            response
        )

        self.update_mood_display()

        self.assistant.speak(
            response
        )

    def update_mood_display(self):

        mood = (
            self.assistant
            .personality
            .mood
        )

        mood_map = {

            "compliment":
                "● Flustered 😳",

            "praise":
                "● Happy 😁",

            "shy":
                "● Embarrassed 🫣",

            "teasing":
                "● Playful 😈",

            "mistake":
                "● Oops 🥲",

            "success":
                "● Excited 🎉",

            "supportive":
                "● Supportive 🥺",

            "thinking":
                "● Thinking 🤔",

            "thank_you":
                "● Happy 😊",

            "casual":
                "● Casual 😎",

            "good_morning":
                "● Energetic ☀️",

            "good_afternoon":
                "● Cheerful ☀️",

            "good_evening":
                "● Relaxed 🌆",

            "good_night":
                "● Sleepy 🌙",

            "greeting":
                "● Friendly 👋",

            "joke":
                "● Laughing 😂",

            "encouragement":
                "● Encouraging 🤝",

            "normal":
                "● Online 🤖",
        }

        self.status_label.text = (
            mood_map.get(
                mood,
                "● Online 🤖"
            )
        )

    def show_code(
        self,
        *_args
    ):

        self.main_container.clear_widgets()

        layout = BoxLayout(

            orientation="vertical",

            spacing=dp(5),

            padding=dp(4)
        )

        toolbar = BoxLayout(

            size_hint_y=None,

            height=dp(45),

            spacing=dp(3)
        )

        self.language_spinner = Spinner(

            text=(

                self.assistant.last_language

                if self.assistant.last_language
                in [
                    "Python",
                    "Java",
                    "C",
                    "C++"
                ]

                else "Python"
            ),

            values=(

                "Python",
                "Java",
                "C",
                "C++"
            ),

            size_hint_x=None,

            width=dp(95),

            font_size=dp(12)
        )

        toolbar.add_widget(
            self.language_spinner
        )

        actions = [

            ("Analyze",
             self.analyze_editor),

            ("Explain",
             self.explain_editor),

            ("Fix",
             self.fix_editor),

            ("Improve",
             self.improve_editor),

            ("Comments",
             self.comments_editor),

        ]

        for text, callback in actions:

            button = Button(

                text=text,

                font_size=dp(10),

                halign="center",

                valign="middle",

                text_size=(
                    None,
                    None
                )
            )

            button.bind(
                on_release=callback
            )

            toolbar.add_widget(
                button
            )

        layout.add_widget(
            toolbar
        )

        filebar = BoxLayout(

            size_hint_y=None,

            height=dp(42),

            spacing=dp(3)
        )

        file_actions = [

            ("Open",
             self.open_file_popup),

            ("Save",
             self.save_file_popup),

            ("Copy",
             self.copy_code),

            ("Clear",
             self.clear_editor),

        ]

        for text, callback in file_actions:

            button = Button(

                text=text,

                font_size=dp(11)
            )

            button.bind(
                on_release=callback
            )

            filebar.add_widget(
                button
            )

        layout.add_widget(
            filebar
        )

        self.code_editor = TextInput(

            text=self.assistant.last_code,

            multiline=True,

            font_size=dp(14),

            padding=(
                dp(8),
                dp(8)
            ),

            hint_text=(
                "Paste your Python / Java / "
                "C / C++ code here..."
            ),

            size_hint_y=0.55
        )

        layout.add_widget(
            self.code_editor
        )

        output_label = Label(

            text="Analysis / response",

            size_hint_y=None,

            height=dp(28),

            halign="left",

            valign="middle",

            text_size=(

                None,

                dp(28)
            ),

            font_size=dp(13)
        )

        layout.add_widget(
            output_label
        )

        self.code_output = TextInput(

            text="Codey is ready. 🤖",

            readonly=True,

            multiline=True,

            font_size=dp(13),

            padding=(
                dp(8),
                dp(8)
            ),

            size_hint_y=0.45
        )

        layout.add_widget(
            self.code_output
        )

        self.main_container.add_widget(
            layout
        )

    def get_editor_data(self):

        code = (
            self.code_editor.text.strip()
        )

        language = (
            self.language_spinner.text
        )

        self.assistant.last_code = code

        self.assistant.last_language = (
            language
        )

        return code, language

    def set_output(
        self,
        text
    ):

        if self.code_output:

            self.code_output.text = (
                text
            )

    def analyze_editor(
        self,
        *_args
    ):

        code, language = (
            self.get_editor_data()
        )

        result = (
            self.assistant.analyze_code(
                code,
                language
            )
        )

        self.set_output(
            result
        )

    def explain_editor(
        self,
        *_args
    ):

        code, language = (
            self.get_editor_data()
        )

        result = (
            self.assistant.explain_code(
                code,
                language
            )
        )

        self.set_output(
            result
        )

    def fix_editor(
        self,
        *_args
    ):

        code, language = (
            self.get_editor_data()
        )

        result = (
            self.assistant.fix_code(
                code,
                language
            )
        )

        self.set_output(
            result
        )

    def improve_editor(
        self,
        *_args
    ):

        code, language = (
            self.get_editor_data()
        )

        result = (
            self.assistant.improve_code(
                code,
                language
            )
        )

        self.set_output(
            result
        )

    def comments_editor(
        self,
        *_args
    ):

        code, language = (
            self.get_editor_data()
        )

        result = (
            self.assistant.comment_code(
                code,
                language
            )
        )

        self.set_output(
            result
        )

    def copy_code(
        self,
        *_args
    ):

        if not self.code_editor:
            return

        try:

            Clipboard.copy(
                self.code_editor.text
            )

            self.set_output(
                "📋 Code copied to clipboard! 😎"
            )

        except Exception:

            self.set_output(
                "🥲 I couldn't access "
                "the clipboard."
            )

    def clear_editor(
        self,
        *_args
    ):

        if self.code_editor:

            self.code_editor.text = ""

        if self.code_output:

            self.code_output.text = (
                "Editor cleared. 🧹🤖"
            )

    def open_file_popup(
        self,
        *_args
    ):

        content = BoxLayout(

            orientation="vertical",

            spacing=dp(5)
        )

        chooser = FileChooserListView(

            path=APP_DIR,

            filters=[

                "*.py",
                "*.java",
                "*.c",
                "*.cpp",
                "*.txt",

            ]
        )

        content.add_widget(
            chooser
        )

        buttons = BoxLayout(

            size_hint_y=None,

            height=dp(45),

            spacing=dp(5)
        )

        popup = Popup(

            title="Open Code File",

            content=content,

            size_hint=(0.92, 0.88)
        )

        open_button = Button(
            text="Open"
        )

        cancel_button = Button(
            text="Cancel"
        )

        def do_open(
            _button
        ):

            if not chooser.selection:
                return

            path = (
                chooser.selection[0]
            )

            try:

                with open(
                    path,
                    "r",
                    encoding="utf-8"
                ) as f:

                    code = f.read()

                if not self.code_editor:

                    self.show_code()

                self.code_editor.text = (
                    code
                )

                language = (
                    detect_language(code)
                )

                if language in [
                    "Python",
                    "Java",
                    "C",
                    "C++"
                ]:

                    self.language_spinner.text = (
                        language
                    )

                self.assistant.last_code = (
                    code
                )

                self.assistant.last_language = (
                    language
                )

                popup.dismiss()

                self.set_output(
                    f"📂 Opened: "
                    f"{os.path.basename(path)}"
                )

            except Exception as e:

                self.set_output(
                    f"🥲 Couldn't open file:\n{e}"
                )

        open_button.bind(
            on_release=do_open
        )

        cancel_button.bind(
            on_release=popup.dismiss
        )

        buttons.add_widget(
            open_button
        )

        buttons.add_widget(
            cancel_button
        )

        content.add_widget(
            buttons
        )

        popup.open()

    def save_file_popup(
        self,
        *_args
    ):

        if not self.code_editor:
            return

        layout = BoxLayout(

            orientation="vertical",

            padding=dp(10),

            spacing=dp(10)
        )

        filename = TextInput(

            hint_text="Example: my_program.py",

            multiline=False
        )

        layout.add_widget(
            Label(
                text="Enter file name:"
            )
        )

        layout.add_widget(
            filename
        )

        buttons = BoxLayout(

            size_hint_y=None,

            height=dp(45),

            spacing=dp(5)
        )

        popup = Popup(

            title="Save Code",

            content=layout,

            size_hint=(0.88, 0.48)
        )

        save_button = Button(
            text="Save"
        )

        cancel_button = Button(
            text="Cancel"
        )

        def do_save(
            _button
        ):

            name = (
                filename.text.strip()
            )

            if not name:
                return

            name = os.path.basename(
                name
            )

            if "." not in name:

                ext_map = {

                    "Python": ".py",

                    "Java": ".java",

                    "C": ".c",

                    "C++": ".cpp",

                }

                name += ext_map.get(

                    self.language_spinner.text,

                    ".txt"
                )

            path = os.path.join(

                APP_DIR,

                name
            )

            try:

                with open(
                    path,
                    "w",
                    encoding="utf-8"
                ) as f:

                    f.write(
                        self.code_editor.text
                    )

                popup.dismiss()

                self.set_output(
                    f"💾 Saved successfully:\n"
                    f"{path}"
                )

            except Exception as e:

                self.set_output(
                    f"🥲 Couldn't save file:\n"
                    f"{e}"
                )

        save_button.bind(
            on_release=do_save
        )

        cancel_button.bind(
            on_release=popup.dismiss
        )

        buttons.add_widget(
            save_button
        )

        buttons.add_widget(
            cancel_button
        )

        layout.add_widget(
            buttons
        )

        popup.open()

    def show_features(
        self,
        *_args
    ):

        popup = Popup(

            title="What can Codey do?",

            size_hint=(0.92, 0.88)
        )

        text = TextInput(

            text=self.assistant.features(),

            readonly=True,

            multiline=True,

            font_size=dp(13),

            padding=dp(10)
        )

        popup.content = text

        popup.open()

    def open_teach_popup(
        self,
        *_args
    ):

        layout = BoxLayout(

            orientation="vertical",

            padding=dp(10),

            spacing=dp(8)
        )

        info = Label(

            text=(

                "📚 Teach Codey "
                "a custom response\n\n"

                "Enter a phrase Codey "
                "should recognize, then "
                "give multiple possible replies.\n\n"

                "Codey will randomly choose one."
            ),

            size_hint_y=None,

            height=dp(120),

            halign="left",

            valign="top",

            text_size=(

                None,

                dp(120)
            ),

            font_size=dp(13)
        )

        layout.add_widget(
            info
        )

        trigger = TextInput(

            hint_text="Trigger: you're smart",

            multiline=False,

            size_hint_y=None,

            height=dp(45)
        )

        layout.add_widget(
            trigger
        )

        responses = TextInput(

            hint_text=(

                "One response per line:\n"

                "W-Wait 😳\n"

                "Hehe, thanks! 🥰\n"

                "I knew you'd notice 😎"
            ),

            multiline=True
        )

        layout.add_widget(
            responses
        )

        buttons = BoxLayout(

            size_hint_y=None,

            height=dp(45),

            spacing=dp(5)
        )

        popup = Popup(

            title="Teach Codey",

            content=layout,

            size_hint=(0.92, 0.88)
        )

        save = Button(
            text="Teach"
        )

        cancel = Button(
            text="Cancel"
        )

        def teach(
            _button
        ):

            ok = (
                self.assistant
                .memory
                .add_rule(
                    trigger.text,
                    responses.text
                )
            )

            if ok:

                popup.dismiss()

                if self.chat_messages:

                    self.add_codey_message(

                        "📚 Learned a new "
                        "custom rule! 😎🧠\n\n"

                        f"Trigger: "
                        f"{trigger.text.strip()}\n"

                        "I'll randomly choose "
                        "between the responses "
                        "you taught me."
                    )

            else:

                responses.text = (

                    "Please enter a trigger "
                    "and at least one response. 🤔"
                )

        save.bind(
            on_release=teach
        )

        cancel.bind(
            on_release=popup.dismiss
        )

        buttons.add_widget(
            save
        )

        buttons.add_widget(
            cancel
        )

        layout.add_widget(
            buttons
        )

        if self.assistant.memory.rules:

            existing = (
                "\n\n📖 Saved custom triggers:\n"
            )

            rule_names = list(
                self.assistant
                .memory
                .rules
                .keys()
            )[:15]

            for trigger_name in rule_names:

                existing += (
                    f"• {trigger_name}\n"
                )

            layout.add_widget(

                Label(

                    text=existing,

                    size_hint_y=None,

                    height=dp(

                        min(

                            200,

                            35
                            + 25
                            * len(rule_names)
                        )
                    ),

                    halign="left",

                    valign="top",

                    text_size=(
                        None,
                        None
                    ),

                    font_size=dp(12)
                )
            )

        popup.open()

    def toggle_theme(
        self,
        *_args
    ):

        self.dark_mode = (
            not self.dark_mode
        )

        if self.dark_mode:

            Window.clearcolor = (
                0.05,
                0.05,
                0.07,
                1
            )

            self.status_label.text = (
                "● Dark mode 🌙"
            )

        else:

            Window.clearcolor = (
                1,
                1,
                1,
                1
            )

            self.status_label.text = (
                "● Light mode ☀️"
            )

    def toggle_tts(
        self,
        *_args
    ):

        if (
            self.assistant.tts_engine
            is None
        ):

            self.add_codey_message(

                "🔊 Voice output isn't "
                "available on this device. "

                "You can still use normal chat. 😊"
            )

            return

        self.assistant.tts_enabled = (
            not self.assistant.tts_enabled
        )

        if self.assistant.tts_enabled:

            self.add_codey_message(
                "🔊 Voice mode ON! 😎"
            )

        else:

            self.add_codey_message(
                "🔇 Voice mode OFF."
            )

    def clear_chat(
        self,
        *_args
    ):

        if self.chat_messages:

            self.chat_messages.clear_widgets()

        self.assistant.recent_turns.clear()

        self.add_codey_message(

            "Chat cleared. 🧹✨\n\n"

            "Fresh start! What are we building? 🤖"
        )

    def exit_app(
        self,
        *_args
    ):

        App.get_running_app().stop()

if __name__ == "__main__":

    CodeyApp().run()
