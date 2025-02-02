# Water Monitoring System

This project is a water monitoring system designed to track water levels in a tank. It provides a web-based dashboard to visualize water levels, daily usage, and weekly statistics. The system uses a Flask web server, an SQLite database, and a simple HTML/JavaScript frontend.

## Features
- Real-time water level monitoring
- Daily and weekly water usage statistics
- Modern and responsive web-based dashboard
- Alerts for invalid sensor readings
- Data validation to ensure accurate measurements
- Indian Standard Time (IST) display

## Technologies Used
- Python
- Flask
- SQLite
- HTML/CSS
- JavaScript (Chart.js)

## Setup Instructions

### Prerequisites
- Python 3.6+
- Git
- A compatible Linux environment (Ubuntu preferred)

### Installation

1. **Set Up Project Directory**
    ```bash
    mkdir water_monitoring
    cd water_monitoring
    ```

2. **Create and Activate Virtual Environment**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

3. **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4. **Set Up Database and Log Directories**
    ```bash
    mkdir -p data
    sudo mkdir -p /var/log/water_monitoring
    sudo chown -R $USER:$USER /var/log/water_monitoring
    ```

5. **Run the Application**
    ```bash
    python app.py
    ```

### Running as a Service

1. **Create a Systemd Service File**
    ```ini
    sudo nano /etc/systemd/system/water-monitor.service
    ```

    Add the following content:
    ```ini
    [Unit]
    Description=Water Tank Monitoring System
    After=network.target

    [Service]
    User=ubuntu
    Group=ubuntu
    WorkingDirectory=/home/ubuntu/water_monitoring
    Environment="PATH=/home/ubuntu/water_monitoring/venv/bin"
    Environment="FLASK_APP=app.py"
    Environment="FLASK_ENV=production"
    ExecStart=/home/ubuntu/water_monitoring/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:8080 app:app
    Restart=always
    StandardOutput=append:/var/log/water_monitoring/water_monitor.log
    StandardError=append:/var/log/water_monitoring/water_monitor.error.log

    [Install]
    WantedBy=multi-user.target
    ```

2. **Start and Enable the Service**
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl start water-monitor
    sudo systemctl enable water-monitor
    sudo systemctl status water-monitor
    ```

### Accessing the Dashboard
- Open a web browser and navigate to `http://YOUR_SERVER_IP:8080`

## API Endpoints

### Update Water Level
- **URL:** `/update`
- **Method:** `POST`
- **Parameters:**
    - `distance`: (float) Distance measured by the sensor
- **Response:**
    ```json
    {
        "status": "success",
        "data": {
            "timestamp": "2023-01-24 00:00:00 IST",
            "distance": 50.0,
            "water_level": 50.0,
            "water_volume": 50.0,
            "status": "valid"
        }
    }
    ```

### Get Water Data
- **URL:** `/get_data`
- **Method:** `GET`
- **Response:**
    ```json
    [
        {
            "timestamp": "2023-01-24 00:00:00 IST",
            "distance": 50.0,
            "water_level": 50.0,
            "water_volume": 50.0,
            "status": "valid"
        },
        ...
    ]
    ```

### Health Check
- **URL:** `/health`
- **Method:** `GET`
- **Response:**
    ```json
    {
        "status": "healthy",
        "timestamp": "2023-01-24 00:00:00 IST",
        "database": "connected"
    }
    ```

## Code Structure
```
water_monitoring/
├── app.py
├── config.py
├── requirements.txt
├── static/
│   ├── css/
│   └── js/
├── templates/
│   └── index.html
└── data/
    └── water_data.db
```