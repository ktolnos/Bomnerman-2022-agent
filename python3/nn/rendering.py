import abc
import functools
from dataclasses import dataclass
from typing import Tuple

import numpy as np
import pygame
from numpy import ndarray


@dataclass(frozen=True)
class RendererScreenSettings:
    width: int
    height: int
    scale_factor: int

    def __post_init__(self):
        assert self.width > 0 and self.height > 0 and self.scale_factor > 0

    @functools.cached_property
    def size(self) -> Tuple[int, int]:
        return self.width, self.height

    @functools.cached_property
    def scaled_size(self) -> Tuple[int, int]:
        return self.width * self.scale_factor, self.height * self.scale_factor


class Renderer(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def render(self, rgb: ndarray) -> None:
        ...


class PyGameRenderer(Renderer):
    @staticmethod
    def _transform_to_pygame_coordinates(rgb: ndarray) -> ndarray:
        transformed_rgb = np.rot90(rgb)
        return np.flip(transformed_rgb, axis=0)

    def __init__(self, screen_settings: RendererScreenSettings, transform_coords: bool = False):
        pygame.init()
        self.screen_settings = screen_settings
        self.transform_coords = transform_coords
        self.screen = pygame.display.set_mode(screen_settings.scaled_size)
        self.surface = pygame.surface.Surface(screen_settings.size)
        self.scaled_surface = pygame.surface.Surface(screen_settings.scaled_size)

    def render(self, rgb: ndarray) -> None:
        transformed_rgb = rgb
        if self.transform_coords:
            transformed_rgb = self._transform_to_pygame_coordinates(rgb)
        pygame.pixelcopy.array_to_surface(self.surface, transformed_rgb)
        pygame.transform.scale(self.surface, self.screen_settings.scaled_size, self.scaled_surface)
        self.screen.blit(self.scaled_surface, (0, 0))
        pygame.display.flip()
