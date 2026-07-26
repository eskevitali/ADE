"""Hello function and TimerSimulator — console reference implementation."""

from __future__ import annotations

import time


def hello() -> None:
    print("Hello, World!")


class TimerSimulator:
    """Simulates clock time with adjustable speed_multiplier variable."""

    def __init__(self, start_time: int = 12 * 3600, speed: float = 1.0) -> None:
        self.current_time = float(start_time)
        self.speed_multiplier = float(speed)
        self.is_running = False
        self.paused = False
        self.tick_count = 0

    def format_time(self) -> str:
        sec = int(self.current_time) % 86400
        h, rem = divmod(sec, 3600)
        m, s = divmod(rem, 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def set_speed(self, multiplier: float) -> None:
        self.speed_multiplier = multiplier

    def start(self) -> None:
        self.is_running = True
        self.paused = False

    def pause(self) -> None:
        self.paused = not self.paused

    def stop(self) -> None:
        self.is_running = False
        self.paused = False

    def tick(self, dt: float = 1.0) -> None:
        if self.is_running and not self.paused:
            self.current_time += dt * self.speed_multiplier
            self.tick_count += 1

    def status(self) -> dict:
        return {
            "time": self.format_time(),
            "current_time": self.current_time,
            "speed_multiplier": self.speed_multiplier,
            "tick_count": self.tick_count,
            "is_running": self.is_running,
            "paused": self.paused,
        }


def main() -> None:
    hello()
    sim = TimerSimulator()
    print("TimerSimulator ready. Open /preview/.../simulator in ADE for full web UI.")
    sim.start()
    for step, speed in enumerate([1.0, 10.0, 0.1, -1.0], start=1):
        sim.set_speed(speed)
        print(f"Step {step}: speed_multiplier={speed}")
        for _ in range(3):
            sim.tick(1.0)
            print(f"  {sim.format_time()} ticks={sim.tick_count}")
            time.sleep(0.3)
    sim.stop()
    print("Done:", sim.status())


if __name__ == "__main__":
    main()
