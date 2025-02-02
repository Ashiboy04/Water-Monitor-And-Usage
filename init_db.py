import os
import sqlite3
from datetime import datetime, timedelta
import random
import math
import pytz
import logging

# Constants
TANK_HEIGHT = 100  # cm
MIN_DISTANCE = 9   # cm - minimum distance from sensor to water
MAX_DISTANCE = 100  # cm - maximum valid distance reading
LITERS_PER_CM = 16  # Liters per cm of height
USER_LOGIN = 'Ashiboy04'
INITIAL_DATE = datetime(2025, 1, 25, 5, 29, 43, tzinfo=pytz.UTC)  # Specified UTC time
DATABASE_PATH = 'data/water_levels.db'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def create_data_directory():
    """Create data directory if it doesn't exist"""
    try:
        os.makedirs('data', exist_ok=True)
        logger.info("Data directory checked/created successfully")
    except Exception as e:
        logger.error(f"Error creating data directory: {e}")
        raise

def create_tables(cursor):
    """Create necessary database tables"""
    try:
        # Drop existing tables
        cursor.execute('DROP TABLE IF EXISTS water_levels')
        cursor.execute('DROP TABLE IF EXISTS settings')

        # Create water_levels table
        cursor.execute('''
        CREATE TABLE water_levels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp DATETIME NOT NULL,
            distance FLOAT NOT NULL,
            water_level FLOAT NOT NULL,
            water_volume FLOAT NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'valid'
        )
        ''')

        # Create settings table
        cursor.execute('''
        CREATE TABLE settings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id VARCHAR(50) UNIQUE NOT NULL,
            critical_threshold INTEGER DEFAULT 20,
            warning_threshold INTEGER DEFAULT 40,
            theme VARCHAR(20) DEFAULT 'light',
            show_weather BOOLEAN DEFAULT 1,
            show_predictions BOOLEAN DEFAULT 1,
            last_update DATETIME
        )
        ''')
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        raise

def insert_default_settings(cursor):
    """Insert default settings for the user"""
    try:
        cursor.execute('''
        INSERT INTO settings (
            user_id, 
            critical_threshold, 
            warning_threshold, 
            theme, 
            show_weather, 
            show_predictions,
            last_update
        ) VALUES (?, 20, 40, 'light', 1, 1, ?)
        ''', (USER_LOGIN, INITIAL_DATE.strftime('%Y-%m-%d %H:%M:%S')))
        logger.info(f"Default settings inserted for user: {USER_LOGIN}")
    except Exception as e:
        logger.error(f"Error inserting default settings: {e}")
        raise

def generate_sample_data(cursor):
    """Generate sample water level data with very random values"""
    try:
        start_date = INITIAL_DATE - timedelta(days=150)  # 5 months of data
        current_time = start_date
        end_time = INITIAL_DATE

        data_points = []
        usable_height = MAX_DISTANCE - MIN_DISTANCE
        
        while current_time <= end_time:
            # Generate very random water level data
            distance = random.uniform(MIN_DISTANCE, MAX_DISTANCE)
            
            # Calculate water level and volume correctly
            water_height = MAX_DISTANCE - distance
            water_level = ((water_height - MIN_DISTANCE) / usable_height) * 100
            water_volume = water_height * LITERS_PER_CM

            data_points.append((
                current_time.strftime('%Y-%m-%d %H:%M:%S'),
                round(distance, 2),
                round(max(0, min(100, water_level)), 2),
                round(max(0, water_volume), 2),
                'valid'
            ))
            
            current_time += timedelta(hours=1)

        cursor.executemany('''
        INSERT INTO water_levels (timestamp, distance, water_level, water_volume, status)
        VALUES (?, ?, ?, ?, ?)
        ''', data_points)

        logger.info(f"Generated {len(data_points)} sample data points with very random values")
    except Exception as e:
        logger.error(f"Error generating sample data: {e}")
        raise

def init_db():
    """Initialize the database with tables and sample data"""
    try:
        # Create data directory
        create_data_directory()

        # Connect to SQLite database
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute('PRAGMA foreign_keys = ON')

        # Create tables
        create_tables(cursor)

        # Insert default settings
        insert_default_settings(cursor)

        # Generate sample data
        generate_sample_data(cursor)

        # Commit changes
        conn.commit()
        logger.info("Database initialization completed successfully")

        # Verify data
        cursor.execute('SELECT COUNT(*) FROM water_levels')
        data_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM settings')
        settings_count = cursor.fetchone()[0]

        logger.info(f"Verification: {data_count} water level readings, {settings_count} settings records")

        return True

    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        return False

    finally:
        if 'conn' in locals():
            conn.close()
            logger.info("Database connection closed")

def verify_database():
    """Verify database integrity and data"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        logger.info(f"Found tables: {[table[0] for table in tables]}")

        # Check water_levels data
        cursor.execute('SELECT COUNT(*), MIN(timestamp), MAX(timestamp) FROM water_levels')
        count, min_date, max_date = cursor.fetchone()
        logger.info(f"Water levels: {count} records from {min_date} to {max_date}")

        # Check settings
        cursor.execute('SELECT * FROM settings')
        settings = cursor.fetchall()
        logger.info(f"Settings records: {len(settings)}")

        return True

    except Exception as e:
        logger.error(f"Database verification failed: {e}")
        return False

    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == '__main__':
    logger.info("Starting database initialization...")
    logger.info(f"Initial date: {INITIAL_DATE}")
    logger.info(f"User login: {USER_LOGIN}")
    
    if init_db():
        if verify_database():
            logger.info("Database initialized and verified successfully!")
            print("Database initialized and verified successfully!")
        else:
            logger.error("Database verification failed!")
            print("Database verification failed!")
    else:
        logger.error("Database initialization failed!")
        print("Database initialization failed!")