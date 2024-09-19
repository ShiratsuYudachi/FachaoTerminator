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
        self.root.geometry("1600x900")  # Increased window size to accommodate font list and batch apply button

        # Initialize variables
        self.text = tk.StringVar()
        self.square_size = 50
        self.font_size = int(self.square_size * 0.85)  # Initial font size is 85% of box size
        self.font_color = "black"
        self.selected_languages = tk.StringVar(value="ja")  # Default language

        # Store source and destination regions as relative ratios
        self.region_pairs = []  # Each pair: {'source': [x1_ratio, y1_ratio, x2_ratio, y2_ratio], 'destinations': [[x1_ratio, y1_ratio, x2_ratio, y2_ratio], ...]}

        # Store selected font file paths
        self.selected_fonts = []
        self.loaded_fonts = {}  # Cache loaded fonts

        # Variable to store interval between target boxes, default 1 pixel
        self.interval = tk.IntVar(value=1)

        # Variable to track preview rectangle
        self.preview_rect = None  # Preview rectangle ID

        # Variables to track right-click dragging
        self.right_dragging = False
        self.right_drag_start = None  # Starting position of right-click drag
        self.right_drag_direction = None  # 'horizontal' or 'vertical'
        self.right_drag_preview = []  # List of preview target box IDs

        # Initialize EasyOCR Reader
        self.init_easyocr()

        # Set up UI
        self.setup_ui()

        # Load initial image
        self.load_image_initial()

        self.debug_image = None  # To store debug image

    def init_easyocr(self):
        try:
            # Initialize EasyOCR with selected languages
            languages = self.selected_languages.get().split('+')
            self.reader = easyocr.Reader(languages, gpu=False)  # Set gpu=True if you have a compatible GPU
        except Exception as e:
            messagebox.showerror("错误", f"初始化 EasyOCR 时发生错误：{e}")
            sys.exit(1)

    def setup_ui(self):
        # Left Canvas to display image
        self.canvas_frame = tk.Frame(self.root, bd=2, relief=tk.SUNKEN)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg="grey")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_left_press)    # Left mouse button press
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)  # Left mouse button release
        self.canvas.bind("<Button-3>", self.on_right_press)   # Right mouse button press
        self.canvas.bind("<B3-Motion>", self.on_right_drag_motion)      # Right mouse button drag
        self.canvas.bind("<ButtonRelease-3>", self.on_right_release_drag)  # Right mouse button release
        self.canvas.bind("<Motion>", self.on_mouse_move)           # Mouse move
        self.canvas.bind("<Leave>", self.on_mouse_leave)           # Mouse leave canvas

        # Bind mouse wheel events
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

        # Right Control Panel
        control_frame = tk.Frame(self.root, padx=10, pady=10)
        control_frame.pack(side=tk.RIGHT, fill=tk.Y)

        # Target box interval setting
        tk.Label(control_frame, text="目标框间隔:").pack(anchor='w', pady=(10, 0))
        self.interval_spinbox = tk.Spinbox(control_frame, from_=0, to=100, width=5, textvariable=self.interval)
        self.interval_spinbox.pack(anchor='w', pady=5)

        # Input label and entry (Reserved to maintain original functionality)
        tk.Label(control_frame, text="输入内容:").pack(anchor='w')
        self.text_entry = tk.Entry(control_frame, textvariable=self.text, width=30)
        self.text_entry.pack(anchor='w', pady=5)

        # Font selection
        tk.Label(control_frame, text="选择字体文件:").pack(anchor='w', pady=(10, 0))
        self.select_font_button = tk.Button(control_frame, text="选择字体文件", command=self.select_fonts)
        self.select_font_button.pack(anchor='w', pady=5)

        # List of selected fonts
        self.font_listbox = tk.Listbox(control_frame, height=5, width=40)
        self.font_listbox.pack(anchor='w', pady=5)

        # Font size
        tk.Label(control_frame, text="字体大小:").pack(anchor='w', pady=(10, 0))
        self.size_var = tk.StringVar(value=str(self.font_size))
        self.size_spinbox = tk.Spinbox(control_frame, from_=10, to=100, width=5, textvariable=self.size_var)
        self.size_spinbox.pack(anchor='w', pady=5)
        self.size_spinbox.bind("<FocusOut>", self.update_font_size)
        self.size_spinbox.bind("<Return>", self.update_font_size)

        # Font color
        tk.Label(control_frame, text="字体颜色:").pack(anchor='w', pady=(10, 0))
        self.color_entry = tk.Entry(control_frame, width=10)
        self.color_entry.insert(0, self.font_color)
        self.color_entry.pack(anchor='w', pady=5)

        # Language selection
        tk.Label(control_frame, text="选择OCR语言:").pack(anchor='w', pady=(10, 0))
        language_options = {
            "中文简体": "ch_sim",
            "中文繁体": "ch_tra",
            "日语": "jpn",
            "中文简体+繁体": "ch_sim+ch_tra",
            "中文简体+日语": "ch_sim+jpn",
            "中文繁体+日语": "ch_tra+jpn",
            "中文简体+繁体+日语": "ch_sim+ch_tra+jpn"
        }
        self.language_menu = tk.OptionMenu(control_frame, self.selected_languages, *language_options.keys(),
                                          command=self.update_selected_language)
        self.language_menu.pack(anchor='w', pady=5)

        # OCR and Copy Button
        self.process_button = tk.Button(control_frame, text="执行OCR并复制文本", command=self.process_ocr_and_copy)
        self.process_button.pack(anchor='w', pady=(20, 0))

        # Batch Apply Button
        self.batch_button = tk.Button(control_frame, text="批量应用", command=self.batch_apply_ocr_copy, fg="blue")
        self.batch_button.pack(anchor='w', pady=(10, 0))

        # Save Button
        self.save_button = tk.Button(control_frame, text="保存图片", command=self.save_image)
        self.save_button.pack(anchor='w', pady=(10, 0))

        # Reload Image Button (Optional)
        self.reload_button = tk.Button(control_frame, text="重新加载图片", command=self.load_image_initial)
        self.reload_button.pack(anchor='w', pady=(10, 0))

        # Debug Information Area
        self.debug_frame = tk.Frame(self.root, bd=2, relief=tk.SUNKEN)
        self.debug_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.debug_label = tk.Label(self.debug_frame, text="调试信息")
        self.debug_label.pack()

        self.debug_canvas = tk.Canvas(self.debug_frame, width=200, height=200)
        self.debug_canvas.pack()

        # "Clear All Selections" Button
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
        # Display the internal code corresponding to the selected language
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
            # Reinitialize EasyOCR Reader
            self.init_easyocr()

    def load_image_initial(self):
        # Clear previous markings
        self.region_pairs = []
        self.undo_stack = []

        # Select image file
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

        # Adjust image size based on Canvas size while maintaining aspect ratio
        self.canvas.update()  # Update Canvas to get its size
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        if canvas_width < 10 or canvas_height < 10:
            # If Canvas is not properly initialized, set default size
            canvas_width = 800
            canvas_height = 600

        img_width, img_height = self.original_image.size

        # Calculate relative scaling factors
        self.scale_x = img_width / canvas_width
        self.scale_y = img_height / canvas_height

        ratio = min(canvas_width / img_width, canvas_height / img_height, 1)
        self.display_size = (int(img_width * ratio), int(img_height * ratio))
        
        # Replace Image.ANTIALIAS with the appropriate resampling filter
        try:
            resample_filter = Image.Resampling.LANCZOS  # Pillow >=10
        except AttributeError:
            resample_filter = Image.LANCZOS  # Pillow <10

        self.display_image = self.original_image.resize(self.display_size, resample=resample_filter)

        self.draw = ImageDraw.Draw(self.display_image)
        self.update_canvas()

    def update_canvas(self):
        self.tk_image = ImageTk.PhotoImage(self.display_image)
        self.canvas.delete("all")  # Clear previous content
        self.canvas.config(width=self.tk_image.width(), height=self.tk_image.height())
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.tk_image)

        # Redraw all marked boxes
        for pair in self.region_pairs:
            src = pair['source']  # [x1_ratio, y1_ratio, x2_ratio, y2_ratio]
            destinations = pair.get('destinations', [])  # List of [x1_ratio, y1_ratio, x2_ratio, y2_ratio]
            if src:
                src_x1 = src[0] * self.display_size[0]
                src_y1 = src[1] * self.display_size[1]
                src_x2 = src[2] * self.display_size[0]
                src_y2 = src[3] * self.display_size[1]
                # Draw source region red box
                self.canvas.create_rectangle(src_x1, src_y1, src_x2, src_y2, outline="red", width=2, tag="selection")
            for dst in destinations:
                dst_x1 = dst[0] * self.display_size[0]
                dst_y1 = dst[1] * self.display_size[1]
                dst_x2 = dst[2] * self.display_size[0]
                dst_y2 = dst[3] * self.display_size[1]
                # Draw destination region blue box
                self.canvas.create_rectangle(dst_x1, dst_y1, dst_x2, dst_y2, outline="blue", width=2, tag="selection")

        # Keep preview rectangle on top
        if self.preview_rect:
            self.canvas.tag_raise(self.preview_rect)  # Ensure preview rectangle is on top

    def on_left_press(self, event):
        # No action needed on left press; preview is always displayed
        pass

    def on_left_release(self, event):
        # Create source region
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

        # Determine drag direction
        if self.right_drag_direction is None:
            delta_x = end_x - start_x
            delta_y = end_y - start_y
            if abs(delta_x) > abs(delta_y):
                self.right_drag_direction = 'horizontal'
            else:
                self.right_drag_direction = 'vertical'
            print(f"拖动方向确定为：{self.right_drag_direction}")

        # Generate continuous target boxes based on drag direction
        if self.right_drag_direction == 'horizontal':
            step = self.square_size + self.interval.get()
            num = (end_x - start_x) // step
        else:
            step = self.square_size + self.interval.get()
            num = (end_y - start_y) // step

        num = max(num, 1)  # At least one box

        self.generate_continuous_targets(start_x, start_y, num, self.right_drag_direction)

    def on_right_release_drag(self, event):
        if not self.right_dragging:
            return

        self.right_dragging = False
        self.right_drag_start = None
        self.right_drag_direction = None

        # Get the last region pair
        if not self.region_pairs:
            return

        last_pair = self.region_pairs[-1]

        for rect_id in self.right_drag_preview:
            # Get box coordinates
            coords = self.canvas.coords(rect_id)
            x1, y1, x2, y2 = coords

            # Convert to original image ratios
            x1_ratio = x1 / self.display_size[0]
            y1_ratio = y1 / self.display_size[1]
            x2_ratio = x2 / self.display_size[0]
            y2_ratio = y2 / self.display_size[1]

            # Add to destinations list
            last_pair['destinations'].append([x1_ratio, y1_ratio, x2_ratio, y2_ratio])

            # Change box style to solid line
            self.canvas.itemconfig(rect_id, dash=(), outline="blue", tag="selection")

            print(f"添加目标区域：矩形({x1_ratio:.4f}, {y1_ratio:.4f}, {x2_ratio:.4f}, {y2_ratio:.4f})")

        # Clear the preview list
        self.right_drag_preview.clear()

        print("右键拖动释放，目标方框已添加。")

    def generate_continuous_targets(self, start_x, start_y, num, direction):
        # Clear previous previews
        for rect_id in self.right_drag_preview:
            self.canvas.delete(rect_id)
        self.right_drag_preview.clear()

        # Get the last region pair
        if not self.region_pairs:
            messagebox.showwarning("警告", "请先用左键点击标记源区域。")
            return

        last_pair = self.region_pairs[-1]

        # Get user-defined interval
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

            # Draw preview rectangle
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
        # Remove preview rectangle when mouse leaves canvas
        if self.preview_rect:
            self.canvas.delete(self.preview_rect)
            self.preview_rect = None
        # Also stop right-click dragging
        if self.right_dragging:
            self.on_right_release_drag(event)

    def update_preview_rectangle(self, x, y):
        half_size = self.square_size // 2
        x1 = x - half_size
        y1 = y - half_size
        x2 = x + half_size
        y2 = y + half_size

        if self.preview_rect is None:
            # Create preview rectangle
            self.preview_rect = self.canvas.create_rectangle(
                x1, y1, x2, y2,
                outline="orange", dash=(2, 2), width=2, tag="preview"
            )
        else:
            # Update preview rectangle position
            self.canvas.coords(self.preview_rect, x1, y1, x2, y2)

    def on_mousewheel(self, event):
        # Detect scroll direction and adjust square_size
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
            self.square_size = min(self.square_size + 5, 200)  # Maximum limit
        elif delta < 0:
            self.square_size = max(self.square_size - 5, 10)   # Minimum limit

        # Update font size
        self.font_size = int(self.square_size * 0.85)

        print(f"当前方框大小: {self.square_size}, 字体大小: {self.font_size}")

        # Update font size Spinbox display
        self.size_spinbox.delete(0, "end")
        self.size_spinbox.insert(0, str(self.font_size))

        # Update preview rectangle size
        if self.preview_rect:
            x1, y1, x2, y2 = self.canvas.coords(self.preview_rect)
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2
            self.update_preview_rectangle(center_x, center_y)

        # Optionally, add code here to update existing boxes and text if needed

    def create_source_region(self, x, y):
        half_size = self.square_size // 2
        x1_display = x - half_size
        y1_display = y - half_size
        x2_display = x + half_size
        y2_display = y + half_size

        # Convert display coordinates to original image ratios
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

        # Convert display coordinates to original image ratios
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

        # Update display
        self.update_canvas()
        messagebox.showinfo("完成", "OCR 和文本复制已完成。")

    def process_image(self, image, image_path, display_size):
        draw = ImageDraw.Draw(image)
        img_width, img_height = image.size

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

            # Display debug image
            self.display_debug_image(src_region, f"区域 {index} OCR 图像")

            # Perform OCR
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

            # Get text properties
            font_color = self.color_entry.get()

            # Add OCR text to all destination regions
            for dst_index, dst in enumerate(destinations, start=1):
                dst_box = (
                    int(dst[0] * img_width),
                    int(dst[1] * img_height),
                    int(dst[2] * img_width),
                    int(dst[3] * img_height)
                )
                box_width = dst_box[2] - dst_box[0]
                box_height = dst_box[3] - dst_box[1]

                # Calculate starting position
                text_x = dst_box[0]
                text_y = dst_box[1]

                # Draw text character by character with random fonts and slight variations
                last_font = None
                total_width = 0
                max_text_height = 0

                for char in ocr_text:
                    # Choose a different font than the last one
                    available_fonts = [f for f in self.selected_fonts if f != last_font]
                    if not available_fonts:
                        available_fonts = self.selected_fonts  # Allow repetition if all fonts used
                    font_path = random.choice(available_fonts)
                    last_font = font_path

                    # Load font if not already loaded
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

                    # Get character size with slight random variation
                    try:
                        char_width, char_height = pil_font.getsize(char)
                    except:
                        char_width, char_height = (10, 10)  # Fallback size

                    # Add 0.05 random variation
                    size_variation = np.random.uniform(0.95, 1.05)
                    char_width = int(char_width * size_variation)
                    char_height = int(char_height * size_variation)

                    max_text_height = max(max_text_height, char_height)

                    # Add random offset
                    max_offset_x = box_width * 0.7
                    max_offset_y = box_height * 0.025
                    random_offset_x = np.random.uniform(-max_offset_x / 2, max_offset_x / 2)
                    random_offset_y = np.random.uniform(-max_offset_y, max_offset_y)

                    # Calculate character position
                    current_x = dst_box[0] + (box_width - total_width) / 2 + random_offset_x - char_width / 2
                    current_y = dst_box[1] + (box_height - max_text_height) / 2 + random_offset_y

                    # Draw character with adjusted size
                    try:
                        font_with_size = pil_font.font_variant(size=int(self.font_size * size_variation))
                        draw.text((current_x + total_width, current_y), char, font=font_with_size, fill=font_color)
                    except Exception as e:
                        print(f"绘制字符时发生错误：{e}")

                    # Update total width
                    total_width += char_width

                print(f"文本已添加到区域 {index}-{dst_index}")

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
        # Resize image to fit debug canvas
        image = image.resize((200, 200), self.get_resampling_filter())
        self.debug_image = ImageTk.PhotoImage(image)
        self.debug_canvas.delete("all")
        self.debug_canvas.create_image(100, 100, anchor=tk.CENTER, image=self.debug_image)
        self.debug_label.config(text=f"{text}\n原始大小: {image.width}x{image.height}")
        self.debug_frame.update()  # Update debug frame only
        self.debug_canvas.update()  # Ensure canvas updates

    def clear_selected_regions(self):
        if not self.region_pairs:
            messagebox.showinfo("信息", "当前没有任何框选需要清除。")
            return

        # Clear region pairs list
        self.region_pairs.clear()

        # Clear all selections on canvas
        self.canvas.delete("selection")

        # Clear debug information area
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

        # Select multiple images
        batch_image_paths = filedialog.askopenfilenames(
            title="选择要批量处理的图片",
            filetypes=[("Image Files", "*.png;*.jpg;*.jpeg;*.bmp")]
        )
        if not batch_image_paths:
            messagebox.showinfo("信息", "未选择任何图片。")
            return

        # Select output folder
        output_folder = filedialog.askdirectory(title="选择输出文件夹")
        if not output_folder:
            messagebox.showinfo("信息", "未选择输出文件夹。")
            return

        # Get selected language codes
        languages = self.selected_languages.get()
        language_list = languages.split('+')  # Split language codes into list
        print(f"使用的OCR语言：{language_list}")

        # Initialize OCR reader with selected languages
        try:
            reader_batch = easyocr.Reader(language_list, gpu=False)
        except Exception as e:
            messagebox.showerror("错误", f"初始化 EasyOCR 时发生错误：{e}")
            return

        total = len(batch_image_paths)
        processed = 0

        for img_path in batch_image_paths:
            try:
                # Open image
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

                    # Perform OCR
                    try:
                        # Convert PIL Image to OpenCV format (BGR)
                        img_cv = src_region.convert("RGB")
                        img_cv = np.array(img_cv)
                        img_cv = img_cv[:, :, ::-1]  # RGB to BGR

                        ocr_result = reader_batch.readtext(img_cv, detail=0, paragraph=True)
                        ocr_text = ' '.join(ocr_result).strip()
                    except Exception as e:
                        print(f"执行OCR时发生错误：{e}")
                        continue

                    print(f"图片 '{os.path.basename(img_path)}' 区域 {index} OCR 结果: {ocr_text}")

                    if not ocr_text:
                        print(f"警告: 图片 '{os.path.basename(img_path)}' 区域 {index} 未识别到任何文本。")
                        continue

                    # Get text properties
                    font_color = self.color_entry.get()

                    # Add OCR text to all destination regions
                    for dst_index, dst in enumerate(destinations, start=1):
                        dst_box = (
                            int(dst[0] * img_width),
                            int(dst[1] * img_height),
                            int(dst[2] * img_width),
                            int(dst[3] * img_height)
                        )
                        box_width = dst_box[2] - dst_box[0]
                        box_height = dst_box[3] - dst_box[1]

                        # Calculate starting position
                        text_x = dst_box[0]
                        text_y = dst_box[1]

                        # Draw text character by character with random fonts and slight variations
                        last_font = None
                        total_width = 0
                        max_text_height = 0

                        for char in ocr_text:
                            # Choose a different font than the last one
                            available_fonts = [f for f in self.selected_fonts if f != last_font]
                            if not available_fonts:
                                available_fonts = self.selected_fonts  # Allow repetition if all fonts used
                            font_path = random.choice(available_fonts)
                            last_font = font_path

                            # Load font if not already loaded
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

                            # Get character size with slight random variation
                            try:
                                char_width, char_height = pil_font.getsize(char)
                            except:
                                char_width, char_height = (10, 10)  # Fallback size

                            # Add 0.05 random variation
                            size_variation = np.random.uniform(0.95, 1.05)
                            char_width = int(char_width * size_variation)
                            char_height = int(char_height * size_variation)

                            max_text_height = max(max_text_height, char_height)

                            # Add random offset
                            max_offset_x = box_width * 0.7
                            max_offset_y = box_height * 0.025
                            random_offset_x = np.random.uniform(-max_offset_x / 2, max_offset_x / 2)
                            random_offset_y = np.random.uniform(-max_offset_y, max_offset_y)

                            # Calculate character position
                            current_x = dst_box[0] + (box_width - total_width) / 2 + random_offset_x - char_width / 2
                            current_y = dst_box[1] + (box_height - max_text_height) / 2 + random_offset_y

                            # Draw character with adjusted size
                            try:
                                font_with_size = pil_font.font_variant(size=int(self.font_size * size_variation))
                                draw.text((current_x + total_width, current_y), char, font=font_with_size, fill=font_color)
                            except Exception as e:
                                print(f"绘制字符时发生错误：{e}")

                            # Update total width
                            total_width += char_width

                        print(f"文本已添加到图片 '{os.path.basename(img_path)}' 区域 {index}-{dst_index}")

                # Save modified image
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
        """Helper method to get the appropriate resampling filter."""
        try:
            return Image.Resampling.LANCZOS  # Pillow >=10
        except AttributeError:
            return Image.LANCZOS  # Pillow <10


if __name__ == "__main__":
    root = tk.Tk()
    app = PenaltyCopyApp(root)
    app.run()