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
mqtt.publish('temp/sensor1', sensor1_temp)
mqtt.publish('temp/sensor2', sensor2_temp)
log_sensor1 = str(sensor1_temp)
logging.info("sensor1: " + log_sensor1)
log_sensor2 = str(sensor2_temp)
logging.info("sensor2: " + log_sensor2)

# Define the GPIO ports that each channel will use.
PUMP = 26
SALT = 19
LIGHT = 13
AERATOR = 6
AUX1 = 5
AUX2 = 22
AUX3 = 27
AUX4 = 17

# Setup each of the GPIO Ports
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(PUMP, GPIO.OUT)
GPIO.setup(SALT, GPIO.OUT)
GPIO.setup(LIGHT, GPIO.OUT)
GPIO.setup(AERATOR, GPIO.OUT)
GPIO.setup(AUX1, GPIO.OUT)
GPIO.setup(AUX2, GPIO.OUT)
GPIO.setup(AUX3, GPIO.OUT)
GPIO.setup(AUX4, GPIO.OUT)


# ########################    MQTT   ########################## 

#Inital test state and publish to MQTT on startup
mqtt.publish('state/pump', GPIO.input(PUMP))
mqtt.publish('state/salt', GPIO.input(SALT))
mqtt.publish('state/light', GPIO.input(LIGHT))
mqtt.publish('state/aerator', GPIO.input(AERATOR))
mqtt.publish('state/aux1', GPIO.input(AUX1))
mqtt.publish('state/aux2', GPIO.input(AUX2))
mqtt.publish('state/aux3', GPIO.input(AUX3))
mqtt.publish('state/aux4', GPIO.input(AUX4))
#TEST
mqtt.publish('toggle/light', "off")
mqtt.publish('toggle/pump', "off")
mqtt.publish('toggle/salt', "off")
mqtt.publish('toggle/aerator', "off")
mqtt.publish('toggle/aux1', "off")
mqtt.publish('toggle/aux2', "off")
mqtt.publish('toggle/aux3', "off")
mqtt.publish('toggle/aux4', "off")


def mqtt_sensor_publish():
     temp_sensor1 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, temp_sensor1_ID)
     temp_sensor2 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, temp_sensor2_ID)
     sensor1_temp = int(temp_sensor1.get_temperature(W1ThermSensor.DEGREES_F) + sensor1_offset)
     sensor2_temp = int(temp_sensor2.get_temperature(W1ThermSensor.DEGREES_F) + sensor2_offset)
     mqtt.publish('temp/sensor1', sensor1_temp)
     mqtt.publish('temp/sensor2', sensor2_temp)
     log_sensor1 = str(sensor1_temp)
     logging.info("sensor1: " + log_sensor1)
     log_sensor2 = str(sensor2_temp)
     logging.info("sensor2: " + log_sensor2)

scheduler = BackgroundScheduler()
scheduler.add_job(func=mqtt_sensor_publish, trigger="interval", seconds=temp_sched)
scheduler.start()

mqtt.subscribe('toggle/pump')
@mqtt.on_topic('toggle/pump')
def handle_mytopic(client, userdata, message):
   with app.app_context():
    status=int(GPIO.input(PUMP))
    if status == 0 and message.payload.decode() == "on":
        GPIO.output(PUMP, GPIO.HIGH)
        GPIO.output(SALT, GPIO.HIGH)
        verify_pump_state = GPIO.input(SALT)
        verify_salt_state = GPIO.input(PUMP)
        mqtt.publish('toggle/salt', "on")
        mqtt.publish('state/pump', verify_pump_state)
        mqtt.publish('state/salt', verify_salt_state)
        logging.info("MQTT - Pump turned on")
        logging.info("MQTT - Salt turned on")
    elif status == 1 and message.payload.decode() == "off": 
        GPIO.output(PUMP, GPIO.LOW)
        GPIO.output(SALT, GPIO.LOW)
        verify_pump_state = GPIO.input(PUMP)
        verify_salt_state = GPIO.input(SALT)
        mqtt.publish('state/pump', verify_pump_state)
        mqtt.publish('state/salt', verify_salt_state)
        mqtt.publish('toggle/salt', "off")
        logging.info("MQTT - Pump turned off")
        logging.info("MQTT - Salt turned off")
    else:
        logging.info("MQTT - Pump - Nah Bruh")

mqtt.subscribe('toggle/salt')
@mqtt.on_topic('toggle/salt')
def handle_mytopic(client, userdata, message):
    with app.app_context():
        salt_status=int(GPIO.input(SALT))
        pump_status=int(GPIO.input(PUMP))
        if pump_status == 0 and message.payload.decode() == "on":
            GPIO.output(SALT, GPIO.LOW)
            verify_state = GPIO.input(SALT)
            mqtt.publish('state/salt', verify_state)
            logging.info("MQTT - WARNING - You can't turn on the Salt system without the pump running") 
        elif pump_status == 1 and message.payload.decode() == "off":
            GPIO.output(SALT, GPIO.LOW)
            verify_state = GPIO.input(SALT)
            logging.info("MQTT - Salt turned off")
            mqtt.publish('state/salt', verify_state)
        elif pump_status == 1 and message.payload.decode() == "on":
            GPIO.output(SALT, GPIO.HIGH)
            verify_state = GPIO.input(SALT)
            logging.info("MQTT - Salt turned on")
            mqtt.publish('state/salt', verify_state)
        else:s
            logging.info("MQTT - Salt - Nah Bruh")

mqtt.subscribe('toggle/light')
@mqtt.on_topic('toggle/light')
def handle_mytopic(client, userdata, message):
    with app.app_context():
        status=int(GPIO.input(LIGHT))
        if status == 1 and message.payload.decode() == "off":
            GPIO.output(LIGHT, GPIO.LOW)
            verify_state = GPIO.input(LIGHT)
            mqtt.publish('state/light', verify_state)
            logging.info("MQTT - Light turned off")
        elif status== 0 and message.payload.decode() == "on":
            GPIO.output(LIGHT, GPIO.HIGH)
            verify_state = GPIO.input(LIGHT)
            mqtt.publish('state/light', verify_state)
            logging.info("MQTT - Light turned on")
        else:
            logging.info("MQTT - Light - Nah Bruh")

# -- status/update is used when Home assistant restarts. 
# -- It re-publishes the current state of all channels and temperature probes

mqtt.subscribe('status/update')
@mqtt.on_topic('status/update')
def handle_mytopic(client, userdata, message):
    with app.app_context():
        light_status=int(GPIO.input(LIGHT))
        pump_status=int(GPIO.input(PUMP))
        salt_status=int(GPIO.input(SALT))
        aerator_status=int(GPIO.input(AERATOR))
        aux1_status=int(GPIO.input(AUX1))
        aux2_status=int(GPIO.input(AUX2))
        aux3_status=int(GPIO.input(AUX3))
        aux4_status=int(GPIO.input(AUX4))

        mqtt.publish('state/light', light_status)
        mqtt.publish('state/pump', pump_status)
        mqtt.publish('state/salt', salt_status)
        mqtt.publish('state/aerator', aerator_status)
        mqtt.publish('state/aux1', aux1_status)
        mqtt.publish('state/aux2', aux2_status)
        mqtt.publish('state/aux3', aux3_status)
        mqtt.publish('state/aux4', aux4_status)

        temp_sensor1 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, temp_sensor1_ID)
        temp_sensor2 = W1ThermSensor(W1ThermSensor.THERM_SENSOR_DS18B20, temp_sensor2_ID)
        sensor1_temp = int(temp_sensor1.get_temperature(W1ThermSensor.DEGREES_F) + sensor1_offset)
        sensor2_temp = int(temp_sensor2.get_temperature(W1ThermSensor.DEGREES_F) + sensor2_offset)
        mqtt.publish('temp/sensor1', sensor1_temp)
        mqtt.publish('temp/sensor2', sensor2_temp)

        logging.info("MQTT Updated state info")

mqtt.subscribe('toggle/aerator')
@mqtt.on_topic('toggle/aerator')
def handle_mytopic(client, userdata, message):
    with app.app_context():
        status=int(GPIO.input(AERATOR))
        if status == 1 and message.payload.decode() == "off":
            GPIO.output(AERATOR, GPIO.LOW)
            verify_state = GPIO.input(AERATOR)
            logging.info("MQTT - Aerator turned off")
            mqtt.publish('state/aerator', verify_state)
        elif status== 0 and message.payload.decode() == "on":
            GPIO.output(AERATOR, GPIO.HIGH)
            verify_state = GPIO.input(AERATOR)
            logging.info("MQTT - Aerator turned on")
            mqtt.publish('state/aerator', verify_state)
        else:
            logging.info("MQTT - Aerator - Nah Bruh")

mqtt.subscribe('toggle/aux1')
@mqtt.on_topic('toggle/aux1')
def handle_mytopic(client, userdata, message):
    with app.app_context():
        status=int(GPIO.input(AUX1))
        if status == 1 and message.payload.decode() == "off":
            GPIO.output(AUX1, GPIO.LOW)
            verify_state = GPIO.input(AUX1)
            logging.info("MQTT - Aux1 turned off")
            mqtt.publish('state/aux1', verify_state)
        elif status== 0 and message.payload.decode() == "on":
            GPIO.output(AUX1, GPIO.HIGH)
            verify_state = GPIO.input(AUX1)
            logging.info("MQTT - Aux1 turned on")
            mqtt.publish('state/aux1', verify_state)
        else:
            logging.info("MQTT - Aux1 - Nah Bruh")

mqtt.subscribe('toggle/aux2')
@mqtt.on_topic('toggle/aux2')
def handle_mytopic(client, userdata, message):
    with app.app_context():
        status=int(GPIO.input(AUX2))
        if status == 1 and message.payload.decode() == "off":
            GPIO.output(AUX2, GPIO.LOW)
            verify_state = GPIO.input(AUX2)
            logging.info("MQTT - Aux2 turned off")
            mqtt.publish('state/aux2', verify_state)
        elif status== 0 and message.payload.decode() == "on":
            GPIO.output(AUX2, GPIO.HIGH)
            verify_state = GPIO.input(AUX2)
            logging.info("MQTT - Aux2 turned on")
            mqtt.publish('state/aux2', verify_state)
        else:
            logging.info("MQTT - Aux2 - Nah Bruh")

mqtt.subscribe('toggle/aux3')
@mqtt.on_topic('toggle/aux3')
def handle_mytopic(client, userdata, message):
    with app.app_context():
        status=int(GPIO.input(AUX3))
        if status == 1 and message.payload.decode() == "off":
            GPIO.output(AUX3, GPIO.LOW)
            logging.info("MQTT - Aux3 turned off")
            verify_state = GPIO.input(AUX3)
            mqtt.publish('state/aux3', verify_state)
        elif status== 0 and message.payload.decode() == "on":
            GPIO.output(AUX3, GPIO.HIGH)
            verify_state = GPIO.input(AUX3)
            logging.info("MQTT - Aux3 turned on")
            mqtt.publish('state/aux3', verify_state)
        else:
            logging.info("MQTT - Aux - Nah Bruh")

mqtt.subscribe('toggle/aux4')
@mqtt.on_topic('toggle/aux4')
def handle_mytopic(client, userdata, message):
    with app.app_context():
        status=int(GPIO.input(AUX4))
        if status== 1 and message.payload.decode() == "off":
            GPIO.output(AUX4, GPIO.LOW)
            verify_state = GPIO.input(AUX4)
            logging.info("MQTT - Aux4 turned off")
            mqtt.publish('state/aux4', verify_state)
        elif status == 0 and message.payload.decode() == "on":
            GPIO.output(AUX4, GPIO.HIGH)
            verify_state = GPIO.input(AUX4)
            logging.info("MQTT - Aux4 turned on")
            mqtt.publish('state/aux4', verify_state)
        else:
            logging.info("MQTT - Aux4 - Nah Bruh")


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
        mqtt.publish('state/pump', verify_pump_state)
        mqtt.publish('state/salt', verify_salt_state)
        logging.info("REST API - Pump turned off")
        return jsonify({"message": "Pump successfully turned off"})
        return jsonify({"message": "Salt successfully turned off"})
    elif status == 0:
        GPIO.output(PUMP, GPIO.HIGH)
        GPIO.output(SALT, GPIO.HIGH)
        verify_pump_state = GPIO.input(PUMP)
        verify_salt_state = GPIO.input(SALT)
        mqtt.publish('state/pump', verify_pump_state)
        mqtt.publish('state/salt', verify_salt_state)
        logging.info("REST API - Pump turned on")
        return jsonify({"message": "Pump successfully turned on"})
        return jsonify({"message": "Salt successfully turned on"})
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
        mqtt.publish('state/salt', salt_state)
        return jsonify(message="Salt system successfully turned off")
    elif pump_status == 1 and salt_status == 0:
        GPIO.output(SALT, GPIO.HIGH)
        salt_state=GPIO.input(SALT)
        logging.info("REST API - Salt turned on")
        mqtt.publish('state/salt', salt_state)
        return jsonify(message="Salt system successfully turned on")
    elif pump_status == 0 and salt_status == 0:
        GPIO.output(SALT, GPIO.LOW)
        salt_state=GPIO.input(SALT)
        logging.info("REST API - Warning - Can not turn on Salt system without the pump running. Salt system off")
        mqtt.publish('state/salt', salt_state)
        return jsonify(message="Warning - Can not turn on Salt system without the pump running. Salt system off")
    elif pump_status == 0 and salt_status == 1:
        GPIO.output(SALT, GPIO.LOW)
        salt_state=GPIO.input(SALT)
        logging.info("REST API - Warning - Your salt system was found to be on without the pump. Salt off, check you system for possible damage")
        mqtt.publish('state/salt', salt_state)
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
        mqtt.publish('state/light', light_state)
        return jsonify(message="Light successfully turned off")
    elif status == 0:
        GPIO.output(LIGHT, GPIO.HIGH)
        light_state=GPIO.input(LIGHT)
        logging.info("REST API - Light turned on")
        mqtt.publish('state/light', light_state)
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
        mqtt.publish('state/aerator', aerator_state)
        return jsonify(message="AERATOR successfully turned off")
    elif status == 0:
        GPIO.output(AERATOR, GPIO.HIGH)
        aerator_state=GPIO.input(AERATOR)
        logging.info("REST API - Aerator turned on")
        mqtt.publish('state/aerator', aerator_state)
        return jsonify(message="AERATOR successfully turned on")
    else:
        aerator_state=GPIO.input(AERATOR)
        logging.info("REST API - Boom! Something blew up, check your settings and try again - Aerator Toggle")
        return jsonify(message="Boom! Something blew up, check your settings and try again", Aerator_state=aerator_state)

# AUX1 Toggle
@app.route('/toggle/aux1/', methods=['GET'])
def aux1_toggle():
    status = GPIO.input(AUX1)
    if status == 1:
        GPIO.output(AUX1, GPIO.LOW)
        aux1_state=GPIO.input(AUX1)
        logging.info("REST API - Aux1 turned off")
        mqtt.publish('state/aux1', aux1_state)
        return jsonify(message="AUX1 successfully turned off")
    elif status == 0:
        GPIO.output(AUX1, GPIO.HIGH)
        aux1_state=GPIO.input(AUX1)
        logging.info("REST API - Aux1 turned on")
        mqtt.publish('state/aux1', aux1_state)
        return jsonify(message="AUX1 successfully turned on")
    else:
        aux1_state=GPIO.input(AUX1)
        logging.info("REST API - Boom! Something blew up, check your settings and try again - Aux1 Toggle")
        return jsonify(message="Boom! Something blew up, check your settings and try again", Aux1_state=aux1_state)

# AUX2 Toggle
@app.route('/toggle/aux2/', methods=['GET'])
def aux2_toggle():
    status = GPIO.input(AUX2)
    if status == 1:
        GPIO.output(AUX2, GPIO.LOW)
        aux2_state=GPIO.input(AUX2)
        logging.info("REST API - Aux2 turned off")
        mqtt.publish('state/aux2', aux2_state)
        return jsonify(message="AUX2 successfully turned off")
    elif status == 0:
        GPIO.output(AUX2, GPIO.HIGH)
        aux2_state=GPIO.input(AUX2)
        logging.info("REST API - Aux2 turned on")
        mqtt.publish('state/aux2', aux2_state)
        return jsonify(message="AUX2 successfully turned on")
    else:
        logging.info("REST API - Boom! Something blew up, check your settings and try again - Aux2 Toggle")
        return jsonify(message="Boom! Something blew up, check your settings and try again", Aux2_state=aux2_state)

# AUX3 Toggle
@app.route('/toggle/aux3/', methods=['GET'])
def aux3_toggle():
    status = GPIO.input(AUX3)
    if status == 1:
        GPIO.output(AUX3, GPIO.LOW)
        aux3_state=GPIO.input(AUX3)
        logging.info("REST API - Aux3 turned off")
        mqtt.publish('state/aux3', aux3_state)
        return jsonify(message="AUX3 successfully turned off")
    elif status == 0:
        GPIO.output(AUX3, GPIO.HIGH)
        aux3_state=GPIO.input(AUX3)
        logging.info("REST API - Aux3 turned on")
        mqtt.publish('state/aux3', aux3_state)
        return jsonify(message="AUX3 successfully turned on")
    else:
        aux3_state=GPIO.input(AUX3)
        logging.info("REST API - Boom! Something blew up, check your settings and try again - Aux3 Toggle")
        return jsonify(message="Boom! Something blew up, check your settings and try again", Aux3_state=aux3_state)

# AUX4 Toggle
@app.route('/toggle/aux4/', methods=['GET'])
def aux4_toggle():
    status = GPIO.input(AUX4)
    if status == 0:
        GPIO.output(AUX4, GPIO.HIGH)
        aux4_state=GPIO.input(AUX4)
        logging.info("REST API - Aux4 turned on")
        mqtt.publish('state/aux4', aux4_state)
        return jsonify(message="AUX4 successfully turned on")
    elif status == 1:
        GPIO.output(AUX4, GPIO.LOW)
        aux4_state=GPIO.input(AUX4)
        logging.info("REST API - Aux4 turned off")
        mqtt.publish('state/aux4', aux4_state)
        return jsonify(message="AUX4 successfully turned off")
    else:
        logging.info("REST API - Boom! Something blew up, check your settings and try again - Aux4 Toggle")
        return jsonify(message="Boom! Something blew up, check your settings and try again", Aux4_state=aux4_state)


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

# AUX1 State
@app.route('/state/aux1/', methods=['GET'])
def aux1_state():
    status = GPIO.input(AUX1)
    return jsonify(aux1_state=status)

# AUX2 State
@app.route('/state/aux2/', methods=['GET'])
def aux2_state():
    status = GPIO.input(AUX2)
    return jsonify(aux2_state=status)

# AUX3 State
@app.route('/state/aux3/', methods=['GET'])
def aux3_state():
    status = GPIO.input(AUX3)
    return jsonify(aux3_state=status)

# AUX4 State
@app.route('/state/aux4/', methods=['GET'])
def aux4_state():
    status = GPIO.input(AUX4)
    return jsonify(aux4_state=status)
