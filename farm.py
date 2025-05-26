from flask import Flask, render_template, Response, jsonify
from flask_cors import CORS
import cv2
from picamera2 import Picamera2

import RPi.GPIO as GPIO
import spidev

import RPi_I2C_driver
import time
import adafruit_dht
import board
import threading

dhtDevice = adafruit_dht.DHT11(board.D4,use_pulseio=False)

lcd = RPi_I2C_driver.lcd(0x27)

Pump_Motor_A = 5
Pump_Motor_B = 6
Fan_Motor_A = 19
Fan_Motor_B = 13

GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)

GPIO.setup(Pump_Motor_A, GPIO.OUT)
GPIO.setup(Pump_Motor_B, GPIO.OUT)
GPIO.setup(Fan_Motor_A, GPIO.OUT)
GPIO.setup(Fan_Motor_B, GPIO.OUT)

GPIO.output(Pump_Motor_A,GPIO.LOW)
GPIO.output(Pump_Motor_B,GPIO.LOW)
GPIO.output(Fan_Motor_A,GPIO.LOW)
GPIO.output(Fan_Motor_B,GPIO.LOW)

spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 1000000

moisture=0
moisture_set_start=50
moisture_set_stop=65

temperature=0
humidity=0
humidity_start=65
humidity_stop=57

hum_ch=0
moi_ch=0

lcd.cursor()
lcd.clear()
lcd.noCursor()

SCREEN_X = 640
SCREEN_Y = 480

app = Flask(__name__)
CORS(app)

# Initialize the camera
picam2 = Picamera2()
picam2.preview_configuration.main.size = (SCREEN_X, SCREEN_Y)
picam2.preview_configuration.main.format = "RGB888"
picam2.preview_configuration.align()
picam2.configure("preview")
picam2.start()

def gen_frames():  
    while True:
        frame= picam2.capture_array()  # 현재 영상을 받아옴
        frame= cv2.rotate(frame, cv2.ROTATE_180)
        ref, buffer = cv2.imencode('.jpg', frame)   # 현재 영상을 그림파일형태로 바꿈
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')  # 그림파일들을 쌓아두고 호출을 기다림

@app.route('/')
def index():
    return render_template('index1.html')             # index1.html의 형식대로 웹페이지를 보여줌

@app.route('/sensor_data')
def sensor_data():
    return jsonify({
        'temperature' : temperature,
        'humidity' : humidity,
        'moisture' : moisture
        })

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame') # 그림파일들을 쌓아서 보여줌

    # 웹사이트를 호스팅하여 접속자에게 보여주기 위한 부분
def camera_thread():
    app.run(host="0.0.0.0", port = "8080")
    
def Pump_Start():
    GPIO.output(Pump_Motor_A,GPIO.HIGH)
    GPIO.output(Pump_Motor_B,GPIO.LOW)
    
def Pump_Stop():
    GPIO.output(Pump_Motor_A,GPIO.LOW)
    GPIO.output(Pump_Motor_B,GPIO.LOW)
    
def Fan_Start():
    GPIO.output(Fan_Motor_A,GPIO.HIGH)
    GPIO.output(Fan_Motor_B,GPIO.LOW)
    
def Fan_Stop():
    GPIO.output(Fan_Motor_A,GPIO.LOW)
    GPIO.output(Fan_Motor_B,GPIO.LOW)

def map(value,min_water, max_water, min_ave,max_ave) :
    water_range=max_water-min_water
    ave_range=max_ave-min_ave
    scale_factor=float(water_range)/float(ave_range)
    return min_ave+(value/scale_factor)

def analogRead(ch):
    buf = [(1<<2)|(1<<1)|(ch&4)>>2,(ch&3)<<6,0]
    buf = spi.xfer(buf)
    adcValue = ((buf[1]&0xF)<<8)|buf[2]
    return adcValue

def main():
    global moisture_set_start
    global moisture_set_stop
    global humidity_start
    global humidity_stop
    global hum_ch
    global moi_ch
    global temperature, humidity, moisture
    
    while (True):
        try:
            
            moisture = analogRead(0)
            moisture = 4096-moisture

            moisture=int(map(moisture,0,4096,0,100))
            if moisture>=100:
                moisture=99
 
            temperature = dhtDevice.temperature
            humidity = dhtDevice.humidity
            
            if temperature is not None and humidity is not None:
                lcd_string1 = ("T=%2d H=%2d S=%2d  " %(temperature,humidity,humidity_start))
                lcd.setCursor(0, 0)
                lcd.print(lcd_string1)
                humidity_int=int(humidity)
                
                if humidity > humidity_start and hum_ch==0:
                    hum_ch=1
                    Fan_Start()
                
                if humidity < humidity_stop and hum_ch==1:
                    hum_ch=0
                    Fan_Stop()
            else:
                print("DHT11 error....!!")
                
            lcd_string2 = ("W=%2d S=%2d M=%2d  " %(moisture,moisture_set_start,moisture_set_stop))            

            
            lcd.setCursor(0, 1)
            lcd.print(lcd_string2)
            
            time.sleep(0.3)

            if moisture < moisture_set_start and moi_ch==0:
                moi_ch=1
                Pump_Start()
            
            if moisture > moisture_set_stop and moi_ch==1:
                moi_ch=0
                Pump_Stop()
    
        except RuntimeError as error:
            error_c=0
            
        except KeyboardInterrupt:
            dhtDevice.exit()
            GPIO.cleanup()
            
        except (KeyboardInterrupt, SystemExit):
            cleanAndExit()
             
if __name__ == '__main__':

    task1 = threading.Thread(target = camera_thread)
    task1.start()
    main()