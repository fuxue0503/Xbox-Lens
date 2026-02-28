import pygame
import time
import os

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"

pygame.init()
pygame.joystick.init()

print("="*40)
print("XBOX CONTROLLER DIAGNOSTIC SCRIPT")
print("="*40)

def main():
    if pygame.joystick.get_count() == 0:
        print("❌ No joystick detected by pygame! Please make sure your Xbox Controller is connected and turned on.")
        return

    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    
    print(f"✅ Joystick Detected: {joystick.get_name()}")
    print("Move your sticks or press buttons. Press Ctrl+C to exit.")
    print("="*40)

    try:
        while True:
            for event in pygame.event.get():
                if event.type == pygame.JOYAXISMOTION:
                    # Only print significant movement
                    if abs(event.value) > 0.15:
                        print(f"Axis {event.axis} moved to {event.value:.2f}")
                elif event.type == pygame.JOYBUTTONDOWN:
                    print(f"Button {event.button} pressed")
                elif event.type == pygame.JOYHATMOTION:
                    print(f"D-Pad moved to {event.value}")
            time.sleep(0.01)
    except KeyboardInterrupt:
        print("Diagnostic exiting.")

if __name__ == "__main__":
    main()
