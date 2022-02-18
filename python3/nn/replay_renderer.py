import pygame

from nn.keyboard import PyGameKeyboardListener
from nn.mastermind import Mastermind
from nn.observation_converter import ObservationConverter
from nn.rendering import PyGameRenderer, RendererScreenSettings
from nn.running_speed import RunningSpeed

# replay_path = "../logs/replay.json"
replay_path = "../../runs/arxiv/replay-78-1644097313.134485-1644097313.150521.json"
# replay_path = "../lost_runs/lucky-lock-vs-honorable-friend.json"


def pygame_sleep(seconds: float) -> None:
    pygame.time.wait(int(seconds * 1000))


def main():
    screen_settings = RendererScreenSettings(15, 15, 50)
    renderer = PyGameRenderer(screen_settings)
    observation_converter = ObservationConverter()
    keyboard_listener = PyGameKeyboardListener()
    mastermind = Mastermind(
        observation_converter,
        keyboard_listener,
        renderer,
        speed=RunningSpeed.Normal,
        sleep_func=pygame_sleep
    )
    mastermind.replay_episode(replay_path)


if __name__ == "__main__":
    main()



