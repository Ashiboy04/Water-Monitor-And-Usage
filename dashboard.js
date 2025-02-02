// Global Variables
const USER_LOGIN = 'Ashiboy04';
const UPDATE_INTERVAL = 5000; // 5 seconds
const INITIAL_DATE = '2025-01-25 05:27:37'; // Starting UTC time

const CHART_COLORS = {
    blue: 'rgba(0, 123, 255, 0.5)',
    green: 'rgba(40, 167, 69, 0.5)',
    yellow: 'rgba(255, 193, 7, 0.5)',
    red: 'rgba(220, 53, 69, 0.5)',
};

let charts = {};
let lastUpdate = new Date(INITIAL_DATE);
let chartUpdateTimer = null;
let lastDataUpdate = new Date();
let selectedTimeRange = 24; // Default 24 hours
let alertHistory = new Set(); // Store alert hashes to prevent duplicates

// Utility Functions
function formatUTCDateTime(date) {
    return date.toISOString().slice(0, 19).replace('T', ' ');
}

// Update clock for IST
function updateClock() {
    const now = new Date();
    const istOptions = { 
        year: 'numeric', month: '2-digit', day: '2-digit',
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false, timeZone: 'Asia/Kolkata'
    };
    const formattedTime = now.toLocaleString('en-US', istOptions).replace(',', '');
    document.getElementById('currentTime').textContent = formattedTime;
    document.getElementById('footerTime').textContent = formattedTime;
}

// API Functions
async function fetchWaterLevel() {
    try {
        const response = await fetch('/api/data?hours=24');
        if (!response.ok) throw new Error(`Failed to fetch water level data: ${response.statusText}`);
        const data = await response.json();
        console.log('Fetched water level data:', data);
        
        if (data.success && data.data && data.data.length > 0) {
            const latestReading = data.data[data.data.length - 1];
            console.log('Latest reading:', latestReading);
            return latestReading;
        }
        console.warn('No water level data available');
        return null;
    } catch (error) {
        console.error('Error fetching water level:', error);
        showAlert('error', `Failed to fetch water level data: ${error.message}`);
        return null;
    }
}

async function fetchWeatherData() {
    const apiKey = 'bbe9d41a08718ad8acf3d88f7dd1ddf1';
    const location = 'Chikitigarh';
    const url = `https://api.openweathermap.org/data/2.5/weather?q=${location}&appid=${apiKey}&units=metric`;

    try {
        const response = await fetch(url);
        if (!response.ok) throw new Error(`Failed to fetch weather data: ${response.statusText}`);
        const data = await response.json();
        return {
            location: location,
            temperature: data.main.temp,
            feels_like: data.main.feels_like,
            humidity: data.main.humidity,
            pressure: data.main.pressure,
            wind_speed: data.wind.speed,
            description: data.weather[0].description,
            icon: data.weather[0].icon,
            sunrise: new Date(data.sys.sunrise * 1000).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' }),
            sunset: new Date(data.sys.sunset * 1000).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kolkata' })
        };
    } catch (error) {
        console.error('Error fetching weather:', error);
        showAlert('error', `Failed to fetch weather data: ${error.message}`);
        displayWeatherError('Failed to fetch weather data');
        return null;
    }
}

function displayWeatherError(message) {
    const weatherContent = document.getElementById('weatherContent');
    weatherContent.innerHTML = `
        <div class="weather-error">
            <i class="fas fa-exclamation-triangle"></i>
            <p>${message}</p>
        </div>
    `;
}

async function fetchHistoricalData(hours = selectedTimeRange) {
    try {
        const response = await fetch(`/api/data?hours=${hours}`);
        if (!response.ok) throw new Error(`Failed to fetch historical data: ${response.statusText}`);
        return await response.json();
    } catch (error) {
        console.error('Error fetching historical data:', error);
        showAlert('error', `Failed to fetch historical data: ${error.message}`);
        return null;
    }
}

async function fetchWeeklyStats() {
    try {
        const response = await fetch('/api/stats/weekly');
        if (!response.ok) throw new Error(`Failed to fetch weekly stats: ${response.statusText}`);
        return await response.json();
    } catch (error) {
        console.error('Error fetching weekly stats:', error);
        showAlert('error', `Failed to fetch weekly statistics: ${error.message}`);
        return null;
    }
}

async function eraseData() {
    const password = prompt('Enter passcode to erase data:');
    if (!password) return;

    if (password !== 'AS95as95@#') {
        showAlert('error', 'Invalid passcode');
        return;
    }

    try {
        const response = await fetch('/api/data/erase', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ password: password })
        });
        if (!response.ok) throw new Error('Failed to erase data');
        const result = await response.json();
        if (result.success) {
            showAlert('success', 'Data erased successfully');
            clearDashboardData();
        } else {
            showAlert('error', result.message);
        }
    } catch (error) {
        console.error('Error erasing data:', error);
        showAlert('error', 'Failed to erase data');
    }
}

function clearDashboardData() {
    document.getElementById('waterFill').style.height = '0%';
    document.getElementById('waterLevelValue').textContent = '--%';
    document.getElementById('waterVolume').textContent = '-- L';
    document.getElementById('lastUpdate').textContent = '--:--:--';
    document.getElementById('waterLevelStatus').className = 'status-indicator';

    document.getElementById('dailyUsage').textContent = 'No data';
    document.getElementById('weeklyAvg').textContent = 'No data';
    document.getElementById('lastRefill').textContent = 'No data';
    document.getElementById('peakUsageDay').textContent = 'No data';
    document.getElementById('totalWeeklyUsage').textContent = 'No data';
    document.getElementById('avgDailyUsage').textContent = 'No data';

    if (charts.historical) {
        charts.historical.data.datasets[0].data = [];
        charts.historical.update();
    }
}

function clearLogs() {
    const alertsContainer = document.getElementById('alertsContainer');
    alertsContainer.innerHTML = '';
    alertHistory.clear();
    updateEmptyState();
}

function updateWaterLevel(data) {
    if (!data) {
        console.warn('No water level data provided');
        return;
    }
    
    console.log('Updating water level with:', data);
    
    const waterFill = document.getElementById('waterFill');
    const waterLevelValue = document.getElementById('waterLevelValue');
    const waterVolume = document.getElementById('waterVolume');
    const lastUpdate = document.getElementById('lastUpdate');
    const waterLevelStatus = document.getElementById('waterLevelStatus');
    const lastRefill = document.getElementById('lastRefill');

    if (!waterFill) {
        console.error('Water fill element not found');
        return;
    }

    const previousLevel = parseFloat(waterLevelValue.textContent) || 0;
    const level = parseFloat(data.water_level);

    console.log('Previous level:', previousLevel, 'New level:', level);

    if (level < 0 || level > 100) {
        showAlert('danger', 'Invalid water level detected!');
        waterLevelStatus.className = 'status-indicator status-danger';
        waterLevelValue.textContent = 'Invalid';
        waterVolume.textContent = '-- L';
        lastUpdate.textContent = '--:--:--';
        return;
    }

    waterFill.style.height = `${level}%`;
    waterFill.innerHTML = '';

    const percentLabel = document.createElement('div');
    percentLabel.className = 'water-percent-label';
    percentLabel.textContent = `${level.toFixed(1)}%`;
    waterFill.appendChild(percentLabel);

    if (waterLevelValue) {
        animateValue(waterLevelValue, previousLevel, level, 1000, '%');
    }

    if (waterVolume) {
        const previousVolume = parseFloat(waterVolume.textContent) || 0;
        animateValue(waterVolume, previousVolume, data.water_volume, 1000, ' L');
    }

    if (lastUpdate) {
        lastUpdate.textContent = data.timestamp.split(' ')[1];
        lastUpdate.classList.add('highlight');
        setTimeout(() => lastUpdate.classList.remove('highlight'), 2000);
    }

    if (waterLevelStatus) {
        if (level <= 20) {
            waterLevelStatus.className = 'status-indicator status-danger';
            showAlert('danger', 'Critical water level!');
        } else if (level <= 40) {
            waterLevelStatus.className = 'status-indicator status-warning';
            showAlert('warning', 'Low water level warning');
        } else {
            waterLevelStatus.className = 'status-indicator status-success';
        }
    }

    if (lastRefill && level > previousLevel + 1) {
        const now = new Date();
        const istTime = now.toLocaleString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false,
            timeZone: 'Asia/Kolkata'
        });
        lastRefill.textContent = istTime;
        lastRefill.classList.add('highlight');
        setTimeout(() => lastRefill.classList.remove('highlight'), 2000);
        showAlert('success', `Tank refilled at ${istTime}`);
    }

    console.log('Water level update complete');
}

function updateWeatherDisplay(data) {
    if (!data) {
        console.warn('No weather data to update');
        return;
    }
    
    console.log('Updating weather with:', data);
    
    document.getElementById('weatherLocation').textContent = data.location;
    
    const weatherContent = document.getElementById('weatherContent');
    weatherContent.innerHTML = `
        <div class="weather-main weather-${data.icon}">
            <div class="weather-icon" id="weatherIcon">
                <i class="wi wi-owm-${data.icon}"></i>
            </div>
            <div class="weather-info">
                <div class="temperature" id="temperature">${data.temperature.toFixed(1)}°C</div>
                <div class="description" id="weatherDescription">${data.description}</div>
            </div>
        </div>
        <div class="weather-details">
            <div class="weather-item">
                <i class="wi wi-thermometer"></i>
                <span id="feelsLike">Feels like: ${data.feels_like.toFixed(1)}°C</span>
            </div>
            <div class="weather-item">
                <i class="wi wi-humidity"></i>
                <span id="humidity">Humidity: ${data.humidity}%</span>
            </div>
            <div class="weather-item">
                <i class="wi wi-barometer"></i>
                <span id="pressure">Pressure: ${data.pressure} hPa</span>
            </div>
            <div class="weather-item">
                <i class="wi wi-strong-wind"></i>
                <span id="windSpeed">Wind: ${data.wind_speed.toFixed(1)} m/s</span>
            </div>
        </div>
        <div class="sun-info">
            <div class="sun-item">
                <i class="wi wi-sunrise"></i>
                <span id="sunrise">Sunrise: ${data.sunrise}</span>
            </div>
            <div class="sun-item">
                <i class="wi wi-sunset"></i>
                <span id="sunset">Sunset: ${data.sunset}</span>
            </div>
        </div>
    `;
    
    const weatherStatus = document.getElementById('weatherStatus');
    weatherStatus.className = 'status-indicator status-success';
}

function animateValue(element, start, end, duration, suffix = '') {
    const range = end - start;
    const startTime = performance.now();
    
    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        
        const value = start + (range * progress);
        element.textContent = `${value.toFixed(1)}${suffix}`;
        
        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }
    
    requestAnimationFrame(update);
}

const enhancedChartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
        duration: 2000,
        easing: 'easeInOutQuart'
    },
    elements: {
        point: {
            radius: 4,
            hoverRadius: 8,
            hitRadius: 10,
            borderWidth: 3,
            hoverBorderWidth: 2,
            backgroundColor: 'rgba(255, 255, 255, 0.8)'
        },
        line: {
            tension: 0.4,
            borderWidth: 3,
            borderCapStyle: 'round',
            fill: true
        },
        bar: {
            borderRadius: 10,
            borderSkipped: false,
            maxBarThickness: 40
        }
    },
    plugins: {
        legend: {
            labels: {
                font: {
                    family: "'Roboto', sans-serif",
                    size: 14,
                    weight: '500'
                },
                padding: 20,
                usePointStyle: true,
                pointStyle: 'circle'
            }
        },
        tooltip: {
            backgroundColor: 'rgba(255, 255, 255, 0.9)',
            titleColor: '#000',
            bodyColor: '#000',
            bodyFont: {
                family: "'Roboto', sans-serif",
                size: 13
            },
            padding: 12,
            cornerRadius: 8,
            borderColor: 'rgba(0, 0, 0, 0.1)',
            borderWidth: 1,
            displayColors: true,
            animation: {
                duration: 150
            },
            callbacks: {
                label: function(context) {
                    return ` ${context.parsed.y.toFixed(1)}${context.dataset.units || ''}`;
                }
            }
        }
    },
    interaction: {
        mode: 'index',
        intersect: false
    },
    scales: {
        x: {
            type: 'time',
            time: {
                unit: 'hour',
                displayFormats: {
                    hour: 'MMM D, HH:mm'
                }
            },
            title: {
                display: true,
                text: 'Time'
            },
            ticks: {
                maxRotation: 0,
                autoSkip: true,
                maxTicksLimit: 6
            }
        },
        y: {
            beginAtZero: true,
            max: 100,
            title: {
                display: true,
                text: 'Water Level (%)'
            }
        }
    }
};

function initializeCharts() {
    if (charts.historical) charts.historical.destroy();

    const historicalChartElement = document.getElementById('historicalChart');
    if (!historicalChartElement) {
        console.error('historicalChart element not found');
        return;
    }

    charts.historical = new Chart(historicalChartElement.getContext('2d'), {
        type: 'line',
        data: {
            datasets: [{
                label: 'Water Level',
                data: [],
                borderColor: '#2196F3',
                backgroundColor: 'rgba(33, 150, 243, 0.2)',
                fill: true,
                tension: 0.4,
                units: '%'
            }]
        },
        options: enhancedChartOptions
    });
}

function updateHistoricalChart(data) {
    if (!data?.data || !charts.historical) return;

    const chartData = data.data
        .map(item => ({
            x: new Date(item.timestamp),
            y: parseFloat(item.water_level)
        }))
        .sort((a, b) => a.x - b.x);

    charts.historical.data.datasets[0].data = chartData;
    charts.historical.update('none');
}

function showAlert(type, message) {
    const alertHash = `${type}-${message}`;
    if (alertHistory.has(alertHash)) return;
    
    alertHistory.add(alertHash);
    const alertsContainer = document.getElementById('alertsContainer');
    
    const now = new Date();
    const istTime = now.toLocaleString('en-US', {
        hour: '2-digit', minute: '2-digit', second: '2-digit',
        hour12: false, timeZone: 'Asia/Kolkata'
    });

    const icon = {
        success: 'check-circle',
        warning: 'exclamation-triangle',
        danger: 'exclamation-circle',
        info: 'info-circle'
    }[type] || 'info-circle';

    const alert = document.createElement('div');
    alert.className = `alert alert-${type} fade-in`;
    alert.innerHTML = `
        <div class="alert-content">
            <div class="alert-icon">
                <i class="fas fa-${icon}"></i>
            </div>
            <div class="alert-message">${message}</div>
            <div class="alert-time">${istTime}</div>
        </div>
    `;

    if (alertsContainer.firstChild) {
        alertsContainer.insertBefore(alert, alertsContainer.firstChild);
    } else {
        alertsContainer.appendChild(alert);
    }

    const maxAlerts = 50;
    const alerts = alertsContainer.getElementsByClassName('alert');
    if (alerts.length > maxAlerts) {
        alertsContainer.removeChild(alerts[alerts.length - 1]);
    }

    setTimeout(() => alertHistory.delete(alertHash), 3600000);
    updateEmptyState();
}

function updateEmptyState() {
    const alertsContainer = document.getElementById('alertsContainer');
    const existingEmpty = alertsContainer.querySelector('.alerts-empty');
    
    if (alertsContainer.getElementsByClassName('alert').length === 0) {
        if (!existingEmpty) {
            const emptyState = document.createElement('div');
            emptyState.className = 'alerts-empty';
            emptyState.innerHTML = `
                <i class="fas fa-bell-slash"></i>
                <p>No alerts to display</p>
            `;
            alertsContainer.appendChild(emptyState);
        }
    } else if (existingEmpty) {
        existingEmpty.remove();
    }
}

function initializeAlerts() {
    const alertsContainer = document.getElementById('alertsContainer');
    const alertControls = document.querySelector('.alert-controls');

    const filterContainer = document.createElement('div');
    filterContainer.className = 'alert-filter';
    filterContainer.innerHTML = `
        <select id="logLevel" class="log-level-select">
            <option value="all">All Levels</option>
            <option value="success">Success</option>
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="danger">Error</option>
        </select>
        <div class="search-box">
            <input type="text" id="logSearch" placeholder="Search logs...">
            <i class="fas fa-search"></i>
        </div>
    `;
    alertControls.insertBefore(filterContainer, alertControls.firstChild);

    const buttonGroup = document.createElement('div');
    buttonGroup.className = 'button-group';
    buttonGroup.innerHTML = `
        <button class="btn btn-secondary" id="clearLogs">
            <i class="fas fa-trash"></i> Clear
        </button>
        <button class="btn btn-primary" id="exportLogs">
            <i class="fas fa-download"></i> Export
        </button>
    `;
    alertControls.appendChild(buttonGroup);

    updateEmptyState();

    document.getElementById('logLevel').addEventListener('change', filterLogs);
    document.getElementById('logSearch').addEventListener('input', filterLogs);
    document.getElementById('clearLogs').addEventListener('click', clearLogs);
    document.getElementById('exportLogs').addEventListener('click', exportLogs);

    showAlert('info', 'System initialized successfully');
}

function filterLogs() {
    const level = document.getElementById('logLevel').value;
    const search = document.getElementById('logSearch').value.toLowerCase();
    const alerts = document.querySelectorAll('.alert');

    alerts.forEach(alert => {
        const messageText = alert.querySelector('.alert-message').textContent.toLowerCase();
        const alertType = Array.from(alert.classList)
            .find(cls => cls.startsWith('alert-'))
            ?.replace('alert-', '');

        const matchesLevel = level === 'all' || alertType === level;
        const matchesSearch = search === '' || messageText.includes(search);

        alert.style.display = matchesLevel && matchesSearch ? 'grid' : 'none';
    });
}

function exportLogs() {
    const alerts = Array.from(document.querySelectorAll('.alert'))
        .map(alert => {
            const type = Array.from(alert.classList)
                .find(cls => cls.startsWith('alert-'))
                ?.replace('alert-', '');
            const message = alert.querySelector('.alert-message').textContent;
            const time = alert.querySelector('.alert-time').textContent;
            return `[${time}] ${type.toUpperCase()}: ${message}`;
        })
        .join('\n');

    const blob = new Blob([alerts], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `water-monitoring-logs-${new Date().toISOString().slice(0,10)}.txt`;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

function initializeThemeToggle() {
    const themeToggle = document.getElementById('themeToggle');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
    
    function setTheme(isDark) {
        document.body.classList.add('theme-transition');
        document.body.className = isDark ? 'theme-dark' : 'theme-light';
        localStorage.setItem('theme', isDark ? 'dark' : 'light');
        
        themeToggle.classList.add('theme-toggle-animation');
        setTimeout(() => themeToggle.classList.remove('theme-toggle-animation'), 300);
    }
    
    const savedTheme = localStorage.getItem('theme');
    setTheme(savedTheme ? savedTheme === 'dark' : prefersDark.matches);
    
    themeToggle.addEventListener('click', () => {
        setTheme(document.body.classList.contains('theme-light'));
    });
    
    prefersDark.addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) {
            setTheme(e.matches);
        }
    });
}

async function updateDashboard() {
    try {
        const [waterData, weatherData, historicalData, weeklyData] = await Promise.all([
            fetchWaterLevel(),
            fetchWeatherData(),
            fetchHistoricalData(selectedTimeRange),
            fetchWeeklyStats()
        ]);

        if (waterData) {
            updateWaterLevel(waterData);
            lastDataUpdate = new Date();
        }

        if (weatherData) {
            console.log('Weather data received:', weatherData);
            updateWeatherDisplay(weatherData);
        }

        if (historicalData?.data) {
            updateHistoricalChart(historicalData);
        }

        if (weeklyData?.data) {
            const totalUsage = weeklyData.data.reduce((a, b) => a + b.consumption, 0);
            const avgDaily = totalUsage / (weeklyData.data.length || 1);
            document.getElementById('totalWeeklyUsage').textContent = `${totalUsage.toFixed(1)} L`;
            document.getElementById('avgDailyUsage').textContent = `${avgDaily.toFixed(1)} L`;
            document.getElementById('peakUsageDay').textContent = weeklyData.data.reduce((a, b) => a.consumption > b.consumption ? a : b, { date: 'No data' }).date;
        }

        await updateQuickStats();

    } catch (error) {
        console.error('Error updating dashboard:', error);
        showAlert('error', `Failed to update dashboard data: ${error.message}`);
    }
}

async function updateQuickStats() {
    try {
        const response = await fetch('/api/stats/daily');
        const data = await response.json();
        
        if (data.success) {
            const dailyUsage = document.getElementById('dailyUsage');
            const weeklyAvg = document.getElementById('weeklyAvg');
            const lastRefill = document.getElementById('lastRefill');
            
            if (dailyUsage) animateValue(dailyUsage, parseFloat(dailyUsage.textContent) || 0, data.daily_usage, 1000, ' L');
            if (weeklyAvg) animateValue(weeklyAvg, parseFloat(weeklyAvg.textContent) || 0, data.weekly_avg, 1000, ' L');
            
            if (lastRefill && data.last_refill !== lastRefill.textContent) {
                lastRefill.textContent = data.last_refill;
                lastRefill.classList.add('highlight');
                setTimeout(() => lastRefill.classList.remove('highlight'), 2000);
                
                if (data.last_refill !== "No refill") {
                    showAlert('success', `Tank refilled at ${data.last_refill}`);
                }
            }

            const lastUpdate = document.getElementById('lastUpdate');
            if (lastUpdate && data.last_update !== lastUpdate.textContent) {
                lastUpdate.textContent = data.last_update;
                lastUpdate.classList.add('highlight');
                setTimeout(() => lastUpdate.classList.remove('highlight'), 2000);
            }
        }
    } catch (error) {
        console.error('Error updating quick stats:', error);
    }
}

function initializeTabs() {
    const tabs = document.querySelectorAll('.nav-item');
    const tabPanes = document.querySelectorAll('.tab-pane');

    tabs.forEach(tab => {
        tab.addEventListener('click', (e) => {
            e.preventDefault();
            const targetTab = tab.getAttribute('data-tab');

            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            tabPanes.forEach(pane => {
                pane.classList.toggle('active', pane.id === targetTab);
            });
        });
    });
}

function initializeControls() {
    document.getElementById('eraseDataBtn').addEventListener('click', async () => {
        await eraseData();
    });
}

document.addEventListener('DOMContentLoaded', async () => {
    try {
        console.log('Initializing dashboard...');
        
        initializeCharts();
        initializeThemeToggle();
        initializeTabs();
        updateClock();
        initializeControls();
        initializeAlerts();
        
        await updateDashboard();
        if (chartUpdateTimer) clearInterval(chartUpdateTimer);
        chartUpdateTimer = setInterval(updateDashboard, UPDATE_INTERVAL);
        setInterval(updateClock, 1000);
        
        const timeRange = document.getElementById('timeRange');
        if (timeRange) {
            timeRange.addEventListener('change', async () => {
                selectedTimeRange = parseInt(timeRange.value);
                const data = await fetchHistoricalData(selectedTimeRange);
                if (data) updateHistoricalChart(data);
            });
            selectedTimeRange = parseInt(timeRange.value);
        }

        if ('ontouchstart' in window) {
            document.body.classList.add('touch-device');
            
            document.querySelectorAll('.btn, .nav-item').forEach(button => {
                button.addEventListener('touchend', (e) => {
                    e.preventDefault();
                    e.target.click();
                });
            });
        }

    } catch (error) {
        console.error('Error initializing dashboard:', error);
        showAlert('error', `Failed to initialize dashboard: ${error.message}`);
    }
});

window.addEventListener('orientationchange', () => {
    setTimeout(() => {
        if (charts.historical) charts.historical.resize();
    }, 100);
});

document.getElementById('configForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const configData = Object.fromEntries(formData.entries());
    configData.deep_sleep_enabled = formData.get('deep_sleep_enabled') === 'on';

    try {
        const response = await fetch('/api/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(configData)
        });
        const result = await response.json();
        if (result.success) {
            showAlert('success', 'Configuration saved successfully');
            fetchCurrentConfig();
        } else {
            showAlert('error', 'Failed to save configuration');
        }
    } catch (error) {
        console.error('Error saving configuration:', error);
        showAlert('error', 'Failed to save configuration');
    }
});

document.getElementById('firmwareForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const progressBar = document.getElementById('uploadProgressBar');
    const uploadStatus = document.getElementById('uploadStatus');

    try {
        const response = await fetch('/api/firmware', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        if (result.success) {
            showAlert('success', 'Firmware uploaded successfully');
            fetchCurrentFirmware();
            progressBar.style.width = '100%';
            uploadStatus.innerHTML = '<i class="fas fa-thumbs-up thumbs-up"></i> Upload Done!';
            uploadStatus.style.display = 'block';
        } else {
            showAlert('error', 'Failed to upload firmware');
            progressBar.style.width = '0';
            uploadStatus.style.display = 'none';
        }
    } catch (error) {
        console.error('Error uploading firmware:', error);
        showAlert('error', 'Failed to upload firmware');
        progressBar.style.width = '0';
        uploadStatus.style.display = 'none';
    }
});

async function fetchCurrentFirmware() {
    try {
        const response = await fetch('/api/firmware/latest');
        const firmware = await response.json();
        if (firmware.filename) {
            document.getElementById('currentFirmware').textContent = firmware.filename;
        }
    } catch (error) {
        console.error('Error fetching current firmware:', error);
    }
}

async function fetchCurrentConfig() {
    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        document.getElementById('currentConfig').textContent = JSON.stringify(config, null, 2);

        document.getElementById('wifi_ssid').value = config.wifi_ssid;
        document.getElementById('wifi_password').value = config.wifi_password;
        document.getElementById('sleep_time').value = config.sleep_time;
        document.getElementById('timeout_time').value = config.timeout_time;
        document.getElementById('deep_sleep_enabled').checked = config.deep_sleep_enabled;
        document.getElementById('update_frequency').value = config.update_frequency;

        toggleUpdateFrequency();
    } catch (error) {
        console.error('Error fetching current configuration:', error);
    }
}