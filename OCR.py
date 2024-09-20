import os
import tempfile
from PPOCR_api import GetOcrApi

def getTextFromImage(image, language=None):
    # 设置参数
    argument = {"config_path": "models/config_japan.txt"}

    # 初始化识别器对象
    ocr = GetOcrApi(r".\PaddleOCR-json_v1.4.1\PaddleOCR-json.exe", argument=argument)

    # 创建临时文件来保存图像
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as temp_file:
        temp_filename = temp_file.name
        image.save(temp_filename, format='PNG')

    try:
        # 识别图片
        getObj = ocr.run(temp_filename)
        
        if getObj["code"] == 100:
            # 如果识别成功，返回识别的文本
            result = getObj["data"][0]["text"]
            return result
        else:
            # 如果识别失败，返回错误信息
            return f"OCR识别失败，状态码：{getObj['code']}"
    
    finally:
        # 删除临时文件
        os.unlink(temp_filename)

# 使用示例
# from PIL import Image
# image = Image.open("path_to_your_image.png")
# text = getTextFromImage_EasyOCR(image)
# print(text)