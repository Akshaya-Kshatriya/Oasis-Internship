"""
PyQt-based graphical application that displays weather information.
"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional

from PyQt6 import QtCore, QtGui, QtWidgets

from .icon_factory import WeatherIconFactory
from .weather_client import (
    Location,
    WeatherAPIError,
    WeatherClient,
    WeatherForecast,
)


class WorkerSignals(QtCore.QObject):
    result = QtCore.pyqtSignal(object)
    error = QtCore.pyqtSignal(Exception)
    finished = QtCore.pyqtSignal()


class Worker(QtCore.QRunnable):
    def __init__(self, fn, *args, **kwargs) -> None:
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @QtCore.pyqtSlot()
    def run(self) -> None:
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as exc:  # noqa: BLE001 - propagate errors through signal
            self.signals.error.emit(exc)
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()


class WeatherWindow(QtWidgets.QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Weather Dashboard")
        self.resize(1024, 720)
        self.setWindowIcon(QtGui.QIcon.fromTheme("weather-clear"))

        self._thread_pool = QtCore.QThreadPool.globalInstance()
        self._client = WeatherClient()
        self._icon_factory = WeatherIconFactory(size=120)
        self._current_forecast: Optional[WeatherForecast] = None

        self._build_ui()

    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        header = self._build_header()
        layout.addWidget(header)

        current_group = self._build_current_group()
        layout.addWidget(current_group)

        forecasts = self._build_forecast_section()
        layout.addWidget(forecasts, 1)

        self.setCentralWidget(central)

    def _build_header(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)

        self.location_input = QtWidgets.QLineEdit()
        self.location_input.setPlaceholderText("Enter a city or ZIP code (e.g. London, New York, 94105)")
        self.location_input.returnPressed.connect(self.fetch_for_location)

        self.units_combo = QtWidgets.QComboBox()
        self.units_combo.addItem("Celsius (°C)", userData="metric")
        self.units_combo.addItem("Fahrenheit (°F)", userData="imperial")
        self.units_combo.currentIndexChanged.connect(self._units_changed)

        self.search_button = QtWidgets.QPushButton("Search")
        self.search_button.clicked.connect(self.fetch_for_location)

        self.detect_button = QtWidgets.QPushButton("Use Current Location")
        self.detect_button.clicked.connect(self.fetch_for_current_location)

        for control in (self.location_input, self.units_combo, self.search_button, self.detect_button):
            control.setMinimumHeight(36)

        layout.addWidget(self.location_input, 3)
        layout.addWidget(self.units_combo, 1)
        layout.addWidget(self.search_button, 1)
        layout.addWidget(self.detect_button, 1)
        return widget

    def _build_current_group(self) -> QtWidgets.QGroupBox:
        group = QtWidgets.QGroupBox("Current Conditions")
        layout = QtWidgets.QHBoxLayout(group)

        self.icon_label = QtWidgets.QLabel()
        self.icon_label.setFixedSize(140, 140)
        self.icon_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        self.temp_label = QtWidgets.QLabel("--°")
        font = QtGui.QFont()
        font.setPointSize(42)
        font.setBold(True)
        self.temp_label.setFont(font)

        self.summary_label = QtWidgets.QLabel("Please search for a location.")
        self.summary_label.setWordWrap(True)

        left_layout = QtWidgets.QVBoxLayout()
        left_layout.addWidget(self.temp_label)
        left_layout.addWidget(self.summary_label)
        left_layout.addStretch()

        details_widget = QtWidgets.QWidget()
        details_layout = QtWidgets.QFormLayout(details_widget)
        details_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)
        details_layout.setFormAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)

        self.feels_like_label = QtWidgets.QLabel("--°")
        self.wind_label = QtWidgets.QLabel("--")
        self.precip_label = QtWidgets.QLabel("--")
        self.humidity_label = QtWidgets.QLabel("--")
        self.updated_label = QtWidgets.QLabel("--")

        details_layout.addRow("Feels like:", self.feels_like_label)
        details_layout.addRow("Wind:", self.wind_label)
        details_layout.addRow("Precipitation:", self.precip_label)
        details_layout.addRow("Humidity:", self.humidity_label)
        details_layout.addRow("Updated:", self.updated_label)

        layout.addWidget(self.icon_label)
        layout.addLayout(left_layout, 2)
        layout.addWidget(details_widget, 2)

        return group

    def _build_forecast_section(self) -> QtWidgets.QTabWidget:
        tabs = QtWidgets.QTabWidget()
        tabs.setTabPosition(QtWidgets.QTabWidget.TabPosition.North)

        self.hourly_table = QtWidgets.QTableWidget(0, 4)
        self.hourly_table.setHorizontalHeaderLabels(["Time", "Temperature", "Precip %", "Conditions"])
        self.hourly_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.hourly_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.hourly_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        tabs.addTab(self.hourly_table, "Hourly Forecast")

        self.daily_table = QtWidgets.QTableWidget(0, 5)
        self.daily_table.setHorizontalHeaderLabels(["Day", "Min", "Max", "Sunrise", "Sunset"])
        self.daily_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.daily_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.daily_table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        tabs.addTab(self.daily_table, "Daily Forecast")

        return tabs

    def _set_loading(self, loading: bool, message: str = "Loading...") -> None:
        for widget in (self.search_button, self.detect_button, self.location_input, self.units_combo):
            widget.setDisabled(loading)
        if loading:
            self.statusBar().showMessage(message)
        else:
            self.statusBar().clearMessage()

    def _units_changed(self) -> None:
        if self._current_forecast:
            self.fetch_for_existing_location()

    def fetch_for_location(self) -> None:
        query = self.location_input.text().strip()
        if not query:
            QtWidgets.QMessageBox.information(self, "Missing Location", "Please type a city name, postal code, or address.")
            self.location_input.setFocus()
            return
        units = self.units_combo.currentData()
        self._set_loading(True, f"Searching for {query}...")
        worker = Worker(self._fetch_forecast_workflow, query, units)
        worker.signals.result.connect(self._handle_forecast_result)
        worker.signals.error.connect(self._handle_error)
        worker.signals.finished.connect(lambda: self._set_loading(False))
        self._thread_pool.start(worker)

    def fetch_for_existing_location(self) -> None:
        if not self._current_forecast:
            return
        location = self._current_forecast.location
        units = self.units_combo.currentData()
        self._set_loading(True, f"Refreshing weather for {location.display_name}...")
        worker = Worker(self._fetch_existing_location, location, units)
        worker.signals.result.connect(self._handle_forecast_result)
        worker.signals.error.connect(self._handle_error)
        worker.signals.finished.connect(lambda: self._set_loading(False))
        self._thread_pool.start(worker)

    def fetch_for_current_location(self) -> None:
        units = self.units_combo.currentData()
        self._set_loading(True, "Detecting your location...")
        worker = Worker(self._fetch_current_location, units)
        worker.signals.result.connect(self._handle_forecast_result)
        worker.signals.error.connect(self._handle_error)
        worker.signals.finished.connect(lambda: self._set_loading(False))
        self._thread_pool.start(worker)

    def _fetch_forecast_workflow(self, query: str, units: str) -> WeatherForecast:
        location = self._client.geocode(query)
        return self._client.fetch_forecast(location, units=units)

    def _fetch_existing_location(self, location: Location, units: str) -> WeatherForecast:
        return self._client.fetch_forecast(location, units=units)

    def _fetch_current_location(self, units: str) -> WeatherForecast:
        location = self._client.geolocate()
        return self._client.fetch_forecast(location, units=units)

    @QtCore.pyqtSlot(object)
    def _handle_forecast_result(self, forecast: WeatherForecast) -> None:
        self._current_forecast = forecast
        self.location_input.setText(forecast.location.display_name)
        self.statusBar().showMessage(f"Updated at {forecast.current.time}")
        self._populate_current(forecast)
        self._populate_hourly(forecast)
        self._populate_daily(forecast)

    @QtCore.pyqtSlot(Exception)
    def _handle_error(self, error: Exception) -> None:
        message = str(error)
        if isinstance(error, WeatherAPIError):
            title = "Weather Service Error"
        else:
            title = "Unexpected Error"
        QtWidgets.QMessageBox.warning(self, title, message or "Something went wrong.")

    def _populate_current(self, forecast: WeatherForecast) -> None:
        current = forecast.current
        pixmap = self._icon_factory.pixmap_for_code(current.weather_code)
        self.icon_label.setPixmap(pixmap)

        self.temp_label.setText(f"{current.temperature:.0f}{forecast.units_label}")

        summary = weather_code_description(current.weather_code)
        self.summary_label.setText(f"{summary} in {forecast.location.display_name}")

        if current.apparent_temperature is not None:
            self.feels_like_label.setText(f"{current.apparent_temperature:.0f}{forecast.units_label}")
        else:
            self.feels_like_label.setText("N/A")

        wind_direction = f"{current.wind_direction}°" if current.wind_direction is not None else "N/A"
        self.wind_label.setText(f"{current.wind_speed:.1f} {wind_unit(self.units_combo.currentData())} @ {wind_direction}")

        if current.precipitation is not None:
            precip_unit = "in" if self.units_combo.currentData() == "imperial" else "mm"
            self.precip_label.setText(f"{current.precipitation:.2f} {precip_unit}")
        else:
            self.precip_label.setText("N/A")

        if current.relative_humidity is not None:
            self.humidity_label.setText(f"{current.relative_humidity}%")
        else:
            self.humidity_label.setText("N/A")

        self.updated_label.setText(format_time(current.time))

    def _populate_hourly(self, forecast: WeatherForecast) -> None:
        entries = forecast.hourly
        self.hourly_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.hourly_table.setItem(row, 0, QtWidgets.QTableWidgetItem(format_time(entry.time, "hour")))
            self.hourly_table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{entry.temperature:.0f}{forecast.units_label}"))
            precip = f"{entry.precipitation_probability}%" if entry.precipitation_probability is not None else "—"
            self.hourly_table.setItem(row, 2, QtWidgets.QTableWidgetItem(precip))
            self.hourly_table.setItem(row, 3, QtWidgets.QTableWidgetItem(weather_code_description(entry.weather_code)))

    def _populate_daily(self, forecast: WeatherForecast) -> None:
        entries = forecast.daily
        self.daily_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            self.daily_table.setItem(row, 0, QtWidgets.QTableWidgetItem(format_time(entry.date, "day")))
            self.daily_table.setItem(row, 1, QtWidgets.QTableWidgetItem(f"{entry.temp_min:.0f}{forecast.units_label}"))
            self.daily_table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{entry.temp_max:.0f}{forecast.units_label}"))
            self.daily_table.setItem(row, 3, QtWidgets.QTableWidgetItem(format_time(entry.sunrise, "time") if entry.sunrise else "—"))
            self.daily_table.setItem(row, 4, QtWidgets.QTableWidgetItem(format_time(entry.sunset, "time") if entry.sunset else "—"))


def weather_code_description(code: int) -> str:
    lookup = {
        0: "Clear sky",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
        45: "Fog",
        48: "Depositing rime fog",
        51: "Light drizzle",
        53: "Moderate drizzle",
        55: "Dense drizzle",
        56: "Light freezing drizzle",
        57: "Dense freezing drizzle",
        61: "Slight rain",
        63: "Moderate rain",
        65: "Heavy rain",
        66: "Light freezing rain",
        67: "Heavy freezing rain",
        71: "Slight snow",
        73: "Moderate snow",
        75: "Heavy snow",
        77: "Snow grains",
        80: "Rain showers",
        81: "Heavy rain showers",
        82: "Violent rain showers",
        85: "Snow showers",
        86: "Heavy snow showers",
        95: "Thunderstorm",
        96: "Thunderstorm with hail",
        99: "Severe thunderstorm with hail",
    }
    return lookup.get(code, f"Code {code}")


def wind_unit(units: str) -> str:
    return "mph" if units == "imperial" else "km/h"


def format_time(value: Optional[str], mode: str = "full") -> str:
    if not value:
        return "—"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value

    if mode == "hour":
        return dt.strftime("%a %I:%M %p")
    if mode == "day":
        return dt.strftime("%a %b %d")
    if mode == "time":
        return dt.strftime("%I:%M %p")
    return dt.strftime("%Y-%m-%d %I:%M %p")


def main() -> int:
    # High DPI scaling is enabled by default in PyQt6
    app = QtWidgets.QApplication(sys.argv)
    window = WeatherWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

