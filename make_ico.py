import os
from PIL import Image

ico_path = r"C:\Users\wongs\.gemini\antigravity\scratch\tradingview_xbox\icon.ico"
img = Image.open(r"C:\Users\wongs\.gemini\antigravity\brain\f71e74fd-f2a2-4a5a-ad95-c8a5de4e3b40\xbox_lens_icon_1772310936614.png")
icon_sizes = [(16,16), (32, 32), (48, 48), (64,64)]

# Save as .ico
img.save(ico_path, sizes=icon_sizes)
print(f"Generated {ico_path}")
