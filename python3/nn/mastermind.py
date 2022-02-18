import logging
import time
from typing import Callable, Optional

import numpy as np

from .keyboard import KeyboardEvent, KeyboardListener
from .observation_converter import ObservationConverter
from .rendering import Renderer
from .running_speed import RunningSpeed

SLEEP_TIME_BETWEEN_GAMES = 0.1

logger = logging.getLogger(__name__)


class Mastermind:
    @staticmethod
    def _add_overlay(obs: np.ndarray, overlay: np.ndarray) -> np.ndarray:
        red, green, blue = overlay[:, :, 0], overlay[:, :, 1], overlay[:, :, 2]
        mask = (red != 0) | (green != 0) | (blue != 0)
        result = np.copy(obs)
        result[mask] = 0
        result += overlay
        return result

    def __init__(
        self,
        observation_converter: ObservationConverter,
        keyboard_listener: Optional[KeyboardListener] = None,
        renderer: Optional[Renderer] = None,
        speed: RunningSpeed = RunningSpeed.Slow,
        runs: int = 1,
        sleep_func: Callable[[float], None] = time.sleep,
    ):
        self.observation_converter = observation_converter
        self.renderer = renderer
        self.episode_num = 0
        self.runs = runs
        self.sleep_func = sleep_func
        self.keyboard_listener = keyboard_listener
        self.is_paused = False
        self.make_step = False
        self.quit = False
        self._set_running_speed(speed)

    def replay_episode(self, replay_path) -> None:
        history, unit_actions, unit_mask, unit_act_freq, bomb_actions, bomb_mask, bomb_act_freq =\
            self.observation_converter.get_replay_history(replay_path)
        step_num = -1
        for idx, screen in enumerate(history):
            step_num += 1
            if self.keyboard_listener:
                self._listen_keyboard_events()

            if self.quit:
                return
            while self.is_paused and not self.make_step:
                if self.keyboard_listener:
                    self._listen_keyboard_events()
                if self.quit:
                    return
            self.make_step = False

            print(np.sum(unit_actions[idx]))
            if self.renderer and step_num % self.render_n_frame == 0:
                self.renderer.render(self.observation_converter.screen_to_rgb(screen, unit_actions[idx], bomb_actions[idx]))
            if self.sleep_between_frames:
                self.sleep_func(self.sleep_between_frames)
        self.sleep_func(SLEEP_TIME_BETWEEN_GAMES)
        return

    def _listen_keyboard_events(self):
        events = self.keyboard_listener.listen()
        if KeyboardEvent.Quit in events:
            self.quit = True
        if KeyboardEvent.Pause in events:
            self.is_paused = not self.is_paused

        if KeyboardEvent.Step in events:
            self._set_running_speed(RunningSpeed.Step)
        elif KeyboardEvent.SpeedSlow in events:
            self._set_running_speed(RunningSpeed.Slow)
        elif KeyboardEvent.SpeedNormal in events:
            self._set_running_speed(RunningSpeed.Normal)
        elif KeyboardEvent.SpeedFast in events:
            self._set_running_speed(RunningSpeed.Fast)

    def _set_running_speed(self, speed: RunningSpeed):
        self.render_n_frame = speed.value.steps_per_frame
        self.sleep_between_frames = speed.value.sleep_between_frames
        self.is_paused = False
        if speed.value.is_step:
            self.is_paused = True
            self.make_step = True
