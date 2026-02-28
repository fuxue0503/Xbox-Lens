"""
TradingView Xbox Controller Integration
Optimized for Xbox Gamepads via Pygame & Pynput.
"""
import os
import time
import math
import ctypes
import logging

# Suppress pygame welcome message
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame

from pynput.keyboard import Controller as KeyboardController, Key, GlobalHotKeys
from pynput.mouse import Controller as MouseController, Button

import sys
import threading
import tkinter as tk

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# --- CONFIGURATION ---
DEADZONE = 0.15
DEBUG_MODE = True  # Added debug mode flag
# Maximum mouse speed (pixels per frame)
MOUSE_SPEED_MAX = 40.0
# Maximum scroll speed (clicks per frame multiplier)
SCROLL_SPEED_MAX = 0.8  

# Axis Mapping for Standard Xbox Controller (XInput via Pygame)
AXIS_LX = 0
AXIS_LY = 1
# Note: If your right stick moves the triggers instead, change these to 3 and 4
AXIS_RX = 2 
AXIS_RY = 3 

# Button Mapping for Standard Xbox Controller
BTN_A = 0
BTN_B = 1
BTN_X = 2
BTN_Y = 3
BTN_LB = 4
BTN_RB = 5
BTN_VIEW = 6   # BACK
BTN_MENU = 7   # START

# Timeframes to cycle through with LB/RB
TIMEFRAMES = ["15", "60", "120", "240", "480", "D", "W"]

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class TradingViewController:
    def __init__(self):
        self.keyboard = KeyboardController()
        self.mouse = MouseController()
        
        self.tf_index = 0 # Default to 15
        self.scroll_accum_x = 0.0
        self.scroll_accum_y = 0.0
        
        self.is_active = False # Default to paused state
        self.running = True
        self.last_window_title = ""
        
        # UI variables
        self.overlay_root = None
        self.status_label = None
        self._drag_data = {"x": 0, "y": 0}
        
        # Start overlay in a separate thread
        self.ui_thread = threading.Thread(target=self._run_overlay, daemon=True)
        self.ui_thread.start()

        pygame.init()
        pygame.joystick.init()
        self.joystick = None
        self._connect_joystick()

    def _connect_joystick(self):
        # We must call pygame.event.pump() or pygame.event.get() for pygame to recognize joysticks
        pygame.event.pump() 
        if pygame.joystick.get_count() > 0:
            self.joystick = pygame.joystick.Joystick(0)
            self.joystick.init()
            logging.info(f"Xbox Controller Connected: {self.joystick.get_name()}")
        else:
            logging.warning("No Xbox Controller found. Waiting...")

    def is_tradingview_active(self):
        """Check if TradingView is the currently active window."""
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value
        
        # Debounced Logging of window title changes
        if title != self.last_window_title:
            if DEBUG_MODE and self.is_active:
                print(f"[DEBUG Window] Active window changed to: '{title}'")
            self.last_window_title = title
            
        # The user's TradingView window title format is like: 'ETHUSD ▲ 1,957.88 +1.45% / Unnamed'
        # It doesn't contain 'TradingView' or 'TV'.
        # For now, we returns True to let the script work anywhere as long as it's 'ACTIVE' via the Home key.
        return True

    def apply_deadzone(self, val):
        """Apply deadzone to raw axis value and normalize."""
        if abs(val) < DEADZONE:
            return 0.0
        norm = (abs(val) - DEADZONE) / (1.0 - DEADZONE)
        return math.copysign(norm, val)

    def calculate_mouse_delta(self, val):
        """
        Exponential curve for precise micro-movements and fast macro-movements.
        val is already deadzone-adjusted and normalized [-1.0, 1.0].
        x^3 maintains sign and gives a nice exponential acceleration curve.
        """
        return (val ** 3) * MOUSE_SPEED_MAX

    def type_string(self, text):
        """Type a string out sequentially and press Enter."""
        for char in text:
            self.keyboard.press(char)
            self.keyboard.release(char)
            time.sleep(0.02)
        self.keyboard.press(Key.enter)
        self.keyboard.release(Key.enter)

    def execute_shortcut(self, key, alt=True):
        """Execute a keyboard shortcut with or without Alt."""
        if alt:
            self.keyboard.press(Key.alt)
        self.keyboard.press(key)
        self.keyboard.release(key)
        if alt:
            self.keyboard.release(Key.alt)

    def handle_button_down(self, button):
        if button == BTN_A:
            logging.info("A Button -> Left Click (放置点位)")
            self.mouse.click(Button.left)
        elif button == BTN_X:
            logging.info("X Button -> Alt+T (绘制趋势线)")
            self.execute_shortcut('t')
        elif button == BTN_Y:
            logging.info("Y Button -> Alt+H (绘制水平线)")
            self.execute_shortcut('h')
        elif button == BTN_B:
            logging.info("B Button -> Alt+R (重置图表)")
            self.execute_shortcut('r')
        elif button == BTN_MENU:
            logging.info("Start Button -> Alt+P (切换对数坐标)")
            self.execute_shortcut('p')
        elif button == BTN_LB:
            self.tf_index = max(0, self.tf_index - 1)
            tf = TIMEFRAMES[self.tf_index]
            logging.info(f"LB -> Switch Timeframe to: {tf}")
            self.type_string(tf)
        elif button == BTN_RB:
            self.tf_index = min(len(TIMEFRAMES) - 1, self.tf_index + 1)
            tf = TIMEFRAMES[self.tf_index]
            logging.info(f"RB -> Switch Timeframe to: {tf}")
            self.type_string(tf)

    def handle_hat_motion(self, x, y):
        if y == 1:
            logging.info("D-Pad Up -> Switch Watchlist Up")
            self.keyboard.press(Key.up)
            self.keyboard.release(Key.up)
        elif y == -1:
            logging.info("D-Pad Down -> Switch Watchlist Down")
            self.keyboard.press(Key.down)
            self.keyboard.release(Key.down)

    def _update_ui(self):
        if self.status_label and self.overlay_root:
            if self.is_active:
                self.status_label.config(text="● XBOX LENS: ACTIVE", fg="#00FF00")
            else:
                self.status_label.config(text="⏸ XBOX LENS: PAUSED", fg="#FF8800")
            self.overlay_root.update_idletasks()

    def _start_move(self, event):
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

    def _on_motion(self, event):
        x = self.overlay_root.winfo_x() - self._drag_data["x"] + event.x
        y = self.overlay_root.winfo_y() - self._drag_data["y"] + event.y
        self.overlay_root.geometry(f"+{x}+{y}")

    def _run_overlay(self):
        self.overlay_root = tk.Tk()
        self.overlay_root.title("TradingView Xbox Overlay")
        
        # Bind dragging events to the main window
        self.overlay_root.bind("<ButtonPress-1>", self._start_move)
        self.overlay_root.bind("<B1-Motion>", self._on_motion)
        
        # Semi-transparent, borderless, always on top
        self.overlay_root.attributes("-alpha", 0.75)
        self.overlay_root.attributes("-topmost", True)
        self.overlay_root.overrideredirect(True)
        self.overlay_root.configure(bg="#1A1A1A")
        
        # Position at top right
        screen_width = self.overlay_root.winfo_screenwidth()
        window_width = 300
        window_height = 340 # Increased height
        x_pos = screen_width - window_width - 20
        y_pos = 20
        self.overlay_root.geometry(f"{window_width}x{window_height}+{x_pos}+{y_pos}")

        # Note: We removed the WS_EX_TRANSPARENT click-through click so the user can click the close button.
        # It is still always on top and semi-transparent.

        # UI Elements
        # We also bind mouse events to these child widgets to allow clicking them to drag
        def bind_drag(widget):
            widget.bind("<ButtonPress-1>", self._start_move)
            widget.bind("<B1-Motion>", self._on_motion)

        # Status
        self.status_label = tk.Label(self.overlay_root, text="⏸ XBOX LENS: PAUSED", 
                                     font=("Segoe UI", 12, "bold"), fg="#FF8800", bg="#1A1A1A")
        self.status_label.pack(pady=(15, 10))
        bind_drag(self.status_label)
        
        # Divider
        divider = tk.Frame(self.overlay_root, height=1, bg="#333333")
        divider.pack(fill=tk.X, padx=20)
        bind_drag(divider)
        
        # Controls Mapping
        mappings = [
            ("L-Stick", "Mouse Move (Exp)"),
            ("R-Stick", "Scroll & Zoom"),
            ("A", "Left Click (Place)"),
            ("X", "Alt+T (Trendline)"),
            ("Y", "Alt+H (Horizontal)"),
            ("B", "Alt+R (Reset Chart)"),
            ("Start", "Alt+P (Log Scale)"),
            ("LB/RB", "Cycle Timeframes"),
            ("D-Pad \u2191\u2193", "Watchlist Up/Down"),
        ]
        
        mapping_frame = tk.Frame(self.overlay_root, bg="#1A1A1A")
        mapping_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)
        bind_drag(mapping_frame)
        
        for key, desc in mappings:
            row = tk.Frame(mapping_frame, bg="#1A1A1A")
            row.pack(fill=tk.X, pady=3)
            bind_drag(row)
            lbl1 = tk.Label(row, text=key, font=("Segoe UI", 9, "bold"), fg="#888888", bg="#1A1A1A", width=8, anchor="e")
            lbl1.pack(side=tk.LEFT, padx=(0,10))
            lbl2 = tk.Label(row, text=desc, font=("Segoe UI", 9), fg="#FFFFFF", bg="#1A1A1A", anchor="w")
            lbl2.pack(side=tk.LEFT)
            bind_drag(lbl1)
            bind_drag(lbl2)

        # Hotkeys instruction
        hotkey_frame = tk.Frame(self.overlay_root, bg="#1A1A1A")
        hotkey_frame.pack(fill=tk.X, padx=20, pady=(5, 5))
        bind_drag(hotkey_frame)
        
        shortcut_lbl = tk.Label(hotkey_frame, text="[Home] toggle state", font=("Segoe UI", 9, "italic"), fg="#777777", bg="#1A1A1A")
        shortcut_lbl.pack(side=tk.LEFT)
        bind_drag(shortcut_lbl)
        
        # Close Button
        close_btn = tk.Button(hotkey_frame, text="    STOP & EXIT    ", font=("Segoe UI", 8, "bold"), 
                              bg="#551111", fg="white", bd=0, cursor="hand2", 
                              command=self._ui_close_clicked)
        close_btn.pack(side=tk.RIGHT)

        # Initial UI sync
        self._update_ui()
        
        # Standard Tkinter mainloop
        self.overlay_root.mainloop()

    def activate(self):
        if not self.is_active:
            self.is_active = True
            print("\n" + "="*40)
            print(">>> 🎮 XBOX CONTROLLER MODE: ACTIVE <<<")
            print("="*40 + "\n")
            self._update_ui()

    def deactivate(self):
        if self.is_active:
            self.is_active = False
            print("\n" + "="*40)
            print(">>> ⏸️ XBOX CONTROLLER MODE: PAUSED. Press Home to resume. <<<")
            print("="*40 + "\n")
            self._update_ui()

    def stop_program(self):
        print("\n" + "="*40)
        print(">>> 🛑 PROGRAM EXITING... <<<")
        print("="*40 + "\n")
        self.running = False
        
        # Also destroy the tkinter root if it's running
        if self.overlay_root:
            try:
                self.overlay_root.quit()
            except:
                pass

    def _ui_close_clicked(self):
        # Trigger same teardown process as pressing Delete
        self.stop_program()
        # In case the main thread waits for events
        dummy_event = pygame.event.Event(pygame.USEREVENT)
        pygame.event.post(dummy_event)

    def on_press(self, key):
        if key == Key.home:
            self.activate()
        elif key == Key.end:
            self.deactivate()
        elif key == Key.delete:
            self.stop_program()
            return False

    def run(self):
        clock = pygame.time.Clock()
        
        print(r"""
  _______        ___        __      _          _                 
 |__   __|       | |       / _|    | |        | |                
    | |_ __ __ _ | |__    | |_   _ | |_  _   _| |_  ___   _ __   
    | | '__/ _` || '_ \   |  _| | || __|| | | | __|/ _ \ | '_ \  
    | | | | (_| || | | |  | |   | || |_ | |_| | |_| (_) || | | | 
    |_|_|  \__,_||_| |_|  |_|   |_| \__| \__,_|\__|\___/ |_| |_| 
                                                                 
        """)
        print("="*60)
        print("🚀 TRADINGVIEW XBOX CONTROLLER ACTIVATED")
        print("="*60)
        print("  - [HOME]   : Start / Resume control")
        print("  - [END]    : Pause control (DEFAULT STATE)")
        print("  - [DELETE] : Safe exit")
        print("="*60)
        print("\n>>> ⏸️ XBOX CONTROLLER MODE: PAUSED. Press Home to resume. <<<\n")
        
        # Start global keyboard listener
        from pynput.keyboard import Listener as KeyboardListener
        listener = KeyboardListener(on_press=self.on_press)
        listener.start()
        
        while self.running:
            try:
                # Handle connection drops
                if pygame.joystick.get_count() == 0 and self.joystick is not None:
                    logging.warning("Controller disconnected.")
                    self.joystick = None
                elif pygame.joystick.get_count() > 0 and self.joystick is None:
                    self._connect_joystick()

                # Event Processing guarantees Windows doesn't see us as frozen
                events = pygame.event.get()
                
                # Context Awareness: Proceed only if active and TradingView is the active window
                if not self.is_active:
                    clock.tick(60)
                    continue

                for event in events:
                    if event.type == pygame.JOYBUTTONDOWN:
                        self.handle_button_down(event.button)
                    elif event.type == pygame.JOYHATMOTION:
                        self.handle_hat_motion(*event.value)

                # Continuous Axis Processing (Mouse Move & Scroll)
                if self.joystick:
                    num_axes = self.joystick.get_numaxes()
                    
                    # Read Axes
                    lx = self.apply_deadzone(self.joystick.get_axis(AXIS_LX)) if num_axes > AXIS_LX else 0.0
                    ly = self.apply_deadzone(self.joystick.get_axis(AXIS_LY)) if num_axes > AXIS_LY else 0.0
                    rx = self.apply_deadzone(self.joystick.get_axis(AXIS_RX)) if num_axes > AXIS_RX else 0.0
                    ry = self.apply_deadzone(self.joystick.get_axis(AXIS_RY)) if num_axes > AXIS_RY else 0.0

                    # 1. Left Stick -> Mouse Movement
                    if lx != 0 or ly != 0:
                        dx = self.calculate_mouse_delta(lx)
                        dy = self.calculate_mouse_delta(ly)
                        self.mouse.move(dx, dy)
                        if DEBUG_MODE:
                            print(f"[DEBUG Left Stick] Raw(lx:{lx:.2f}, ly:{ly:.2f}) -> Move(dx:{dx:.2f}, dy:{dy:.2f})")

                    # 2. Right Stick -> Mouse Scroll
                    # Exponential curve for smooth scrolling
                    if rx != 0:
                        # rx positive -> push right -> Scroll right
                        self.scroll_accum_x += (rx ** 3) * SCROLL_SPEED_MAX
                        if abs(self.scroll_accum_x) >= 1.0:
                            clicks = int(self.scroll_accum_x)
                            self.mouse.scroll(clicks, 0)
                            self.scroll_accum_x -= clicks
                            if DEBUG_MODE:
                                print(f"[DEBUG Right Stick X] Scroll X clicks: {clicks}")
                            
                    if ry != 0:
                        # ry negative -> push up -> Zoom in -> Scroll positive (dy > 0)
                        self.scroll_accum_y += ((-ry) ** 3) * SCROLL_SPEED_MAX
                        if abs(self.scroll_accum_y) >= 1.0:
                            clicks = int(self.scroll_accum_y)
                            self.mouse.scroll(0, clicks)
                            self.scroll_accum_y -= clicks
                            if DEBUG_MODE:
                                print(f"[DEBUG Right Stick Y] Scroll Y clicks: {clicks}")

                clock.tick(60) # 60 FPS update loop
                
            except KeyboardInterrupt:
                logging.info("Exiting...")
                self.running = False
                break
            except Exception as e:
                logging.error(f"Error: {e}")
                time.sleep(1)
        
        # Ensure we wait for listener thread if exiting normally
        if listener.is_alive():
            listener.stop()

if __name__ == "__main__":
    if not is_admin():
        print("*" * 60)
        print("⚠️ WARNING: NOT RUNNING AS ADMINISTRATOR! ⚠️")
        print("TradingView usually operates with high privileges. If the script can't simulate")
        print("inputs (mouse/keyboard not working in TV), you MUST run this script in an")
        print("Administrator terminal (e.g. VSCode running as Admin).")
        print("We will attempt to run it anyway for testing purposes...")
        print("*" * 60)
        time.sleep(2)
        
    controller = TradingViewController()
    controller.run()
