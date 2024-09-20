# OCR.py
import easyocr
import numpy as np
from PIL import Image

def getTextFromImage_EasyOCR(image, language):
    """
    从图片中提取文本。

    参数:
        image (PIL.Image): 待处理的图片。
        language (str): OCR识别的语言，支持 'en'（英语）、'cn'（中文）、'ja'（日语）。

    返回:
        str: 识别出的文本。
    """
    # 确保语言参数有效
    supported_languages = ['en', 'cn', 'ja']
    if language not in supported_languages:
        raise ValueError(f"Unsupported language: {language}. Supported languages are: {supported_languages}")
    

    # 将PIL图片转换为OpenCV格式（BGR）
    img = image.convert("RGB")
    img = np.array(img)
    img = img[:, :, ::-1]  # RGB to BGR

    # 初始化EasyOCR Reader
    reader = easyocr.Reader([language], gpu=False)  # 如果有兼容的GPU，可以设置gpu=True

    # 执行OCR
    result = reader.readtext(img, detail=0, paragraph=True)

    # 将结果合并为一个字符串
    ocr_text = ' '.join(result[::-1]).strip()

    return ocr_text




getTextFromImage = getTextFromImage_EasyOCR
