import os
import json
import numpy as np
import tkinter as tk
from tkinter import ttk
from paddleocr import PaddleOCR
import threading
import win32gui
import time
from PIL import Image, ImageTk
from pyautogui import screenshot, moveTo, mouseDown, mouseUp
import keyboard

class AutoBuyApp:
    def __init__(self):
        self.ocr = self.init_paddleocr()
        self.stop_detection = threading.Event()
        self.paused = threading.Event()
        self.checkbox_vars = {}
        self.selected_heroes = []
        self.images = {}
        self.click_count = {}
        self.detection_thread = None
        self.shuffling_thread = None
        self.hwnd = None
        self.current_heroes_label = None
        self.root = None
        self.window_choice = None

    def get_current_directory(self):
        return os.path.dirname(os.path.abspath(__file__))

    def init_paddleocr(self):
        current_dir = self.get_current_directory()
        dict_path = os.path.join(current_dir, 'dict', 'chinese_cht_dict.txt')
        os.makedirs(os.path.dirname(dict_path), exist_ok=True)
        if not os.path.exists(dict_path):
            return PaddleOCR(use_angle_cls=False, lang="ch", use_gpu=False, show_log=False)
        else:
            return PaddleOCR(
                use_angle_cls=False,
                lang="chinese_cht",
                use_gpu=False,
                show_log=False,
                rec_char_dict_path=dict_path
            )

    def load_json_data(self):
        config_path = os.path.join(self.get_current_directory(), 'hero.json')
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                try:
                    return json.load(f)
                except json.JSONDecodeError:
                    print("JSONDecodeError: 文件內容無效")
        print("文件不存在")
        return {}

    def list_windows(self, keyword="League Of Legends"):
        def enum_windows(hwnd, results):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                window_text = win32gui.GetWindowText(hwnd)
                if keyword.lower() in window_text.lower():
                    results.append((window_text, hwnd))
        window_list = []
        win32gui.EnumWindows(enum_windows, window_list)
        return window_list

    def get_window_rect(self, hwnd):
        if hwnd:
            return win32gui.GetWindowRect(hwnd)
        return None

    def capture_and_ocr(self, hwnd, left_ratio=0.2, right_ratio=0.1, bottom_ratio=0.95):
        rect = self.get_window_rect(hwnd)
        if not rect:
            return None, None, None, None, None
        StartLeft, StartTop, right, bottom = rect
        width = right - StartLeft
        height = bottom - StartTop
        image = screenshot(region=(StartLeft, StartTop, width, height))
        left_crop = image.width * left_ratio
        right_crop = image.width * right_ratio
        bottom_crop = image.height * bottom_ratio
        cropped_image = image.crop((int(left_crop), int(bottom_crop), image.width - int(right_crop), image.height))
        image_np = np.array(cropped_image)
        result = self.ocr.ocr(image_np, cls=False)
        return result, StartLeft, StartTop, left_crop, bottom_crop

    def ocr_hero_buy(self):
        while not self.stop_detection.is_set():
            if self.paused.is_set():
                time.sleep(0.1)
                continue
            result, StartLeft, StartTop, left_crop, bottom_crop = self.capture_and_ocr(self.hwnd)
            if result is None:
                print("未找到指定遊戲視窗")
                break
            recognized_texts = []
            for line in result:
                if line:
                    for word in line:
                        recognized_text = word[1][0]
                        recognized_text = ''.join(filter(lambda ch: u'\u4e00' <= ch <= u'\u9fff', recognized_text))
                        if recognized_text:
                            recognized_texts.append(recognized_text)
                            if recognized_text in self.selected_heroes:
                                x, y = word[0][0][0] + StartLeft + int(left_crop), word[0][0][1] + StartTop + int(bottom_crop)
                                print(f"檢測到目標: '{recognized_text}', 準備拿牌...")
                                moveTo(x, y)
                                time.sleep(0.01)
                                mouseDown()
                                time.sleep(0.01)
                                mouseUp()
                                position_key = (x, y)
                                self.click_count[position_key] = self.click_count.get(position_key, 0) + 1
                                if self.click_count[position_key] > 5:
                                    print(f"位置 {position_key} 點擊超過5次，自動暫停。")
                                    self.toggle_pause()
                                    self.click_count[position_key] = 0
            if recognized_texts:
                print(f"檢測到: {' '.join(recognized_texts)}")
            elif not self.paused.is_set():
                print("目前沒有檢測到英雄")
            time.sleep(0.33)

    def shuffling(self):
        print("開始ALL_IN...")
        self.stop_detection.clear()
        self.paused.clear()
        while not self.stop_detection.is_set():
            if self.paused.is_set():
                time.sleep(0.1)
                continue
            result, StartLeft, StartTop, left_crop, bottom_crop = self.capture_and_ocr(self.hwnd)
            if result is None:
                print("未找到指定遊戲視窗")
                break
            found_hero = False
            for line in result:
                if line:
                    for word in line:
                        recognized_text = word[1][0]
                        recognized_text = ''.join(filter(lambda ch: u'\u4e00' <= ch <= u'\u9fff', recognized_text))
                        if recognized_text in self.selected_heroes:
                            found_hero = True
                            x, y = word[0][0][0] + StartLeft + int(left_crop), word[0][0][1] + StartTop + int(bottom_crop)
                            # 這裡可加上點擊動作
                            break
            if not found_hero:
                print("未檢測到目標，按下 D 键刷新卡牌...")
            time.sleep(0.2)

    def start_detection(self):
        if self.hwnd is None:
            print("沒選擇視窗，無法開始檢測。")
            return
        self.stop_detection.clear()
        self.paused.clear()
        self.detection_thread = threading.Thread(target=self.ocr_hero_buy)
        self.detection_thread.start()
        print("開始持續檢測螢幕中的目標")

    def stop_detection_func(self):
        self.stop_detection.set()
        if self.detection_thread is not None:
            self.detection_thread.join()
        print("檢測已停止")

    def toggle_pause(self):
        if self.paused.is_set():
            self.paused.clear()
            print("再次開始檢測...")
        else:
            self.paused.set()
            print("檢測已暂停。按 HOME 鍵繼續檢測，或者再次按 END 鍵解除暫停。")

    def uncheck_all(self):
        for var in self.checkbox_vars.values():
            var.set(False)
        self.update_current_heroes()

    def update_current_heroes(self):
        current_heroes = [hero for hero, var in self.checkbox_vars.items() if var.get()]
        if self.current_heroes_label:
            self.current_heroes_label.config(text="目前選取的英雄: " + ', '.join(current_heroes))

    def create_ui(self):
        self.root = tk.Tk()
        self.root.title("請選擇遊戲視窗")
        data = self.load_json_data()
        hero_image_path = os.path.join(self.get_current_directory(), 'hero')
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill='both', expand=True)
        for cost, heroes in data.items():
            frame = tk.Frame(notebook)
            notebook.add(frame, text=f"{cost}英雄")
            row_count = 0
            column_count = 0
            for hero in heroes:
                hero_frame = tk.Frame(frame)
                image_path = os.path.join(hero_image_path, f"{hero}.jpg")
                if os.path.exists(image_path):
                    image = Image.open(image_path).resize((50, 50), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(image)
                    self.images[hero] = photo
                else:
                    photo = None
                var = tk.BooleanVar()
                checkbox = tk.Checkbutton(hero_frame, text=hero, variable=var, font=("Segoe UI", 12))
                checkbox.pack()
                self.checkbox_vars[hero] = var
                if photo:
                    label = tk.Label(hero_frame, image=photo)
                    label.pack()
                hero_frame.grid(row=row_count, column=column_count, padx=5, pady=5)
                column_count += 1
                if column_count >= 5:
                    column_count = 0
                    row_count += 1
        window_list_label = tk.Label(self.root, text="", font=("Segoe UI", 12))
        window_list_label.pack()
        self.window_choice = tk.StringVar()
        window_dropdown = ttk.Combobox(self.root, textvariable=self.window_choice, font=("Segoe UI", 12))
        window_dropdown.pack()
        def update_window_dropdown():
            windows = self.list_windows()
            window_dropdown['values'] = [title for title, hwnd in windows]
            window_dropdown.after(5000, update_window_dropdown)
        update_window_dropdown()
        def start_button_click():
            self.hwnd = next((hwnd for name, hwnd in self.list_windows() if name == self.window_choice.get()), None)
            self.selected_heroes = [hero for hero, var in self.checkbox_vars.items() if var.get()]
            self.update_current_heroes()
            if self.selected_heroes:
                self.start_detection()
            else:
                print("請至少選一個英雄！")
        button = tk.Button(self.root, text="開始抓牌[HOME]", command=start_button_click)
        button.pack()
        def on_closing():
            self.stop_detection_func()
            self.root.destroy()
            print("程序已關閉")
            os._exit(0)
        self.root.protocol("WM_DELETE_WINDOW", on_closing)
        keyboard.add_hotkey('home', self.start_detection)
        keyboard.add_hotkey('end', self.toggle_pause)
        keyboard.add_hotkey('f1', lambda: threading.Thread(target=self.shuffling).start())
        keyboard.add_hotkey('ctrl+u', self.uncheck_all)
        keyboard.add_hotkey('f12', on_closing)
        self.root.mainloop()

if __name__ == "__main__":
    app = AutoBuyApp()
    app.create_ui()
