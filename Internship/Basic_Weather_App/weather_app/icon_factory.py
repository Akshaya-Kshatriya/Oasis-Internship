"""
Utilities for generating weather icons using Qt painting primitives.
"""

from __future__ import annotations

from typing import Dict

from PyQt6 import QtGui


class WeatherIconFactory:
    """Generate simplified weather icons on demand."""

    _cache: Dict[str, QtGui.QPixmap] = {}

    def __init__(self, size: int = 80) -> None:
        self.size = size

    def pixmap_for_code(self, code: int) -> QtGui.QPixmap:
        key = f"{code}:{self.size}"
        if key in self._cache:
            return self._cache[key]

        pixmap = QtGui.QPixmap(self.size, self.size)
        pixmap.fill(QtGui.QColor("transparent"))

        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        try:
            self._draw_icon(painter, code)
        finally:
            painter.end()

        self._cache[key] = pixmap
        return pixmap

    def _draw_icon(self, painter: QtGui.QPainter, code: int) -> None:
        theme = _weather_theme(code)
        background = QtGui.QColor(theme.background)
        accent = QtGui.QColor(theme.accent)

        rect = painter.viewport()

        brush = QtGui.QBrush(background)
        painter.setBrush(brush)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 40), 2))
        painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 18, 18)

        painter.setPen(QtGui.QPen(QtGui.QColor("white"), 4))

        if theme.kind == "sunny":
            self._draw_sun(painter, rect, accent)
        elif theme.kind == "partly_cloudy":
            self._draw_sun(painter, rect, accent, small=True)
            self._draw_cloud(painter, rect, offset=(0.0, 0.2))
        elif theme.kind == "cloudy":
            self._draw_cloud(painter, rect)
        elif theme.kind == "rain":
            self._draw_cloud(painter, rect)
            self._draw_raindrops(painter, rect)
        elif theme.kind == "snow":
            self._draw_cloud(painter, rect)
            self._draw_snowflakes(painter, rect)
        elif theme.kind == "storm":
            self._draw_cloud(painter, rect)
            self._draw_lightning(painter, rect)
        elif theme.kind == "fog":
            self._draw_cloud(painter, rect, flattened=True)
            self._draw_fog(painter, rect)
        else:
            # fallback
            painter.drawText(rect, int(QtGui.Qt.AlignmentFlag.AlignCenter), theme.label)

    def _draw_sun(self, painter: QtGui.QPainter, rect: QtGui.QRect, color: QtGui.QColor, small: bool = False) -> None:
        painter.save()
        painter.setBrush(QtGui.QBrush(color))
        radius = rect.width() * (0.18 if small else 0.3)
        center = rect.center()
        if small:
            center.setY(int(center.y() - rect.height() * 0.15))
            center.setX(int(center.x() - rect.width() * 0.18))
        painter.drawEllipse(center, int(radius), int(radius))
        painter.restore()

    def _draw_cloud(
        self,
        painter: QtGui.QPainter,
        rect: QtGui.QRect,
        *,
        offset: tuple[float, float] = (0.0, 0.0),
        flattened: bool = False,
    ) -> None:
        painter.save()
        painter.setBrush(QtGui.QBrush(QtGui.QColor("white")))
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 220), 2))

        base_width = rect.width() * 0.65
        base_height = rect.height() * (0.28 if flattened else 0.35)
        base_x = rect.x() + rect.width() * (0.17 + offset[0])
        base_y = rect.y() + rect.height() * (0.5 + offset[1])

        painter.drawRoundedRect(int(base_x), int(base_y), int(base_width), int(base_height), 20, 20)
        painter.drawEllipse(
            int(base_x - base_width * 0.15),
            int(base_y - base_height * 0.6),
            int(base_width * 0.5),
            int(base_height * 1.2),
        )
        painter.drawEllipse(
            int(base_x + base_width * 0.35),
            int(base_y - base_height * 0.8),
            int(base_width * 0.45),
            int(base_height * 1.3),
        )
        painter.restore()

    def _draw_raindrops(self, painter: QtGui.QPainter, rect: QtGui.QRect) -> None:
        painter.save()
        painter.setPen(QtGui.QPen(QtGui.QColor("#3498db"), 3))
        for i in range(3):
            x = rect.x() + rect.width() * (0.3 + i * 0.15)
            y1 = rect.y() + rect.height() * 0.7
            y2 = y1 + rect.height() * 0.15
            painter.drawLine(int(x), int(y1), int(x - rect.width() * 0.03), int(y2))
        painter.restore()

    def _draw_snowflakes(self, painter: QtGui.QPainter, rect: QtGui.QRect) -> None:
        painter.save()
        painter.setPen(QtGui.QPen(QtGui.QColor("#ecf0f1"), 2))
        for i in range(3):
            center_x = rect.x() + rect.width() * (0.32 + i * 0.14)
            center_y = rect.y() + rect.height() * 0.75
            radius = rect.width() * 0.05
            painter.drawLine(int(center_x - radius), int(center_y), int(center_x + radius), int(center_y))
            painter.drawLine(int(center_x), int(center_y - radius), int(center_x), int(center_y + radius))
            painter.drawLine(
                int(center_x - radius * 0.7),
                int(center_y - radius * 0.7),
                int(center_x + radius * 0.7),
                int(center_y + radius * 0.7),
            )
            painter.drawLine(
                int(center_x - radius * 0.7),
                int(center_y + radius * 0.7),
                int(center_x + radius * 0.7),
                int(center_y - radius * 0.7),
            )
        painter.restore()

    def _draw_lightning(self, painter: QtGui.QPainter, rect: QtGui.QRect) -> None:
        painter.save()
        painter.setBrush(QtGui.QBrush(QtGui.QColor("#f1c40f")))
        painter.setPen(QtGui.QPen(QtGui.QColor("#f39c12"), 2))
        points = [
            QtGui.QPoint(int(rect.x() + rect.width() * 0.55), int(rect.y() + rect.height() * 0.55)),
            QtGui.QPoint(int(rect.x() + rect.width() * 0.45), int(rect.y() + rect.height() * 0.85)),
            QtGui.QPoint(int(rect.x() + rect.width() * 0.6), int(rect.y() + rect.height() * 0.85)),
            QtGui.QPoint(int(rect.x() + rect.width() * 0.45), int(rect.y() + rect.height() * 1.05)),
        ]
        painter.drawPolygon(QtGui.QPolygon(points))
        painter.restore()

    def _draw_fog(self, painter: QtGui.QPainter, rect: QtGui.QRect) -> None:
        painter.save()
        painter.setPen(QtGui.QPen(QtGui.QColor("#bdc3c7"), 3, QtGui.Qt.PenStyle.SolidLine, cap=QtGui.Qt.PenCapStyle.RoundCap))
        for i in range(3):
            y = rect.y() + rect.height() * (0.7 + i * 0.08)
            painter.drawLine(int(rect.x() + rect.width() * 0.25), int(y), int(rect.x() + rect.width() * 0.75), int(y))
        painter.restore()


class Theme:
    __slots__ = ("kind", "background", "accent", "label")

    def __init__(self, kind: str, background: str, accent: str, label: str) -> None:
        self.kind = kind
        self.background = background
        self.accent = accent
        self.label = label


def _weather_theme(code: int) -> Theme:
    """
    Map Open-Meteo WMO weather codes to icon themes.
    """
    mapping = {
        0: Theme("sunny", "#f6b93b", "#f39c12", "☀"),
        1: Theme("partly_cloudy", "#74b9ff", "#f1c40f", "🌤"),
        2: Theme("partly_cloudy", "#74b9ff", "#f1c40f", "⛅"),
        3: Theme("cloudy", "#95a5a6", "#bdc3c7", "☁"),
        45: Theme("fog", "#95a5a6", "#bdc3c7", "🌫"),
        48: Theme("fog", "#95a5a6", "#bdc3c7", "🌫"),
        51: Theme("rain", "#5dade2", "#3498db", "🌦"),
        53: Theme("rain", "#5dade2", "#3498db", "🌦"),
        55: Theme("rain", "#5dade2", "#3498db", "🌧"),
        56: Theme("snow", "#85c1e9", "#ecf0f1", "🌨"),
        57: Theme("snow", "#85c1e9", "#ecf0f1", "🌨"),
        61: Theme("rain", "#5dade2", "#3498db", "🌧"),
        63: Theme("rain", "#5dade2", "#3498db", "🌧"),
        65: Theme("rain", "#5dade2", "#3498db", "🌧"),
        66: Theme("snow", "#85c1e9", "#ecf0f1", "🌨"),
        67: Theme("snow", "#85c1e9", "#ecf0f1", "🌨"),
        71: Theme("snow", "#85c1e9", "#ecf0f1", "❄"),
        73: Theme("snow", "#85c1e9", "#ecf0f1", "❄"),
        75: Theme("snow", "#85c1e9", "#ecf0f1", "❄"),
        77: Theme("snow", "#85c1e9", "#ecf0f1", "❄"),
        80: Theme("rain", "#5dade2", "#3498db", "🌧"),
        81: Theme("rain", "#5dade2", "#3498db", "🌧"),
        82: Theme("rain", "#5dade2", "#3498db", "⛈"),
        85: Theme("snow", "#85c1e9", "#ecf0f1", "❄"),
        86: Theme("snow", "#85c1e9", "#ecf0f1", "❄"),
        95: Theme("storm", "#5d6d7e", "#f9ca24", "⛈"),
        96: Theme("storm", "#5d6d7e", "#f9ca24", "⛈"),
        99: Theme("storm", "#5d6d7e", "#f9ca24", "⛈"),
    }
    return mapping.get(code, Theme("cloudy", "#95a5a6", "#bdc3c7", "?"))

