from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import os
import pytz
import logging
import math
import json
from logging.handlers import RotatingFileHandler
from flask_cors import CORS  # Add this import
from dotenv import load_dotenv
import requests
from werkzeug.utils import secure_filename
import hashlib  # Add this import

# Constants
TANK_HEIGHT = 100  # cm - maximum distance
MIN_DISTANCE = 9   # cm - minimum distance from sensor to water
MAX_DISTANCE = 100  # cm - maximum valid distance reading
LITERS_PER_CM = 16  # Liters per cm of height
USER_LOGIN = 'Ashiboy04'
INITIAL_DATE = datetime(2025, 1, 25, 5, 37, 33, tzinfo=pytz.UTC)

# Create data and log directories if they don't exist
os.makedirs('data', exist_ok=True)

# Update log directory handling
LOG_DIR = os.path.join(os.path.expanduser('~'), 'water_monitoring', 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s UTC - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        RotatingFileHandler(
            os.path.join(LOG_DIR, 'water_monitor.log'),
            maxBytes=10485760,  # 10MB
            backupCount=5
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS

# Add this near the top with other route handlers
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

# Database Configuration
db_path = os.path.join(os.getcwd(), 'data', 'water_levels.db')
app.config.update(
    SECRET_KEY='dev-key-please-change-in-production',
    SQLALCHEMY_DATABASE_URI=f'sqlite:///{db_path}',
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SQLALCHEMY_ECHO=True
)

# Initialize SQLAlchemy
db = SQLAlchemy(app)

# Load environment variables
load_dotenv()
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
LOCATION_NAME = os.getenv('LOCATION_NAME', 'Chikitigarh')
LOCATION_LAT = float(os.getenv('LOCATION_LAT', '20.2983'))
LOCATION_LON = float(os.getenv('LOCATION_LON', '86.7215'))
OPENWEATHER_API_KEY = os.getenv('OPENWEATHER_API_KEY')
WEATHER_API_URL = "https://api.openweathermap.org/data/2.5/weather"

# Configuration file path
CONFIG_FILE_PATH = os.path.join(os.getcwd(), 'data', 'config.json')
FIRMWARE_DIR = os.path.join(os.getcwd(), 'data', 'firmware')
os.makedirs(FIRMWARE_DIR, exist_ok=True)

# Load default configuration
default_config = {
    "wifi_ssid": "",
    "wifi_password": "",
    "fast_data": False,
    "version": "1.0.0"
}

# Ensure config file exists
if not os.path.exists(CONFIG_FILE_PATH):
    with open(CONFIG_FILE_PATH, 'w') as f:
        json.dump(default_config, f)

# Models
class WaterLevel(db.Model):
    __tablename__ = 'water_levels'
    
    # Add index for timestamp
    __table_args__ = (
        db.Index('idx_timestamp', 'timestamp'),
    )
    
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    distance = db.Column(db.Float, nullable=False)
    water_level = db.Column(db.Float, nullable=False)
    water_volume = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='valid')

    def to_dict(self):
        # Convert UTC to IST for display
        ist_time = self.timestamp.replace(tzinfo=pytz.UTC).astimezone(pytz.timezone('Asia/Kolkata'))
        return {
            'id': self.id,
            'timestamp': ist_time.strftime('%Y-%m-%d %H:%M:%S'),
            'distance': round(self.distance, 2),
            'water_level': round(self.water_level, 2),
            'water_volume': round(self.water_volume, 2),
            'status': self.status
        }

class Settings(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), unique=True, nullable=False)
    critical_threshold = db.Column(db.Integer, default=20)
    warning_threshold = db.Column(db.Integer, default=40)
    theme = db.Column(db.String(20), default='light')
    show_weather = db.Column(db.Boolean, default=True)
    show_predictions = db.Column(db.Boolean, default=True)
    last_update = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'critical_threshold': self.critical_threshold,
            'warning_threshold': self.warning_threshold,
            'theme': self.theme,
            'show_weather': self.show_weather,
            'show_predictions': self.show_predictions,
            'last_update': self.last_update.strftime('%Y-%m-%d %H:%M:%S')
        }

# Routes
@app.route('/')
def index():
    try:
        settings = Settings.query.filter_by(user_id=USER_LOGIN).first()
        if not settings:
            settings = Settings(user_id=USER_LOGIN)
            db.session.add(settings)
            db.session.commit()
        
        return render_template('index.html',
                             user_login=USER_LOGIN,
                             current_time=INITIAL_DATE.strftime('%Y-%m-%d %H:%M:%S'),
                             settings=settings.to_dict())
    except Exception as e:
        logger.error(f"Error rendering index: {e}")
        return jsonify({'error': 'Internal server error'}), 500

def calculate_data_checksum(data):
    """Calculate the SHA256 checksum of the data."""
    sha256 = hashlib.sha256()
    sha256.update(json.dumps(data, sort_keys=True).encode('utf-8'))
    return sha256.hexdigest()

@app.route('/api/data')
def get_data():
    try:
        hours = request.args.get('hours', 24, type=int)
        end_time = datetime.now(pytz.UTC)
        start_time = end_time - timedelta(hours=hours)
        
        logger.info(f"Fetching data for last {hours} hours from {start_time}")

        readings = WaterLevel.query.filter(
            WaterLevel.timestamp >= start_time,
            WaterLevel.timestamp <= end_time
        ).order_by(WaterLevel.timestamp.asc()).all()  # Changed to ascending order

        logger.info(f"Found {len(readings)} readings")

        response_data = [reading.to_dict() for reading in readings]
        checksum = calculate_data_checksum(response_data)
        logger.info(f"Returning {len(response_data)} readings with checksum {checksum}")
        return jsonify({
            'success': True,
            'data': response_data,
            'checksum': checksum
        })

    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return jsonify({'error': str(e)}), 500

# Update the weekly stats route for more accurate data
@app.route('/api/stats/weekly')
def get_weekly_stats():
    try:
        end_date = datetime.now(pytz.UTC)
        start_date = end_date - timedelta(days=7)

        daily_stats = []
        current_date = start_date

        while current_date <= end_date:
            next_date = current_date + timedelta(days=1)
            
            # Get all readings for the day
            readings = WaterLevel.query.filter(
                WaterLevel.timestamp >= current_date,
                WaterLevel.timestamp < next_date
            ).order_by(WaterLevel.timestamp.asc()).all()

            if readings:
                # Calculate more accurate daily statistics
                day_readings = []
                last_reading = None
                total_consumption = 0

                for reading in readings:
                    if last_reading:
                        # Calculate consumption between readings
                        if reading.water_level < last_reading.water_level:
                            consumption = (last_reading.water_level - reading.water_level) * LITERS_PER_CM
                            total_consumption += consumption
                    last_reading = reading
                    day_readings.append(reading.water_level)

                daily_stats.append({
                    'date': current_date.strftime('%Y-%m-%d'),
                    'avg_level': round(sum(day_readings) / len(day_readings), 2),
                    'max_level': round(max(day_readings), 2),
                    'min_level': round(min(day_readings), 2),
                    'consumption': round(total_consumption, 2),
                    'readings_count': len(readings)
                })

            current_date = next_date

        return jsonify({
            'success': True,
            'data': daily_stats
        })

    except Exception as e:
        logger.error(f"Error fetching weekly stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/api/settings', methods=['GET', 'POST'])
def handle_settings():
    try:
        if request.method == 'GET':
            settings = Settings.query.filter_by(user_id=USER_LOGIN).first()
            if not settings:
                return jsonify({'error': 'Settings not found'}), 404
            return jsonify(settings.to_dict())

        elif request.method == 'POST':
            data = request.get_json()
            settings = Settings.query.filter_by(user_id=USER_LOGIN).first()
            
            if not settings:
                settings = Settings(user_id=USER_LOGIN)
                db.session.add(settings)

            # Update settings
            for key, value in data.items():
                if hasattr(settings, key):
                    setattr(settings, key, value)
            
            settings.last_update = datetime.now(pytz.UTC)
            db.session.commit()

            return jsonify({
                'success': True,
                'message': 'Settings updated successfully',
                'data': settings.to_dict()
            })

    except Exception as e:
        logger.error(f"Error handling settings: {e}")
        db.session.rollback()
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/update', methods=['POST'])
def update_water_level():
    try:
        data = request.get_json() if request.is_json else request.form
        if not data or 'distance' not in data:
            return jsonify({'error': 'Missing distance data'}), 400

        try:
            distance = float(data['distance'])
        except ValueError:
            return jsonify({'error': 'Distance must be a number'}), 400

        if not (MIN_DISTANCE <= distance <= MAX_DISTANCE):
            logger.warning(f"Invalid distance value received: {distance}")
            return jsonify({
                'error': f'Invalid distance value: {distance}. Must be between {MIN_DISTANCE} and {MAX_DISTANCE} cm'
            }), 400

        # Improved water level calculation
        usable_height = MAX_DISTANCE - MIN_DISTANCE
        water_level = ((MAX_DISTANCE - distance) / usable_height) * 100
        water_level = max(0, min(100, water_level))  # Clamp between 0 and 100
        
        # Calculate volume based on actual water height
        water_height = MAX_DISTANCE - distance
        water_volume = max(0, water_height * LITERS_PER_CM)

        # Use UTC for timestamp
        current_time = datetime.now(pytz.UTC)
        
        new_reading = WaterLevel(
            timestamp=current_time,
            distance=round(distance, 2),
            water_level=round(water_level, 2),
            water_volume=round(water_volume, 2),
            status='valid'
        )

        db.session.add(new_reading)
        db.session.commit()

        return jsonify({
            'success': True,
            'data': new_reading.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating water level: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health')
def health_check():
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        db_status = 'connected'
        
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'),
            'database': db_status,
            'user': USER_LOGIN,
            'version': '1.0.0'
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')
        }), 500

@app.route('/api/weather')
def get_weather():
    try:
        if not OPENWEATHER_API_KEY:
            logger.error("OpenWeather API key not configured")
            return jsonify({'error': "Weather API key not configured"}), 500
            
        params = {
            'lat': LOCATION_LAT,
            'lon': LOCATION_LON,
            'appid': OPENWEATHER_API_KEY,
            'units': 'metric'  # For Celsius
        }
        
        logger.info(f"Fetching weather data with params: {params}")
        
        try:
            response = requests.get(WEATHER_API_URL, params=params, timeout=5)
            response.raise_for_status()
            weather_data = response.json()
            
            logger.info(f"Raw weather response: {weather_data}")
            
            formatted_weather = {
                'location': LOCATION_NAME,
                'temperature': round(weather_data['main']['temp'], 1),
                'feels_like': round(weather_data['main']['feels_like'], 1),
                'humidity': weather_data['main']['humidity'],
                'pressure': weather_data['main']['pressure'],
                'wind_speed': round(weather_data['wind']['speed'], 1),
                'description': weather_data['weather'][0]['description'].capitalize(),
                'icon': map_weather_icon(weather_data['weather'][0]['icon']),
                'sunrise': datetime.fromtimestamp(weather_data['sys']['sunrise']).strftime('%H:%M'),
                'sunset': datetime.fromtimestamp(weather_data['sys']['sunset']).strftime('%H:%M')
            }
            
            logger.info(f"Formatted weather data: {formatted_weather}")
            return jsonify(formatted_weather)
            
        except requests.RequestException as e:
            logger.error(f"Weather API request failed: {e}")
            # Return simulated data if API fails
            return jsonify({
                'location': LOCATION_NAME,
                'temperature': 30.0,
                'feels_like': 32.0,
                'humidity': 65,
                'pressure': 1013,
                'wind_speed': 3.5,
                'description': 'Partly cloudy',
                'icon': 'day-cloudy',
                'sunrise': '06:00',
                'sunset': '18:00'
            })
            
    except Exception as e:
        logger.error(f"Error in weather route: {e}")
        return jsonify({'error': str(e)}), 500

def map_weather_icon(openweather_icon):
    """Map OpenWeatherMap icons to Weather Icons (wi) classes"""
    icon_map = {
        '01d': 'day-sunny',
        '02d': 'day-cloudy',
        '03d': 'cloud',
        '04d': 'cloudy',
        '09d': 'showers',
        '10d': 'day-rain',
        '11d': 'thunderstorm',
        '13d': 'snow',
        '50d': 'fog',
        '01n': 'night-clear',
        '02n': 'night-cloudy',
        '03n': 'cloud',
        '04n': 'cloudy',
        '09n': 'showers',
        '10n': 'night-rain',
        '11n': 'thunderstorm',
        '13n': 'snow',
        '50n': 'fog'
    }
    return icon_map.get(openweather_icon, 'na')

# Add these debug routes
@app.route('/debug/data')
def debug_data():
    try:
        readings = WaterLevel.query.order_by(WaterLevel.timestamp.desc()).limit(5).all()
        return jsonify({
            'success': True,
            'count': len(readings),
            'data': [reading.to_dict() for reading in readings]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Update the erase_data route to check password and clear all data
@app.route('/api/data/erase', methods=['POST'])
def erase_data():
    try:
        data = request.get_json()
        if not data or data.get('password') != 'AS95as95@#':
            return jsonify({
                'success': False,
                'message': 'Invalid password'
            }), 403

        # Delete all water level readings
        WaterLevel.query.delete()
        db.session.commit()
        
        logger.info("All water level data erased successfully")
        return jsonify({
            'success': True,
            'message': 'All data erased successfully'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error erasing data: {e}")
        return jsonify({'error': 'Failed to erase data'}), 500

# Update the get_daily_stats function to handle accurate data usage calculation
@app.route('/api/stats/daily')
def get_daily_stats():
    try:
        # Get current IST time and start of day
        ist = pytz.timezone('Asia/Kolkata')
        ist_now = datetime.now(ist)
        ist_start_of_day = ist_now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Convert to UTC for database query
        utc_start_of_day = ist_start_of_day.astimezone(pytz.UTC)
        
        # Get today's readings
        readings = WaterLevel.query.filter(
            WaterLevel.timestamp >= utc_start_of_day
        ).order_by(WaterLevel.timestamp.asc()).all()

        # Calculate daily usage from drops in water level
        daily_usage = 0
        last_level = None
        last_refill = "No refill"
        
        for reading in readings:
            current_level = reading.water_level
            
            if last_level is not None:
                # Check for water usage (level decrease)
                if current_level < last_level:
                    usage = (last_level - current_level) * LITERS_PER_CM
                    daily_usage += usage
                # Check for refill (level increase)
                elif current_level > last_level + 1:  # +1 to avoid minor fluctuations
                    ist_time = reading.timestamp.replace(tzinfo=pytz.UTC).astimezone(ist)
                    last_refill = ist_time.strftime('%H:%M')
            
            last_level = current_level

        # Calculate weekly average
        week_ago = utc_start_of_day - timedelta(days=7)
        weekly_usage = []
        
        # Calculate usage for each of the last 7 days
        for day in range(7):
            day_start = week_ago + timedelta(days=day)
            day_end = day_start + timedelta(days=1)
            
            day_readings = WaterLevel.query.filter(
                WaterLevel.timestamp >= day_start,
                WaterLevel.timestamp < day_end
            ).order_by(WaterLevel.timestamp.asc()).all()
            
            day_usage = 0
            last_level = None
            
            for reading in day_readings:
                if last_level is not None and reading.water_level < last_level:
                    day_usage += (last_level - reading.water_level) * LITERS_PER_CM
                last_level = reading.water_level
            
            weekly_usage.append(day_usage)

        # Calculate weekly average
        weekly_avg = sum(weekly_usage) / len(weekly_usage) if weekly_usage else 0

        # Get last update time
        last_update = "No update"
        if readings:
            last_update = readings[-1].timestamp.replace(tzinfo=pytz.UTC).astimezone(ist).strftime('%H:%M')

        return jsonify({
            'success': True,
            'daily_usage': round(daily_usage, 2),
            'weekly_avg': round(weekly_avg, 2),
            'last_refill': last_refill,
            'last_update': last_update
        })

    except Exception as e:
        logger.error(f"Error fetching daily stats: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Add new tracking variables after other constants
last_config_fetch = None
last_firmware_fetch = None

# Replace the config handler
@app.route('/api/config', methods=['GET', 'POST'])
def handle_config():
    global last_config_fetch
    
    if request.method == 'GET':
        try:
            last_config_fetch = datetime.now(pytz.UTC)
            with open(CONFIG_FILE_PATH, 'r') as f:
                config = json.load(f)
            return jsonify({
                'wifi_ssid': config['wifi_ssid'],
                'wifi_password': config['wifi_password'],
                'fast_data': config.get('fast_data', False)
            })
        except Exception as e:
            logger.error(f"Error reading config file: {e}")
            return jsonify({'error': 'Failed to read config file'}), 500

    elif request.method == 'POST':
        try:
            config_data = request.get_json()
            if not config_data.get('wifi_ssid'):
                return jsonify({'error': 'SSID is required'}), 400
            
            config = {
                'wifi_ssid': config_data['wifi_ssid'],
                'wifi_password': config_data.get('wifi_password', ''),
                'fast_data': config_data.get('fast_data', False)
            }
            
            with open(CONFIG_FILE_PATH, 'w') as f:
                json.dump(config, f)
            
            return jsonify({'success': True, 'message': 'Configuration saved'})
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            return jsonify({'error': 'Failed to save config'}), 500

# Replace firmware handlers
@app.route('/api/firmware', methods=['GET', 'POST'])
def handle_firmware():
    global last_firmware_fetch
    
    if request.method == 'GET':
        try:
            firmware_path = os.path.join(FIRMWARE_DIR, 'firmware.bin')
            if not os.path.exists(firmware_path):
                return jsonify({'error': 'No firmware found'}), 404
            
            last_firmware_fetch = datetime.now(pytz.UTC)
            return send_from_directory(FIRMWARE_DIR, 'firmware.bin')
        except Exception as e:
            logger.error(f"Error serving firmware: {e}")
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'POST':
        try:
            if 'firmware' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            file = request.files['firmware']
            if file.filename == '' or not file.filename.endswith('.bin'):
                return jsonify({'error': 'Invalid firmware file'}), 400
            
            firmware_path = os.path.join(FIRMWARE_DIR, 'firmware.bin')
            if os.path.exists(firmware_path):
                os.remove(firmware_path)
            
            file.save(firmware_path)
            
            return jsonify({
                'success': True,
                'message': 'Firmware uploaded successfully',
                'size': os.path.getsize(firmware_path)
            })
        except Exception as e:
            logger.error(f"Error uploading firmware: {e}")
            return jsonify({'error': str(e)}), 500

# Add new endpoint to get fetch timestamps
@app.route('/api/fetch-status')
def get_fetch_status():
    ist = pytz.timezone('Asia/Kolkata')
    
    last_config_time = None
    if last_config_fetch:
        ist_config_time = last_config_fetch.replace(tzinfo=pytz.UTC).astimezone(ist)
        last_config_time = ist_config_time.strftime('%Y-%m-%d %H:%M:%S IST')
    
    last_firmware_time = None
    if last_firmware_fetch:
        ist_firmware_time = last_firmware_fetch.replace(tzinfo=pytz.UTC).astimezone(ist)
        last_firmware_time = ist_firmware_time.strftime('%Y-%m-%d %H:%M:%S IST')
    
    return jsonify({
        'last_config_fetch': last_config_time,
        'last_firmware_fetch': last_firmware_time
    })

@app.route('/api/config/verify', methods=['POST'])
def verify_config():
    try:
        data = request.get_json()
        config_data = data.get('config')

        if not config_data:
            return jsonify({'error': 'Configuration data is required'}), 400

        with open(CONFIG_FILE_PATH, 'r') as f:
            current_config = json.load(f)

        if current_config != config_data:
            return jsonify({'error': 'Configuration verification failed'}), 400

        return jsonify({'success': True, 'message': 'Configuration verified successfully'})
    except Exception as e:
        logger.error(f"Error verifying configuration: {e}")
        return jsonify({'error': 'Failed to verify configuration'}), 500

@app.route('/config')
def config_page():
    try:
        return render_template('config.html', current_time=datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'))
    except Exception as e:
        logger.error(f"Error rendering config page: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/firmware')
def firmware_page():
    try:
        return render_template('firmware.html', current_time=datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S'))
    except Exception as e:
        logger.error(f"Error rendering firmware page: {e}")
        return jsonify({'error': 'Internal server error'}), 500

# Add these after other route handlers
@app.route('/api/config/current')
def get_current_config():
    """Return config in the same format as local server"""
    try:
        with open(CONFIG_FILE_PATH, 'r') as f:
            config = json.load(f)
            response = f"{1 if config.get('fast_data', False) else 0}\n{config.get('wifi_ssid', '')}\n{config.get('wifi_password', '')}"
            return response, 200, {'Content-Type': 'text/plain'}
    except Exception as e:
        logger.error(f"Error reading config: {e}")
        return "0\n\n", 500

@app.route('/api/firmware/status')
def get_firmware_status():
    """Get current firmware status"""
    try:
        firmware_path = os.path.join(FIRMWARE_DIR, 'firmware.bin')
        if os.path.exists(firmware_path):
            size = os.path.getsize(firmware_path)
            modified = datetime.fromtimestamp(os.path.getmtime(firmware_path))
            return jsonify({
                'exists': True,
                'size': size,
                'last_modified': modified.strftime('%Y-%m-%d %H:%M:%S'),
                'filename': 'firmware.bin'
            })
        return jsonify({'exists': False})
    except Exception as e:
        logger.error(f"Error checking firmware status: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/firmware/remove', methods=['POST'])
def remove_firmware():
    """Remove current firmware file"""
    try:
        firmware_path = os.path.join(FIRMWARE_DIR, 'firmware.bin')
        if os.path.exists(firmware_path):
            os.remove(firmware_path)
            return jsonify({'success': True, 'message': 'Firmware removed'})
        return jsonify({'error': 'No firmware found'}), 404
    except Exception as e:
        logger.error(f"Error removing firmware: {e}")
        return jsonify({'error': str(e)}), 500

# Create database tables
with app.app_context():
    try:
        db.create_all()
        settings = Settings.query.filter_by(user_id=USER_LOGIN).first()
        if not settings:
            settings = Settings(
                user_id=USER_LOGIN,
                critical_threshold=20,
                warning_threshold=40,
                theme='light',
                show_weather=True,
                show_predictions=True,
                last_update=INITIAL_DATE
            )
            db.session.add(settings)
            db.session.commit()
        logger.info("Database tables and default settings created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)