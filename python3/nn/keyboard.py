import abc
from enum import IntEnum
from typing import Set

import pygame


class KeyboardEvent(IntEnum):
    Quit = 0
    Pause = 1
    Step = 2
    SpeedFast = 3
    SpeedNormal = 4
    SpeedSlow = 5


class KeyboardListener(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def listen(self) -> Set[KeyboardEvent]:
        ...


class PyGameKeyboardListener(KeyboardListener):
    def listen(self) -> Set[KeyboardEvent]:
        actions_set = set()
        for event in pygame.event.get(pygame.KEYDOWN):
            if event.key == pygame.K_p:
                actions_set.add(KeyboardEvent.Pause)
            if event.key == pygame.K_s:
                actions_set.add(KeyboardEvent.Step)
            if event.key == pygame.K_1:
                actions_set.add(KeyboardEvent.SpeedSlow)
            if event.key == pygame.K_2:
                actions_set.add(KeyboardEvent.SpeedNormal)
            if event.key == pygame.K_3:
                actions_set.add(KeyboardEvent.SpeedFast)
            if event.key == pygame.K_ESCAPE:
                actions_set.add(KeyboardEvent.Quit)
        if pygame.event.get(pygame.QUIT):
            actions_set.add(KeyboardEvent.Quit)
        return actions_set
