"""
########################################
#                                      #
#         ffmpeg resize-recode         #
#                                      #
#   Author  : github.com/Nenotriple    #
#                                      #
########################################

Description:
-------------
This Python script uses ffmpeg to resize and re-encode video files.
The default settings target a very low quality video suitable for low power media players.

Tested on Windows 10.

Requirements:
-------------
FFmpeg:
    Place `ffmpeg.exe` in the same directory as this script.
    Or install ffmpeg to the system path.

"""


################################################################################################################################################
################################################################################################################################################
#region -  Global


import os
import time
import shutil
import datetime
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, Toplevel


VERSION = "v1.0"
TITLE = f"{VERSION} - ffmpeg - resize-recode"

WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
MIN_WINDOW_WIDTH = 250
MIN_WINDOW_HEIGHT = 325

SUPPORTED_FILETYPES = [".mp4", ".avi", ".mkv", ".flv", ".mov", ".wmv", ".3gp", ".webm", ".ogg"]
CLEAN_SUPPORTED_FILETYPES = ', '.join(f'{item}' for item in SUPPORTED_FILETYPES)

DEFAULT_SCALE = "240:-2"
DEFAULT_VIDEO_BITRATE = "48"
DEFAULT_AUDIO_BITRATE = "48"
DEFAULT_FRAMERATE = "12"
DEFAULT_FILETYPE = ".avi"


#endregion
################################################################################################################################################
################################################################################################################################################
#region -  ToolTips



"""

Example tooltip:

ToolTip.create_tooltip(self.widget, "ToolTip text", 10, 6, 4)

Values = delay=10, x_offset=6, y_offset=4
These values create an instant Tooltip just under the mouse.

"""


class ToolTip:
    def __init__(self, widget, x_offset=0, y_offset=0):
        self.widget = widget
        self.tip_window = None
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.id = None
        self.hide_time = 0


    def show_tip(self, tip_text, x, y):
        if self.tip_window or not tip_text: return
        x += self.x_offset
        y += self.y_offset
        self.tip_window = tw = Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.wm_attributes("-topmost", True)
        tw.wm_attributes("-disabled", True)
        label = tk.Label(tw, text=tip_text, background="#ffffee", relief="ridge", borderwidth=1, justify="left", padx=4, pady=4)
        label.pack()
        self.id = self.widget.after(10000, self.hide_tip)

    def hide_tip(self):
        tw = self.tip_window
        self.tip_window = None
        if tw: tw.destroy()
        self.hide_time = time.time()


    @staticmethod
    def create_tooltip(widget, text, delay=0, x_offset=0, y_offset=0):
        tool_tip = ToolTip(widget, x_offset, y_offset)
        def enter(event):
            if tool_tip.id:
                widget.after_cancel(tool_tip.id)
            if time.time() - tool_tip.hide_time > 0.1:
                tool_tip.id = widget.after(delay, lambda: tool_tip.show_tip(text, widget.winfo_pointerx(), widget.winfo_pointery()))
        def leave(event):
            if tool_tip.id:
                widget.after_cancel(tool_tip.id)
            tool_tip.hide_tip()
        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)


#endregion
################################################################################################################################################
################################################################################################################################################
#region -  Setup and Interface


class VideoResizer:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"{TITLE}")
        self.root.minsize(MIN_WINDOW_WIDTH,MIN_WINDOW_HEIGHT)
        self.root.filename = None
        self.queue_number = 0
        self.widgets = []
        self.process = None
        self.center_window()
        self.create_widgets()
        self.create_textlog()
        self.update_queue_display()
        self.get_ffmpeg_path()


    def center_window(self):
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width / 2) - (WINDOW_WIDTH / 2)
        y = (screen_height / 2) - (WINDOW_HEIGHT / 2)
        self.root.geometry(f'{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{int(x)}+{int(y)}')


    def create_widgets(self):
        self.select_video_button = self.create_button("Select video", self.select_video_file)
        self.open_file_button = self.create_button("Open File Path", self.open_file_path)
        self.run_button = self.create_button("Run", self.confirm_and_run_ffmpeg)

        self.output_filename_label = tk.Label(self.root, text="Output Filename:")
        self.output_filename_label.pack(fill="x", padx="2", pady="2")
        self.filename_entry = tk.Entry(self.root)
        self.filename_entry.pack(fill="x", padx="2", pady="2")
        self.filename_label = tk.Label(self.root, text="")
        self.filename_label.pack(fill="x", padx="2", pady="2")

        spacer = tk.Label(self.root, text="");spacer.pack(fill="x")

        self.scale_entry = self.create_label_and_entry("Scale:", DEFAULT_SCALE, 15)
        self.v_bitrate_entry = self.create_label_and_entry("Video Bitrate (kbps):", DEFAULT_VIDEO_BITRATE, 15)
        self.a_bitrate_entry = self.create_label_and_entry("Audio Bitrate (kbps):", DEFAULT_AUDIO_BITRATE, 15)
        self.framerate_entry = self.create_label_and_entry("Framerate:", DEFAULT_FRAMERATE, 15)
        self.file_extension_entry = self.create_label_and_entry("Filetype:", DEFAULT_FILETYPE, 15)

        ToolTip.create_tooltip(self.filename_entry, "Output filename\n\nDO NOT add a file extension! Use the `Output Filetype` text box instead!", 10, 15, 15)
        ToolTip.create_tooltip(self.scale_entry, "Resize the video to a specified width and height.\n\nIn `scale=240:-2`, 240 is the width in pixels, and -2 auto-calculates the height, keeping it a multiple of 2 and preserving the aspect ratio.\nIf you want to auto-calculate the height without the multiple of 2 constraint, use -1 instead of -2.\nSome codecs don't support resolutions that aren't divisible by 2.\n\nLeave empty for no change.", 10, 15, 15)
        ToolTip.create_tooltip(self.v_bitrate_entry, "Leave empty for Auto", 10, 15, 15)
        ToolTip.create_tooltip(self.a_bitrate_entry, "Leave empty for Auto", 10, 15, 15)
        ToolTip.create_tooltip(self.framerate_entry, "Leave empty for no change", 10, 15, 15)
        ToolTip.create_tooltip(self.file_extension_entry, f"Supported Filetypes: {CLEAN_SUPPORTED_FILETYPES}", 10, 15, 15)

        self.filename_entry.bind("<Return>", self.confirm_and_run_ffmpeg)
        self.filename_entry.bind("<KeyRelease>", lambda event: self.update_filename_label())
        self.file_extension_entry.bind("<KeyRelease>", lambda event: self.update_filename_label())

        self.v_bitrate_entry.bind("<Up>",   lambda event: self.adjust_entry_value(event, self.v_bitrate_entry, 8))
        self.v_bitrate_entry.bind("<Down>", lambda event: self.adjust_entry_value(event, self.v_bitrate_entry, 8))
        self.a_bitrate_entry.bind("<Up>",   lambda event: self.adjust_entry_value(event, self.a_bitrate_entry, 8))
        self.a_bitrate_entry.bind("<Down>", lambda event: self.adjust_entry_value(event, self.a_bitrate_entry, 8))
        self.framerate_entry.bind("<Up>",   lambda event: self.adjust_entry_value(event, self.framerate_entry, 1))
        self.framerate_entry.bind("<Down>", lambda event: self.adjust_entry_value(event, self.framerate_entry, 1))


    def create_button(self, text, command):
        button = tk.Button(self.root, text=text, command=command)
        button.pack(side="top", fill="x", padx="2", pady="2")
        self.widgets.append(button)
        return button


    def create_label_and_entry(self, label_text, default_text=None, entry_width=None):
        widget_frame = tk.Frame(self.root)
        widget_frame.pack(padx="2", pady="2")
        label = tk.Label(widget_frame, anchor="w", text=label_text, width=20)
        label.pack(side="left")
        entry = tk.Entry(widget_frame, justify="center", width=entry_width)
        entry.pack(side="left", anchor="w", padx=(0, 10))
        if default_text:
            entry.insert(0, default_text)
        self.widgets.append(widget_frame)
        return entry


    def create_textlog(self):
        spacer = tk.Label(self.root, text="");spacer.pack(fill="x")
        self.textlog_label = tk.Label(self.root, text="Output Log")
        self.textlog_label.pack(fill="x")
        text_frame = tk.Frame(self.root)
        text_frame.pack(side="top", expand="yes", fill="both", padx="2", pady="2")
        vscrollbar = ttk.Scrollbar(text_frame, orient="vertical")
        hscrollbar = ttk.Scrollbar(text_frame, orient="horizontal")
        self.textlog = tk.Text(text_frame, wrap="none", state='disabled', yscrollcommand=vscrollbar.set, xscrollcommand=hscrollbar.set, font=("Consolas", 8))
        vscrollbar.grid(row=0, column=1, sticky="ns")
        hscrollbar.grid(row=1, column=0, sticky="we")
        self.textlog.grid(row=0, column=0, sticky="nsew")
        vscrollbar.config(command=self.textlog.yview)
        hscrollbar.config(command=self.textlog.xview)
        text_frame.grid_columnconfigure(0, weight=1)
        text_frame.grid_rowconfigure(0, weight=1)


#endregion
################################################################################################################################################
################################################################################################################################################
#region -  Primary


    def select_video_file(self):
        filename = filedialog.askopenfilename(filetypes=[("Video files", SUPPORTED_FILETYPES)])
        if filename:
            self.root.filename = filename
            self.filename_entry.delete(0, tk.END)
            self.filename_entry.insert(0, os.path.splitext(os.path.basename(filename))[0])
            self.dir_name = os.path.dirname(self.root.filename)
            self.insert_to_textlog(f'{self.current_formatted_time()}, File Selected: {os.path.normpath(filename)}\n')
            self.update_filename_label()
        else: return


    def get_ffmpeg_command(self, output_file):
        command = f'{self.ffmpeg_path} -i "{self.root.filename}" -map 0:v -map 0:a:0 -sn'
        settings = [f'Input: {os.path.basename(self.root.filename)}']
        # Scale setting
        scale = self.scale_entry.get()
        if scale:
            command += f' -vf "scale={scale}"'
            settings.append(f'Scale: {scale}')
        else:
            settings.append('Scale: Auto')
        # Video bitrate setting
        v_bitrate = self.v_bitrate_entry.get()
        if v_bitrate:
            command += f' -b:v {v_bitrate}k'
            settings.append(f'V_Bitrate: {v_bitrate}k')
        else:
            settings.append('V_Bitrate: Auto')
        # Audio bitrate setting
        a_bitrate = self.a_bitrate_entry.get()
        if a_bitrate:
            command += f' -b:a {a_bitrate}k'
            settings.append(f'A_Bitrate: {a_bitrate}k')
        else:
            settings.append('A_Bitrate: Auto')
        # Frame rate setting
        framerate = self.framerate_entry.get()
        if framerate:
            command += f' -r {framerate}'
            settings.append(f'FPS: {framerate}')
        else:
            settings.append('FPS: Auto')
        # Output file setting
        command += f' -y "{output_file}"'
        settings.append(f'Filetype: {self.file_extension_entry.get()}')

        return command, settings

    def run_ffmpeg(self):
        if self.ffmpeg_precheck():
            return
        output_file = os.path.join(self.dir_name, self.filename_entry.get() + self.file_extension_entry.get())
        if self.check_if_output_exists(output_file):
            command, settings = self.get_ffmpeg_command(output_file)
            self.queue_number += 1
            self.update_queue_display()
            queue_number = self.queue_number

            def run_command(output_file, queue_number):
                self.insert_to_textlog(f'{self.current_formatted_time()}, Queue {queue_number}: Starting...\n')
                self.insert_to_textlog(f'{self.current_formatted_time()}, {queue_number}, ' + ', '.join(settings) + '\n')
                self.process = subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
                self.process.communicate()
                self.insert_to_textlog(f'{self.current_formatted_time()}, Queue {queue_number}: Done: {os.path.normpath(output_file)}\n')
                self.queue_number -= 1
                self.update_queue_display()

            threading.Thread(target=run_command, args=(output_file, queue_number)).start()


    def get_ffmpeg_path(self):
        if os.path.isfile('ffmpeg.exe'):
            self.insert_to_textlog(f'{self.current_formatted_time()}, Using `ffmpeg.exe` from root\n')
            self.ffmpeg_path = './ffmpeg.exe'
        else:
            if shutil.which('ffmpeg') is not None:
                self.insert_to_textlog(f'{self.current_formatted_time()}, Using `ffmpeg` from system\n')
                self.ffmpeg_path = 'ffmpeg'
            else:
                self.insert_to_textlog('FFmpeg not found! https://ffmpeg.org/ \n\nDownload the latest version and place `ffmpeg.exe` in the same directory as this app.\nOr install ffmpeg to your system path.\n')
                for widget in [self.run_button, self.select_video_button, self.open_file_button]:
                    widget.config(state="disabled")


    def check_if_output_exists(self, output_file):
        input_file = self.root.filename
        if os.path.basename(input_file) == os.path.basename(output_file):
            messagebox.showwarning("Filename Conflict", "Input and output filenames are the same.\nPlease create a unique output filename and try again.")
            return False
        elif os.path.isfile(output_file):
            self.insert_to_textlog(f'{self.current_formatted_time()}, File already exists!\n')
            confirm = messagebox.askyesno("Output filename already exists.", "Click YES to overwrite the file.\n\nClick NO to cancel.")
            if confirm:
                self.insert_to_textlog(f'{self.current_formatted_time()}, Overwriting file: {os.path.normpath(output_file)}\n')
                return True
            else:
                self.insert_to_textlog(f'{self.current_formatted_time()}, Aborted by user!\n')
                return False
        return True


    def ffmpeg_precheck(self):
        if self.root.filename is None:
            self.insert_to_textlog(f'{self.current_formatted_time()}, No video selected!\n')
            return True
        if not self.file_extension_entry.get():
            self.insert_to_textlog(f'{self.current_formatted_time()}, No filetype provided, aborting...\nSupported filetypes: {CLEAN_SUPPORTED_FILETYPES}\n')
            return True
        if self.file_extension_entry.get() not in SUPPORTED_FILETYPES:
            self.insert_to_textlog(f'{self.current_formatted_time()}, Unsupported filetype provided, aborting...\nSupported filetypes: {CLEAN_SUPPORTED_FILETYPES}\n')
            return True
        return False


    def confirm_and_run_ffmpeg(self, event=None):
        if self.root.filename is None:
            return
        confirm = messagebox.askyesno("Confirmation", "Are you sure you want to run ffmpeg?")
        if confirm:
            self.run_ffmpeg()

#endregion
################################################################################################################################################
################################################################################################################################################
#region -  Framework / Misc


    def adjust_entry_value(self, event, entry, adjustment):
        try:
            current_value = int(entry.get())
        except ValueError:
            current_value = 0
        if event.keysym == 'Up':
            entry.delete(0, 'end')
            entry.insert(0, str(current_value + adjustment))
        elif event.keysym == 'Down':
            if current_value - adjustment <= 0:
                entry.delete(0, 'end')
            else:
                entry.delete(0, 'end')
                entry.insert(0, str(current_value - adjustment))


    def update_queue_display(self):
        try:
            self.root.title(f"{TITLE} - Queue: {self.queue_number}")
        except RuntimeError: pass


    def current_formatted_time(self):
        current_time = datetime.datetime.now()
        formatted_time = current_time.strftime("%I:%M %p")
        return formatted_time


    def insert_to_textlog(self, text):
        try:
            self.textlog.config(state='normal')
            self.textlog.insert('end', text)
            self.textlog.see('end')
            self.textlog.config(state='disabled')
        except RuntimeError: pass


    def update_filename_label(self):
        if self.root.filename is None:
            return
        self.filename_label.config(text=self.filename_entry.get() + self.file_extension_entry.get())


    def open_file_path(self):
        try: os.startfile(os.path.dirname(self.root.filename))
        except: pass


    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    VideoResizer().run()


#endregion
