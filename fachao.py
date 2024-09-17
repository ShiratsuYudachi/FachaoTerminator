import tkinter as tk
from tkinter import filedialog, font, messagebox, ttk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import easyocr
import os
import sys
import numpy as np
import random

class PenaltyCopyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("罚抄生成器")
        self.root.geometry("1400x800")  # 扩大窗口以容纳字体列表

        # 初始化变量
        self.text = tk.StringVar()
        self.square_size = 50
        self.font_size = int(self.square_size * 0.85)  # 初始字体大小为框大小的85%
        self.font_color = "black"
        self.selected_languages = tk.StringVar(value="ja")  # 默认语言

        # 存储源和目标区域的列表
        self.region_pairs = []
        self.current_source = None

        # 存储选择的字体文件路径
        self.selected_fonts = []
        self.loaded_fonts = {}  # 缓存加载的字体

        # 添加用于存储连续框定目标框时，框之间的间隔值的变量，默认间隔为1像素
        self.interval = tk.IntVar(value=1)

        # 添加用于追踪预览矩形的变量
        self.preview_rect = None  # 预览矩形的ID

        # 添加用于追踪右键拖动的变量
        self.right_dragging = False
        self.right_drag_start = None  # 记录右键拖动的起始位置
        self.right_drag_direction = None  # 'horizontal' 或 'vertical'
        self.right_drag_preview = []  # 预览的连续目标方框ID列表

        # 初始化 EasyOCR Reader
        self.init_easyocr()

        # 设置布局
        self.setup_ui()

        # 加载默认图片
        self.load_image_initial()

        self.debug_image = None  # 添加这行来存储调试图像

    def init_easyocr(self):
        try:
            # 指定语言为日语（根据您的需求可以更改）
            self.reader = easyocr.Reader(['ja'], gpu=False)  # gpu=True 如果您有GPU并安装了CUDA
        except Exception as e:
            messagebox.showerror("错误", f"初始化 EasyOCR 时发生错误：{e}")
            sys.exit(1)

    def setup_ui(self):
        # 左侧Canvas显示图片
        self.canvas_frame = tk.Frame(self.root, bd=2, relief=tk.SUNKEN)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg="grey")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_left_press)    # 左键按下
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)# 左键释放
        self.canvas.bind("<Button-3>", self.on_right_press)   # 右键按下
        self.canvas.bind("<B3-Motion>", self.on_right_drag_motion)      # 右键拖动
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release_drag)  # 右键释放
        self.canvas.bind("<Motion>", self.on_mouse_move)           # 鼠标移动
        self.canvas.bind("<Leave>", self.on_mouse_leave)           # 鼠标离开画布

        # 绑定滚轮事件
        if sys.platform == "darwin":
            # macOS
            self.canvas.bind("<MouseWheel>", self.on_mousewheel)
        elif sys.platform.startswith("linux"):
            # Linux
            self.canvas.bind("<Button-4>", self.on_mousewheel)
            self.canvas.bind("<Button-5>", self.on_mousewheel)
        else:
            # Windows
            self.canvas.bind("<MouseWheel>", self.on_mousewheel)

        # 右侧控制面板
        control_frame = tk.Frame(self.root, padx=10, pady=10)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # 目标框间隔设置
        tk.Label(control_frame, text="目标框间隔:").pack(anchor='w', pady=(10,0))
        self.interval_spinbox = tk.Spinbox(control_frame, from_=0, to=100, width=5, textvariable=self.interval)
        self.interval_spinbox.pack(anchor='w', pady=5)

        # 输入标签和输入框（保留以兼容原功能）
        tk.Label(control_frame, text="输入内容:").pack(anchor='w')
        self.text_entry = tk.Entry(control_frame, textvariable=self.text, width=30)
        self.text_entry.pack(anchor='w', pady=5)

        # 字体选择
        tk.Label(control_frame, text="选择字体文件:").pack(anchor='w', pady=(10,0))
        self.select_font_button = tk.Button(control_frame, text="选择字体文件", command=self.select_fonts)
        self.select_font_button.pack(anchor='w', pady=5)

        # 列出已选择的字体
        self.font_listbox = tk.Listbox(control_frame, height=5, width=40)
        self.font_listbox.pack(anchor='w', pady=5)

        # 字体大小
        tk.Label(control_frame, text="字体大小:").pack(anchor='w', pady=(10,0))
        self.size_spinbox = tk.Spinbox(control_frame, from_=10, to=100, width=5, textvariable=tk.StringVar(value=str(self.font_size)))
        self.size_spinbox.pack(anchor='w', pady=5)
        self.size_spinbox.bind("<FocusOut>", self.update_font_size)
        self.size_spinbox.bind("<Return>", self.update_font_size)

        # 字体颜色
        tk.Label(control_frame, text="字体颜色:").pack(anchor='w', pady=(10,0))
        self.color_entry = tk.Entry(control_frame, width=10)
        self.color_entry.insert(0, self.font_color)
        self.color_entry.pack(anchor='w', pady=5)

        # 语言选择
        tk.Label(control_frame, text="选择OCR语言:").pack(anchor='w', pady=(10,0))
        language_options = {
            "中文简体": "ch_sim",
            "中文繁体": "ch_tra",
            "日语": "jpn",
            "中文简体+繁体": "ch_sim+ch_tra",
            "中文简体+日语": "ch_sim+jpn",
            "中文繁体+日语": "ch_tra+jpn",
            "中文简体+繁体+日语": "ch_sim+ch_tra+jpn"
        }
        self.language_menu = tk.OptionMenu(control_frame, self.selected_languages, *language_options.keys(), command=self.update_selected_language)
        self.language_menu.pack(anchor='w', pady=5)

        # OCR和复制按钮
        self.process_button = tk.Button(control_frame, text="执行OCR并复制文本", command=self.process_ocr_and_copy)
        self.process_button.pack(anchor='w', pady=(20,0))

        # 保存按钮
        self.save_button = tk.Button(control_frame, text="保存图片", command=self.save_image)
        self.save_button.pack(anchor='w', pady=(10,0))

        # 重新加载图片按钮（可选）
        self.reload_button = tk.Button(control_frame, text="重新加载图片", command=self.load_image_initial)
        self.reload_button.pack(anchor='w', pady=(10,0))

        # 添加调试信息区域
        self.debug_frame = tk.Frame(self.root, bd=2, relief=tk.SUNKEN)
        self.debug_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.debug_label = tk.Label(self.debug_frame, text="调试信息")
        self.debug_label.pack()

        self.debug_canvas = tk.Canvas(self.debug_frame, width=200, height=200)
        self.debug_canvas.pack()

        # 添加"清除所有框选"按钮
        self.clear_button = tk.Button(control_frame, text="清除所有框选", command=self.clear_selected_regions)
        self.clear_button.pack(anchor='w', pady=(10,0))

    def update_font_size(self, event=None):
        try:
            new_size = int(self.size_spinbox.get())
            self.font_size = new_size
            print(f"字体大小更新为: {self.font_size}")
        except ValueError:
            messagebox.showerror("错误", "字体大小必须是整数。")
            self.size_spinbox.delete(0, "end")
            self.size_spinbox.insert(0, str(self.font_size))

    def select_fonts(self):
        font_paths = filedialog.askopenfilenames(
            title="选择字体文件",
            filetypes=[("Font Files", "*.ttf;*.otf;*.ttc"), ("All Files", "*.*")]
        )
        if font_paths:
            for path in font_paths:
                if path not in self.selected_fonts:
                    self.selected_fonts.append(path)
                    self.font_listbox.insert(tk.END, os.path.basename(path))
            print(f"已选择的字体: {self.selected_fonts}")

    def update_selected_language(self, selection):
        # 显示当前选择的语言对应的内部代码
        language_map = {
            "中文简体": "ch_sim",
            "中文繁体": "ch_tra",
            "日语": "jpn",
            "中文简体+繁体": "ch_sim+ch_tra",
            "中文简体+日语": "ch_sim+jpn",
            "中文繁体+日语": "ch_tra+jpn",
            "中文简体+繁体+日语": "ch_sim+ch_tra+jpn"
        }
        if selection in language_map:
            self.selected_languages.set(language_map[selection])
            # 重新初始化 EasyOCR Reader
            self.init_easyocr()

    def load_image_initial(self):
        # 清除之前的标记
        self.region_pairs = []
        self.undo_stack = []

        # 选择图片文件
        self.image_path = filedialog.askopenfilename(title="请选择一张图片",
                                                     filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")])
        if not self.image_path:
            messagebox.showerror("错误", "未选择图片，程序将退出。")
            self.root.destroy()
            return
        self.load_image(self.image_path)

    def load_image(self, path):
        try:
            self.original_image = Image.open(path).convert("RGBA")
        except Exception as e:
            messagebox.showerror("错误", f"无法打开图片：{e}")
            return

        # 根据Canvas大小调整图片大小，保持比例
        self.canvas.update()  # 更新Canvas以获取其大小
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width < 10 or canvas_height < 10:
            # 如果Canvas还未正确初始化大小，设置默认尺寸
            canvas_width = 800
            canvas_height = 600

        img_width, img_height = self.original_image.size

        ratio = min(canvas_width / img_width, canvas_height / img_height, 1)
        new_size = (int(img_width * ratio), int(img_height * ratio))
        self.display_image = self.original_image.resize(new_size)

        self.draw = ImageDraw.Draw(self.display_image)
        self.update_canvas()

    def update_canvas(self):
        self.tk_image = ImageTk.PhotoImage(self.display_image)
        self.canvas.delete("all")  # 清除之前的内容
        self.canvas.config(width=self.tk_image.width(), height=self.tk_image.height())
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        # 重新绘制所有标记的方框
        for pair in self.region_pairs:
            src = pair['source']
            destinations = pair.get('destinations', [])
            if src:
                src_x1, src_y1, src_x2, src_y2 = src
                # 绘制源区域红色方框
                self.canvas.create_rectangle(src_x1, src_y1, src_x2, src_y2, outline="red", width=2, tag="selection")
            for dst in destinations:
                dst_x1, dst_y1, dst_x2, dst_y2 = dst
                # 绘制目标区域蓝色方框
                self.canvas.create_rectangle(dst_x1, dst_y1, dst_x2, dst_y2, outline="blue", width=2, tag="selection")

        # 保留预览矩形
        if self.preview_rect:
            self.canvas.tag_raise(self.preview_rect)  # 确保预览矩形在最上层

    def on_left_press(self, event):
        # 按下左键时，无需显示预览，因为预览已始终显示
        pass

    def on_left_release(self, event):
        # 创建源区域
        self.create_source_region(event.x, event.y)

    def on_right_press(self, event):
        self.right_dragging = True
        self.right_drag_start = (event.x, event.y)
        self.right_drag_direction = None
        print(f"右键按下，起始位置：{self.right_drag_start}")

    def on_right_drag_motion(self, event):
        if not self.right_dragging:
            return

        current_pos = (event.x, event.y)
        start_x, start_y = self.right_drag_start
        end_x, end_y = current_pos

        # 确定拖动方向
        if self.right_drag_direction is None:
            delta_x = end_x - start_x
            delta_y = end_y - start_y
            if abs(delta_x) > abs(delta_y):
                self.right_drag_direction = 'horizontal'
            else:
                self.right_drag_direction = 'vertical'
            print(f"拖动方向确定为：{self.right_drag_direction}")

        # 根据拖动方向生成连续方框
        if self.right_drag_direction == 'horizontal':
            step = self.square_size + self.interval.get()
            num = (end_x - start_x) // step
        else:
            step = self.square_size + self.interval.get()
            num = (end_y - start_y) // step

        num = max(num, 1)  # 至少生成一个方框

        self.generate_continuous_targets(start_x, start_y, num, self.right_drag_direction)

    def on_right_release_drag(self, event):
        if not self.right_dragging:
            return

        self.right_dragging = False
        self.right_drag_start = None
        self.right_drag_direction = None

        # 获取最后一个源区域
        if not self.region_pairs:
            return

        last_pair = self.region_pairs[-1]

        for rect_id in self.right_drag_preview:
            # 获取方框坐标
            coords = self.canvas.coords(rect_id)
            x1, y1, x2, y2 = coords

            # 添加到destinations列表
            last_pair['destinations'].append((x1, y1, x2, y2))

            # 修改方框样式为实线
            self.canvas.itemconfig(rect_id, dash=(), outline="blue", tag="selection")

            print(f"添加目标区域：矩形({x1}, {y1}, {x2}, {y2})")

        # 清空预览列表
        self.right_drag_preview.clear()

        print("右键拖动释放，目标方框已添加。")

    def generate_continuous_targets(self, start_x, start_y, num, direction):
        # 清除之前的预览
        for rect_id in self.right_drag_preview:
            self.canvas.delete(rect_id)
        self.right_drag_preview.clear()

        # 获取最后一个源区域
        if not self.region_pairs:
            messagebox.showwarning("警告", "请先用左键点击标记源区域。")
            return

        last_pair = self.region_pairs[-1]

        # 获取用户配置的间隔值
        interval = self.interval.get()

        for i in range(max(num, 1)):
            if direction == 'horizontal':
                x_offset = i * (self.square_size + interval)
                y_offset = 0
            else:
                x_offset = 0
                y_offset = i * (self.square_size + interval)

            new_x = start_x + x_offset
            new_y = start_y + y_offset

            half_size = self.square_size // 2
            x1 = new_x - half_size
            y1 = new_y - half_size
            x2 = new_x + half_size
            y2 = new_y + half_size

            # 绘制预览矩形
            rect_id = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline="blue", dash=(2, 2), width=2
            )
            self.right_drag_preview.append(rect_id)

            print(f"生成预览目标区域：中心({new_x}, {new_y}), 矩形({x1}, {y1}, {x2}, {y2})")

    def on_mouse_move(self, event):
        x, y = event.x, event.y
        self.update_preview_rectangle(x, y)

    def on_mouse_leave(self, event):
        # 鼠标离开画布时，移除预览矩形
        if self.preview_rect:
            self.canvas.delete(self.preview_rect)
            self.preview_rect = None
        # 同时停止右键拖动
        if self.right_dragging:
            self.on_right_release_drag(event)

    def update_preview_rectangle(self, x, y):
        half_size = self.square_size // 2
        x1 = x - half_size
        y1 = y - half_size
        x2 = x + half_size
        y2 = y + half_size

        if self.preview_rect is None:
            # 创建预览矩形
            self.preview_rect = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline="orange", dash=(2, 2), width=2, tag="preview"
            )
        else:
            # 更新预览矩形的位置
            self.canvas.coords(self.preview_rect, x1, y1, x2, y2)

    def on_mousewheel(self, event):
        # 检测滚轮方向并调整 square_size
        if sys.platform.startswith('linux'):
            if event.num == 4:
                delta = 1
            elif event.num == 5:
                delta = -1
            else:
                delta = 0
        else:
            delta = event.delta

        if delta > 0:
            self.square_size = min(self.square_size + 5, 200)  # 最大限制
        elif delta < 0:
            self.square_size = max(self.square_size - 5, 10)   # 最小限制

        # 更新字体大小
        self.font_size = int(self.square_size * 0.85)

        print(f"当前方框大小: {self.square_size}, 字体大小: {self.font_size}")

        # 更新字体大小 Spinbox 显示
        self.size_spinbox.delete(0, "end")
        self.size_spinbox.insert(0, str(self.font_size))

        # 更新预览矩形的大小
        if self.preview_rect:
            x1, y1, x2, y2 = self.canvas.coords(self.preview_rect)
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            self.update_preview_rectangle(center_x, center_y)

        # 如果需要，可以在这里添加代码来更新已经存在的方框和文本

    def create_source_region(self, x, y):
        half_size = self.square_size // 2
        x1 = x - half_size
        y1 = y - half_size
        x2 = x + half_size
        y2 = y + half_size

        pair = {'source': (x1, y1, x2, y2), 'destinations': []}
        self.region_pairs.append(pair)

        self.canvas.create_rectangle(x1, y1, x2, y2, outline="red", width=2, tag="selection")
        print(f"标记源区域：中心({x}, {y}), 矩形({x1}, {y1}, {x2}, {y2})")

    def create_destination_region(self, x, y):
        if not self.region_pairs:
            messagebox.showwarning("警告", "请先用左键点击标记源区域。")
            return

        last_pair = self.region_pairs[-1]
        half_size = self.square_size // 2
        x1 = x - half_size
        y1 = y - half_size
        x2 = x + half_size
        y2 = y + half_size

        last_pair['destinations'].append((x1, y1, x2, y2))

        self.canvas.create_rectangle(x1, y1, x2, y2, outline="blue", width=2, tag="selection")
        print(f"标记目标区域：中心({x}, {y}), 矩形({x1}, {y1}, {x2}, {y2})")

    def process_ocr_and_copy(self):
        if not self.region_pairs:
            messagebox.showwarning("警告", "没有标记任何源和目标区域。")
            return

        if not self.selected_fonts:
            messagebox.showwarning("警告", "请先选择至少一个字体文件。")
            return

        # 获取选择的语言代码
        languages = self.selected_languages.get()
        language_list = languages.split('+')  # 将语言代码拆分为列表
        print(f"使用的OCR语言：{language_list}")

        for index, pair in enumerate(self.region_pairs, start=1):
            src = pair['source']
            destinations = pair.get('destinations', [])

            src_x1, src_y1, src_x2, src_y2 = src

            # 裁剪源区域，考虑图像缩放比例
            scale_x = self.original_image.width / self.display_image.width
            scale_y = self.original_image.height / self.display_image.height
            src_box = (
                int(src_x1 * scale_x),
                int(src_y1 * scale_y),
                int(src_x2 * scale_x),
                int(src_y2 * scale_y)
            )
            src_region = self.original_image.crop(src_box)

            # 显示调试图像
            self.display_debug_image(src_region, f"区域 {index} OCR 图像")

            # 执行 OCR
            try:
                # Convert PIL Image to OpenCV format (BGR)
                img = src_region.convert("RGB")
                img = np.array(img)
                img = img[:, :, ::-1]  # RGB to BGR

                ocr_result = self.reader.readtext(img, detail=0, paragraph=True)
                ocr_text = ' '.join(ocr_result).strip()
            except Exception as e:
                messagebox.showerror("错误", f"执行OCR时发生错误：{e}")
                return

            print(f"区域 {index} OCR 结果: {ocr_text}")

            if not ocr_text:
                messagebox.showwarning("警告", f"区域 {index} 未识别到任何文本。")
                continue

            # 获取文本属性
            font_color = self.color_entry.get()

            # 将OCR文本添加到所有目标区域
            for dst_index, dst in enumerate(destinations, start=1):
                dst_x1, dst_y1, dst_x2, dst_y2 = dst
                box_width = dst_x2 - dst_x1
                box_height = dst_y2 - dst_y1

                # 计算起始位置
                text_x = dst_x1
                text_y = dst_y1

                # 将文本逐字符绘制，随机选择字体，确保相邻字符字体不同
                last_font = None
                total_width = 0
                max_text_height = 0

                for char in ocr_text:
                    # 选择不同于上一个字体的字体
                    available_fonts = [f for f in self.selected_fonts if f != last_font]
                    if not available_fonts:
                        available_fonts = self.selected_fonts  # 如果所有字体都被使用，允许重复
                    font_path = random.choice(available_fonts)
                    last_font = font_path

                    # 加载字体，如果未加载过
                    if font_path not in self.loaded_fonts:
                        try:
                            pil_font = ImageFont.truetype(font_path, self.font_size)
                            self.loaded_fonts[font_path] = pil_font
                        except Exception as e:
                            print(f"无法加载字体 {font_path}：{e}")
                            pil_font = ImageFont.load_default()
                            self.loaded_fonts[font_path] = pil_font
                    else:
                        pil_font = self.loaded_fonts[font_path]
                    # 获取字符大小并添加随机变化
                    text_bbox = pil_font.getbbox(char)
                    char_width = text_bbox[2] - text_bbox[0]
                    char_height = text_bbox[3] - text_bbox[1]
                    
                    # 添加0.05的随机变化
                    size_variation = np.random.uniform(0.95, 1.05)
                    char_width *= size_variation
                    char_height *= size_variation
                    
                    max_text_height = max(max_text_height, char_height)

                    # 添加随机偏差
                    max_offset_x = box_width * 0.10
                    max_offset_y = box_height * 0.05
                    random_offset_x = np.random.uniform(-max_offset_x/2, max_offset_x/2)
                    random_offset_y = np.random.uniform(-max_offset_y, max_offset_y)

                    # 计算字符位置
                    current_x = dst_x1 + (box_width - total_width) / 2 + random_offset_x - char_width / 2
                    current_y = dst_y1 + (box_height - max_text_height) / 2 + random_offset_y

                    # 绘制字符，使用调整后的大小
                    font_with_size = pil_font.font_variant(size=int(self.font_size * size_variation))
                    self.draw.text((current_x + total_width, current_y), char, font=font_with_size, fill=font_color)

                    # 更新总宽度
                    total_width += char_width

                print(f"文本已添加到区域 {index}-{dst_index}")

        # 更新显示
        self.update_canvas()
        messagebox.showinfo("完成", "OCR 和文本复制已完成。")

    def save_image(self):
        save_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                 filetypes=[("PNG Image", "*.png"),
                                                            ("JPEG Image", "*.jpg;*.jpeg"),
                                                            ("Bitmap Image", "*.bmp")],
                                                 title="保存图片")
        if save_path:
            try:
                self.display_image.save(save_path)
                messagebox.showinfo("成功", f"图片已保存到 {save_path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存图片时发生错误：{e}")

    def display_debug_image(self, image, text):
        # 调整图像大小以适应调试画布
        image = image.resize((200, 200), Image.LANCZOS)
        self.debug_image = ImageTk.PhotoImage(image)
        self.debug_canvas.delete("all")
        self.debug_canvas.create_image(100, 100, anchor=tk.CENTER, image=self.debug_image)
        self.debug_label.config(text=f"{text}\n原始大小: {image.width}x{image.height}")
        self.debug_frame.update()  # 只更新调试框架
        self.debug_canvas.update()  # 确保画布更新

    def clear_selected_regions(self):
        if not self.region_pairs:
            messagebox.showinfo("信息", "当前没有任何框选需要清除。")
            return

        # 清空区域对列表
        self.region_pairs.clear()

        # 清除画布上的所有框选
        self.canvas.delete("selection")

        # 清除调试信息区域
        self.debug_canvas.delete("all")
        self.debug_label.config(text="调试信息")

        messagebox.showinfo("信息", "所有框选已清除。")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    root = tk.Tk()
    app = PenaltyCopyApp(root)
    app.run()