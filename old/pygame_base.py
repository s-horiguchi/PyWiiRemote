#!/usr/bin/env python
#-*- coding:utf-8 -*-

from __future__ import with_statement #for version <= 2.5
import wiiremote
import pygame
import time
import math
import ConfigParser
import sys
#[0x1F7F, 0x1F7F, 0x1F7F]
#conf
CONF_FILENAME = "settings.cfg"
param = {"width":0, "height":0, "acc_zero":[], "acc_gain":[], "saber":False, "gyro_zero":[0x2000, 0x2050, 0x1F30], "gyro_gain":8192 / (1.35 * 1000 / 2.27), "gyro_fast":2000.0 / 440}

#pygame
maxA = 5.0
side_width = 15
colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)] #x, y, z
snames = ["on", "off", "swing1", "strike1", "fall"]

usage = ["Horizontal with the A button facing up", "IR sensor down on the table so the expansion port is facing up", "Laying on its side, so the left side is facing up"]

def load_conf(divide=False):
    global conf, param
    conf = ConfigParser.SafeConfigParser()
    conf.read(CONF_FILENAME)
    change = False
    #screen
    if not conf.has_section("SCREEN"): 
        conf.add_section("SCREEN")
    if not conf.has_option("SCREEN", "width"):
        width = raw_input("Screen width size >").strip()
        conf.set("SCREEN", "width", width)
        change = True
    else:
        width = conf.get("SCREEN", "width")
    if not conf.has_option("SCREEN", "height"):
        height = raw_input("Screen height size >").strip()
        conf.set("SCREEN", "height", height)
        change = True
    else:
        height = conf.get("SCREEN", "height")
    param["width"] = int(width)
    param["height"] = int(height)
    if divide:
        param["width"] /= 2
        param["height"] /= 2
    #accel
    if not conf.has_section("ACC_ZERO"): 
        conf.add_section("ACC_ZERO")
        change = True
    if not conf.has_section("ACC_GAIN"): 
        conf.add_section("ACC_GAIN")
        change = True
    if conf.has_option("ACC_ZERO", "x") and conf.has_option("ACC_ZERO", "y") and conf.has_option("ACC_ZERO", "z") and conf.has_option("ACC_GAIN", "x") and conf.has_option("ACC_GAIN", "y") and conf.has_option("ACC_GAIN", "z"):
        param["acc_zero"] = [0, 0, 0]
        param["acc_gain"] = [0, 0, 0]
        for c in range(3):
            param["acc_zero"][c] = float(conf.get("ACC_ZERO", ["x", "y", "z"][c]))
            param["acc_gain"][c] = float(conf.get("ACC_GAIN", ["x", "y", "z"][c]))
    if change:
        with open(CONF_FILENAME, "wb") as fd:
            conf.write(fd)
    return
    
def init_sound():
    global conf, sounds
    sounds = {}
    change = False
    print "--- Loading sound ---"
    pygame.mixer.init()
    if not conf.has_section("SOUNDS"):
        conf.add_section("SOUNDS")
    for sname in snames:
        if not conf.has_option("SOUNDS", sname):
            conf.set("SOUNDS", sname, raw_input("sound file use for %s >" % sname).strip())
            change = True
        sounds[sname] = pygame.mixer.Sound(conf.get("SOUNDS", sname))
    
    if change:
        with open(CONF_FILENAME, "wb") as fd:
            conf.write(fd)
    print ""
    return

def init_accel():
    global conf, param
    print "--- Initalize accel ---"
    if not param["acc_zero"]: #or not param["acc_gain"]:
        acc = [[], [], []]
        param["acc_zero"] = [0, 0, 0]
        param["acc_gain"] = [0, 0, 0]
        for i in range(3):
            ready = False
            print "%d. Set WiiRemote %s >" % (i+1, usage[i])
            while wiiremote.wiimote.go and not acc[i]:
                pygame.time.wait(10)
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        wiiremote.quit()
                        return
                    if event.type == wiiremote.WIIMOTE_BUTTON_PRESS:
                        if event.button == "A":
                            ready = True
                    if event.type == wiiremote.WIIMOTE_ACCEL:
                        if ready == True:
                            acc[i] = [event.accel[c] for c in range(3)]
        
        if not wiiremote.wiimote.go:
            wiiremote.quit()
            return
        #calc
        param["acc_zero"][0] = (acc[0][0] + acc[1][0]) / 2
        param["acc_zero"][1] = (acc[0][1] + acc[2][1]) / 2
        param["acc_zero"][2] = (acc[1][2] + acc[2][2]) / 2
        param["acc_gain"][0] = acc[2][0] - param["acc_zero"][0]
        param["acc_gain"][1] = acc[1][1] - param["acc_zero"][1]
        param["acc_gain"][2] = acc[0][2] - param["acc_zero"][2]
        for c in range(3):
            conf.set("ACC_ZERO", ["x", "y", "z"][c], str(param["acc_zero"][c]))
            conf.set("ACC_GAIN", ["x", "y", "z"][c], str(param["acc_gain"][c]))
    
        with open(CONF_FILENAME, "wb") as fd:
            conf.write(fd)
    
    print "acc_zero =", param["acc_zero"]
    print "acc_gain =", param["acc_gain"]
    print ""
    return

def saber_on():
    #print "saber on"
    sounds["on"].play()
    param["saber"] = True
    wiiremote.whileRumble(500)
    return

def saber_off():
    #print "saber off"
    sounds["off"].play()
    param["saber"] = False
    wiiremote.whileRumble(500)
    return

def play_sound(sname, busy=False, stop=False):
    if stop: 
        pygame.mixer.stop()
    if busy:
        if not pygame.mixer.get_busy():
            sounds[sname].play()
    else:
        sounds[sname].play()
    return

def main():
    #exec options
    debug = {"button":False, "accel":False, "orient":False, "divide":False, "sound":True, "fall":False, "gyro":False, "save":False}
    if "--button" in sys.argv[1:]:
        debug["button"] = True
    if "--acc" in sys.argv[1:]:
        debug["accel"] = True
    if "--acc_orient" in sys.argv[1:]:
        debug["orient"] = True
    if "--gyro" in sys.argv[1:]:
        debug["gyro"] = True
    if "--divide-view" in sys.argv[1:]:
        debug["divide"] = True
    if "--sound-off" in sys.argv[1:]:
        debug["sound"] = False
    if "--fall-detect" in sys.argv[1:]:
        debug["fall"] = True
        debug["sound"] = True
    if "--config" in sys.argv[1:]:
        pass
    if "--help" in sys.argv[1:] or "-h" in sys.argv[1:]:
        print (
            "Usage: %s" % sys.argv[0] + 
            "--button      Show press or release button.\n" +
            "--acc         Show 3axis accel data.\n" + 
            "--acc_orient  Show 3axis orient data calclated from acc.\n" + 
            "--gyro        Show 3axis gyro data.\n" +
            "--divide-view Show divided every axis graph view.\n" +
            "--sound-off   Disable light-saber sound.\n" +
            "--fall-detect Enable fall detection.\n" +
               )
    #init
    global sounds, param
    load_conf(divide=debug["divide"])
    pygame.init()
    wiiremote.init()
    if not wiiremote.running(): return

    #sound
    wiiremote.pause(True) #pause 
    if debupg["sound"]:
        init_sound()

    #status
    wiiremote.status()
    print "--- status ---"
    print "flag:\n ", wiiremote.getFlag_p()
    print "LED:", wiiremote.getLED_p()
    print "battery: %f %%" % (wiiremote.getBattery() * 100)
    print ""
    wiiremote.pause(False) #pause release

    #accel
    init_accel()
    acc = [0, 0, 0]

    #gyro
    angle_yaw = 0
    angle_pitch = 0
    angle_roll = 0

    #pygame
    old = [param["height"] / 2] * 3
    view = [True, True, True]
    if debug["divide"]: screen = pygame.display.set_mode((param["width"], param["height"]*3))
    else: screen = pygame.display.set_mode((param["width"], param["height"]))
    font = pygame.font.SysFont(None, side_width*1.5)
    param["width_"] = param["width"] - side_width

    print "--- start ---"
    if debug["sound"]:
        print "press A to on/off saber"
    
    prev_time = time.time() # init prev_time
    while wiiremote.wiimote.go:
        if debug["divide"]:
            for c in [1, 2]:
                pygame.draw.line(screen, (255, 255, 255), (0, param["height"]*c), (param["width_"], param["height"]*c))

        pygame.time.wait(10)
        pygame.display.update()

        screen.fill((0, 0, 0), (param["width_"], 0, side_width, param["height"]))
        screen.blit(screen, (-1, 0))

        if not debug["divide"]: 
            for i in range(int(maxA*2+1)):
                screen.blit(font.render("%-d" % (maxA - i), True, (144, 144, 144)), (param["width"]-side_width, float(param["height"]) / (maxA*2) * i - side_width*1.5/4))
                pygame.draw.line(screen, (144, 144, 144), (0, float(param["height"]) / (maxA*2) * i), (param["width_"], float(param["height"]) / (maxA*2) * i))
                
        #pygame
        for c in range(3): # 3axis
            if view[c]:
                s = int((acc[c] * param["height"] / maxA + param["height"]) / 2)
                s = max(0, min(param["height"] - 1, s))
                if debug["divide"]: pygame.draw.line(screen, colors[c], (param["width_"]-3, param["height"]*c+old[c]), (param["width_"]-2, param["height"]*c+s))
                else: pygame.draw.line(screen, colors[c], (param["width_"]-3, old[c]), (param["width_"]-2, s))
                old[c] = s

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                wiiremote.quit()
                break
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    wiiremote.quit()
                    break
                if event.key == pygame.K_x:
                    if view[0]: view[0] = False
                    else: view[0] = True
                elif event.key == pygame.K_y:
                    if view[1]: view[1] = False
                    else: view[1] = True
                elif event.key == pygame.K_z:
                    if view[2]: view[2] = False
                    else: view[2] = True
            elif event.type == wiiremote.WIIMOTE_BUTTON_PRESS:
                if debug["button"]: print event.button, "pressed"
                if event.button == "A":
                    if debug["sound"]:
                        if param["saber"]:
                            wiiremote.do(saber_off)
                        else:
                            wiiremote.do(saber_on)
                #if event.button == "B":
                 #   wiiremote.setRumble(1)
            elif event.type == wiiremote.WIIMOTE_BUTTON_RELEASE:
                if debug["button"]: print event.button, "released"
                #if event.button == "B":
                 #   wiiremote.setRumble(0)
            elif event.type == wiiremote.WIIMOTE_ACCEL:
                acc[0] = (event.accel[0] - param["acc_zero"][0]) / param["acc_gain"][0]
                acc[1] = (event.accel[1] - param["acc_zero"][1]) / param["acc_gain"][1]
                acc[2] = (event.accel[2] - param["acc_zero"][2]) / param["acc_gain"][2]
                if debug["accel"]: print "acc =", acc
                if debug["save"]: 
                    pass
                if debug["sound"] and param["saber"]:
                    if (4 > abs(acc[0]) >= 1.5) or (4 > abs(acc[1]) >= 2.5) or (4 > abs(acc[2]) >= 2.5):
                        play_sound("swing1", True)
                    elif (abs(acc[0]) >= 4) or (abs(acc[1]) >= 3) or (abs(acc[2]) >= 3): 
                        play_sound("strike1", False, stop=True)
                if acc[0] > 1: gx = 1
                elif acc[0] < -1: gx = -1
                else: gx = acc[0]
                if acc[1] > 1: gy = 1
                elif acc[1] < -1: gy = -1
                else: gy = acc[1]
                if acc[2] > 1: gz = 1
                elif acc[2] < -1: gz = -1
                else: gz = acc[2]
                #print "gx, gy, gz =", gx, gy, gz
                jx = 90 - (math.asin(gx) * 180 / math.pi)
                jy = 90 - (math.asin(gy) * 180 / math.pi)
                jz = 90 - (math.asin(gz) * 180 / math.pi)
                
                if debug["orient"]: print "acc orient : %f %f %f" % (jx, jy, jz)
                if debug["fall"]:
                    if abs(gx) * 10 < 1 and abs(gy) * 10 < 1 and abs(gz) * 10 < 1 and not pygame.mixer.get_busy():
                        print "Fall!"
                        wiiremote.do(sounds["fall"].play)
            elif event.type == wiiremote.WIIMOTE_ORIENT:
                yaw = (event.orient[0] - param["gyro_zero"][0]) / param["gyro_gain"]
                if event.fast_mode[0]: yaw *= param["gyro_fast"]
                pitch = (event.orient[1] - param["gyro_zero"][1]) / param["gyro_gain"]
                if event.fast_mode[1]: pitch *= param["gyro_fast"]
                roll = (event.orient[2] - param["gyro_zero"][2]) / param["gyro_gain"]
                if event.fast_mode[2]: roll *= param["gyro_fast"]
                
                frametime = time.time() - prev_time
                prev_time = time.time()
                #print frametime
                angle_yaw += yaw * frametime
                angle_pitch += pitch * frametime
                angle_roll += roll * frametime
                # -180 <= angle < 180
                angle_yaw = angle_yaw % 360
                angle_pitch = angle_pitch % 360
                angle_roll = angle_roll % 360
                
                if debug["gyro"]:
                    #print "yaw, pitch, roll =", yaw, pitch, roll
                    print "angle_yaw, angle_pitch, angle_roll =", angle_yaw, angle_pitch, angle_roll
    
    wiiremote.quit()
    print "--- stop ---"
    return


if __name__ == "__main__":
    main()
