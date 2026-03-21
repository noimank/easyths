from PIL import Image, ImageDraw, ImageFont
import random
import uuid
import os


def generate_ths_captcha(output_dir="./", code=None):
    """
    生成同花顺风格验证码图片

    特征：
    - 120x40像素，纯白背景
    - 蓝色系字符 (#2E82D6 左右的明亮蓝色)
    - 4位字符（数字+大小写字母，排除0oOIl等易混淆字符）
    - 字符有轻微上下浮动（2-8px）和旋转（±12度）
    - 整体干净整洁，几乎无噪点

    文件名格式: {验证码}_{uuid}.png
    """

    # 1. 生成随机验证码（如果未指定）
    if code is None:
        chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz"
        code = ''.join(random.choice(chars) for _ in range(4))

    # 2. 创建画布（120x40是同花顺验证码的标准尺寸）
    width, height = 120, 40
    img = Image.new('RGB', (width, height), (255, 255, 255))

    # 3. 加载字体（优先使用系统无衬线粗体）
    try:
        font_paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "C:/Windows/Fonts/arialbd.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        ]
        font = ImageFont.load_default()
        for fp in font_paths:
            if os.path.exists(fp):
                font = ImageFont.truetype(fp, 30)
                break
    except:
        font = ImageFont.load_default()

    # 4. 绘制4个字符
    for i, char in enumerate(code):
        # 同花顺蓝色系（明亮的天蓝色）
        blue_shades = [
            (46, 130, 214),  # 标准蓝
            (56, 140, 224),  # 亮蓝
            (36, 120, 204),  # 稍深蓝
            (50, 135, 218),  # 中蓝
        ]
        color = random.choice(blue_shades)

        # 位置计算：基础位置 + 随机偏移
        x = 10 + i * 27 + random.randint(-2, 2)  # 水平分布，轻微偏移
        y = random.randint(2, 8)  # 垂直浮动（模拟原图的上下错位）

        # 随机旋转角度（-12度到12度）
        angle = random.randint(-12, 12)

        # 创建透明图层绘制单个字符
        char_layer = Image.new('RGBA', (36, 36), (255, 255, 255, 0))
        char_draw = ImageDraw.Draw(char_layer)
        char_draw.text((4, 2), char, font=font, fill=color)

        # 旋转并粘贴到主图
        if angle != 0:
            rotated = char_layer.rotate(angle, resample=Image.BICUBIC)
            img.paste(rotated, (x, y), rotated)
        else:
            img.paste(char_layer, (x, y), char_layer)

    # 5. 添加极少噪点（同花顺原图很干净）
    draw = ImageDraw.Draw(img)
    for _ in range(10):
        x = random.randint(0, width - 1)
        y = random.randint(0, height - 1)
        draw.point((x, y), fill=(245, 245, 245))

    # 6. 保存为 {验证码}_{uuid}.png
    filename = f"{code}_{uuid.uuid4().hex}.png"
    filepath = os.path.join(output_dir, filename)
    img.save(filepath, "PNG")

    return filepath, code


# 使用示例
if __name__ == "__main__":
    import argparse
    from tqdm import tqdm

    parser = argparse.ArgumentParser(
        description="生成同花顺风格验证码图片",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # 生成单张随机验证码
    python ths_data_generate.py

    # 批量生成100张验证码到默认目录
    python ths_data_generate.py --num_sample 100

    # 批量生成1000张验证码到指定目录
    python ths_data_generate.py --num_sample 1000 --output_dir ./my_captchas

    # 生成指定验证码内容
    python ths_data_generate.py --code 2BRe
        """
    )
    parser.add_argument(
        "--num_sample",
        type=int,
        default=10,
        help="生成验证码的数量 (默认: 1)",
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="./captchas",
        help="输出目录 (默认: ./captchas)",
    )
    parser.add_argument(
        "--code",
        type=str,
        default=None,
        help="指定验证码内容，仅在 num_sample=1 时有效",
    )
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    if args.num_sample > 1:
        print(f"开始批量生成 {args.num_sample} 张验证码图片...")
        print(f"输出目录: {os.path.abspath(args.output_dir)}")
        for _ in tqdm(range(args.num_sample), desc="生成进度"):
            generate_ths_captcha(args.output_dir)
        print(f"\n✓ 成功生成 {args.num_sample} 张，保存至: {os.path.abspath(args.output_dir)}")
    else:
        filepath, code = generate_ths_captcha(args.output_dir, args.code)
        print(f"已生成: {filepath} (验证码: {code})")