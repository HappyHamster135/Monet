// Open-Meteo's ISO times are local to the chosen place, not the computer's zone.
.pragma library

function number(value, suffix) {
    return typeof value === "number" && isFinite(value) ? Math.round(value) + (suffix || "") : "—";
}

function value(series, key, index) {
    return series && Array.isArray(series[key]) ? series[key][index] : null;
}

function localHour(weather, now) {
    const offset = weather && typeof weather.utc_offset_seconds === "number" ? weather.utc_offset_seconds : 0;
    return new Date(now + offset * 1000).toISOString().slice(0, 13) + ":00";
}

function hours(weather, day, now) {
    if (!weather || !weather.hourly || !Array.isArray(weather.hourly.time)) return [];
    const source = weather.hourly;
    const start = localHour(weather, now);
    const result = [];
    for (let i = 0; i < source.time.length; i++) {
        const time = source.time[i];
        if (day ? time.slice(0, 10) !== day : time < start) continue;
        result.push({time: time, temperature: value(source, "temperature_2m", i),
            code: value(source, "weather_code", i), day: value(source, "is_day", i) !== 0,
            rain: value(source, "precipitation_probability", i), wind: value(source, "wind_speed_10m", i)});
        if (!day && result.length === 24) break;
    }
    return result;
}

function days(weather) {
    if (!weather || !weather.daily || !Array.isArray(weather.daily.time)) return [];
    const source = weather.daily;
    return source.time.slice(0, 7).map((time, i) => ({time: time,
        code: value(source, "weather_code", i), high: value(source, "temperature_2m_max", i),
        low: value(source, "temperature_2m_min", i), rain: value(source, "precipitation_probability_max", i),
        sunrise: value(source, "sunrise", i), sunset: value(source, "sunset", i),
        wind: value(source, "wind_speed_10m_max", i)}));
}

function clock(time) { return typeof time === "string" && time.length >= 16 ? time.slice(11, 16) : "—"; }
