## Basic Weather App

An advanced graphical weather dashboard built with PyQt6 that shows current conditions, hourly and daily forecasts, unit conversion, and optional location auto-detection.

### Features

- Search for any city, postal code, or address using Open-Meteo geocoding
- Automatically detect your approximate location via IP lookup
- Detailed current conditions with feels-like temperature, wind, precipitation, and humidity
- 12-hour forecast and 7-day outlook tables
- Switch between Celsius and Fahrenheit units
- Custom drawn weather icons that adapt to the reported conditions
- Robust error handling with clear feedback for the user

### Getting Started

1. **Install dependencies**

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Run the application**

   ```powershell
   python -m weather_app.app
   ```

   Or from inside the `weather_app` directory:

   ```powershell
   python app.py
   ```

3. **Search for weather**
   - Type a location (e.g., `Paris`, `Tokyo`, `10001`) and press Enter or click `Search`.
   - Click `Use Current Location` to detect your location using IP-based geolocation.
   - Change the unit selector to refresh the forecast in Celsius or Fahrenheit.

### Notes

- The app uses the [Open-Meteo Forecast API](https://open-meteo.com/) plus their Geocoding service.
- IP-based auto-detection relies on [ipapi.co](https://ipapi.co/); location accuracy may vary.
- Network calls run on background threads to keep the interface responsive.

### Development

- The GUI code lives in `weather_app/app.py`.
- API integration and data models are in `weather_app/weather_client.py`.
- Icon generation is handled by `weather_app/icon_factory.py`.
- Run `python -m weather_app.app` while developing to test live changes.

Feel free to extend the app with additional visualizations, caching, or platform-specific integrations such as GPS hardware.

