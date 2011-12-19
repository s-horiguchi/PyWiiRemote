#!/usr/bin/env python
#-*- coding:utf-8 -*-

from __future__ import with_statement #for version <= 2.5
import wiiremote_ocemp as wiiremote # changable
import pygame
from ocempgui.events import INotifyable
import visual
import time
import math
import ConfigParser
import sys

#[0x1F7F, 0x1F7F, 0x1F7F]
#conf
CONF_FILENAME = "settings.cfg"

#pygame
maxA = 5.0
maxT = 10.0
colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)] #x, y, z graph
sound_names = ["on", "off", "swing1", "strike1", "fall"]

usage = ["Horizontal with the A button facing up", "IR sensor down on the table so the expansion port is facing up", "Laying on its side, so the left side is facing up"]


class WiiRemoteApp(INotifyable):
    def __init__(self):
        # check exec options
        self.option = {"button":False, "accel":False, "acc_orient":False, "sound":False, "fall":False, "gyro":False, "save":False}
        if "--button" in sys.argv[1:] or "-b" in sys.argv[1:]:
            self.option["button"] = True
        if "--acc" in sys.argv[1:] or "-a" in sys.argv[1:]:
            self.option["accel"] = True
        if "--acc_orient" in sys.argv[1:] or "-ao" in sys.argv[1:]:
            self.option["acc_orient"] = True
        if "--gyro" in sys.argv[1:] or "-g" in sys.argv[1:]:
            self.option["gyro"] = True
        if "--sound-on" in sys.argv[1:] or "-so" in sys.argv[1:]:
            self.option["sound"] = True
        if "--fall-detect" in sys.argv[1:] or "-fd" in sys.argv[1:]:
            self.option["fall"] = True
        if "--config" in sys.argv[1:] or "-c" in sys.argv[1:]:
            pass
        if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
            print (
                "Usage: %s" % sys.argv[0] + 
                "--button,-b       Show press or release button.\n" +
                "--acc,-a          Show 3axis accel data.\n" + 
                "--acc_orient,-ao  Show 3axis orient data calclated from acc.\n" + 
                "--gyro,-g         Show 3axis gyro data.\n" +
                "--sound-on,-so    Enable light-saber sound.\n" +
                "--fall-detect,-fd Enable fall detection.\n" +
                "--help,-h         Show this message.\n"
                )
            return
        
        self.param = {"width":0, "height":0, "sidebar_width":15,
                      "acc_zero":[], "acc_gain":[], 
                      "saber":False, "org_mode":None,
                      "gyro_zero":[0x2000, 0x2050, 0x1F30], 
                      "gyro_gain":8192 / (1.35 * 1000 / 2.27), 
                      "gyro_fast":2000.0 / 440,
                      "running":True}
        self.data = {"accel":[[((0, 0, 0), 0)], ], "gyro":[[((0, 0, 0), 0), ], ]}
        self.visual = {"wiiobj":None, "axis":[None, None, None]}
        self.sounds = {}
    
    def load_conf(self):
    
        self.conf = ConfigParser.SafeConfigParser()
        self.conf.read(CONF_FILENAME)
        change = False
        #screen
        if not self.conf.has_section("SCREEN"): 
            self.conf.add_section("SCREEN")
        if not self.conf.has_option("SCREEN", "width"):
            width = raw_input("Screen width size >").strip()
            self.conf.set("SCREEN", "width", width)
            change = True
        else:
            width = self.conf.get("SCREEN", "width")
        if not self.conf.has_option("SCREEN", "height"):
            height = raw_input("Screen height size >").strip()
            self.conf.set("SCREEN", "height", height)
            change = True
        else:
            height = self.conf.get("SCREEN", "height")
        self.param["width"] = int(width)
        self.param["height"] = int(height)
        #accel
        if not self.conf.has_section("ACC_ZERO"): 
            self.conf.add_section("ACC_ZERO")
            change = True
        if not self.conf.has_section("ACC_GAIN"): 
            self.conf.add_section("ACC_GAIN")
            change = True
        if self.conf.has_option("ACC_ZERO", "x") and self.conf.has_option("ACC_ZERO", "y") and self.conf.has_option("ACC_ZERO", "z") and self.conf.has_option("ACC_GAIN", "x") and self.conf.has_option("ACC_GAIN", "y") and self.conf.has_option("ACC_GAIN", "z"):
            self.param["acc_zero"] = [0, 0, 0]
            self.param["acc_gain"] = [0, 0, 0]
            for c in range(3):
                self.param["acc_zero"][c] = float(self.conf.get("ACC_ZERO", ["x", "y", "z"][c]))
                self.param["acc_gain"][c] = float(self.conf.get("ACC_GAIN", ["x", "y", "z"][c]))
        if change:
            with open(CONF_FILENAME, "wb") as fd:
                self.conf.write(fd)
        return
        
    def init_sound(self):
        change = False
        print "[--- Loading sound ---]"
        pygame.mixer.init()
        if not self.conf.has_section("SOUNDS"):
            self.conf.add_section("SOUNDS")
        for sname in sound_names:
            if not self.conf.has_option("SOUNDS", sname):
                self.conf.set("SOUNDS", sname, raw_input("sound file use for %s >" % sname).strip())
                change = True
            self.sounds[sname] = pygame.mixer.Sound(self.conf.get("SOUNDS", sname))
        
        if change:
            with open(CONF_FILENAME, "wb") as fd:
                self.conf.write(fd)
        print ""
        return

    def init_accel(self):
        print "[--- Initalize accel ---]"
        if not self.param["acc_zero"]: #or not param["acc_gain"]:
            acc = [[], [], []]
            self.param["acc_zero"] = [0, 0, 0]
            self.param["acc_gain"] = [0, 0, 0]
            for i in range(3):
                print "%d. Set WiiRemote %s >" % (i+1, usage[i])
                while wiiremote.running() and not acc[i]:
                    pygame.time.wait(10)
                    if self.accel:
                        if self.param["acc_zero"] == [1, 1, 1]:
                            acc[i] = self.accel
            
            if not wiiremote.running():
                wiiremote.quit()
                return
            #calc
            self.param["acc_zero"][0] = (acc[0][0] + acc[1][0]) / 2
            self.param["acc_zero"][1] = (acc[0][1] + acc[2][1]) / 2
            self.param["acc_zero"][2] = (acc[1][2] + acc[2][2]) / 2
            self.param["acc_gain"][0] = acc[2][0] - self.param["acc_zero"][0]
            self.param["acc_gain"][1] = acc[1][1] - self.param["acc_zero"][1]
            self.param["acc_gain"][2] = acc[0][2] - self.param["acc_zero"][2]
            for c in range(3):
                self.conf.set("ACC_ZERO", ["x", "y", "z"][c], str(self.param["acc_zero"][c]))
                self.conf.set("ACC_GAIN", ["x", "y", "z"][c], str(self.param["acc_gain"][c]))
        
            with open(CONF_FILENAME, "wb") as fd:
                self.conf.write(fd)
        
        print "acc_zero =", self.param["acc_zero"]
        print "acc_gain =", self.param["acc_gain"]
        print ""
        return
    
    def notify(self, event): # ** IMPORTANT **
        if event.signal == "WIIMOTE_BUTTON_PRESS":
            if self.option["button"]: print event.data["button"], "pressed"
            if event.data["button"] == "Home":
                wiiremote.quit()
                return
            if event.data["button"] == "A": # in init_accel()
                if self.param["acc_zero"] == [0, 0, 0]:
                    self.param["acc_zero"] = [1, 1, 1]
                    return
                if self.option["sound"]:
                    if self.param["saber"]: # saber off
                        self.play_sound("off")
                        self.param["saber"] = False
                        wiiremote.do(wiiremote.whileRumble500msec)
                    else: # saber on
                        self.play_sound("on")
                        self.param["saber"] = True
                        wiiremote.do(wiiremote.whileRumble500msec)
                    return
        elif event.signal == "WIIMOTE_BUTTON_RELEASE":
            if self.option["button"]: print event.data["button"], "released"
            return
        elif event.signal == "WIIMOTE_ACCEL":
            self.accel(event.data)
            return
        elif event.signal == "WIIMOTE_GYRO":
            self.gyro(event.data)
            return
        elif event.signal == "WIIMOTE_STATUS":
            print "[--- status ---]"
            print "flag:\n ", wiiremote.getFlag_format(event.data["flag"])
            print "LED:", wiiremote.getLED_format(event.data["LEDs"])
            print "battery: %f %%" % (event.data["battery"] * 100)
            print ""
            wiiremote.end_status(self.param["org_mode"]) # restore mode
            self.param["org_mode"] = None
            return
        elif event.signal == "WIIMOTE_DISCONNECT":
            self.param["running"] = False
            sys.exit(1)
            return

    def play_sound(self, sname, busy=False, stop=False):
        if not pygame.mixer.get_init():
            print "init"
            self.init_sound()
        if stop: # stop before play
            pygame.mixer.stop()
        if busy: # don't play if busy
            if not pygame.mixer.get_busy():
                return self.sounds[sname].play().get_busy()
        else:
            return self.sounds[sname].play().get_busy()

    def get_status(self):
        self.param["org_mode"] = wiiremote.start_status()
        while wiiremote.running():
            if not self.param["org_mode"]:
                wiiremote.pause(False) #pause release
                break       
        return
    
    def accel(self, data):
        acc = [0, 0, 0]
        acc[0] = (data["accel"][0] - self.param["acc_zero"][0]) / self.param["acc_gain"][0]
        acc[1] = (data["accel"][1] - self.param["acc_zero"][1]) / self.param["acc_gain"][1]
        acc[2] = (data["accel"][2] - self.param["acc_zero"][2]) / self.param["acc_gain"][2]
        if self.option["accel"]: # output accel
            print "accel", acc
        
        if self.option["sound"] and self.param["saber"]: # saber's sound
            if (4 > abs(acc[0]) >= 1.5) or (4 > abs(acc[1]) >= 2.5) or (4 > abs(acc[2]) >= 2.5):
                self.play_sound("swing1", True)
            elif (abs(acc[0]) >= 4) or (abs(acc[1]) >= 3) or (abs(acc[2]) >= 3): 
                self.play_sound("strike1", False, stop=True)
        gx = max(min(acc[0], 1), -1)
        gy = max(min(acc[1], 1), -1)
        gz = max(min(acc[2], 1), -1)
        jx = math.asin(gx)# * 180 / math.pi
        jy = math.asin(gy)# * 180 / math.pi
        jz = math.asin(gz)# * 180 / math.pi
        if self.option["acc_orient"]: # output orient calclated by accel
            print "acc_orient", jx, jy, jz
        #visual
        self.visual["axis"][0].axis = (3+acc[0], 0, 0)
        self.visual["axis"][1].axis = (0, 3+acc[1], 0)
        self.visual["axis"][2].axis = (0, 0, 3+acc[2])
        self.visual["wiiobj"].axis = (gx, gy, gz)
        if self.option["fall"]: # free fall detection
            if abs(gx) * 10 < 1 and abs(gy) * 10 < 1 and abs(gz) * 10 < 1 and not pygame.mixer.get_busy():
                print "Fall!"
                if self.option["sound"]:
                    self.play_sound("fall")
        # save the data
        if int(self.data["accel"][-1][-1][1] / maxT) < int(data["time"] / maxT):
            self.data["accel"].append([])
        self.data["accel"][-1].append((acc, data["time"]))
        return

    def gyro(self, data):
        yaw_speed = (data["gyro"][0] - self.param["gyro_zero"][0]) / self.param["gyro_gain"]
        if data["fast_mode"][0]: yaw_speed *= self.param["gyro_fast"]
        pitch_speed = (data["gyro"][1] - self.param["gyro_zero"][0]) / self.param["gyro_gain"]
        if data["fast_mode"][1]: pitch_speed *= self.param["gyro_fast"]
        roll_speed = (data["gyro"][2] - self.param["gyro_zero"][2]) / self.param["gyro_gain"]
        if data["fast_mode"][2]: roll_speed *= self.param["gyro_fast"]
        frametime = self.data["gyro"][-1][-1][1] - data["time"]
        yaw_rotate = yaw_speed * frametime
        pitch_rotate = pitch_speed * frametime
        roll_rotate = roll_speed * frametime
        if self.option["gyro"]:
            print "gyro", yaw_rotate, pitch_rotate, roll_rotate
        # save the data
        if frametime > maxT:
            self.data["gyro"].append([])
        self.data["gyro"][-1].append((data["gyro"], data["time"]))
        return
    
    def main(self):
        #init
        self.load_conf()
        pygame.init()
        wiiremote.init(self)
        if not wiiremote.running(): return
        wiiremote.pause(True) #pause to get acc and gyro data
        
        #visual
        visual.scene.width = self.param["width"]
        visual.scene.height = self.param["height"]
        visual.scene.title = "WiiRemote"
        visual.scene.forward = visual.vector(1,0,0) # not to error ?
        visual.scene.up = visual.vector(0,0,1)
        visual.scene.forward = visual.vector(-1,1,-1)
        visual.scene.autoscale = 0
        self.visual["axis"][0] = visual.arrow(color=visual.color.red, axis=(3,0,0), headwidth=1, shaftwidth=0.5, fixedwidth=1)
        self.visual["axis"][1] = visual.arrow(color=visual.color.green, axis=(0,3,0), headwidth=1, shaftwidth=0.5, fixedwidth=1)
        self.visual["axis"][2] = visual.arrow(color=visual.color.blue, axis=(0,0,3), headwidth=1, shaftwidth=0.5, fixedwidth=1)
        self.visual["wiiobj"] = visual.box(pos=(0, 0, 0), length=1, height=4, width=1.5, color=visual.color.white,)

        #sound
        if self.option["sound"]:
            self.init_sound()

        #status
        self.get_status()
        
        #accel
        self.init_accel()
        acc = [0, 0, 0]

        #pygame
        old = [self.param["height"] / 2] * 3
        view = [True, True, True]
        screen = pygame.display.set_mode((self.param["width"], self.param["height"]))
        font = pygame.font.SysFont(None, int(self.param["sidebar_width"]*1.5))
        self.param["width_"] = self.param["width"] - self.param["sidebar_width"]

        print "[--- start ---]"
        if self.option["sound"]:
            print "press A to on/off saber"
        
        while self.param["running"]:
            #self.re.refresh()
            pygame.time.wait(100)
            pygame.display.update()

            screen.fill((0, 0, 0), (self.param["width_"], 0, self.param["sidebar_width"], self.param["height"]))
            screen.blit(screen, (-1, 0))

            for i in range(int(maxA*2+1)):
                screen.blit(font.render("%-d" % (maxA - i), True, (144, 144, 144)), (self.param["width_"], float(self.param["height"]) / (maxA*2) * i - self.param["sidebar_width"]*1.5/4))
                pygame.draw.line(screen, (144, 144, 144), (0, float(self.param["height"]) / (maxA*2) * i), (self.param["width_"], float(self.param["height"]) / (maxA*2) * i))
                
            #pygame
            for c in range(3): # 3axis
                if view[c]:
                    s = int((acc[c] * self.param["height"] / maxA + self.param["height"]) / 2)
                    s = max(0, min(self.param["height"] - 1, s))
                    pygame.draw.line(screen, colors[c], (self.param["width_"]-3, old[c]), (self.param["width_"]-2, s))
                    old[c] = s

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    wiiremote.quit()
                    sys.exit(1)
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        wiiremote.quit()
                        sys.exit(1)
                        return
                    if event.key == pygame.K_x:
                        if view[0]: view[0] = False
                        else: view[0] = True
                    elif event.key == pygame.K_y:
                        if view[1]: view[1] = False
                        else: view[1] = True
                    elif event.key == pygame.K_z:
                        if view[2]: view[2] = False
                        else: view[2] = True



if __name__ == "__main__":
    app = WiiRemoteApp()
    app.main()
