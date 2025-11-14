"""
Networking utilities for fetching weather information from the Open-Meteo API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


class WeatherAPIError(RuntimeError):
    """Raised when the weather API returns an error or malformed response."""


@dataclass(slots=True)
class Location:
    """Represents a geographic location."""

    name: str
    latitude: float
    longitude: float
    country: Optional[str] = None
    admin1: Optional[str] = None

    @property
    def display_name(self) -> str:
        parts: List[str] = [self.name]
        if self.admin1:
            parts.append(self.admin1)
        if self.country:
            parts.append(self.country)
        return ", ".join(parts)


@dataclass(slots=True)
class CurrentWeather:
    temperature: float
    wind_speed: float
    wind_direction: Optional[int]
    weather_code: int
    apparent_temperature: Optional[float]
    precipitation: Optional[float]
    relative_humidity: Optional[int]
    time: str


@dataclass(slots=True)
class HourlyWeatherPoint:
    time: str
    temperature: float
    precipitation_probability: Optional[int]
    weather_code: int


@dataclass(slots=True)
class DailyWeatherPoint:
    date: str
    temp_max: float
    temp_min: float
    sunrise: Optional[str]
    sunset: Optional[str]
    weather_code: int


@dataclass(slots=True)
class WeatherForecast:
    location: Location
    current: CurrentWeather
    hourly: List[HourlyWeatherPoint]
    daily: List[DailyWeatherPoint]
    units_label: str


class WeatherClient:
    """Client wrapping the Open-Meteo forecast and geocoding APIs."""

    FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
    GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
    GEOLOCATION_URL = "https://ipapi.co/json"

    def __init__(self, session: Optional[requests.Session] = None) -> None:
        self._session = session or requests.Session()

    def geocode(self, query: str, *, count: int = 1) -> Location:
        payload = {"name": query, "count": count, "language": "en", "format": "json"}
        response = self._session.get(self.GEOCODE_URL, params=payload, timeout=10)
        data = self._check_response(response)
        results = data.get("results")
        if not results:
            raise WeatherAPIError(f"No results found for location: {query}")

        first = results[0]
        latitude = first.get("latitude")
        longitude = first.get("longitude")
        name = first.get("name")

        if latitude is None or longitude is None or name is None:
            raise WeatherAPIError(f"Incomplete geocoding data for: {query}")

        return Location(
            name=name,
            latitude=float(latitude),
            longitude=float(longitude),
            country=first.get("country"),
            admin1=first.get("admin1"),
        )

    def geolocate(self) -> Location:
        response = self._session.get(self.GEOLOCATION_URL, timeout=10)
        data = self._check_response(response)
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        city = data.get("city")
        region = data.get("region")
        country = data.get("country_name") or data.get("country")

        if latitude is None or longitude is None:
            raise WeatherAPIError("Unable to determine your current location.")

        name = city or region or country or "Current Location"
        return Location(
            name=name,
            latitude=float(latitude),
            longitude=float(longitude),
            admin1=region,
            country=country,
        )

    def fetch_forecast(
        self,
        location: Location,
        *,
        units: str = "metric",
        hourly_limit: int = 12,
        daily_limit: int = 7,
    ) -> WeatherForecast:
        temperature_unit, wind_speed_unit, precipitation_unit = self._unit_params(units)

        params: Dict[str, Any] = {
            "latitude": location.latitude,
            "longitude": location.longitude,
            "current": [
                "temperature_2m",
                "apparent_temperature",
                "wind_speed_10m",
                "wind_direction_10m",
                "precipitation",
                "relative_humidity_2m",
                "weather_code",
            ],
            "hourly": [
                "temperature_2m",
                "precipitation_probability",
                "weather_code",
            ],
            "daily": [
                "weather_code",
                "temperature_2m_max",
                "temperature_2m_min",
                "sunrise",
                "sunset",
            ],
            "timezone": "auto",
            "forecast_days": max(daily_limit, 7),
            "temperature_unit": temperature_unit,
            "windspeed_unit": wind_speed_unit,
            "precipitation_unit": precipitation_unit,
        }

        response = self._session.get(self.FORECAST_URL, params=params, timeout=10)
        data = self._check_response(response)

        current = self._parse_current(data, units)
        hourly = self._parse_hourly(data, hourly_limit)
        daily = self._parse_daily(data, daily_limit)

        return WeatherForecast(
            location=location,
            current=current,
            hourly=hourly,
            daily=daily,
            units_label="°F" if units == "imperial" else "°C",
        )

    @staticmethod
    def _check_response(response: requests.Response) -> Dict[str, Any]:
        try:
            response.raise_for_status()
        except requests.HTTPError as err:
            raise WeatherAPIError(f"API returned {response.status_code}: {response.text}") from err

        try:
            return response.json()
        except ValueError as err:
            raise WeatherAPIError("Received invalid JSON response.") from err

    @staticmethod
    def _unit_params(units: str) -> Tuple[str, str, str]:
        if units == "imperial":
            return "fahrenheit", "mph", "inch"
        return "celsius", "kmh", "mm"

    @staticmethod
    def _parse_current(data: Dict[str, Any], units: str) -> CurrentWeather:
        current = data.get("current")
        if not current:
            raise WeatherAPIError("Current weather data missing from response.")

        return CurrentWeather(
            temperature=float(current.get("temperature_2m")),
            wind_speed=float(current.get("wind_speed_10m")),
            wind_direction=current.get("wind_direction_10m"),
            weather_code=int(current.get("weather_code")),
            apparent_temperature=_safe_float(current.get("apparent_temperature")),
            precipitation=_safe_float(current.get("precipitation")),
            relative_humidity=_safe_int(current.get("relative_humidity_2m")),
            time=current.get("time"),
        )

    @staticmethod
    def _parse_hourly(data: Dict[str, Any], limit: int) -> List[HourlyWeatherPoint]:
        hourly = data.get("hourly")
        if not hourly:
            raise WeatherAPIError("Hourly weather data missing from response.")

        time_values: List[str] = hourly.get("time", [])
        temperatures = hourly.get("temperature_2m", [])
        probabilities = hourly.get("precipitation_probability", [])
        weather_codes = hourly.get("weather_code", [])

        items: List[HourlyWeatherPoint] = []
        for idx, time_value in enumerate(time_values[:limit]):
            temp = temperatures[idx] if idx < len(temperatures) else None
            prob = probabilities[idx] if idx < len(probabilities) else None
            code = weather_codes[idx] if idx < len(weather_codes) else None
            if temp is None or code is None:
                continue
            items.append(
                HourlyWeatherPoint(
                    time=time_value,
                    temperature=float(temp),
                    precipitation_probability=_safe_int(prob),
                    weather_code=int(code),
                )
            )
        return items

    @staticmethod
    def _parse_daily(data: Dict[str, Any], limit: int) -> List[DailyWeatherPoint]:
        daily = data.get("daily")
        if not daily:
            raise WeatherAPIError("Daily weather data missing from response.")

        times = daily.get("time", [])
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        sunrises = daily.get("sunrise", [])
        sunsets = daily.get("sunset", [])
        weather_codes = daily.get("weather_code", [])

        days: List[DailyWeatherPoint] = []
        for idx, day in enumerate(times[:limit]):
            max_temp = max_temps[idx] if idx < len(max_temps) else None
            min_temp = min_temps[idx] if idx < len(min_temps) else None
            code = weather_codes[idx] if idx < len(weather_codes) else None
            if max_temp is None or min_temp is None or code is None:
                continue
            days.append(
                DailyWeatherPoint(
                    date=day,
                    temp_max=float(max_temp),
                    temp_min=float(min_temp),
                    sunrise=sunrises[idx] if idx < len(sunrises) else None,
                    sunset=sunsets[idx] if idx < len(sunsets) else None,
                    weather_code=int(code),
                )
            )
        return days


def _safe_float(value: Any) -> Optional[float]:
    try:
        return None if value is None else float(value)
    except (ValueError, TypeError):
        return None


def _safe_int(value: Any) -> Optional[int]:
    try:
        return None if value is None else int(value)
    except (ValueError, TypeError):
        return None

