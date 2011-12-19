#!/usr/bin/env python
#-*- coding:utf-8 -*-

from __future__ import with_statement #for version <= 2.5
import wiiremote
import pygame
import visual
import time
import math
import ConfigParser
import sys
import os.path



class WiiRemoteApp(object):
    def __init__(self):
        self.param = {"conf_name":"settings.cfg", # load from argv or not
                      "width":0, "height":0, # load from conf
                      "sidebar_width":15, "sidebar_height":30,
                      "colors":[(255, 0, 0), (0, 255, 0), (0, 0, 255)],  #for graph
                      "acc_zero":[], "acc_gain":[], # load from conf
                      "saber":False, "org_mode":None,
                      "gyro_zero":[], # load from conf
                      "gyro_gain":8192 / (1.35 * 1000 / 2.27), #static
                      "gyro_fast":2000.0 / 440, #static
                      "view-axis":[True, True, False, True, True, True, True, True, True],
                      "acc_thresh":0, "gyro_thresh":0, #load from conf
                      "maxA":0.1, "maxG":0.1, "maxO":math.pi,
                      "sound_names":["on", "off", "swing1", "strike1", "fall"],
                      "patterns":["if acc[i] <= 0.5", 
                                  "if sign(acc) != sign(prev_acc)",
                                  "if gyro_rotate[i] < (math.pi/9)", 
                                  "if acc_theta[i]+acc_theta[i+1] < (math.pi/2)", 
                                  "if 1 < acc[i] < 2", 
                                  "if acc[i] >= 2"],
                      "cur_pattern":0,
                      "fall":False}
        self.data = {"accel":[[], [], []], "gyro_speed":[[], [], []], 
                     "prev_time":time.time(), "prev_acc_average":[0,0,0],
                     "prev_accel":[0, 0, 0], "graph_accel":None,
                     "prev_acc_orient":[0,0,0], "graph_acc_orient":None,
                     "raw_gyro":[],
                     "prev_gyro":[0, 0, 0], "graph_gyro":None,
                     "prev_gyro_orient":[0,0,0], "graph_gyro_orient":None,
                     "prev_average_orient":[0, 0, 0], "graph_average_orient":None,}
        self.visual = {"wiiobj":[None,None,None], "axis":[None, None, None]*3, "text":[None,None,None]}
        
        # check exec options
        self.option = {"button":False, "average_orient":False, "accel":False, "acc_orient":False, "sound":False, "fall":True, "gyro":False, "gyro_orient":False, "save":False, "3D":"average", "limited":False,}
        c = 1
        while c <= len(sys.argv[1:]):
            if sys.argv[c] in ["--button", "-b"]:
                self.option["button"] = True
                c += 1
            elif sys.argv[c] in ["--average", "-av"]:
                self.option["average_orient"] = True
                c += 1
            elif sys.argv[c] in ["--acc", "-a"]:
                self.option["accel"] = True
                c += 1
            elif sys.argv[c] in ["--acc_orient", "-ao"]:
                self.option["acc_orient"] = True
                c += 1
            elif sys.argv[c] in ["--gyro", "-g"]:
                self.option["gyro"] = True
                c += 1
            elif sys.argv[c] in ["--gyro_orient", "-go"]:
                self.option["gyro_orient"] = True
                c += 1
            elif sys.argv[c] in ["--sound-on", "-so"]:
                self.option["sound"] = True
                c += 1
            elif sys.argv[c] in ["--fall-detect", "-fd"]:
                self.option["fall"] = False
                c += 1
            elif sys.argv[c] in ["--limited", "-l"]:
                self.option["limited"] = True
                c += 1
            elif sys.argv[c] in ["--config", "-c"]:
                if os.path.isfile(sys.argv[c+1]):
                    self.param["conf_name"] = sys.argv[c+1]
                else:
                    print ("Error!\n" +
                           "  Not found config file: '%s'\n" % sys.argv[c+1]+ 
                           "  --help or -h to show usage.")
                    sys.exit(1)
                    return
                c += 2
            elif "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
                print (
                    "  Usage: %s [options]\n" % sys.argv[0] + 
                    "\t--button,-b             Enable press or release button report.\n" +
                    "\t--average,-av           Enable the average data report.\n" +
                    "\t--acc,-a                Enable accel data report.\n" + 
                    "\t--acc_orient,-ao        Enable orient data report calclated from acc.\n" + 
                    "\t--gyro,-g               Enable gyro data report.\n" +
                    "\t--gyro-orient,-go       Enable orient data report calclated from gyro.\n" +
                    "\t--sound-on,-so          Enable light-saber sound(not work).\n" +
                    "\t--fall-detect,-fd       Disable fall detection.\n" +
                    "\t--config,-c [filename]  Set file name of config.\n" +
                    "\t--help,-h               Show this usage.\n"
                    )
                sys.exit(1)
                return
            else:
                print "Unknown option:", sys.argv[c]
                c += 1
        
        if self.option["sound"]: self.sounds = {}
    
    def init_sound(self):
        change = False
        print "[--- Loading the sounds ---]"
        pygame.mixer.init()
        if not self.conf.has_section("SOUNDS"):
            self.conf.add_section("SOUNDS")
        for sname in self.param["sound_names"]:
            if not self.conf.has_option("SOUNDS", sname):
                self.conf.set("SOUNDS", sname, raw_input("sound file use for %s >" % sname).strip())
                change = True
            self.sounds[sname] = pygame.mixer.Sound(self.conf.get("SOUNDS", sname))
        
        if change:
            with open(self.param["conf_name"], "wb") as fd:
                self.conf.write(fd)
        print ""
        return

    def play_sound(self, sname, busy=False, stop=False):
        if not pygame.mixer.get_init():
            self.init_sound()
        if stop: # stop before play
            pygame.mixer.stop()
        if busy: # don't play if busy
            if not pygame.mixer.get_busy():
                return self.sounds[sname].play().get_busy()
        else:
            return self.sounds[sname].play().get_busy()

    def load_conf(self):
        self.conf = ConfigParser.SafeConfigParser()
        self.conf.read(self.param["conf_name"])
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
        #screen sizes
        self.param["width"] = int(width)
        self.param["height"] = int(height)
        self.param["width_"] = self.param["width"] - self.param["sidebar_width"]*2
        self.param["height_"] = self.param["height"] -self.param["sidebar_height"]*2
        self.data["graph_accel"] = [self.param["height"] / 2]*3
        self.data["graph_acc_orient"] = [self.param["height"] / 2]*3
        self.data["graph_gyro"] = [self.param["height"] / 2]*3
        self.data["graph_gyro_orient"] = [self.param["height"] / 2]*3
        self.data["graph_average_orient"] = [self.param["height"] / 2]*3
        

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
            for c in xrange(3):
                self.param["acc_zero"][c] = float(self.conf.get("ACC_ZERO", ["x", "y", "z"][c]))
                self.param["acc_gain"][c] = float(self.conf.get("ACC_GAIN", ["x", "y", "z"][c]))
        #gyro
        if not self.conf.has_section("GYRO_ZERO"):
            self.conf.add_section("GYRO_ZERO")
            change = True
        if self.conf.has_option("GYRO_ZERO", "pitch") and self.conf.has_option("GYRO_ZERO", "roll") and self.conf.has_option("GYRO_ZERO", "yaw"):
            self.param["gyro_zero"] = [0,0,0]
            for c in xrange(3):
                self.param["gyro_zero"][c] = float(self.conf.get("GYRO_ZERO", ["pitch", "roll", "yaw"][c]))
        #thresh
        if not self.conf.has_section("THRESH"):
            self.conf.add_section("THRESH")
            change = True
        if self.conf.has_option("THRESH", "acc") and self.conf.has_option("THRESH", "gyro"):
            self.param["acc_thresh"] = float(self.conf.get("THRESH", "acc"))
            self.param["gyro_thresh"] = float(self.conf.get("THRESH", "gyro"))
            
        if change:
            with open(self.param["conf_name"], "wb") as fd:
                self.conf.write(fd)
        return
    
    def init_sensors(self, force_acc=False, force_gyro=False, save=True):
        settings = ["horizontal with the A button facing up", "IR sensor down on the table so the expansion port is facing up", "laying on its side, so the left side is facing up"]
        change = False
        print "[--- Initalize acceleration ---]"
        if not self.param["acc_zero"] or force_acc == True: #or not param["acc_gain"]:
            acc = [None, None, None]
            self.param["acc_zero"] = [0, 0, 0]
            self.param["acc_gain"] = [0, 0, 0]
            for i in xrange(3):
                print "%d. Set the WiiRemote %s, and press A button >" % (i+1, settings[i])
                while not self.event_handling():
                    pygame.time.wait(100)
                else: # when pressed [A]
                    acc[i] = [self.data["accel"][c][-1] for c in xrange(3)]
            #calc
            self.param["acc_zero"][0] = (acc[0][0] + acc[1][0]) / 2
            self.param["acc_zero"][1] = (acc[0][1] + acc[2][1]) / 2
            self.param["acc_zero"][2] = (acc[1][2] + acc[2][2]) / 2
            self.param["acc_gain"][0] = acc[2][0] - self.param["acc_zero"][0]
            self.param["acc_gain"][1] = acc[1][1] - self.param["acc_zero"][1]
            self.param["acc_gain"][2] = acc[0][2] - self.param["acc_zero"][2]
            for c in xrange(3):
                self.conf.set("ACC_ZERO", ["x", "y", "z"][c], str(self.param["acc_zero"][c]))
                self.conf.set("ACC_GAIN", ["x", "y", "z"][c], str(self.param["acc_gain"][c]))
            change = True
            
        print "acc_zero =", self.param["acc_zero"]
        print "acc_gain =", self.param["acc_gain"]
        print "acc_thresh =", self.param["acc_thresh"]
        print ""
        print "[--- Initalize gyro ---]"
        if not self.param["gyro_zero"] or force_gyro == True:
            self.param["gyro_zero"] = [0,0,0]
            print "Put the WiiRemote horizontally, and press A button >"
            while not self.event_handling():
                pygame.time.wait(100)
            else: # when pressed get gyro
                self.param["gyro_zero"] = [self.data["raw_gyro"][c] for c in xrange(3)]
            for c in xrange(3):
                self.conf.set("GYRO_ZERO", ["pitch", "roll", "yaw"][c], str(self.param["gyro_zero"][c]))
            change = True
        print "gyro_zero =", self.param["gyro_zero"]
        print "gyro_thresh =", self.param["gyro_thresh"]
        print ""

        if change and save == True: # save changes
            with open(self.param["conf_name"], "wb") as fd:
                self.conf.write(fd)
        
        return
    
    def event_handling(self):
        if not wiiremote.running():
            return 1
        for event in wiiremote.get_queue():
            if event.type == wiiremote.WIIMOTE_ACCEL_GYRO:
                self.accel_gyro(event.accel, event.gyro, event.fast_mode, event.time)
                continue
        for event in pygame.event.get():
            #print event
            if event.type == pygame.QUIT:
                return 1
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return 1
                elif event.key == pygame.K_a:
                    self.param["view-axis"][0] = not self.param["view-axis"][0]
                    continue
                elif event.key == pygame.K_b:
                    self.param["view-axis"][1] = not self.param["view-axis"][1]
                    continue
                elif event.key == pygame.K_c:
                    self.param["view-axis"][2] = not self.param["view-axis"][2]
                    continue
                elif event.key == pygame.K_d:
                    self.param["view-axis"][3] = not self.param["view-axis"][3]
                    continue
                elif event.key == pygame.K_e:
                    self.param["view-axis"][4] = not self.param["view-axis"][4]
                    continue
                elif event.key == pygame.K_f:
                    self.param["view-axis"][5] = not self.param["view-axis"][5]
                    continue
                elif event.key == pygame.K_x:
                    self.param["view-axis"][6] = not self.param["view-axis"][6]
                    continue
                elif event.key == pygame.K_y:
                    self.param["view-axis"][7] = not self.param["view-axis"][7]
                    continue
                elif event.key == pygame.K_z:
                    self.param["view-axis"][8] = not self.param["view-axis"][8]
                    continue
            elif event.type == wiiremote.WIIMOTE_BUTTON_PRESS:
                if self.option["button"]: print event.button, "pressed"
                
                if event.button == "Home":
                    return 1
                elif event.button == "A":
                    if self.param["gyro_zero"] == [0,0,0] or self.param["acc_zero"] == [0,0,0]:
                        return 1
                    if self.option["sound"]:
                        if self.param["saber"]:
                            self.play_sound("off")
                            self.param["saber"] = False
                            wiiremote.do(wiiremote.whileRumble500msec)
                        else:
                            self.play_sound("on")
                            self.param["saber"] = True
                            wiiremote.do(wiiremote.whileRumble500msec)
                        return 1
                    self.calibration(reset_gyro_zero=False)
                #elif event.button == "2":
                #    self.calibration(reset_gyro_zero=True)
                continue
            elif event.type == wiiremote.WIIMOTE_BUTTON_RELEASE:
                if self.option["button"]: print event.button, "released"
                continue
            elif event.type == wiiremote.WIIMOTE_STATUS:
                print "[--- status ---]"
                print "flag:\n ", wiiremote.getFlag_format(event.flag)
                print "LED:", wiiremote.getLED_format(event.LEDs)
                print "battery: %f %%" % (event.battery * 100)
                print ""
                if self.param["org_mode"]:
                    wiiremote.end_status(self.param["org_mode"]) # restore mode
                    self.param["org_mode"] = None
                    return 1
                continue
        else:
            return None
        
    def get_status(self):
        self.param["org_mode"] = wiiremote.start_status()
        while not self.event_handling():
            pygame.time.wait(10)
        return

    def calibration(self, reset_gyro_zero=False):
        print "[--- calibration --]"
        self.data["prev_gyro_orient"] = [0,0,0]
        self.data["graph_gyro_orient"] = [self.param["height"] / 2]*3
        self.data["prev_acc_orient"] = [0,0,0]
        self.data["graph_gyro_orient"] = [self.param["height"] / 2]*3
        self.data["prev_average_orient"] = [0,0,0]
        self.data["graph_average_orient"] = [self.param["height"] / 2]*3
        if reset_gyro_zero:
            self.param["gyro_zero"] = []
            self.init_sensors(force_gyro=True, save=False)
        for i in xrange(3):
            self.visual["wiiobj"][i].visible = False
        self.init_visual(only_wiiobj=True)
        return
    
    def turning_angle(self, old_theta, rotate):
        theta = old_theta + rotate
        
        #theta = min(self.param["maxO"], max(theta, -self.param["maxO"])) # limit turning over 360 deg
        
        theta %= (self.param["maxO"]*2)
        if theta == self.param["maxO"]:
            return self.param["maxO"]        
        elif theta > self.param["maxO"]:
            return theta - self.param["maxO"]*2
        else:
            return theta
        ###
        #if rotate < -180:
        #    return 180
        #elif rotate > 180:
        #    return -180
        #else:
        #    return old_theta + rotate
    
    def accel_gyro(self, raccel, rgyro, rfast, time):
        if not self.param["acc_zero"] or not self.param["gyro_zero"]:
            return
        frametime = time - self.data["prev_time"]        

        acc, acc_theta = self.accel(raccel, frametime)
        gyro_rotate = self.gyro(rgyro, rfast, frametime)
        
        if not acc or not gyro_rotate:
            return
        else:
            # saber's sound
            if self.option["sound"] and self.param["saber"]:
                if (4 > abs(acc[0]) >= 1.5) or (4 > abs(acc[1]) >= 2.5) or (4 > abs(acc[2]) >= 2.5):
                    self.play_sound("swing1", True)
                elif (abs(acc[0]) >= 4) or (abs(acc[1]) >= 3) or (abs(acc[2]) >= 3): 
                    self.play_sound("strike1", False, stop=True)
            # free fall detection
            if self.option["fall"]:
                if abs(acc[0]) * 10 < 1 and abs(acc[1]) * 10 < 1 and abs(acc[2]) * 10 < 1 and not pygame.mixer.get_busy():
                    print "Fall!!"
                    self.param["fall"] = True
                    if self.option["sound"]:
                        self.play_sound("fall")
                
        ## calc average routine ##
        
        # select correct angle of acc_orient
        for i in xrange(3):
            if acc_theta[i] <= 180:
                if abs(self.turning_angle(self.data["prev_average_orient"][i], gyro_rotate[i]) - acc_theta[i]) < abs(self.turning_angle(self.data["prev_average_orient"][i], gyro_rotate[i]) - (180 - acc_theta[i])):
                    acc_theta[i] = 180 - acc_theta[i]
                    print self.turning_angle(self.data["prev_average_orient"][i], gyro_rotate[i]),
                    print abs(self.turning_angle(self.data["prev_average_orient"][i], gyro_rotate[i]) - acc_theta[i]),
                    print self.turning_angle(self.data["prev_average_orient"][i], gyro_rotate[i]),
                    print abs(self.turning_angle(self.data["prev_average_orient"][i], gyro_rotate[i]) - (180 - acc_theta[i]))
            else:
                if abs(self.turning_angle(self.data["prev_average_orient"][i], gyro_rotate[i]) - acc_theta[i]) < abs(self.turning_angle(self.data["prev_average_orient"][i], gyro_rotate[i]) - (540 - acc_theta[i])):
                    acc_theta[i] = 540 - acc_theta[i]
                    print "adjust"
        if acc[0]+acc[1]+acc[2] <= 3/math.sqrt(2):
            #加速度の和が3/sqrt(2)G以下のとき (10:0)
            self.param["cur_pattern"] = 0
            rotate = [acc_theta[i] - self.data["prev_average_orient"][i] for i in xrange(2)]
        elif (acc[0] < 0 < self.data["prev_acc_average"][0] or acc[0] > 0 > self.data["prev_acc_average"][0]) or (acc[1] < 0 < self.data["prev_acc_average"][1] or acc[1] > 0 > self.data["prev_acc_average"][1]) or (acc[2] < 0 < self.data["prev_acc_average"][2] or acc[2] > 0 > self.data["prev_acc_average"][2]):
            #加速度の符号が逆になったとき
            self.param["cur_pattern"] = 1
            rotate = [gyro_rotate[i] for i in xrange(2)]
        elif gyro_rotate[0] < (math.pi/5) and gyro_rotate[1] < (math.pi/5) and gyro_rotate[2] < (math.pi/5):
            #ジャイロから算出した角度がそれぞれ36度以下のとき (加速度に外力が加わっている→並進時はジャイロのデ-タのみ)
            self.param["cur_pattern"] = 2
            rotate = [gyro_rotate[i] for i in xrange(2)]
        elif acc_theta[0]+acc_theta[1] <= (math.pi/2) and acc_theta[1]+acc_theta[2] <= (math.pi/2) and acc_theta[2]+acc_theta[0] <= (math.pi/2):
            #加速度から算出した二つの角を合せて90度以下のとき (重力加速度以外の加速度が入っていない→静止時は加速度のデ-タのみ)
            self.param["cur_pattern"] = 3
            rotate = [acc_theta[i] - self.data["prev_average_orient"][i] for i in xrange(2)]
        elif acc[1] < 2 and acc[1] < 2 and acc[2] < 2:
            #加速度が各軸2G以下のとき (1:9)
            self.param["cur_pattern"] = 4
            rotate = [((acc_theta[i] - self.data["prev_average_orient"][i])*1 + gyro_rotate[i]*9) / 10 for i in xrange(2)]
        else:
            #加速度が各軸2G以上のとき (0:10)
            self.param["cur_pattern"] = 5
            rotate = [((acc_theta[i] - self.data["prev_average_orient"][i])*0 + gyro_rotate[i]*10) / 10 for i in xrange(2)]
        rotate.append(gyro_rotate[2])
        ## end rotine ##

        # 3D
        self.visual["wiiobj"][2].rotate(angle=-rotate[0], axis=(1,0,0))
        self.visual["wiiobj"][2].rotate(angle=rotate[1], axis=(0,1,0))
        self.visual["wiiobj"][2].rotate(angle=rotate[2], axis=(0,0,1))
        theta = [self.turning_angle(self.data["prev_average_orient"][i], rotate[i]) for i in xrange(3)]
        # graph
        for i in xrange(3):
            self.data["graph_average_orient"][i] = int((theta[i] * self.param["height_"] / self.param["maxO"] + self.param["height_"]) / 2)
            self.data["graph_average_orient"][i] = max(0, min(self.param["height_"] - 1, self.data["graph_average_orient"][i]))
        
        if self.option["average_orient"]:
            print "average_orient:", [visual.degrees(theta[i]) for i in xrange(3)]
        
        self.data["prev_average_orient"] = theta
        self.data["prev_time"] = time
        return

    def accel(self, data, frametime):
        ## accel ##
        acc = [(data[i] - self.param["acc_zero"][i]) / self.param["acc_gain"][i] for i in xrange(3)]
        
        cutoff_acc = [i for i in xrange(3) if abs(self.data["prev_accel"][i] - acc[i]) > self.param["acc_thresh"]]
        self.data["prev_accel"] = acc
        if len(cutoff_acc) > 0:
            for i in xrange(3):
                self.data["accel"][i].append(acc[i])
            if len(self.data["accel"][0]) >= 2:
                acc_average = [sum(self.data["accel"][i])/2 for i in xrange(3)]
                within = [max(min(acc_average[i], 1), -1) for i in xrange(3)]
                if self.option["accel"]:
                    print "accel", acc_average
                theta = [math.asin(within[i]) for i in [1,0,2]] # tricky?
                if self.option["acc_orient"]:
                    print "acc_orient", theta
                
                for i in cutoff_acc: # graph
                    self.data["graph_accel"][i] = int((acc_average[i] * self.param["height_"] / self.param["maxA"] + self.param["height_"]) / 2)
                    self.data["graph_accel"][i] = max(0, min(self.param["height_"] - 1, self.data["graph_accel"][i]))
                    self.data["graph_acc_orient"][i] = int((theta[i] * self.param["height_"] / self.param["maxO"] + self.param["height_"]) / 2)
                    self.data["graph_acc_orient"][i] = max(0, min(self.param["height_"] - 1, self.data["graph_acc_orient"][i]))

                rotate = (-theta[0]+self.data["prev_acc_orient"][0],
                           theta[1]-self.data["prev_acc_orient"][1],)
                self.data["accel"] = [self.data["accel"][i][1:] for i in xrange(3)]

                self.visual["wiiobj"][0].rotate(angle=rotate[0], axis=(1,0,0))
                self.visual["wiiobj"][0].rotate(angle=rotate[1], axis=(0,1,0))
                self.data["prev_acc_orient"] = theta
                self.data["prev_acc_average"] = acc_average
                return acc, theta
        return (None, None)
        
        
    def gyro(self, data, fast_mode, frametime):
        ## gyro ##
        self.data["raw_gyro"] = data
        gyro_speed = [visual.radians((data[i] - self.param["gyro_zero"][i]) / self.param["gyro_gain"]) for i in xrange(3)]
        for i in xrange(3):
            if fast_mode[i]:
                gyro_speed[i] *= self.param["gyro_fast"]
        
        cutoff = [i for i in xrange(3) if abs(gyro_speed[i]) > self.param["gyro_thresh"]]
        if len(cutoff):
            for i in xrange(3):
                self.data["gyro_speed"][i].append(gyro_speed[i])
            if len(self.data["gyro_speed"][0]) >= 3:
                gyro_speed_average = [sum(self.data["gyro_speed"][i])/3 for i in xrange(3)]
                gyro = [gyro_speed_average[i] * frametime for i in xrange(3)]
                theta = [self.turning_angle(self.data["prev_gyro_orient"][i], gyro[i]-self.data["prev_gyro_orient"][i]) for i in xrange(3)]
                if self.option["gyro"]:
                    print "gyro", [visual.degrees(gyro_speed_average[i]) for i in xrange(3)]
                if self.option["gyro_orient"]:
                    print "gyro_orient", [visual.degrees(theta[i]) for i in xrange(3)]
                for i in cutoff: # graph
                    self.data["graph_gyro"][i] = int((gyro_speed_average[i] * self.param["height_"] / self.param["maxG"] + self.param["height_"]) / 2)
                    self.data["graph_gyro"][i] = max(0, min(self.param["height_"] - 1, self.data["graph_gyro"][i]))
                    self.data["graph_gyro_orient"][i] = int((theta[i] * self.param["height_"] / self.param["maxO"] + self.param["height_"]) / 2)
                    self.data["graph_gyro_orient"][i] = max(0, min(self.param["height_"] - 1, self.data["graph_gyro_orient"][i]))
                    
                self.visual["wiiobj"][1].rotate(angle=-gyro[0], axis=(1,0,0))
                self.visual["wiiobj"][1].rotate(angle=-gyro[1], axis=(0,1,0))
                self.visual["wiiobj"][1].rotate(angle=gyro[2], axis=(0,0,1))
                self.data["prev_gyro_orient"] = theta
                self.data["gyro_speed"] = [self.data["gyro_speed"][i][1:] for i in xrange(3)]
                return (-gyro[0], -gyro[1], gyro[2])
        return None
        

    def init_visual(self, only_wiiobj=False):
        visual_pos = ((0, 0, 0), (7,7,0), (14,14,0))
        if not only_wiiobj:
            #vpython
            visual.scene.width=self.param["width"] * 3
            visual.scene.height=self.param["height"]
            visual.scene.title = "3D WiiMote Simulation"
            visual.scene.forward = visual.vector(1,0,0) # not to error ?
            visual.scene.up = visual.vector(0,0,1)
            visual.scene.forward = visual.vector(-1,1,-1)
            visual.scene.center = (7,7,0)
            visual.scene.scale = (0.07, 0.07, 0.07)
            visual.scene.autoscale = 0
            visual.scene.x = 0
            visual.scene.y = 30
            
            self.visual["axis"] = [(visual.arrow(pos=visual_pos[i], color=visual.color.red, axis=(3,0,0), headwidth=1, shaftwidth=0.5, fixedwidth=1),
                                    visual.arrow(pos=visual_pos[i], color=visual.color.green, axis=(0,3,0), headwidth=1, shaftwidth=0.5, fixedwidth=1),
                                    visual.arrow(pos=visual_pos[i], color=visual.color.blue, axis=(0,0,3), headwidth=1, shaftwidth=0.5, fixedwidth=1))
                                   for i in xrange(3)]
            self.visual["text"] = [visual.label(text="accel", pos=(1, -1, -4), color=visual.color.white),
                                   visual.label(text="gyro", pos=(8, 6, -4), color=visual.color.white),
                                   visual.label(text="accel + gyro", pos=(15, 13, -4), color=visual.color.white),]
        self.visual["wiiobj"] = [visual.box(pos=visual_pos[i], length=2, height=6, width=1, color=visual.color.white, axis=(1,0,0)) #x=length, y=height, z=width
                                 for i in xrange(3)]

        return
    
    def quit_visual(self):
        visual.scene.hide()
        return

    def main(self):
        # initalize
        self.load_conf()
        pygame.init()
        # sound
        if self.option["sound"]:
            self.init_sound()
        # pygame
        old = [self.param["height"] / 2] * 9
        font_title = pygame.font.Font("font/ipag.ttf", int(self.param["sidebar_width"]*1.5))
        font_small = pygame.font.Font("font/ipag.ttf", int(self.param["sidebar_width"]))
        screen = pygame.display.set_mode((self.param["width"] *3 , self.param["height"]+self.param["sidebar_height"]*3), )
        screen.fill((255, 255, 255))
        pygame.display.set_caption(u"WiiRemote Orientation Graph")
        notes = pygame.Surface((self.param["width_"]/2.0-10, self.param["sidebar_height"]*3-10)).convert()
        acc_graph = pygame.Surface((self.param["width_"], self.param["height_"])).convert()
        acc_base = pygame.Surface((self.param["width"], self.param["height"])).convert()
        
        gyro_graph = pygame.Surface((self.param["width_"], self.param["height_"])).convert()
        gyro_base = pygame.Surface((self.param["width"], self.param["height"])).convert()        

        average_graph = pygame.Surface((self.param["width_"], self.param["height_"])).convert()
        average_base = pygame.Surface((self.param["width"], self.param["height"])).convert()
        
        acc_title = font_title.render(u"加速度", True, (0, 0, 0))
        gyro_title = font_title.render(u"ジャイロ", True, (0,0,0))
        average_title = font_title.render(u"加速度＋ジャイロ", True, (0,0,0))
        pitch_font = font_small.render(u"pitch角", True, (255,255,255))#(0,0,0))
        roll_font = font_small.render(u"roll角", True, (255,255,255))#(0,0,0))
        yaw_font = font_small.render(u"yaw角", True, (255,255,255))#(0,0,0))

        for i in xrange(3):
            pygame.draw.line(notes, self.param["colors"][i], (3, self.param["sidebar_height"]*i+self.param["sidebar_height"]/2.0-5), (self.param["width_"]/4.0-3, self.param["sidebar_height"]*i+self.param["sidebar_height"]/2.0-5))
        notes.blit(pitch_font, (self.param["width_"]/4.0, 0))
        notes.blit(roll_font, (self.param["width_"]/4.0, self.param["sidebar_height"]))
        notes.blit(yaw_font, (self.param["width_"]/4.0, self.param["sidebar_height"]*2))
        
        #visual
        self.init_visual()

        # connect WiiRemote
        wiiremote.init()
        if not wiiremote.running():
            return
        # sensors
        self.init_sensors()
        # get status
        if not self.option["limited"]: self.get_status() 
                
        print "[--- start ---]\n"
        if self.option["sound"]:
            print "press [A] to on/off saber"

        while not self.event_handling():
            pygame.display.update()
            pygame.time.wait(10)
            
            bgcolor = (255, 255, 255)
            if self.param["fall"]:
                self.param["fall"] = False
                bgcolor = (255, 0, 0)
                
            screen.fill(bgcolor)
            screen.blit(notes, (self.param["width"]*2.5, self.param["height"]))
            acc_graph.blit(acc_graph, (-1, 0))
            gyro_graph.blit(gyro_graph, (-1, 0))
            average_graph.blit(average_graph, (-1, 0))
            for c in xrange(3):
                if self.param["view-axis"][c]:
                    pygame.draw.line(acc_graph, self.param["colors"][c], (self.param["width_"]-3, old[c]), (self.param["width_"]-2, self.data["graph_acc_orient"][c]))
                    old[c] = self.data["graph_acc_orient"][c]
            
                if self.param["view-axis"][c+3]:
                    pygame.draw.line(gyro_graph, self.param["colors"][c], (self.param["width_"]-3, old[c+3]), (self.param["width_"]-2, self.data["graph_gyro_orient"][c]))
                    old[3+c] = self.data["graph_gyro_orient"][c]
                if self.param["view-axis"][c+6]:
                    pygame.draw.line(average_graph, self.param["colors"][c], (self.param["width_"]-3, old[c+6]), (self.param["width_"]-2, self.data["graph_average_orient"][c]))
                    old[6+c] = self.data["graph_average_orient"][c]
                    
            acc_base.fill(bgcolor)
            gyro_base.fill(bgcolor)
            average_base.fill(bgcolor)
                
            acc_base.blit(acc_graph, (self.param["sidebar_width"], self.param["sidebar_height"]))
            gyro_base.blit(gyro_graph, (self.param["sidebar_width"], self.param["sidebar_height"]))
            average_base.blit(average_graph, (self.param["sidebar_width"], self.param["sidebar_height"]))
            
            acc_base.blit(acc_title, (self.param["sidebar_width"]+10, 0))
            gyro_base.blit(gyro_title, (self.param["sidebar_width"], 0))
            average_base.blit(average_title, (self.param["sidebar_width"], 0))
            
            pygame.draw.line(acc_base, (144, 144, 144), (self.param["sidebar_width"], self.param["sidebar_height"] + self.param["height_"]/2), (self.param["sidebar_width"]+self.param["width_"], self.param["sidebar_height"]+self.param["height_"]/2))
            pygame.draw.line(gyro_base, (144, 144, 144), (self.param["sidebar_width"], self.param["sidebar_height"] + self.param["height_"]/2), (self.param["sidebar_width"]+self.param["width_"], self.param["sidebar_height"]+self.param["height_"]/2))
            pygame.draw.line(average_base, (144, 144, 144), (self.param["sidebar_width"], self.param["sidebar_height"] + self.param["height_"]/2), (self.param["sidebar_width"]+self.param["width_"], self.param["sidebar_height"]+self.param["height_"]/2))
            
            screen.blit(acc_base, (0,0))
            screen.blit(gyro_base, (self.param["width"], 0))
            screen.blit(average_base, (self.param["width"]*2, 0))

            for p in xrange(len(self.param["patterns"])):
                if self.param["cur_pattern"] == p:
                    screen.fill((255, 0, 255), (self.param["sidebar_width"], self.param["height"]+self.param["sidebar_width"]*p, self.param["width"]*2-self.param["sidebar_width"], self.param["sidebar_width"])) # from 2 to 2.25 ?#############
                screen.blit(font_small.render(self.param["patterns"][p], True, (0,0,0)), (self.param["sidebar_width"], self.param["height"]+self.param["sidebar_width"]*p))
        else:
            wiiremote.quit(self.option["limited"])
            self.quit_visual()
            sys.exit(1)


if __name__ == "__main__":
    app = WiiRemoteApp()
    app.main()
