import tkinter as tk
from tkinter import filedialog, font, messagebox, ttk
from PIL import Image, ImageTk, ImageDraw, ImageFont
import os
import sys
import numpy as np
import random
import OCR  # 引入OCR.py中的getTextFromImage函数


class PenaltyCopyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("罚抄生成器")
        self.root.geometry("1600x900")  # 增加窗口大小以适应字体列表和批量应用按钮

        # 初始化变量
        self.text = tk.StringVar()
        self.square_size = 50
        self.font_size = int(self.square_size * 0.85)  # 初始字体大小是框大小的85%
        self.font_color = "black"
        self.selected_language = tk.StringVar(value="cn")  # 默认语言

        # 存储源和目标区域的相对比例
        self.region_pairs = []  # 每对：{'source': [x1_ratio, y1_ratio, x2_ratio, y2_ratio], 'destinations': [[x1_ratio, y1_ratio, x2_ratio, y2_ratio], ...]}

        # 存储选中的字体文件路径
        self.selected_fonts = []
        self.loaded_fonts = {}  # 缓存已加载的字体

        # 存储目标框之间的间隔，默认为1像素
        self.interval = tk.IntVar(value=1)

        # 变量用于跟踪预览矩形
        self.preview_rect = None  # 预览矩形ID

        # 变量用于跟踪右键拖动
        self.right_dragging = False
        self.right_drag_start = None  # 右键拖动的起始位置
        self.right_drag_direction = None  # 'horizontal' 或 'vertical'
        self.right_drag_preview = []  # 预览目标框ID列表

        # 设置UI
        self.setup_ui()

        # 加载初始图片
        self.load_image_initial()

        self.debug_image = None  # 存储调试图片

    def setup_ui(self):
        # 左侧画布显示图片
        self.canvas_frame = tk.Frame(self.root, bd=2, relief=tk.SUNKEN)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg="grey")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_left_press)    # 左键按下
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)  # 左键释放
        self.canvas.bind("<Button-3>", self.on_right_press)   # 右键按下
        self.canvas.bind("<B3-Motion>", self.on_right_drag_motion)      # 右键拖动
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release_drag)  # 右键释放
        self.canvas.bind("<Motion>", self.on_mouse_move)           # 鼠标移动
        self.canvas.bind("<Leave>", self.on_mouse_leave)           # 鼠标离开画布

        # 绑定鼠标滚轮事件
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
        tk.Label(control_frame, text="目标框间隔:").pack(anchor='w', pady=(10, 0))
        self.interval_spinbox = tk.Spinbox(control_frame, from_=0, to=100, width=5, textvariable=self.interval)
        self.interval_spinbox.pack(anchor='w', pady=5)

        # 输入标签和输入框（保留以保持原始功能）
        tk.Label(control_frame, text="输入内容:").pack(anchor='w')
        self.text_entry = tk.Entry(control_frame, textvariable=self.text, width=30)
        self.text_entry.pack(anchor='w', pady=5)

        # 字体选择
        tk.Label(control_frame, text="选择字体文件:").pack(anchor='w', pady=(10, 0))
        self.select_font_button = tk.Button(control_frame, text="选择字体文件", command=self.select_fonts)
        self.select_font_button.pack(anchor='w', pady=5)

        # 选中的字体列表
        self.font_listbox = tk.Listbox(control_frame, height=5, width=40)
        self.font_listbox.pack(anchor='w', pady=5)

        # 字体大小
        tk.Label(control_frame, text="字体大小:").pack(anchor='w', pady=(10, 0))
        self.size_var = tk.StringVar(value=str(self.font_size))
        self.size_spinbox = tk.Spinbox(control_frame, from_=10, to=100, width=5, textvariable=self.size_var)
        self.size_spinbox.pack(anchor='w', pady=5)
        self.size_spinbox.bind("<FocusOut>", self.update_font_size)
        self.size_spinbox.bind("<Return>", self.update_font_size)

        # 字体颜色
        tk.Label(control_frame, text="字体颜色:").pack(anchor='w', pady=(10, 0))
        self.color_entry = tk.Entry(control_frame, width=10)
        self.color_entry.insert(0, self.font_color)
        self.color_entry.pack(anchor='w', pady=5)

        # 语言选择
        tk.Label(control_frame, text="选择OCR语言:").pack(anchor='w', pady=(10, 0))
        language_options = {
            "英语": "en",
            "中文": "cn",
            "日语": "ja"
        }
        self.language_menu = tk.OptionMenu(control_frame, self.selected_language, *language_options.keys(),
                                          command=self.update_selected_language)
        self.language_menu.pack(anchor='w', pady=5)

        # OCR和复制按钮
        self.process_button = tk.Button(control_frame, text="执行OCR并复制文本", command=self.process_ocr_and_copy)
        self.process_button.pack(anchor='w', pady=(20, 0))

        # 批量应用按钮
        self.batch_button = tk.Button(control_frame, text="批量应用", command=self.batch_apply_ocr_copy, fg="blue")
        self.batch_button.pack(anchor='w', pady=(10, 0))

        # 保存按钮
        self.save_button = tk.Button(control_frame, text="保存图片", command=self.save_image)
        self.save_button.pack(anchor='w', pady=(10, 0))

        # 重新加载图片按钮（可选）
        self.reload_button = tk.Button(control_frame, text="重新加载图片", command=self.load_image_initial)
        self.reload_button.pack(anchor='w', pady=(10, 0))

        # 调试信息区域
        self.debug_frame = tk.Frame(self.root, bd=2, relief=tk.SUNKEN)
        self.debug_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.debug_label = tk.Label(self.debug_frame, text="调试信息")
        self.debug_label.pack()

        self.debug_canvas = tk.Canvas(self.debug_frame, width=200, height=200)
        self.debug_canvas.pack()

        # "清除所有框选" 按钮
        self.clear_button = tk.Button(control_frame, text="清除所有框选", command=self.clear_selected_regions)
        self.clear_button.pack(anchor='w', pady=(10, 0))

    def update_font_size(self, event=None):
        try:
            new_size = int(self.size_spinbox.get())
            self.font_size = new_size
            self.size_var.set(str(self.font_size))
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
        language_map = {
            "英语": "en",
            "中文": "cn",
            "日语": "ja"
        }
        if selection in language_map:
            self.selected_language.set(language_map[selection])
            print(f"选择的OCR语言: {self.selected_language.get()}")

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

        # 根据画布大小调整图片大小，同时保持长宽比
        self.canvas.update()  # 更新画布以获取其大小
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width < 10 or canvas_height < 10:
            # 如果画布未正确初始化，设置默认大小
            canvas_width = 800
            canvas_height = 600

        img_width, img_height = self.original_image.size

        # 计算相对缩放因子
        self.scale_x = img_width / canvas_width
        self.scale_y = img_height / canvas_height

        ratio = min(canvas_width / img_width, canvas_height / img_height, 1)
        self.display_size = (int(img_width * ratio), int(img_height * ratio))
        
        # 根据Pillow版本选择重采样滤镜
        try:
            resample_filter = Image.Resampling.LANCZOS  # Pillow >=10
        except AttributeError:
            resample_filter = Image.LANCZOS  # Pillow <10

        self.display_image = self.original_image.resize(self.display_size, resample=resample_filter)

        self.draw = ImageDraw.Draw(self.display_image)
        self.update_canvas()

    def update_canvas(self):
        self.tk_image = ImageTk.PhotoImage(self.display_image)
        self.canvas.delete("all")  # 清除之前的内容
        self.canvas.config(width=self.tk_image.width(), height=self.tk_image.height())
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        # 重新绘制所有标记的框
        for pair in self.region_pairs:
            src = pair['source']  # [x1_ratio, y1_ratio, x2_ratio, y2_ratio]
            destinations = pair.get('destinations', [])  # 目标列表
            if src:
                src_x1 = src[0] * self.display_size[0]
                src_y1 = src[1] * self.display_size[1]
                src_x2 = src[2] * self.display_size[0]
                src_y2 = src[3] * self.display_size[1]
                # 绘制源区域红色框
                self.canvas.create_rectangle(src_x1, src_y1, src_x2, src_y2, outline="red", width=2, tag="selection")
            for dst in destinations:
                dst_x1 = dst[0] * self.display_size[0]
                dst_y1 = dst[1] * self.display_size[1]
                dst_x2 = dst[2] * self.display_size[0]
                dst_y2 = dst[3] * self.display_size[1]
                # 绘制目标区域蓝色框
                self.canvas.create_rectangle(dst_x1, dst_y1, dst_x2, dst_y2, outline="blue", width=2, tag="selection")

        # 保持预览矩形在顶层
        if self.preview_rect:
            self.canvas.tag_raise(self.preview_rect)  # 确保预览矩形在顶层

    def on_left_press(self, event):
        # 左键按下时不执行任何操作；预览始终显示
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

        # 基于拖动方向生成连续的目标框
        if self.right_drag_direction == 'horizontal':
            step = self.square_size + self.interval.get()
            num = (end_x - start_x) // step
        else:
            step = self.square_size + self.interval.get()
            num = (end_y - start_y) // step

        num = max(num, 1)  # 至少一个框

        self.generate_continuous_targets(start_x, start_y, num, self.right_drag_direction)

    def on_right_release_drag(self, event):
        if not self.right_dragging:
            return

        self.right_dragging = False
        self.right_drag_start = None
        self.right_drag_direction = None

        # 获取最后一对区域
        if not self.region_pairs:
            return

        last_pair = self.region_pairs[-1]

        for rect_id in self.right_drag_preview:
            # 获取框的坐标
            coords = self.canvas.coords(rect_id)
            x1, y1, x2, y2 = coords

            # 转换为原始图片的比例
            x1_ratio = x1 / self.display_size[0]
            y1_ratio = y1 / self.display_size[1]
            x2_ratio = x2 / self.display_size[0]
            y2_ratio = y2 / self.display_size[1]

            # 添加到目标列表
            last_pair['destinations'].append([x1_ratio, y1_ratio, x2_ratio, y2_ratio])

            # 更改框样式为实线
            self.canvas.itemconfig(rect_id, dash=(), outline="blue", tag="selection")

            print(f"添加目标区域：矩形({x1_ratio:.4f}, {y1_ratio:.4f}, {x2_ratio:.4f}, {y2_ratio:.4f})")

        # 清除预览列表
        self.right_drag_preview.clear()

        print("右键拖动释放，目标方框已添加。")

    def generate_continuous_targets(self, start_x, start_y, num, direction):
        # 清除之前的预览
        for rect_id in self.right_drag_preview:
            self.canvas.delete(rect_id)
        self.right_drag_preview.clear()

        # 获取最后一对区域
        if not self.region_pairs:
            messagebox.showwarning("警告", "请先用左键点击标记源区域。")
            return

        last_pair = self.region_pairs[-1]

        # 获取用户定义的间隔
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

            # 绘制预览框
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
        # 当鼠标离开画布时删除预览矩形
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
            # 更新预览矩形位置
            self.canvas.coords(self.preview_rect, x1, y1, x2, y2)

    def on_mousewheel(self, event):
        # 检测滚动方向并调整方框大小
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

        # 更新预览矩形大小
        if self.preview_rect:
            x1, y1, x2, y2 = self.canvas.coords(self.preview_rect)
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            self.update_preview_rectangle(center_x, center_y)

        # 可选：在此处添加代码以根据需要更新现有框和文本

    def create_source_region(self, x, y):
        half_size = self.square_size // 2
        x1_display = x - half_size
        y1_display = y - half_size
        x2_display = x + half_size
        y2_display = y + half_size

        # 转换为原始图片的相对比例
        x1_ratio = x1_display / self.display_size[0]
        y1_ratio = y1_display / self.display_size[1]
        x2_ratio = x2_display / self.display_size[0]
        y2_ratio = y2_display / self.display_size[1]

        pair = {'source': [x1_ratio, y1_ratio, x2_ratio, y2_ratio], 'destinations': []}
        self.region_pairs.append(pair)

        self.canvas.create_rectangle(x1_display, y1_display, x2_display, y2_display, outline="red", width=2, tag="selection")
        print(f"标记源区域：中心({x}, {y}), 矩形({x1_ratio:.4f}, {y1_ratio:.4f}, {x2_ratio:.4f}, {y2_ratio:.4f})")

    def create_destination_region(self, x, y):
        if not self.region_pairs:
            messagebox.showwarning("警告", "请先用左键点击标记源区域。")
            return

        last_pair = self.region_pairs[-1]
        half_size = self.square_size // 2
        x1_display = x - half_size
        y1_display = y - half_size
        x2_display = x + half_size
        y2_display = y + half_size

        # 转换为原始图片的相对比例
        x1_ratio = x1_display / self.display_size[0]
        y1_ratio = y1_display / self.display_size[1]
        x2_ratio = x2_display / self.display_size[0]
        y2_ratio = y2_display / self.display_size[1]

        last_pair['destinations'].append([x1_ratio, y1_ratio, x2_ratio, y2_ratio])

        self.canvas.create_rectangle(x1_display, y1_display, x2_display, y2_display, outline="blue", width=2, tag="selection")
        print(f"标记目标区域：中心({x}, {y}), 矩形({x1_ratio:.4f}, {y1_ratio:.4f}, {x2_ratio:.4f}, {y2_ratio:.4f})")

    def process_ocr_and_copy(self):
        if not self.region_pairs:
            messagebox.showwarning("警告", "没有标记任何源和目标区域。")
            return

        if not self.selected_fonts:
            messagebox.showwarning("警告", "请先选择至少一个字体文件。")
            return

        self.process_image(self.original_image.copy(), self.image_path, self.display_size)

        # 更新显示
        self.update_canvas()
        messagebox.showinfo("完成", "OCR 和文本复制已完成。")

    def process_image(self, image, image_path, display_size):
        draw = ImageDraw.Draw(image)
        img_width, img_height = image.size

        language = self.selected_language.get()

        for index, pair in enumerate(self.region_pairs, start=1):
            src = pair['source']  # [x1_ratio, y1_ratio, x2_ratio, y2_ratio]
            destinations = pair.get('destinations', [])

            src_box = (
                int(src[0] * img_width),
                int(src[1] * img_height),
                int(src[2] * img_width),
                int(src[3] * img_height)
            )
            src_region = image.crop(src_box)

            # 显示调试图片
            self.display_debug_image(src_region, f"区域 {index} OCR 图像")

            # 执行OCR
            try:
                ocr_text = OCR.getTextFromImage(src_region, language)
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
                dst_box = (
                    int(dst[0] * img_width),
                    int(dst[1] * img_height),
                    int(dst[2] * img_width),
                    int(dst[3] * img_height)
                )
                box_width = dst_box[2] - dst_box[0]
                box_height = dst_box[3] - dst_box[1]

                # 计算起始位置
                text_x = dst_box[0]
                text_y = dst_box[1]

                # 逐字符绘制文本，随机选择字体并做轻微变化
                last_font = None
                total_width = 0
                max_text_height = 0

                for char in ocr_text:
                    # 选择不同于上一个的字体
                    available_fonts = [f for f in self.selected_fonts if f != last_font]
                    if not available_fonts:
                        available_fonts = self.selected_fonts  # 如果所有字体都用过，允许重复
                    font_path = random.choice(available_fonts)
                    last_font = font_path

                    # 如果字体未加载，则加载字体
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

                    # 获取字符大小，并做轻微随机变化
                    try:
                        char_width, char_height = pil_font.getsize(char)
                    except:
                        char_width, char_height = (10, 10)  # 备用尺寸

                    # 添加0.05的随机变化
                    size_variation = np.random.uniform(0.95, 1.05)
                    char_width = int(char_width * size_variation)
                    char_height = int(char_height * size_variation)

                    max_text_height = max(max_text_height, char_height)

                    # 添加随机偏移
                    max_offset_x = box_width * 0.7
                    max_offset_y = box_height * 0.025
                    random_offset_x = np.random.uniform(-max_offset_x / 2, max_offset_x / 2)
                    random_offset_y = np.random.uniform(-max_offset_y, max_offset_y)

                    # 计算字符位置
                    current_x = dst_box[0] + (box_width - total_width) / 2 + random_offset_x - char_width / 2
                    current_y = dst_box[1] + (box_height - max_text_height) / 2 + random_offset_y

                    # 使用调整后的大小绘制字符
                    try:
                        font_with_size = pil_font.font_variant(size=int(self.font_size * size_variation))
                        draw.text((current_x + total_width, current_y), char, font=font_with_size, fill=font_color)
                    except Exception as e:
                        print(f"绘制字符时发生错误：{e}")

                    # 更新总宽度
                    total_width += char_width

                print(f"文本已添加到区域 {index}-{dst_index}")

        # 更新原始图片
        self.original_image = image

        # **新增部分开始**
        # Resize the updated original_image to display_size to update display_image
        try:
            resample_filter = self.get_resampling_filter()
            self.display_image = self.original_image.resize(self.display_size, resample=resample_filter)
        except Exception as e:
            messagebox.showerror("错误", f"调整图像大小时发生错误：{e}")
            return
        # **新增部分结束**

        # 更新显示画布
        self.update_canvas()

    def save_image(self):
        save_path = filedialog.asksaveasfilename(defaultextension=".png",
                                                 filetypes=[("PNG Image", "*.png"),
                                                            ("JPEG Image", "*.jpg;*.jpeg"),
                                                            ("Bitmap Image", "*.bmp")],
                                                 title="保存图片")
        if save_path:
            try:
                self.original_image.save(save_path)
                messagebox.showinfo("成功", f"图片已保存到 {save_path}")
            except Exception as e:
                messagebox.showerror("错误", f"保存图片时发生错误：{e}")

    def display_debug_image(self, image, text):
        # 调整图片大小以适应调试画布
        image = image.resize((200, 200), self.get_resampling_filter())
        self.debug_image = ImageTk.PhotoImage(image)
        self.debug_canvas.delete("all")
        self.debug_canvas.create_image(100, 100, anchor=tk.CENTER, image=self.debug_image)
        self.debug_label.config(text=f"{text}\n原始大小: {image.width}x{image.height}")
        self.debug_frame.update()  # 仅更新调试框架
        self.debug_canvas.update()  # 确保画布更新

    def clear_selected_regions(self):
        if not self.region_pairs:
            messagebox.showinfo("信息", "当前没有任何框选需要清除。")
            return

        # 清除区域对列表
        self.region_pairs.clear()

        # 清除画布上的所有选择
        self.canvas.delete("selection")

        # 清除调试信息区域
        self.debug_canvas.delete("all")
        self.debug_label.config(text="调试信息")

        messagebox.showinfo("信息", "所有框选已清除。")

    def batch_apply_ocr_copy(self):
        if not self.region_pairs:
            messagebox.showwarning("警告", "请先标记源和目标区域。")
            return

        if not self.selected_fonts:
            messagebox.showwarning("警告", "请先选择至少一个字体文件。")
            return

        # 选择多张图片
        batch_image_paths = filedialog.askopenfilenames(
            title="选择要批量处理的图片",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")]
        )
        if not batch_image_paths:
            messagebox.showinfo("信息", "未选择任何图片。")
            return

        # 选择输出文件夹
        output_folder = filedialog.askdirectory(title="选择输出文件夹")
        if not output_folder:
            messagebox.showinfo("信息", "未选择输出文件夹。")
            return

        # 获取选中的语言代码
        language = self.selected_language.get()
        print(f"使用的OCR语言：{language}")

        total = len(batch_image_paths)
        processed = 0

        for img_path in batch_image_paths:
            try:
                # 打开图片
                image = Image.open(img_path).convert("RGBA")
                img_width, img_height = image.size
                draw = ImageDraw.Draw(image)

                for index, pair in enumerate(self.region_pairs, start=1):
                    src = pair['source']  # [x1_ratio, y1_ratio, x2_ratio, y2_ratio]
                    destinations = pair.get('destinations', [])

                    src_box = (
                        int(src[0] * img_width),
                        int(src[1] * img_height),
                        int(src[2] * img_width),
                        int(src[3] * img_height)
                    )
                    src_region = image.crop(src_box)

                    # 执行OCR
                    try:
                        ocr_text = OCR.getTextFromImage(src_region, language)
                    except Exception as e:
                        print(f"执行OCR时发生错误：{e}")
                        continue

                    print(f"图片 '{os.path.basename(img_path)}' 区域 {index} OCR 结果: {ocr_text}")

                    if not ocr_text:
                        print(f"警告: 图片 '{os.path.basename(img_path)}' 区域 {index} 未识别到任何文本。")
                        continue

                    # 获取文本属性
                    font_color = self.color_entry.get()

                    # 将OCR文本添加到所有目标区域
                    for dst_index, dst in enumerate(destinations, start=1):
                        dst_box = (
                            int(dst[0] * img_width),
                            int(dst[1] * img_height),
                            int(dst[2] * img_width),
                            int(dst[3] * img_height)
                        )
                        box_width = dst_box[2] - dst_box[0]
                        box_height = dst_box[3] - dst_box[1]

                        # 计算起始位置
                        text_x = dst_box[0]
                        text_y = dst_box[1]

                        # 逐字符绘制文本，随机选择字体并做轻微变化
                        last_font = None
                        total_width = 0
                        max_text_height = 0

                        for char in ocr_text:
                            # 选择不同于上一个的字体
                            available_fonts = [f for f in self.selected_fonts if f != last_font]
                            if not available_fonts:
                                available_fonts = self.selected_fonts  # 如果所有字体都用过，允许重复
                            font_path = random.choice(available_fonts)
                            last_font = font_path

                            # 如果字体未加载，则加载字体
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

                            # 获取字符大小，并做轻微随机变化
                            try:
                                char_width, char_height = pil_font.getsize(char)
                            except:
                                char_width, char_height = (10, 10)  # 备用尺寸

                            # 添加0.05的随机变化
                            size_variation = np.random.uniform(0.95, 1.05)
                            char_width = int(char_width * size_variation)
                            char_height = int(char_height * size_variation)

                            max_text_height = max(max_text_height, char_height)

                            # 添加随机偏移
                            max_offset_x = box_width * 0.7
                            max_offset_y = box_height * 0.025
                            random_offset_x = np.random.uniform(-max_offset_x / 2, max_offset_x / 2)
                            random_offset_y = np.random.uniform(-max_offset_y, max_offset_y)

                            # 计算字符位置
                            current_x = dst_box[0] + (box_width - total_width) / 2 + random_offset_x - char_width / 2
                            current_y = dst_box[1] + (box_height - max_text_height) / 2 + random_offset_y

                            # 使用调整后的大小绘制字符
                            try:
                                font_with_size = pil_font.font_variant(size=int(self.font_size * size_variation))
                                draw.text((current_x + total_width, current_y), char, font=font_with_size, fill=font_color)
                            except Exception as e:
                                print(f"绘制字符时发生错误：{e}")

                            # 更新总宽度
                            total_width += char_width

                        print(f"文本已添加到图片 '{os.path.basename(img_path)}' 区域 {index}-{dst_index}")

                # 保存修改后的图片
                base_name = os.path.basename(img_path)
                name, ext = os.path.splitext(base_name)
                save_path = os.path.join(output_folder, f"{name}_modified{ext}")
                image.save(save_path)
                print(f"图片已保存到 {save_path}")
                processed += 1

            except Exception as e:
                print(f"处理图片 '{os.path.basename(img_path)}' 时发生错误：{e}")
                continue

        messagebox.showinfo("完成", f"批量处理完成。共处理 {processed} 张图片。")

    def run(self):
        self.root.mainloop()

    def get_resampling_filter(self):
        """辅助方法以获取适当的重采样滤镜。"""
        try:
            return Image.Resampling.LANCZOS  # Pillow >=10
        except AttributeError:
            return Image.LANCZOS  # Pillow <10


if __name__ == "__main__":
    root = tk.Tk()
    app = PenaltyCopyApp(root)
    app.run()