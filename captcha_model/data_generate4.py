"""
使用 captcha 库生成验证码数据集

特性：
1. 验证码尺寸在可配置范围内随机
2. 字母有间距不粘连
3. 字体基础大小可配置，小写字母大小在基础大小的可配置比例范围内
4. 随机使用 fonts 目录下的字体
5. 验证码长度范围可配置
6. 可配置模糊和噪点效果

作者: noimank (康康)
邮箱: noimank@163.com
"""

import os
import uuid
import random
import argparse
import string
from io import BytesIO
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from captcha.image import ImageCaptcha


def get_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="使用 captcha 库生成验证码数据集",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
    # 生成 100 张默认配置的验证码
    python data_generate4.py --num_samples 100

    # 指定尺寸范围和长度范围
    python data_generate4.py --num_samples 1000 --width_range 100 150 --height_range 36 60 --length_range 4 6

    # 启用模糊和噪点
    python data_generate4.py --num_samples 500 --blur --blur_radius 1.5 --noise_dots 50

    # 自定义小写字母大小比例
    python data_generate4.py --num_samples 200 --base_font_size 32 --lowercase_ratio 0.65 0.85
        """
    )

    # 基本参数
    parser.add_argument("--num_samples", type=int, default=10, help="生成样本数量 (默认: 10)")
    parser.add_argument("--output_dir", type=str, default="./dataset", help="输出目录 (默认: ./dataset)")
    parser.add_argument("--font_dir", type=str, default="./fonts", help="字体库目录 (默认: ./fonts)")

    # 尺寸配置
    parser.add_argument("--width_range", type=int, nargs=2, default=[100, 146],
                        help="宽度范围 [min, max] (默认: 100 146)")
    parser.add_argument("--height_range", type=int, nargs=2, default=[36, 64],
                        help="高度范围 [min, max] (默认: 36 64)")

    # 验证码长度配置
    parser.add_argument("--length_range", type=int, nargs=2, default=[4, 4],
                        help="验证码长度范围 [min, max] (默认: 4 4)")

    # 字符集配置
    parser.add_argument("--charset", type=str, default=None,
                        help="字符集，默认为大小写字母+数字")

    # 字体配置
    parser.add_argument("--base_font_size", type=int, default=30,
                        help="字体基础大小 (默认: 30)")
    parser.add_argument("--lowercase_ratio", type=float, nargs=2, default=[0.7, 0.9],
                        help="小写字母相对基础大小的比例范围 [min, max] (默认: 0.7 0.9)")

    # 间距配置
    parser.add_argument("--char_spacing", type=int, default=5,
                        help="字符间距 (默认: 5)")

    # 模糊配置
    parser.add_argument("--blur", action="store_true", help="启用模糊效果")
    parser.add_argument("--blur_radius", type=float, default=1.0,
                        help="模糊半径 (默认: 1.0)")

    # 噪点配置
    parser.add_argument("--noise_dots", type=int, default=0,
                        help="噪点数量 (默认: 0)")
    parser.add_argument("--noise_lines", type=int, default=0,
                        help="干扰线数量 (默认: 0)")

    return parser.parse_args()


def get_font_files(font_dir: str) -> list[str]:
    """获取字体目录下所有字体文件"""
    font_path = Path(font_dir)
    if not font_path.exists():
        return []

    font_extensions = {'.ttf', '.otf', '.ttc', '.woff', '.woff2'}
    fonts = [
        str(f) for f in font_path.iterdir()
        if f.suffix.lower() in font_extensions
    ]
    return fonts


def generate_random_color() -> tuple[int, int, int]:
    """生成随机蓝色系颜色"""
    blue_shades = [
        (46, 130, 214),   # 标准蓝
        (56, 140, 224),   # 亮蓝
        (36, 120, 204),   # 稍深蓝
        (50, 135, 218),   # 中蓝
        (30, 144, 255),   # 道奇蓝
        (65, 105, 225),   # 皇家蓝
        (70, 130, 180),   # 钢蓝
    ]
    return random.choice(blue_shades)


def draw_character(
    draw: ImageDraw.ImageDraw,
    char: str,
    x: int,
    y: int,
    font: ImageFont.FreeTypeFont,
    color: tuple[int, int, int]
) -> int:
    """
    绘制单个字符并返回字符宽度

    Args:
        draw: PIL 绘图对象
        char: 要绘制的字符
        x: x 坐标
        y: y 坐标
        font: 字体对象
        color: 颜色

    Returns:
        字符的宽度
    """
    # 获取字符边界框
    bbox = draw.textbbox((0, 0), char, font=font)
    char_width = bbox[2] - bbox[0]

    draw.text((x, y), char, font=font, fill=color)
    return char_width


def generate_captcha_with_captcha_lib(
    text: str,
    width: int,
    height: int,
    fonts: list[str],
    base_font_size: int,
    lowercase_ratio: tuple[float, float],
    char_spacing: int,
    use_blur: bool,
    blur_radius: float,
    noise_dots: int,
    noise_lines: int
) -> Image.Image:
    """
    使用 captcha 库结合自定义逻辑生成验证码

    Args:
        text: 验证码文本
        width: 图片宽度
        height: 图片高度
        fonts: 字体文件列表
        base_font_size: 基础字体大小
        lowercase_ratio: 小写字母大小比例范围
        char_spacing: 字符间距
        use_blur: 是否启用模糊
        blur_radius: 模糊半径
        noise_dots: 噪点数量
        noise_lines: 干扰线数量

    Returns:
        生成的 PIL Image 对象
    """
    # 创建白色背景画布
    image = Image.new('RGB', (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # 计算总宽度和起始位置
    total_width = 0
    char_fonts = []

    # 为每个字符准备字体
    for char in text:
        font_path = random.choice(fonts) if fonts else None
        if font_path:
            # 小写字母使用较小字体
            if char.islower():
                scale = random.uniform(lowercase_ratio[0], lowercase_ratio[1])
                font_size = int(base_font_size * scale)
            else:
                font_size = base_font_size

            font = ImageFont.truetype(font_path, font_size)
        else:
            font = ImageFont.load_default()

        # 获取字符宽度
        bbox = draw.textbbox((0, 0), char, font=font)
        char_width = bbox[2] - bbox[0]
        total_width += char_width + char_spacing
        char_fonts.append((char, font, char_width))

    # 减去最后一个间距
    total_width -= char_spacing

    # 计算起始 x 位置（居中）
    start_x = (width - total_width) // 2
    current_x = max(start_x, 5)  # 至少留 5 像素边距

    # 绘制每个字符
    for char, font, char_width in char_fonts:
        # 随机颜色
        color = generate_random_color()

        # 垂直方向随机偏移
        bbox = draw.textbbox((0, 0), char, font=font)
        char_height = bbox[3] - bbox[1]
        max_y_offset = max(0, height - char_height - 4)
        y = random.randint(2, max(2, max_y_offset))

        # 随机旋转角度
        angle = random.randint(-12, 12)

        # 创建字符图层用于旋转
        char_layer_size = (char_width + 20, char_height + 20)
        char_layer = Image.new('RGBA', char_layer_size, (255, 255, 255, 0))
        char_draw = ImageDraw.Draw(char_layer)
        char_draw.text((10, 5), char, font=font, fill=color)

        # 旋转
        if angle != 0:
            char_layer = char_layer.rotate(angle, resample=Image.BICUBIC, expand=True)

        # 粘贴到主图
        paste_y = max(0, y - 10)
        image.paste(char_layer, (current_x - 5, paste_y), char_layer)

        # 移动到下一个字符位置
        current_x += char_width + char_spacing

    # 添加噪点
    if noise_dots > 0:
        for _ in range(noise_dots):
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)
            # 使用浅灰色噪点
            gray = random.randint(200, 240)
            draw.point((x, y), fill=(gray, gray, gray))

    # 添加干扰线
    if noise_lines > 0:
        for _ in range(noise_lines):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            # 使用浅色干扰线
            gray = random.randint(180, 220)
            draw.line([(x1, y1), (x2, y2)], fill=(gray, gray, gray), width=1)

    # 应用模糊
    if use_blur:
        image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))

    return image


def generate_captcha_pure_captcha_lib(
    text: str,
    width: int,
    height: int,
    fonts: list[str]
) -> Image.Image:
    """
    纯 captcha 库生成验证码（简单模式）

    Args:
        text: 验证码文本
        width: 图片宽度
        height: 图片高度
        fonts: 字体文件列表

    Returns:
        生成的 PIL Image 对象
    """
    # 创建 ImageCaptcha 实例
    generator = ImageCaptcha(width=width, height=height, fonts=fonts)

    # 生成验证码图片
    data = generator.generate(text)

    # 转换为 PIL Image
    image = Image.open(BytesIO(data.read()))

    return image


def main():
    args = get_args()

    # 获取脚本所在目录
    script_dir = Path(__file__).parent.resolve()

    # 处理相对路径
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = script_dir / output_dir

    font_dir = Path(args.font_dir)
    if not font_dir.is_absolute():
        font_dir = script_dir / font_dir

    # 创建输出目录
    output_dir.mkdir(parents=True, exist_ok=True)

    # 获取字体文件列表
    fonts = get_font_files(str(font_dir))
    if not fonts:
        print(f"警告: 未在 {font_dir} 找到字体文件，将使用默认字体")
    else:
        print(f"找到 {len(fonts)} 个字体文件")

    # 确定字符集
    if args.charset:
        charset = args.charset
    else:
        # 默认：大小写字母 + 数字
        charset = string.ascii_letters + string.digits

    print(f"字符集: {len(charset)} 个字符")
    print(f"尺寸范围: {args.width_range[0]}x{args.height_range[0]} ~ {args.width_range[1]}x{args.height_range[1]}")
    print(f"长度范围: {args.length_range[0]} ~ {args.length_range[1]}")
    print(f"基础字体大小: {args.base_font_size}")
    print(f"小写字母比例: {args.lowercase_ratio[0]} ~ {args.lowercase_ratio[1]}")
    print(f"字符间距: {args.char_spacing}")
    print(f"模糊: {'启用 (radius={})'.format(args.blur_radius) if args.blur else '禁用'}")
    print(f"噪点: {args.noise_dots} 个, 干扰线: {args.noise_lines} 条")
    print(f"输出目录: {output_dir}")
    print(f"开始生成 {args.num_samples} 张验证码...")

    for i in range(args.num_samples):
        # 随机确定验证码长度
        length = random.randint(args.length_range[0], args.length_range[1])

        # 生成验证码文本
        text = ''.join(random.choices(charset, k=length))

        # 随机确定尺寸
        width = random.randint(args.width_range[0], args.width_range[1])
        height = random.randint(args.height_range[0], args.height_range[1])

        # 生成验证码图片
        image = generate_captcha_with_captcha_lib(
            text=text,
            width=width,
            height=height,
            fonts=fonts,
            base_font_size=args.base_font_size,
            lowercase_ratio=tuple(args.lowercase_ratio),
            char_spacing=args.char_spacing,
            use_blur=args.blur,
            blur_radius=args.blur_radius,
            noise_dots=args.noise_dots,
            noise_lines=args.noise_lines
        )

        # 生成文件名
        file_uuid = uuid.uuid4().hex[:8]
        filename = f"{text}_{file_uuid}.png"
        filepath = output_dir / filename

        # 保存图片
        image.save(filepath, "PNG")

        # 进度显示
        if (i + 1) % 100 == 0 or (i + 1) == args.num_samples:
            print(f"进度: {i + 1}/{args.num_samples}")

    print(f"\n完成! 已生成 {args.num_samples} 张验证码图片至: {output_dir}")


if __name__ == "__main__":
    main()
