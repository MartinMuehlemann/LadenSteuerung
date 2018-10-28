import collections
import datetime
import time
import os

import smbus
import RPi.GPIO as GPIO
from flask import Flask, render_template, request
from flask_apscheduler import APScheduler

GPIO.setmode(GPIO.BCM)
app = Flask(__name__)

currentTimeStr = None

class Config(object):
    JOBS = [
        {
            'id': 'time_scheduler',
            'func': 'app:time_scheduler',
            'args': (1, 2),
            'trigger': 'interval',
            'seconds': 10
        }
    ]

    SCHEDULER_API_ENABLED = True


GPIO_PIN_DOOR = 17
GPIO_PIN_LIGHT1 = 27
GPIO_PIN_LIGHT2 = 22
GPIO_PIN_SIGN = 5
GPIO_PIN_LIGHT_ENTRY = 6

WATCHDOG_TRIGGER_FILE = "/var/log/ladensteuerung_watchdog_trigger"

# Create a dictionary called pins to store the pin number, name, and pin state:
pins = {
   GPIO_PIN_DOOR : {'name' : 'Tuere', 'state' : GPIO.LOW},
   GPIO_PIN_LIGHT1 : {'name' : 'Licht L', 'state' : GPIO.HIGH},
   GPIO_PIN_LIGHT2 : {'name' : 'Licht R', 'state' : GPIO.HIGH},
   GPIO_PIN_SIGN : {'name' : 'Leuchtreklame', 'state' : GPIO.LOW},
   GPIO_PIN_LIGHT_ENTRY : {'name' : 'Scheinwerfer Eingang', 'state' : GPIO.LOW},

   }

# Set each pin as an output and make it low:
for pin in pins:
   GPIO.setup(pin, GPIO.OUT)
   GPIO.output(pin, pins[pin]['state'])


door = {
        'state': "open"
    }

light1 = {
        'state': "on"
    }

light2 = {
        'state': "on"
    }

sign = {
        'state': "on"
    }

lightEntry = {
        'state': "on"
    }

ILLUMINANCE_THRESHOLD_GO_ON = 10
ILLUMINANCE_THRESHOLD_GO_OFF = 15



class Context(object):
    illuminaceBuffer = collections.deque(maxlen=7)
    filteredIlluminance = 0
    signCurThreshold = ILLUMINANCE_THRESHOLD_GO_ON
    lightEntryCurThreshold = ILLUMINANCE_THRESHOLD_GO_ON
    
context = Context()

def bh1750_get_illuminance():
    BH1750_DEVICE_ADDRESS = 0x23      #7 bit address (will be left shifted to add the read write bit)
    BH1750_START_CONT_RES_MODE = 0x10
    BH1750_START_CONT_HRES_MODE = 0x11
        
    try:
        bus = smbus.SMBus(1)    # 0 = /dev/i2c-0 (port I2C0), 1 = /dev/i2c-1 (port I2C1)
    
        #Write a single register
        data = bus.read_i2c_block_data(BH1750_DEVICE_ADDRESS, BH1750_START_CONT_RES_MODE, 2)
        
        illuminance = data[1] | (data[0] << 8)
        print("Illuminane %u lux (Data: %s)" % (illuminance, str(data)))
        return illuminance
    except Exception as e:
        print("Read illuminave failed")
        print(e)
        return None

def filterMedian(collection):
    sortedList = sorted(collection)
    return sortedList[len(sortedList)/2]
  
def todayAt (hr, min=0, sec=0, micros=0):
   now = datetime.datetime.now()
   return now.replace(hour=hr, minute=min, second=sec, microsecond=micros)   

def time_scheduler(a, b):
    try:
        print("Current Time: {:%Y-%m-%d %H:%M:%S}".format(datetime.datetime.now()))
        
        doorOpenTime = todayAt(6, 0)
        doorCloseTime = todayAt(22, 0)
        
        light1OnTime = todayAt(6, 0)
        light2OnTime = todayAt(6, 0)    
        light1OffTime = todayAt(22, 15)
        light2OffTime = todayAt(22, 00)
        
    
        signOffTime = todayAt(23, 59)    
        signOnTime = todayAt(6, 0)
        
        lightEntryOnTime = todayAt(6, 0)
        lightEntryOffTime = todayAt(22, 0)
    
        illuminance = bh1750_get_illuminance();
        if (illuminance != None):
            context.illuminaceBuffer.append(illuminance)
            context.filteredIlluminance = filterMedian(context.illuminaceBuffer)
    #         logStr = "{:%Y-%m-%d %H:%M:%S},".format(datetime.datetime.now()) + str(context.filteredIlluminance)
    #         print(logStr)
    #         # write in file only every 1 minute (if seconds are in range 0..9s
    #         if(datetime.datetime.now().second < 10):
    #             with open('/home/pi/illumimance.csv','a') as fIllumimace:
    #                 fIllumimace.write(logStr + "\n")
        else:
            context.filteredIlluminance = 0
        
        manual = False
    
        if manual == False:
            # Door
            if ((datetime.datetime.now() > doorOpenTime) & (datetime.datetime.now() < doorCloseTime)):
                newDoorState = "open"
                GPIO.output(GPIO_PIN_DOOR, GPIO.LOW)
            else:
                newDoorState = "closed"
                GPIO.output(GPIO_PIN_DOOR, GPIO.HIGH)
                 
            if newDoorState != door["state"]:
                logAction("Door %s->%s" %(door["state"], newDoorState))
                door["state"] = newDoorState
                
            # Light 1
            if ((datetime.datetime.now() > light1OnTime) & (datetime.datetime.now() < light1OffTime)):
                newLight1State = "on"
                GPIO.output(GPIO_PIN_LIGHT1, GPIO.HIGH)
            else:
                newLight1State = "off"
                GPIO.output(GPIO_PIN_LIGHT1, GPIO.LOW) 
                
            if newLight1State != light1["state"]:
                logAction("Light1 %s->%s" %(light1["state"], newLight1State))
                light1["state"] = newLight1State
        
            # Light 2
            if ((datetime.datetime.now() > light2OnTime) & (datetime.datetime.now() < light2OffTime)):
                newLight2State = "on"
                GPIO.output(GPIO_PIN_LIGHT2, GPIO.HIGH)
            else:
                newLight2State = "off"
                GPIO.output(GPIO_PIN_LIGHT2, GPIO.LOW) 
                
            if newLight2State != light2["state"]:
                logAction("Light2 %s->%s" %(light2["state"], newLight2State))
                light2["state"] = newLight2State
        
            # Sign
            if ((datetime.datetime.now() > signOnTime) & (context.filteredIlluminance <= context.signCurThreshold) & (datetime.datetime.now() < signOffTime)):
                context.signCurThreshold = ILLUMINANCE_THRESHOLD_GO_OFF
                newSignState = "on"
                GPIO.output(GPIO_PIN_SIGN, GPIO.HIGH)
            else:
                context.signCurThreshold = ILLUMINANCE_THRESHOLD_GO_ON
                newSignState = "off"
                GPIO.output(GPIO_PIN_SIGN, GPIO.LOW) 
                
            if newSignState != sign["state"]:
                logAction("Sign %s->%s" %(sign["state"], newSignState))
                sign["state"] = newSignState
        
        
            # Light Entry
            if ((datetime.datetime.now() > lightEntryOnTime) & (context.filteredIlluminance <= context.lightEntryCurThreshold) & (datetime.datetime.now() < lightEntryOffTime)):
                context.lightEntryCurThreshold = ILLUMINANCE_THRESHOLD_GO_OFF
                newLightEntryState = "on"
                GPIO.output(GPIO_PIN_LIGHT_ENTRY, GPIO.HIGH)
            else:
                context.lightEntryCurThreshold = ILLUMINANCE_THRESHOLD_GO_ON
                newLightEntryState = "off"
                GPIO.output(GPIO_PIN_LIGHT_ENTRY, GPIO.LOW) 
                
            if newLightEntryState != lightEntry["state"]:
                logAction("LightEntry %s->%s" %(lightEntry["state"], newLightEntryState))
                lightEntry["state"] = newLightEntryState
                
        with open(WATCHDOG_TRIGGER_FILE, "w") as f:
        	f.write("{:%Y-%m-%d %H:%M:%S}".format(datetime.datetime.now()))
                
    except Exception as e:
        logAction("EXCEPTION: " + str(e))
        
def logAction(msg):
    logStr = "LOG: {:%Y-%m-%d %H:%M:%S} ".format(datetime.datetime.now()) + str(msg)
    print(logStr)
    with open('/home/pi/log.txt','a') as f:
        f.write(logStr + "\n")

def updateCurrentTimeString():
    currentTimeStr = "{:%Y-%m-%d %H:%M:%S}".format(datetime.datetime.now())

@app.route("/")
def main():
    currentTimeStr = "{:%Y-%m-%d %H:%M:%S}".format(datetime.datetime.now())
    updateCurrentTimeString()

    # Put the pin dictionary into the template data dictionary:
    templateData = {
        'door' : door,
        'currentTimeStr' : currentTimeStr
    }

    # Pass the template data into the template main.html and return it to the user
    return render_template('main.html', **templateData)

@app.route("/<page>")
def rootPages(page):
    currentTimeStr = "{:%Y-%m-%d %H:%M:%S}".format(datetime.datetime.now())
    updateCurrentTimeString()

    # Put the pin dictionary into the template data dictionary:
    templateData = {
        'door' : door,
        'pins' : pins,
        'currentTimeStr' : currentTimeStr
    }

    print("currentTimeStr" + currentTimeStr)
    # Pass the template data into the template main.html and return it to the user
    return render_template(page, **templateData)

# The function below is executed when someone requests a URL with the pin number and action in it:
@app.route("/<changePin>/<action>")
def action(changePin, action):
   print("Action %s %s" %(changePin, action))
   # Convert the pin from the URL into an integer:
   changePin = int(changePin)
   # Get the device name for the pin being changed:
   deviceName = pins[changePin]['name']
   # If the action part of the URL is "on," execute the code indented below:
   if action == "on":
      # Set the pin high:
      GPIO.output(changePin, GPIO.HIGH)
      # Save the status message to be passed into the template:
      message = "Turned " + deviceName + " on."
   if action == "off":
      GPIO.output(changePin, GPIO.LOW)
      message = "Turned " + deviceName + " off."

   # For each pin, read the pin state and store it in the pins dictionary:
   for pin in pins:
      pins[pin]['state'] = GPIO.input(pin)

   # Along with the pin dictionary, put the message into the template data dictionary:
   templateData = {
      'pins' : pins,
      'door' : door
   }

   return render_template('service.html', **templateData)

if __name__ == "__main__":

    app.config.from_object(Config())
    logAction("Start Webserver")

    # it is also possible to enable the API directly
    # scheduler.api_enabled = True
    if os.environ.get("WERKZEUG_RUN_MAIN") == None:
        print("start scheduler")
        scheduler = APScheduler()
        scheduler.init_app(app)
        scheduler.start()
    
    app.run(host='0.0.0.0', port=80, debug=False) #, use_reloader = False