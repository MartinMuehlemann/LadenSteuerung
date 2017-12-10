import datetime
import time
import os

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

# Create a dictionary called pins to store the pin number, name, and pin state:
pins = {
   GPIO_PIN_DOOR : {'name' : 'Tuere', 'state' : GPIO.LOW},
   27 : {'name' : 'Licht L', 'state' : GPIO.HIGH},
   22 : {'name' : 'Licht R', 'state' : GPIO.HIGH},
   5 : {'name' : 'Leuchtreklame', 'state' : GPIO.LOW},
   }

# Set each pin as an output and make it low:
for pin in pins:
   GPIO.setup(pin, GPIO.OUT)
   GPIO.output(pin, pins[pin]['state'])


door = {
        'state': "closed"
    }

def todayAt (hr, min=0, sec=0, micros=0):
   now = datetime.datetime.now()
   return now.replace(hour=hr, minute=min, second=sec, microsecond=micros)   

def time_scheduler(a, b):
    print("Current Time: {:%Y-%m-%d %H:%M:%S}".format(datetime.datetime.now()))
    
    doorOpenTime = todayAt(6, 00)
    doorCloseTime = todayAt(22, 00)

    if ((datetime.datetime.now() > doorOpenTime) & (datetime.datetime.now() < doorCloseTime)):
        newDoorState = "open"
        GPIO.output(GPIO_PIN_DOOR, GPIO.LOW)
    else:
        newDoorState = "closed"
        GPIO.output(GPIO_PIN_DOOR, GPIO.HIGH)
        
    if newDoorState != door["state"]:
        logAction("Door %s->%s" %(door["state"], newDoorState))
        door["state"] = newDoorState


def logAction(msg):
    logStr = "LOG: {:%Y-%m-%d %H:%M:%S} ".format(datetime.datetime.now()) + str(msg)
    print(logStr)
    with open('log.txt','a') as f:
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
    

    # it is also possible to enable the API directly
    # scheduler.api_enabled = True
    if os.environ.get("WERKZEUG_RUN_MAIN") == None:
        print("start scheduler")
        scheduler = APScheduler()
        scheduler.init_app(app)
        scheduler.start()
    
    app.run(host='0.0.0.0', port=80, debug=True) #, use_reloader = False