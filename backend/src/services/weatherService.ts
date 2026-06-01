import { fetchJson } from './httpClient';

type OpenMeteoResponse = {
  latitude: number;
  longitude: number;
  timezone?: string;
  current?: {
    time?: string;
    temperature_2m?: number;
    relative_humidity_2m?: number;
    apparent_temperature?: number;
    precipitation?: number;
    rain?: number;
    weather_code?: number;
    wind_speed_10m?: number;
  };
  daily?: {
    time?: string[];
    weather_code?: number[];
    temperature_2m_max?: number[];
    temperature_2m_min?: number[];
    precipitation_probability_max?: number[];
  };
};

const weatherDescriptions: Record<number, string> = {
  0: 'Clear sky',
  1: 'Mainly clear',
  2: 'Partly cloudy',
  3: 'Overcast',
  45: 'Fog',
  48: 'Depositing rime fog',
  51: 'Light drizzle',
  53: 'Moderate drizzle',
  55: 'Dense drizzle',
  61: 'Slight rain',
  63: 'Moderate rain',
  65: 'Heavy rain',
  71: 'Slight snow',
  73: 'Moderate snow',
  75: 'Heavy snow',
  80: 'Slight rain showers',
  81: 'Moderate rain showers',
  82: 'Violent rain showers',
  95: 'Thunderstorm',
  96: 'Thunderstorm with slight hail',
  99: 'Thunderstorm with heavy hail',
};

const describeWeather = (code?: number) => {
  if (code === undefined) return 'Unknown';
  return weatherDescriptions[code] || 'Weather condition unavailable';
};

export const getWeather = async (latitude: number, longitude: number) => {
  const params = new URLSearchParams({
    latitude: String(latitude),
    longitude: String(longitude),
    current: [
      'temperature_2m',
      'relative_humidity_2m',
      'apparent_temperature',
      'precipitation',
      'rain',
      'weather_code',
      'wind_speed_10m',
    ].join(','),
    daily: [
      'weather_code',
      'temperature_2m_max',
      'temperature_2m_min',
      'precipitation_probability_max',
    ].join(','),
    forecast_days: '7',
    timezone: 'auto',
  });

  const data = await fetchJson<OpenMeteoResponse>(
    'Open-Meteo',
    `https://api.open-meteo.com/v1/forecast?${params.toString()}`
  );

  return {
    provider: 'Open-Meteo',
    coordinatesUsed: { lat: latitude, lng: longitude },
    timezone: data.timezone,
    current: {
      time: data.current?.time,
      temperatureC: data.current?.temperature_2m,
      feelsLikeC: data.current?.apparent_temperature,
      humidityPercent: data.current?.relative_humidity_2m,
      precipitationMm: data.current?.precipitation,
      rainMm: data.current?.rain,
      windSpeedKmh: data.current?.wind_speed_10m,
      conditionCode: data.current?.weather_code,
      condition: describeWeather(data.current?.weather_code),
    },
    forecast: (data.daily?.time || []).map((date, index) => ({
      date,
      minTempC: data.daily?.temperature_2m_min?.[index],
      maxTempC: data.daily?.temperature_2m_max?.[index],
      precipitationChancePercent: data.daily?.precipitation_probability_max?.[index],
      conditionCode: data.daily?.weather_code?.[index],
      condition: describeWeather(data.daily?.weather_code?.[index]),
    })),
  };
};
