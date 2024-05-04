from flask import Flask, request, jsonify
import RPi.GPIO as GPIO
from flask_mqtt import Mqtt
import time
from w1thermsensor import W1ThermSensor
import logging
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

logging.basicConfig(filename='/var/log/Frosty_app.log', level=logging.INFO,
                    format='%(asctime)s    %(levelname)s   %(message)s' ,
                    datefmt='%d-%m-%Y %H:%M:%S') 

temp_sensor1_ID = '3c01d607e0e2' #change this to be an ID from one of you 1-wire devices in /sys/bus/w1/devices 
temp_sensor2_ID = '3c01d6075170' #change this to be an ID from one of you 1-wire devices in /sys/bus/w1/devices
sensor1_offset = 3 # This is where you calibrate the temperature sensor1 to assure accuracy 
sensor2_offset = 3 # This is where you calibrate the temperature sensor2 to assure accuracy 
temp_sched = 1800 # time period between tempeature readings for scheduler


# Setup MQTT broker connection
app.config['MQTT_BROKER_URL'] = '000.000.000.000' # Your MQTT Broker IP
app.config['MQTT_BROKER_PORT'] = 1883 # Change if you are not using the default port number
app.config['MQTT_USERNAME'] = 'username' # Add your MQTT username or delete the user if no user name is used
app.config['MQTT_PASSWORD'] = 'password' # Add your MQTT password or delete the user if no password name is used
app.config['MQTT_REFRESH_TIME'] = 1.0  # refresh time in seconds
mqtt = Mqtt(app)


# Get inital temperature reading before scheduler starts
temp_sensor1 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, temp_sensor1_ID)
temp_sensor2 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, temp_sensor2_ID)
sensor1_temp = int(temp_sensor1.get_temperature(W1ThermSensor.DEGREES_F) + sensor1_offset)
sensor2_temp = int(temp_sensor2.get_temperature(W1ThermSensor.DEGREES_F) + sensor2_offset)
mqtt.publish('Frosty/temp/sensor1', sensor1_temp)
mqtt.publish('Frosty/temp/sensor2', sensor2_temp)
log_sensor1 = str(sensor1_temp)
logging.info("sensor1: " + log_sensor1)
log_sensor2 = str(sensor2_temp)
logging.info("sensor2: " + log_sensor2)

# Define the GPIO ports that each channel will use.
PUMP = 26
SALT = 19
LIGHT = 13
AERATOR = 6
SPEED1 = 5
SPEED2 = 22
SPEED3 = 27
SPEED4 = 17

# Setup each of the GPIO Ports
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(PUMP, GPIO.OUT)
GPIO.setup(SALT, GPIO.OUT)
GPIO.setup(LIGHT, GPIO.OUT)
GPIO.setup(AERATOR, GPIO.OUT)
GPIO.setup(SPEED1, GPIO.OUT)
GPIO.setup(SPEED2, GPIO.OUT)
GPIO.setup(SPEED3, GPIO.OUT)
GPIO.setup(SPEED4, GPIO.OUT)

def speed_test():
    if GPIO.input(SPEED1) == 1:
        return 1
    elif GPIO.input(SPEED2) == 1:
        return 2
    elif GPIO.input(SPEED3) == 1:
        return 3
    elif GPIO.input(SPEED4) == 1:
        return 4
    else:
        return 0
# Sets the speed for the pump. Takes int 1-4 as speed and triggers the related relay GPIO
def set_speed(speed):
    GPIO.output(SPEED1, GPIO.LOW)
    GPIO.output(SPEED2, GPIO.LOW)
    GPIO.output(SPEED3, GPIO.LOW)
    GPIO.output(SPEED4, GPIO.LOW)
    if speed == 1:
        GPIO.output(SPEED1, GPIO.HIGH)
        mqtt.publish('Frosty/state/speed', 1)
    elif speed == 2:
        GPIO.output(SPEED2, GPIO.HIGH)
        mqtt.publish('Frosty/state/speed', 2)
    elif speed == 3:
        GPIO.output(SPEED3, GPIO.HIGH)
        mqtt.publish('Frosty/state/speed', 3)
    elif speed == 4:
        GPIO.output(SPEED4, GPIO.HIGH)
        mqtt.publish('Frosty/state/speed', 4)

# ########################    MQTT   ########################## 

#Inital test state and publish to MQTT on startup
mqtt.publish('Frosty/state/pump', GPIO.input(PUMP))
mqtt.publish('Frosty/state/salt', GPIO.input(SALT))
mqtt.publish('Frosty/state/light', GPIO.input(LIGHT))
mqtt.publish('Frosty/state/aerator', GPIO.input(AERATOR))
mqtt.publish('Frosty/state/speed', speed_test())
mqtt.publish('Frosty/toggle/light', "off")
mqtt.publish('Frosty/toggle/pump', "off")
mqtt.publish('Frosty/toggle/salt', "off")
mqtt.publish('Frosty/toggle/aerator', "off")

def mqtt_sensor_publish():
     temp_sensor1 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, temp_sensor1_ID)
     temp_sensor2 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, temp_sensor2_ID)
     sensor1_temp = int(temp_sensor1.get_temperature(W1ThermSensor.DEGREES_F) + sensor1_offset)
     sensor2_temp = int(temp_sensor2.get_temperature(W1ThermSensor.DEGREES_F) + sensor2_offset)
     mqtt.publish('Frosty/temp/sensor1', sensor1_temp)
     mqtt.publish('Frosty/temp/sensor2', sensor2_temp)
     log_sensor1 = str(sensor1_temp)
     logging.info("sensor1: " + log_sensor1)
     log_sensor2 = str(sensor2_temp)
     logging.info("sensor2: " + log_sensor2)

scheduler = BackgroundScheduler()
scheduler.add_job(func=mqtt_sensor_publish, trigger="interval", seconds=temp_sched)
scheduler.start()

mqtt.subscribe('Frosty/toggle/pump')
@mqtt.on_topic('Frosty/toggle/pump')
def handle_mytopic(client, userdata, message):
   with app.app_context():
    status=int(GPIO.input(PUMP))
    if status == 0 and message.payload.decode() == "on":
        set_speed(4)
        GPIO.output(PUMP, GPIO.HIGH)
        GPIO.output(SALT, GPIO.HIGH)
        verify_pump_state = GPIO.input(SALT)
        verify_speed_state = speed_test()
        verify_salt_state = GPIO.input(PUMP)
        mqtt.publish('Frosty/toggle/salt', "on")
        mqtt.publish('Frosty/state/pump', verify_pump_state)
        mqtt.publish('Frosty/state/speed', verify_speed_state)
        mqtt.publish('Frosty/state/salt', verify_salt_state)
        logging.info("MQTT - Pump turned on")
        logging.info("MQTT - Salt turned on")
    elif status == 1 and message.payload.decode() == "off": 
        GPIO.output(PUMP, GPIO.LOW)
        GPIO.output(SALT, GPIO.LOW)
        verify_pump_state = GPIO.input(PUMP)
        verify_salt_state = GPIO.input(SALT)
        mqtt.publish('Frosty/state/pump', verify_pump_state)
        mqtt.publish('Frosty/state/salt', verify_salt_state)
        mqtt.publish('Frosty/toggle/salt', "off")
        logging.info("MQTT - Pump turned off")
        logging.info("MQTT - Salt turned off")
    else:
        logging.info("MQTT - Pump - Nah Bruh")

mqtt.subscribe('Frosty/toggle/salt')
@mqtt.on_topic('Frosty/toggle/salt')
def handle_mytopic(client, userdata, message):
    with app.app_context():
        salt_status=int(GPIO.input(SALT))
        pump_status=int(GPIO.input(PUMP))
        if pump_status == 0 and message.payload.decode() == "on":
            GPIO.output(SALT, GPIO.LOW)
            verify_state = GPIO.input(SALT)
            mqtt.publish('Frosty/state/salt', verify_state)
            logging.info("MQTT - WARNING - You can't turn on the Salt system without the pump running") 
        elif pump_status == 1 and message.payload.decode() == "off":
            GPIO.output(SALT, GPIO.LOW)
            verify_state = GPIO.input(SALT)
            logging.info("MQTT - Salt turned off")
            mqtt.publish('Frosty/state/salt', verify_state)
        elif pump_status == 1 and message.payload.decode() == "on":
            GPIO.output(SALT, GPIO.HIGH)
            verify_state = GPIO.input(SALT)
            logging.info("MQTT - Salt turned on")
            mqtt.publish('Frosty/state/salt', verify_state)
        else:
            logging.info("MQTT - Salt - Nah Bruh")

mqtt.subscribe('Frosty/toggle/light')
@mqtt.on_topic('Frosty/toggle/light')
def handle_mytopic(client, userdata, message):
    with app.app_context():
        status=int(GPIO.input(LIGHT))
        if status == 1 and message.payload.decode() == "off":
            GPIO.output(LIGHT, GPIO.LOW)
            verify_state = GPIO.input(LIGHT)
            mqtt.publish('Frosty/state/light', verify_state)
            logging.info("MQTT - Light turned off")
        elif status== 0 and message.payload.decode() == "on":
            GPIO.output(LIGHT, GPIO.HIGH)
            verify_state = GPIO.input(LIGHT)
            mqtt.publish('Frosty/state/light', verify_state)
            logging.info("MQTT - Light turned on")
        else:
            logging.info("MQTT - Light - Nah Bruh")

# -- status/update is used when Home assistant restarts. 
# -- It re-publishes the current state of all channels and temperature probes

mqtt.subscribe('Frosty/status/update')
@mqtt.on_topic('Frosty/status/update')
def handle_mytopic(client, userdata, message):
    with app.app_context():
        light_status=int(GPIO.input(LIGHT))
        pump_status=int(GPIO.input(PUMP))
        salt_status=int(GPIO.input(SALT))
        aerator_status=int(GPIO.input(AERATOR))

        mqtt.publish('Frosty/state/light', light_status)
        mqtt.publish('Frosty/state/pump', pump_status)
        mqtt.publish('Frosty/state/salt', salt_status)
        mqtt.publish('Frosty/state/aerator', aerator_status)
        mqtt.publish('Frosty/state/speed', speed_state())

        temp_sensor1 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, temp_sensor1_ID)
        temp_sensor2 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, temp_sensor2_ID)
        sensor1_temp = int(temp_sensor1.get_temperature(W1ThermSensor.DEGREES_F) + sensor1_offset)
        sensor2_temp = int(temp_sensor2.get_temperature(W1ThermSensor.DEGREES_F) + sensor2_offset)
        mqtt.publish('Frosty/temp/sensor1', sensor1_temp)
        mqtt.publish('Frosty/temp/sensor2', sensor2_temp)

        logging.info("MQTT Updated state info")

mqtt.subscribe('Frosty/toggle/aerator')
@mqtt.on_topic('Frosty/toggle/aerator')
def handle_mytopic(client, userdata, message):
    with app.app_context():
        status=int(GPIO.input(AERATOR))
        if status == 1 and message.payload.decode() == "off":
            GPIO.output(AERATOR, GPIO.LOW)
            verify_state = GPIO.input(AERATOR)
            logging.info("MQTT - Aerator turned off")
            mqtt.publish('Frosty/state/aerator', verify_state)
        elif status== 0 and message.payload.decode() == "on":
            set_speed(4)
            GPIO.output(AERATOR, GPIO.HIGH)
            verify_state = GPIO.input(AERATOR)
            logging.info("MQTT - Aerator turned on")
            mqtt.publish('Frosty/state/aerator', verify_state)
        else:
            logging.info("MQTT - Aerator - Nah Bruh")


#########################    REST TOGGLE   #############################

# PUMP Toggle 
@app.route('/toggle/pump/', methods=['GET'])
def pump_toggle():
    status = GPIO.input(PUMP) 
    if status == 1:
        GPIO.output(PUMP, GPIO.LOW)
        GPIO.output(SALT, GPIO.LOW)
        verify_pump_state = GPIO.input(PUMP)
        verify_salt_state = GPIO.input(SALT)
        mqtt.publish('Frosty/state/pump', verify_pump_state)
        mqtt.publish('Frosty/state/salt', verify_salt_state)
        logging.info("REST API - Pump turned off")
        return jsonify({"message": "Pump successfully turned off"})
        return jsonify({"message": "Salt successfully turned off"})
    elif status == 0:
        set_speed(4)
        GPIO.output(PUMP, GPIO.HIGH)
        GPIO.output(SALT, GPIO.HIGH)
        verify_pump_state = GPIO.input(PUMP)
        verify_speed_state = speed_test()
        verify_salt_state = GPIO.input(SALT)
        mqtt.publish('Frosty/state/pump', verify_pump_state)
        mqtt.publish('Frosty/state/speed', verify_speed_state)
        mqtt.publish('Frosty/state/salt', verify_salt_state)
        logging.info("REST API - Pump turned on")
        return jsonify({"message": "Pump successfully turned on"})
    else:
        logging.info("REST API - Boom! Something blew up, check your settings and try again - Pump Toggle")
        return jsonify({"message": "Boom! Something blew up, check your settings and try again"}, {"GPIO state": status})

# SALT Toggle
@app.route('/toggle/salt/', methods=['GET'])
def salt_toggle():
    salt_status=int((GPIO.input(SALT)))
    pump_status=int((GPIO.input(PUMP)))
    if pump_status == 1 and salt_status == 1:
        GPIO.output(SALT, GPIO.LOW)
        salt_state=GPIO.input(SALT)
        logging.info("REST API - Salt turned off")
        mqtt.publish('Frosty/state/salt', salt_state)
        return jsonify(message="Salt system successfully turned off")
    elif pump_status == 1 and salt_status == 0:
        GPIO.output(SALT, GPIO.HIGH)
        salt_state=GPIO.input(SALT)
        logging.info("REST API - Salt turned on")
        mqtt.publish('Frosty/state/salt', salt_state)
        return jsonify(message="Salt system successfully turned on")
    elif pump_status == 0 and salt_status == 0:
        GPIO.output(SALT, GPIO.LOW)
        salt_state=GPIO.input(SALT)
        logging.info("REST API - Warning - Can not turn on Salt system without the pump running. Salt system off")
        mqtt.publish('Frosty/state/salt', salt_state)
        return jsonify(message="Warning - Can not turn on Salt system without the pump running. Salt system off")
    elif pump_status == 0 and salt_status == 1:
        GPIO.output(SALT, GPIO.LOW)
        salt_state=GPIO.input(SALT)
        logging.info("REST API - Warning - Your salt system was found to be on without the pump. Salt off, check you system for possible damage")
        mqtt.publish('Frosty/state/salt', salt_state)
        return jsonify(message="Warning - Your salt system was found to be on without the pump. Salt off, check you system for possible damage")
    else:
        salt_state=GPIO.input(SALT)
        logging.info("REST API - Boom! Something blew up, check your settings and try again - Salt Toggle")
        return jsonify(message="Boom! Something blew up, check your settings and try again", Salt_state=salt_state)

# LIGHT Toggle
@app.route('/toggle/light/', methods=['GET'])
def light_toggle():
    status = GPIO.input(LIGHT)
    if status == 1:
        GPIO.output(LIGHT, GPIO.LOW)
        light_state=GPIO.input(LIGHT)
        logging.info("REST API - Light turned off")
        mqtt.publish('Frosty/state/light', light_state)
        return jsonify(message="Light successfully turned off")
    elif status == 0:
        GPIO.output(LIGHT, GPIO.HIGH)
        light_state=GPIO.input(LIGHT)
        logging.info("REST API - Light turned on")
        mqtt.publish('Frosty/state/light', light_state)
        return jsonify(message="Light system successfully turned on")
    else:
        light_state=GPIO.input(LIGHT)
        logging.info("REST API - Boom! Something blew up, check your settings and try again - Light Toggle")
        return jsonify(message="Boom! Something blew up, check your settings and try again", Light_status=light_state)

# AERATOR Toggle
@app.route('/toggle/aerator/', methods=['GET'])
def aerator_toggle():
    status = GPIO.input(AERATOR)
    if status == 1:
        GPIO.output(AERATOR, GPIO.LOW)
        aerator_state=GPIO.input(AERATOR)
        logging.info("REST API - Aerator turned off")
        mqtt.publish('Frosty/state/aerator', aerator_state)
        return jsonify(message="AERATOR successfully turned off")
    elif status == 0:
        set_speed(4)
        GPIO.output(AERATOR, GPIO.HIGH)
        aerator_state=GPIO.input(AERATOR)
        logging.info("REST API - Aerator turned on")
        mqtt.publish('Frosty/state/aerator', aerator_state)
        return jsonify(message="AERATOR successfully turned on")
    else:
        aerator_state=GPIO.input(AERATOR)
        logging.info("REST API - Boom! Something blew up, check your settings and try again - Aerator Toggle")
        return jsonify(message="Boom! Something blew up, check your settings and try again", Aerator_state=aerator_state)

######################    REST STATUS    ########################

# # Temperature Sensor 1
@app.route('/temp/sensor1', methods=['GET'])
def temp_1():
    temp_sensor1 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, temp_sensor1_ID)
    sensor1_temp = int(temp_sensor1.get_temperature(W1ThermSensor.DEGREES_F) + sensor1_offset)
    return jsonify(temp_sensor1=int(sensor1_temp))

# Temperature Sensor 2
@app.route('/temp/sensor2', methods=['GET'])
def temp_2():
    temp_sensor2 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, temp_sensor2_ID)
    sensor2_temp = int(temp_sensor2.get_temperature(W1ThermSensor.DEGREES_F) + sensor2_offset)
    return jsonify(temp_sensor2=int(sensor2_temp))

# PUMP State
@app.route('/state/pump/', methods=['GET'])
def pump_state():
    status = GPIO.input(PUMP)
    return jsonify(pump_state=status)

# SALT State
@app.route('/state/salt/', methods=['GET'])
def salt_state():
    status = GPIO.input(SALT)
    return jsonify(salt_state=status)

# LIGHT State
@app.route('/state/light/', methods=['GET'])
def light_state():
    status = GPIO.input(LIGHT)
    return jsonify(light_state=status)

# AERATOR State
@app.route('/state/aerator/', methods=['GET'])
def aerator_state():
    status = GPIO.input(AERATOR)
    return jsonify(aerator_state=status)

# SPEED State
@app.route('/state/speed/', methods=['GET'])
def speed_state():
    if GPIO.input(SPEED1) == 1:
        return jsonify(speed_state=1)
    elif GPIO.input(SPEED2) == 1:
        return jsonify(speed_state=2)
    elif GPIO.input(SPEED3) == 1:
        return jsonify(speed_state=3)
    elif GPIO.input(SPEED4) == 1:
        return jsonify(speed_state=4)
    else:
        return jsonify(speed_state=0)
