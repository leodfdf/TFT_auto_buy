import os
import json
import numpy as np # type: ignore
import tkinter as tk
from tkinter import ttk
from paddleocr import PaddleOCR
import threading
import win32gui
import time
from PIL import Image, ImageTk
from pyautogui import screenshot, moveTo, mouseDown, mouseUp
import keyboard

# 獲取目前腳本路徑
def get_current_directory():
    return os.path.dirname(os.path.abspath(__file__))

# 保存當前選擇的英雄到配置文件
def save_selected_heroes(selected_heroes):
    config_path = os.path.join(get_current_directory(), 'selected_heroes.json')
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(selected_heroes, f)

# 加载配置文件中的英雄
def load_selected_heroes():
    config_path = os.path.join(get_current_directory(), 'selected_heroes.json')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

# 初始化 PaddleOCR
ocr = PaddleOCR(use_angle_cls=False, lang="chinese_cht", use_gpu=True, show_log=False)

# 定義全局變數
stop_detection = False
paused = False
window_choice = None
checkbox_vars = {}
selected_heroes = []
images = {}
detection_thread = None
hwnd = None
current_heroes_label = None

# 點擊計數
click_count = {}
shuffling_thread = None

# 獲取 JSON 數據
def load_json_data():
    config_path = os.path.join(get_current_directory(), 'hero.json')
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# 獲取所有視窗
def list_windows(keyword="League Of Legends"):
    def enum_windows(hwnd, results):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            results.append((win32gui.GetWindowText(hwnd), hwnd))

    window_list = []
    win32gui.EnumWindows(enum_windows, window_list)
    return window_list

def update_window_list(label):
    windows = list_windows()
    display_text = "\n".join([f"Title: {title}, HWND: {hwnd}" for title, hwnd in windows])
    label.config(text=display_text)
    label.after(5000, update_window_list, label)  # 每5秒刷新一次

# 獲取視窗hwnd
def get_window_rect(hwnd):
    if hwnd:
        return win32gui.GetWindowRect(hwnd)
    return None

# 持續檢測並獲取英雄函數
def ocr_hero_buy():
    global stop_detection, paused, selected_heroes

    while not stop_detection:
        if paused:
            time.sleep(0.1)  # 暫停狀態下暫時休眠
            continue

        rect = get_window_rect(hwnd)
        if not rect:
            print("未找到指定遊戲視窗")
            break

        StartLeft, StartTop, right, bottom = rect
        width = right - StartLeft
        height = bottom - StartTop

        # OCR截圖並裁剪
        image = screenshot(region=(StartLeft, StartTop, width, height))
        left_crop = image.width * 0.2
        right_crop = image.width * 0.1
        bottom_crop = image.height * 0.95
        cropped_image = image.crop((int(left_crop), int(bottom_crop), image.width - int(right_crop), image.height))

        # OCR 辨認
        image_np = np.array(cropped_image)
        result = ocr.ocr(image_np, cls=False)

        recognized_texts = []
        for line in result:
            if line:
                for word in line:
                    recognized_text = word[1][0]
                    # 只保留中文字符
                    recognized_text = ''.join(filter(lambda ch: u'\u4e00' <= ch <= u'\u9fff', recognized_text))
                    if recognized_text:
                        recognized_texts.append(recognized_text)
                        # 檢測目標，進行操作
                        if recognized_text in selected_heroes:
                            x, y = word[0][0][0] + StartLeft + int(left_crop), word[0][0][1] + StartTop + int(bottom_crop)
                            print(f"檢測到目標: '{recognized_text}', 準備拿牌...")
                            print(f"點擊座標: ({x}, {y})")

                            # 使用 pyautogui 進行點擊
                            moveTo(x, y)  # 移動到目標位置
                            time.sleep(0.01)  # 等待0.01秒
                            mouseDown()  # 按下鼠标左键
                            time.sleep(0.01)  # 按下後等待0.01~0.05秒按照自己需求改
                            mouseUp()  # 鼠標左鍵彈起

                            # 記錄點擊次數
                            position_key = (x, y)  # 创建一个坐标元组作为字典的key
                            if position_key not in click_count:
                                click_count[position_key] = 0
                            click_count[position_key] += 1

                            # 確認是否點擊超過5次
                            if click_count[position_key] > 5:
                                print(f"位置 {position_key} 點擊超過5次，自動暫停。")
                                toggle_pause()  # 調用暂停變數
                                # 在暂停後重製點擊計數
                                click_count[position_key] = 0  # 重置點擊計數

        # 只有在未暫停輸出當前未識別到英雄的信息
        if recognized_texts:
            print(f"檢測到: {' '.join(recognized_texts)}")
        elif not paused:  # 只有在為暫停情況下輸出未識別到英雄的信息
            print("目前沒有檢測到英雄")

        time.sleep(0.33)

# 更新並寫入選取的英雄列表
def update_current_heroes():
    current_heroes = [hero for hero, var in checkbox_vars.items() if var.get()]
    if current_heroes_label:  # 确保 current_heroes_label 被定义
        current_heroes_label.config(text="目前選取的英雄: " + ', '.join(current_heroes))

# 更新下拉視窗
def update_window_choice():
    global hwnd
    windows = list_windows()
    window_names = [name for name, _ in windows]
    window_choice['values'] = window_names
    if hwnd is not None:
        current_window_name = win32gui.GetWindowText(hwnd)
        if current_window_name in window_names:
            window_choice.set(current_window_name)  # 選取當前視窗
        else:
            window_choice.set("")  # 清空選項

# 選擇窗口時更新視窗信息
def on_window_selected(event):
    global hwnd
    selected_window_name = window_choice.get()
    if selected_window_name:
        hwnd = next((hwnd for name, hwnd in list_windows() if name == selected_window_name), None)

# 持續檢測的啟動變數
def start_detection():
    global stop_detection, paused, detection_thread
    if hwnd is None:
        print("沒選擇視窗，無法開始檢測。")
        return
    stop_detection = False
    paused = False
    detection_thread = threading.Thread(target=ocr_hero_buy)
    detection_thread.start()
    print("開始持續檢測螢幕中的目標")

# 停止檢測
def stop_detection_func():
    global stop_detection, detection_thread
    stop_detection = True
    if detection_thread is not None:
        detection_thread.join()
    print("檢測已停止")

# 暂停和恢復檢測
def toggle_pause():
    global paused
    paused = not paused
    if paused:
        print("檢測已暂停。按 HOME 鍵繼續檢測，或者再次按 END 鍵解除暫停。")
    else:
        print("再次開始檢測...")

# 取消所有選取的英雄
def uncheck_all():
    for var in checkbox_vars.values():
        var.set(False)
    update_current_heroes()

# F1 鍵all_in功能
def shuffling():
    global stop_detection, paused, shuffling_thread
    stop_detection = False
    paused = False
    print("開始ALL_IN...")

    while not stop_detection:
        if paused:
            time.sleep(0.1)
            continue

        rect = get_window_rect(hwnd)
        if not rect:
            print("未找到指定遊戲視窗")
            break

        StartLeft, StartTop, right, bottom = rect
        width = right - StartLeft
        height = bottom - StartTop

        # 截圖並裁剪所需要的資訊
        image = screenshot(region=(StartLeft, StartTop, width, height))
        left_crop = image.width * 0.2
        right_crop = image.width * 0.1
        bottom_crop = image.height * 0.95
        cropped_image = image.crop((int(left_crop), int(bottom_crop), image.width - int(right_crop), image.height))

        # OCR 辨認
        image_np = np.array(cropped_image)
        result = ocr.ocr(image_np, cls=False)

        found_hero = False
        for line in result:
            if line:
                for word in line:
                    recognized_text = word[1][0]
                    # 只保留中文字符
                    recognized_text = ''.join(filter(lambda ch: u'\u4e00' <= ch <= u'\u9fff', recognized_text))
                    if recognized_text in selected_heroes:
                        found_hero = True
                        x, y = word[0][0][0] + StartLeft + int(left_crop), word[0][0][1] + StartTop + int(bottom_crop)
                        print(f"檢測到目標: '{recognized_text}', 準備抓牌...")
                        print(f"點擊座標: ({x}, {y})")

                        # 使用 pyautogui 進行點擊操作
                        moveTo(x, y)  # 移動到目標位置
                        time.sleep(0.01)  # 等待0.01秒
                        mouseDown()  # 按下滑鼠左鍵
                        time.sleep(0.05)  # 按下後等待0.05秒
                        mouseUp()  # 滑鼠左键彈起
                        break  # 找到目標英雄後跳出循環

        if not found_hero:
            print("未檢測到目標，按下 D 键刷新卡牌...")

        time.sleep(0.2)  # 每 0.2 秒进行一次识别

# 停止all_in功能
def stop_shuffling():
    global stop_detection
    stop_detection = True
    print("停止ALL_IN模式")

# 綁定鍵盤熱鍵
keyboard.add_hotkey('home', start_detection)  # 開始持續檢測
keyboard.add_hotkey('end', toggle_pause)  # 按下 End 鍵暫停/恢復
keyboard.add_hotkey('f1', lambda: threading.Thread(target=shuffling).start())  # F1 鍵開啟ALL_IN
keyboard.add_hotkey('ctrl+u', uncheck_all)  # Ctrl+U 取消所有勾選
keyboard.add_hotkey('f12', stop_detection_func)  # 停止檢測並關閉程序

# 創建 UI 視窗
def create_ui():
    global root, window_choice, checkbox_vars, selected_heroes, hwnd, current_heroes_label
    root = tk.Tk()
    root.title("請選擇遊戲視窗")

    # 加載 JSON 數據和圖片路徑
    data = load_json_data()
    hero_image_path = os.path.join(get_current_directory(), 'hero')

    # 創建 Notebook（分頁容器）
    notebook = ttk.Notebook(root)
    notebook.pack(fill='both', expand=True)

    for cost, heroes in data.items():
        frame = tk.Frame(notebook)
        notebook.add(frame, text=f"{cost}英雄")

        row_count = 0
        column_count = 0
        for hero in heroes:
            hero_frame = tk.Frame(frame)

            # 加载英雄圖片
            image_path = os.path.join(hero_image_path, f"{hero}.jpg")
            if os.path.exists(image_path):
                image = Image.open(image_path).resize((50, 50), Image.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                images[hero] = photo  # 保存引用
            else:
                photo = None

            # 創建複選框
            var = tk.BooleanVar()
            checkbox = tk.Checkbutton(hero_frame, text=hero, variable=var, font=("Segoe UI", 12))
            checkbox.pack()

            # 圖片標籤和圖片識別
            if photo:
                label = tk.Label(hero_frame, image=photo)
                label.image = photo  # 保存引用
                label.pack()
                label.bind("<Button-1>", lambda e, v=var: v.set(1 - v.get()))

            hero_frame.grid(row=row_count, column=column_count, padx=5, pady=5)
            checkbox_vars[hero] = var

            # 綁定複選框
            var.trace_add("write", lambda *args, hero=hero: update_current_heroes())

            column_count += 1
            if column_count >= 4:
                column_count = 0
                row_count += 1

    # 彈出提示視窗
    label = tk.Label(root, text="請選擇遊戲視窗:", font=("Segoe UI", 12))
    label.pack(pady=5)

    # 選擇視窗
    window_choice = ttk.Combobox(root, state='readonly')
    window_choice.pack(pady=10)
    window_choice.bind("<<ComboboxSelected>>", on_window_selected)

    # 下方出現按鍵提示
    key_info_label = tk.Label(root, text="功能按键: [HOME] 開始抓牌 | [END] 暂停/再開 | [F1] ALL_IN | [CTRL+U] 全部取消 | [F12] 退出", font=("Segoe UI", 10), wraplength=600)
    key_info_label.pack(pady=5)

    # 加载窗口列表
    update_window_choice()

    # 加载上次保存的英雄配置
    selected_heroes = load_selected_heroes()
    for hero, var in checkbox_vars.items():
        if hero in selected_heroes:
            var.set(True)

    # 现在定义 current_heroes_label
    global current_heroes_label
    current_heroes_label = tk.Label(root, text="當前選取的英雄: " + ', '.join(selected_heroes), font=("Segoe UI", 12), wraplength=400)
    current_heroes_label.pack(pady=10)

    # 开始按钮
    def start_button_click():
        global hwnd
        hwnd = next((hwnd for name, hwnd in list_windows() if name == window_choice.get()), None)
        selected_heroes.clear()
        selected_heroes.extend([hero for hero, var in checkbox_vars.items() if var.get()])
        save_selected_heroes(selected_heroes)
        update_current_heroes()
        if selected_heroes:
            start_detection()
        else:
            print("請至少選一個英雄！")

    button = tk.Button(root, text="開始抓牌[HOME]", command=start_button_click)
    button.pack()

    # F12關閉程序處理
    def on_closing():
        stop_detection_func()
        root.destroy()
        print("程序已關閉")
        os._exit(0)

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    create_ui()
