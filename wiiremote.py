#!/usr/bin/env python

from ctypes import *
from Queue import Queue, Empty
import time
import threading
import pygame
import os

VID = c_ushort(0x057E)
PID = c_ushort(0x0306)

MAXREPORTSIZE = 256
LED = [0x10, 0x20, 0x40, 0x80]
buttons = {0x0001:"2", 0x0002:"1", 0x0004:"B", 0x0008:"A", 0x0010:"-", 0x0080:"Home", 0x0100:"Left", 0x0200:"Right", 0x0400:"Down", 0x0800:"Up", 0x1000:"+"}
FLAG = {0x01:"Battery is nearly empty", 0x02:"An Extension Controller is connected", 0x04:"Speaker enabled", 0x08:"IR camera enabled"}

base = pygame.USEREVENT
WIIMOTE_BUTTON_PRESS = base + 1
WIIMOTE_BUTTON_RELEASE = base + 2
WIIMOTE_ACCEL = base + 3
WIIMOTE_IR = base + 4
WIIMOTE_GYRO = base + 5
WIIMOTE_STATUS = base + 6
WIIMOTE_DISCONNECT = base + 7
WIIMOTE_ACCEL_GYRO = base + 8

InputReport = c_ubyte * MAXREPORTSIZE
OutputReport = c_ubyte * MAXREPORTSIZE

if os.name == "nt":
    INVALID_HANDLE_VALUE = c_void_p(-1).value
    #kernel32 = windll.kernel32
    user32 = windll.user32
    tiny_hid = windll.tiny_hid_dll

    #QueryPerformanceFrequency = kernel32.QueryPerformanceFrequency
    #QueryPerformanceCounter = kernel32.QueryPerformanceCounter
    MessageBox = user32.MessageBoxA
    tiny_hid.OpenHidHandle.restype = c_void_p
    tiny_hid.OpenHidHandle.argtypes = [c_ushort, c_ushort] #vender_id, product_id
    OpenHidHandle = tiny_hid.OpenHidHandle
    tiny_hid.ReadReport.restype = None
    tiny_hid.ReadReport.argtypes = [c_void_p, POINTER(InputReport), POINTER(c_int)] #handle, input report, len
    ReadReport = tiny_hid.ReadReport
    tiny_hid.WriteReport.restype = None
    tiny_hid.WriteReport.argtypes = [c_void_p, POINTER(OutputReport), POINTER(c_int)] #handle, output report len
    WriteReport = tiny_hid.WriteReport
    tiny_hid.CloseHidHandle.restype = None
    tiny_hid.CloseHidHandle.argtypes = [c_void_p] #handle
    CloseHidHandle = tiny_hid.CloseHidHandle
else:
    import lightblue
    DEVICE_NAME = 'Nintendo RVL-CNT-01'


class WiiRemote(threading.Thread):
    def __init__(self):
        threading.Thread.__init__(self, name="wiiremote")
        self.recv_mode = None
        self.set_mode = None
        self.MotionPlusInit = 0
        self.pause = False
        self.yaw = self.pitch = self.roll = -1
        self.yaw_fast = self.pitch_fast = self.roll_fast = -1
        self.Ax = self.Ay = self.Az = -1
        self.button = -1
        self.startup = Queue()
        self.funcs = Queue()
        self.eventqueue = []
        self.setDaemon(1)
        self.start()
        self.startup.get(True)
        
    def Report_0x11(self, data): #c_ubyte
        report = OutputReport()
        length = c_int()
        report[0] = 0x11 #Report ID
        report[1] = data
        WriteReport(self.handle, report, byref(length))
        return
    
    def Report_0x12(self, data1, data2): #c_ubyte, c_ubyte
        report = OutputReport()
        length = c_int()
        report[0] = 0x12 #Report ID
        report[1] = data1
        report[2] = data2
        WriteReport(self.handle, report, byref(length))
        return

    def Report_0x13(self, data): #c_ubyte
        report = OutputReport()
        length = c_int()
        report[0] = 0x13 #Report ID
        report[1] = data
        WriteReport(self.handle, report, byref(length))
        return

    def Report_0x15(self, data):
        report = OutputReport()
        length = c_int()
        report[0] = 0x15
        report[1] = data
        WriteReport(self.handle, report, byref(length))
        return

    def Report_0x16(self, adr, len_, d1, d2): # write data
        report = OutputReport()
        length = c_int()
        report[0] = 0x16
        report[1] = 0x04 # 00(EEPROM) or 0x04(other i2c device)  or 0x08(other type2)
        report[2] = adr # I2C ADRS
        report[3] = 0x00 # ignore?
        report[4] = d1 # mem adr or command
        report[5] = len_ - 1 # len = 2 ...  if you want to send 2 bytes (d1 and d2)
        report[6] = d2 # data
        WriteReport(self.handle, report, byref(length))
        return
    
    def Report_0x17(self, adr, len_, d1): # read data
        report = OutputReport()
        length = c_int()
        report[0] = 0x17
        report[1] = 0x04 # 00(EEPROM) or 04(other ... 1byte type)
        report[2] = adr # I2C ADRS
        report[3] = 0x00 # ignore?
        report[4] = d1 # mem adr or command
        report[5] = 0x00 # length H
        report[6] = len_ # length L
        WriteReport(self.handle, report, byref(length))
        return

    def Read_i2c_device(self, offset, adr): # offset = 0xA4 or 0xA6
        self.Report_0x17(offset, 16, adr)
        return

    def MotionPlus_init(self):
        self.Read_i2c_device(0xA6, 0xFA)
        self.MotionPlusInit = 1
        while 1:
            self.Wii_Remote_Input()
            if self.MotionPlusInit <= 0: break
        return self.MotionPlusInit
    
    def Wii_Remote_mode(self, mode):
        #0x20 : Status mode
        #0x30 : button ONLY Report mode
        #0x31 : Acc Sensor + button  Report mode
        #0x33 : Acc Sensor + button + IR Report mode
        #0x37 : Acc Sensor + button + IR + ext Report mode
        if not mode:
            return
        self.set_mode = mode
        self.Report_0x12(0x00, mode)
        return
    
    def Wii_Remote_Input(self):
        if os.name == "nt":
            report = InputReport()
            length = c_int()
            ReadReport(self.handle, report, byref(length))
        else:
            report = self.read_socket.recv(MAXREPORTSIZE)
        self.recv_mode = report[0]
        #print hex(self.recv_mode)
        if self.recv_mode & 0xF0 == 0x20:
            self.button = report[1] * 0x100 + report[2]
            if self.recv_mode & 0x01: # mode:0x21
                if report[3] & 0x0F == 0x07:
                    #print "[gyro error]"
                    buf = [0] * 11
                else:
                    buf = report[6:17]
                if not self.MotionPlusInit:
                    self.yaw = buf[0] + (buf[3] >> 2) * 256
                    self.roll = buf[1] + (buf[4] >> 2) * 256
                    self.pitch = buf[2] + (buf[5] >> 2) * 256
                    self.yaw_fast = self.pitch_fast = self.roll_fast = 0
                    if buf[3] & 0x02 == 0: self.yaw_fast = 1
                    if buf[4] & 0x02 == 0: self.roll_fast = 1
                    if buf[3] & 0x01 == 0: self.pitch_fast = 1
                elif self.MotionPlusInit == 1:
                    if (buf[0] != 1) | (buf[1] != 0) | (buf[2] != 0xA6) | (buf[3] != 0x20) | (buf[4] != 0) | (buf[5] != 5):
                        self.Read_i2c_device(0xA4, 0xFA)
                        self.MotionPlusInit = 2
                    else:
                        self.Report_0x16(0xA6, 2, 0xFE, 0x04)
                        self.Report_0x15(0x00)
                        self.MotionPlusInit = 0
                elif self.MotionPlusInit == 2:
                    if (buf[0] != 1) | (buf[1] != 0) | (buf[2] != 0xA4) | (buf[3] != 0x20) | (buf[4] != 0) | (buf[5] != 5):
                        self.MotionPlusInit = 0
                    else:
                        self.MotionPlusInit = -1
            elif self.recv_mode & 0x02: # mode:0x22
                pass
            else: # mode:0x20
                flag = report[3] & 0x0F
                LEDs = report[3] & 0xF0
                battery = float(report[6]) / 255
                pygame.event.post(pygame.event.Event(WIIMOTE_STATUS,
                                                     flag=flag, LEDs=LEDs, battery=battery))
        elif self.recv_mode & 0xF0 == 0x30:
            self.button = report[1] * 0x100 + report[2]
            if self.recv_mode & 0x01:
                self.Ax = report[3]
                self.Ay = report[4]
                self.Az = report[5]
            elif self.recv_mode & 0x02:
                pass
            elif self.recv_mode & 0x04:
                report[16] = (report[16] ^ 0x17) + 0x17
                report[17] = (report[17] ^ 0x17) + 0x17
                report[18] = (report[18] ^ 0x17) + 0x17
                report[19] = (report[19] ^ 0x17) + 0x17
                report[20] = (report[20] ^ 0x17) + 0x17
                report[21] = (report[21] ^ 0x17) + 0x17
        return
 
    def quit(self, limited=False):
        if self.go == True:
            if not limited:
                self.Report_0x11(0x00) # LED off
                self.Report_0x13(0x00) # Rumble off
            self.go = False
            print "[*] disconnecting"
            CloseHidHandle(self.handle)
        return

    def do(self, func):
        self.funcs.put(func)
        return
    
    def run(self):
        notfound = False
        if os.name == "nt":
            self.handle = OpenHidHandle(VID, PID)
            if self.handle == INVALID_HANDLE_VALUE:
                notfound = True
        else:
            devs = lightblue.finddevices(getnames=True, length=5) # wait for 5sec
            addr = [d for dev in devs if d[1] == DEVICE_NAME] and dev[0] or None
            if not addr: 
                notfound = True
        if notfound:
            MessageBox(0, "Wii Remote not found.", 0, 0)
            self.startup.put(False)
            self.go = False
            return False
        if os.name != "nt":
            # create a socket for writing control data
            self.write_socket = lightblue.socket(lightblue.L2CAP)
            self.write_socket.connect((addr, 0x11))
            # create a socket for reading accelerometer data
            self.read_socket = lightblue.socket(lightblue.L2CAP)
            self.read_socket.connect((addr, 0x13))
        
        self.go = True
        print "[*] connected"
        
        if -1 != -1:
            MessageBox(0, "Wii Remote cannot open.", 0, 0)
            self.startup.put(False)
            self.quit()
            return False
        self.Report_0x13(0x01) #Rumble on
        time.sleep(1) #Sleep2(200)
        self.Report_0x11(LED[0]|LED[1]|LED[2]|LED[3]) #LEDs on
        self.Report_0x13(0x00) #Rumble off
        time.sleep(1) #Sleep2(200) 
        self.Report_0x11(0x00) #LEDs off
        
        if self.MotionPlus_init() == -1:
            MessageBox(0, "Wii MotionPlus not found.", 0, 0)
            self.startup.put(False)
            self.quit()
            return False
        else:
            print "[*] conected Wii MotionPlus."
            self.Wii_Remote_mode(0x31)

        self.startup.put(True)
        
        self.pressed = []
        while self.go:
            #time.sleep(0.1)
            self.Wii_Remote_Input()
            
            self.Read_i2c_device(0xA4, 0x00) # Wii Motion Plus bottom of regs
            self.Wii_Remote_Input()
            
            if not self.pause:
                event = pygame.event.Event(WIIMOTE_ACCEL_GYRO,
                                           accel=(float(self.Ax), float(self.Ay), float(self.Az)),
                                           gyro=(self.pitch, self.roll, self.yaw),
                                           fast_mode=(self.pitch_fast, self.roll_fast, self.yaw_fast),
                                           time=time.time())
                self.eventqueue.append(event)
            self.prev_pressed = self.pressed
            self.pressed = []
            self.new_pressed = []
            self.released = []
            #if self.button & 0x0080 == 0x0080: #Home button to quit
            #    #print "pressed Home"
            #    self.quit()
            for b, name in buttons.items():
                if self.button & b == b:
                    self.pressed.append(b)
            #Event management
            for b in self.pressed:
                if not b in self.prev_pressed:
                    self.new_pressed.append(b)
                    if not self.pause:
                        pygame.event.post(pygame.event.Event(WIIMOTE_BUTTON_PRESS,
                                                             button=buttons[b], time=time.time()))
            for b in self.prev_pressed:
                if not b in self.pressed:
                    self.released.append(b)
                    if not self.pause:
                        pygame.event.post(pygame.event.Event(WIIMOTE_BUTTON_RELEASE,
                                                             button=buttons[b], time=time.time()))
            
            while 1:
                try:
                    func = self.funcs.get_nowait()
                except Empty:
                    break
                else:
                    th = threading.Thread(target=func)
                    th.start()
        self.quit()
        return True

wiimote = None

def init():
    global wiimote
    if wiimote:
        return
    wiimote = WiiRemote()
    
    return

def pause(b):
    global wiimote
    wiimote.pause = b
    return

def get_queue():
    global wiimote
    while 1:
        try:
            yield wiimote.eventqueue[0]
        except IndexError:
            break
        wiimote.eventqueue = wiimote.eventqueue[1:]


def do(func):
    global wiimote
    wiimote.do(func)
    return

def start_status():
    global wiimote
    org_mode = wiimote.set_mode
    wiimote.Wii_Remote_mode(0x20) #change to status mode
    wiimote.Report_0x15(0x00) #send status requeset
    return org_mode

def end_status(org_mode):
    global wiimote
    wiimote.Wii_Remote_mode(org_mode) #restore mode
    return

def running():
    global wiimote

    return wiimote.go

def getFlag_format(flag):
    flags = ""
    for f, desc in FLAG.items():
        if flag & f:
            flags += desc
            flags += "\n"
    if not flags: flags = "None"
    return flags

def getLED_format(LEDs):
    led = ""
    for l in LED:
        if LEDs & l:
            led += "on "
        else:
            led += "off "
    return led

def setLED(c):
    global wiimote
    wiimote.Report_0x11(c)
    return

def setRumble(b):
    global wiimote
    wiimote.Report_0x13(b)
    return

def whileRumble(msec):
    global wiimote
    wiimote.Report_0x13(1)
    pygame.time.wait(msec)
    wiimote.Report_0x13(0)
    return

def whileRumble500msec():
    whileRumble(500)
    return

def quit(limited=False):
    global wiimote
    wiimote.quit(limited)
    wiimote.join()
    return
