#! /usr/bin/python
# -*- coding: utf-8 -*-

# Copyright (C) 2011 ~ 2012 Deepin, Inc.
#               2011 ~ 2012 Wang Yong
# 
# Author:     Wang Yong <lazycat.manatee@gmail.com>
# Maintainer: Wang Yong <lazycat.manatee@gmail.com>
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from PyQt5.QtCore import QObject, pyqtSignal
from Xlib import X, XK
from Xlib.ext import record
from Xlib.protocol import rq
from ocr import ocr_word
from threading import Timer
from xutils import record_dpy, local_dpy
import commands, subprocess

press_ctrl = False

class RecordEvent(QObject):
    
    press_ctrl = pyqtSignal()    
    release_ctrl = pyqtSignal()    
    
    left_button_press = pyqtSignal(int, int, int)
    right_button_press = pyqtSignal(int, int, int)    
    wheel_press = pyqtSignal()
    
    cursor_stop = pyqtSignal(int, int, str)
    
    translate_selection = pyqtSignal(int, int, str)
    
    def __init__(self, view):
        QObject.__init__(self)

        self.timer = None
        self.stop_delay = 0.05
        self.view = view
    
    def lookup_keysym(self, keysym):
        for name in dir(XK):
            if name[:3] == "XK_" and getattr(XK, name) == keysym:
                return name[3:]
        return "[%d]" % keysym
     
    def record_callback(self, reply):
        global press_ctrl
        
        if reply.category != record.FromServer:
            return
        if reply.client_swapped:
            return
        if not len(reply.data) or ord(reply.data[0]) < 2:
            return
     
        data = reply.data
        while len(data):
            event, data = rq.EventField(None).parse_binary_value(data, record_dpy.display, None, None)
            
            if event.type == X.KeyPress:
                keyname = self.lookup_keysym(local_dpy.keycode_to_keysym(event.detail, 0))
                if keyname in ["Control_L", "Control_R"]:
                    press_ctrl = True
                    
                    if not self.view.in_translate_area():
                        self.press_ctrl.emit()
            elif event.type == X.KeyRelease:
                keyname = self.lookup_keysym(local_dpy.keycode_to_keysym(event.detail, 0))
                if keyname in ["Control_L", "Control_R"]:
                    press_ctrl = False
                    self.release_ctrl.emit()
            elif event.type == X.ButtonPress:
                if event.detail == 1:
                    self.left_button_press.emit(event.root_x, event.root_y, event.time)
                elif event.detail == 3:
                    self.right_button_press.emit(event.root_x, event.root_y, event.time)
                elif event.detail == 5:
                    self.wheel_press.emit()
            elif event.type == X.ButtonRelease:
                if not self.view.in_translate_area():
                    selection_content = commands.getoutput("xsel -p -o")
                    subprocess.Popen("xsel -c", shell=True).wait()
                    
                    if len(selection_content) > 1:
                        self.translate_selection.emit(event.root_x, event.root_y, selection_content)
            elif event.type == X.MotionNotify:
                if self.timer:
                    self.timer.cancel()
                self.timer = Timer(self.stop_delay, lambda : self.emit_cursor_stop(event.root_x, event.root_y))
                self.timer.start()
                
    def emit_cursor_stop(self, mouse_x, mouse_y):
        if press_ctrl and not self.view.in_translate_area():
            ocr_info = ocr_word(mouse_x, mouse_y)
            if ocr_info:
                self.cursor_stop.emit(*ocr_info)
                
    def filter_event(self):
        ctx = record_dpy.record_create_context(
                0,
                [record.AllClients],
                [{
                        'core_requests': (0, 0),
                        'core_replies': (0, 0),
                        'ext_requests': (0, 0, 0, 0),
                        'ext_replies': (0, 0, 0, 0),
                        'delivered_events': (0, 0),
                        'device_events': (X.KeyPress, X.MotionNotify),
                        'errors': (0, 0),
                        'client_started': False,
                        'client_died': False,
                }])
         
        record_dpy.record_enable_context(ctx, self.record_callback)
        record_dpy.record_free_context(ctx)