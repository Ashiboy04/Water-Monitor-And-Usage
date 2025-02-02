import os
import sys
import logging
from datetime import datetime
import pytz
from app import app, db
from flask import jsonify

# Constants
USER_LOGIN = 'Ashiboy04'
INITIAL_DATE = datetime(2025, 1, 25, 5, 31, 33, tzinfo=pytz.UTC)  # Specified UTC time
LOG_DIR = os.path.join('logs')  # Changed from absolute path
LOG_FILE = 'water_monitor.log'
DATA_DIR = 'data'

# Fix logging setup
def setup_logging():
    """Configure logging with UTC timestamp"""
    try:
        # Create log directory if it doesn't exist
        os.makedirs(LOG_DIR, exist_ok=True)
        
        # Configure logging format with UTC time
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s UTC - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(os.path.join(LOG_DIR, LOG_FILE)),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        # Set timezone to UTC for logging
        logging.Formatter.converter = lambda *args: datetime.now(pytz.UTC).timetuple()
        
        return logging.getLogger(__name__)
    except Exception as e:
        print(f"Failed to setup logging: {e}")
        sys.exit(1)

# Initialize logger
logger = setup_logging()

def check_system_requirements():
    """Check if all system requirements are met"""
    try:
        # Check Python version
        python_version = sys.version_info
        if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
            logger.error("Python 3.8 or higher is required")
            return False

        # Check data directory
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
            logger.info(f"Created data directory: {DATA_DIR}")

        # Check database file
        db_path = os.path.join(DATA_DIR, 'water_levels.db')
        if not os.path.exists(db_path):
            logger.warning("Database file not found. Please run init_db.py first")
            return False

        return True

    except Exception as e:
        logger.error(f"System requirements check failed: {e}")
        return False

def create_health_check_route():
    """Create health check endpoint"""
    @app.route('/health')
    def health_check():
        try:
            # Check database connection
            db.session.execute('SELECT 1')
            db_status = 'connected'
            
            # Get current UTC time
            current_time = datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')
            
            return jsonify({
                'status': 'healthy',
                'timestamp': current_time,
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

def initialize_app():
    """Initialize the application"""
    try:
        # Create health check route
        create_health_check_route()
        
        # Log startup information
        logger.info(f"Starting Water Monitoring System")
        logger.info(f"UTC Time: {INITIAL_DATE}")
        logger.info(f"User: {USER_LOGIN}")
        logger.info(f"Python Version: {sys.version}")
        logger.info(f"Data Directory: {os.path.abspath(DATA_DIR)}")
        logger.info(f"Log Directory: {os.path.abspath(LOG_DIR)}")
        
        return True
    except Exception as e:  # Fixed syntax error here
        logger.error(f"Application initialization failed: {e}")
        return False

def setup_error_handlers():
    """Setup custom error handlers"""
    @app.errorhandler(404)
    def not_found_error(error):
        logger.warning(f"404 error: {error}")
        return jsonify({
            'error': 'Resource not found',
            'timestamp': datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        logger.error(f"500 error: {error}")
        db.session.rollback()
        return jsonify({
            'error': 'Internal server error',
            'timestamp': datetime.now(pytz.UTC).strftime('%Y-%m-%d %H:%M:%S')
        }), 500

def get_application_config():
    """Get application configuration"""
    return {
        'HOST': os.environ.get('HOST', '0.0.0.0'),
        'PORT': int(os.environ.get('PORT', 8080)),
        'DEBUG': os.environ.get('FLASK_DEBUG', '0') == '1',
        'DATABASE_URI': f'sqlite:///{os.path.join(DATA_DIR, "water_levels.db")}',
        'LOG_LEVEL': os.environ.get('LOG_LEVEL', 'INFO'),
        'USER_LOGIN': USER_LOGIN,
        'INITIAL_DATE': INITIAL_DATE.strftime('%Y-%m-%d %H:%M:%S')
    }

if __name__ == '__main__':
    try:
        # Check system requirements
        if not check_system_requirements():
            logger.error("System requirements not met. Exiting.")
            sys.exit(1)

        # Initialize application
        if not initialize_app():
            logger.error("Application initialization failed. Exiting.")
            sys.exit(1)

        # Setup error handlers
        setup_error_handlers()

        # Get configuration
        config = get_application_config()
        logger.info(f"Application configured with: {config}")

        # Start the application
        logger.info(f"Starting server on {config['HOST']}:{config['PORT']}")
        app.run(
            host=config['HOST'],
            port=config['PORT'],
            debug=config['DEBUG']
        )

    except KeyboardInterrupt:
        logger.info("Application shutdown requested by user")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Unhandled exception: {e}")
        sys.exit(1)
    finally:
        logger.info("Application shutdown complete")