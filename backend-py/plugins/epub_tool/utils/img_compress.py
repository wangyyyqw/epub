# -*- coding: utf-8 -*-
# 图片压缩工具
# 功能：
# 1. 质量压缩（JPEG/WebP 质量参数可调）
# 2. 无透明度的 PNG 转为 JPG
# 3. 有透明度的 PNG 压缩为 PNG-8 二值透明
# 4. PNG 优化压缩（Pillow optimize）
# 5. 支持所有常见图片格式（JPEG/PNG/WebP/BMP/GIF）

import os
import zipfile
from PIL import Image
import io
import re
from urllib.parse import unquote, quote

try:
    from ..log import logwriter
except:
    from .log import logwriter

logger = logwriter()


def has_transparency(img):
    """检查图片是否有透明度"""
    if img.mode == 'RGBA':
        alpha = img.split()[3]
        if alpha.getextrema()[0] < 255:
            return True
    elif img.mode == 'LA':
        alpha = img.split()[1]
        if alpha.getextrema()[0] < 255:
            return True
    elif img.mode == 'P':
        if 'transparency' in img.info:
            return True
    return False


def convert_to_binary_alpha(img):
    """将图片转换为二值透明 PNG-8"""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    r, g, b, a = img.split()
    a = a.point(lambda x: 255 if x > 128 else 0)
    img = Image.merge('RGBA', (r, g, b, a))
    bg = Image.new('RGB', img.size, (255, 255, 255))
    bg.paste(img, mask=a)
    p_img = bg.quantize(colors=255, method=2)
    trans_index = 255
    out_img = Image.new('P', img.size, color=trans_index)
    palette = p_img.getpalette()
    if len(palette) < 768:
        palette += [0] * (768 - len(palette))
    out_img.putpalette(palette)
    out_img.paste(p_img, mask=a)
    out_img.info['transparency'] = trans_index
    return out_img


def _detect_format(img, filename):
    """检测图片实际格式"""
    fmt = (img.format or '').upper()
    if not fmt:
        ext = os.path.splitext(filename)[1].lower()
        fmt_map = {'.jpg': 'JPEG', '.jpeg': 'JPEG', '.png': 'PNG',
                   '.webp': 'WEBP', '.bmp': 'BMP', '.gif': 'GIF'}
        fmt = fmt_map.get(ext, '')
    if fmt == 'JPG':
        fmt = 'JPEG'
    return fmt


def _size_str(sz):
    """格式化文件大小"""
    if sz < 1024:
        return f"{sz} B"
    elif sz < 1048576:
        return f"{sz / 1024:.1f} KB"
    else:
        return f"{sz / 1048576:.2f} MB"


def process_image(img_data, filename, jpeg_quality=85, webp_quality=80, png_to_jpg=True):
    """处理单张图片
    
    Args:
        img_data: 图片二进制数据
        filename: 文件名
        jpeg_quality: JPEG 压缩质量 (1-100)
        webp_quality: WebP 压缩质量 (1-100)
        png_to_jpg: 是否将无透明 PNG 转为 JPG
    
    Returns:
        (new_data, new_ext, status, msg)
    """
    try:
        img = Image.open(io.BytesIO(img_data))
        fmt = _detect_format(img, filename)
        original_size = len(img_data)

        if fmt == 'JPEG':
            # JPEG 质量压缩
            if img.mode != 'RGB':
                img = img.convert('RGB')
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=jpeg_quality, optimize=True)
            new_data = output.getvalue()
            if len(new_data) >= original_size:
                return None, None, 'skip', '已优化，无需再压缩'
            reduction = (1 - len(new_data) / original_size) * 100
            msg = f"JPEG 质量压缩 (q={jpeg_quality}): {_size_str(original_size)} → {_size_str(len(new_data))} (-{reduction:.1f}%)"
            return new_data, 'jpg', 'success', msg

        elif fmt == 'PNG':
            if has_transparency(img):
                # 有透明度：转为 PNG-8 二值透明
                new_img = convert_to_binary_alpha(img)
                output = io.BytesIO()
                new_img.save(output, format='PNG', optimize=True)
                new_data = output.getvalue()
                reduction = (1 - len(new_data) / original_size) * 100
                msg = f"PNG(透明) → PNG-8(二值透明): {_size_str(original_size)} → {_size_str(len(new_data))} ({'-' if reduction > 0 else '+'}{abs(reduction):.1f}%)"
                return new_data, 'png', 'success', msg
            elif png_to_jpg:
                # 无透明度：转为 JPG
                if img.mode in ('RGBA', 'LA', 'P'):
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                output = io.BytesIO()
                img.save(output, format='JPEG', quality=jpeg_quality, optimize=True)
                new_data = output.getvalue()
                reduction = (1 - len(new_data) / original_size) * 100
                msg = f"PNG(无透明) → JPG (q={jpeg_quality}): {_size_str(original_size)} → {_size_str(len(new_data))} ({'-' if reduction > 0 else '+'}{abs(reduction):.1f}%)"
                return new_data, 'jpg', 'success', msg
            else:
                # 仅 PNG 优化
                output = io.BytesIO()
                img.save(output, format='PNG', optimize=True)
                new_data = output.getvalue()
                if len(new_data) >= original_size:
                    return None, None, 'skip', '已优化，无需再压缩'
                reduction = (1 - len(new_data) / original_size) * 100
                msg = f"PNG 优化: {_size_str(original_size)} → {_size_str(len(new_data))} (-{reduction:.1f}%)"
                return new_data, 'png', 'success', msg

        elif fmt == 'WEBP':
            # WebP 质量压缩
            output = io.BytesIO()
            if has_transparency(img):
                img.save(output, format='WEBP', quality=webp_quality, method=4)
            else:
                img.save(output, format='WEBP', quality=webp_quality, method=4)
            new_data = output.getvalue()
            if len(new_data) >= original_size:
                return None, None, 'skip', '已优化，无需再压缩'
            reduction = (1 - len(new_data) / original_size) * 100
            msg = f"WebP 质量压缩 (q={webp_quality}): {_size_str(original_size)} → {_size_str(len(new_data))} (-{reduction:.1f}%)"
            return new_data, 'webp', 'success', msg

        elif fmt == 'BMP':
            # BMP 转为 JPG（BMP 无损，转 JPG 大幅减小体积）
            if img.mode != 'RGB':
                img = img.convert('RGB')
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=jpeg_quality, optimize=True)
            new_data = output.getvalue()
            reduction = (1 - len(new_data) / original_size) * 100
            msg = f"BMP → JPG (q={jpeg_quality}): {_size_str(original_size)} → {_size_str(len(new_data))} (-{reduction:.1f}%)"
            return new_data, 'jpg', 'success', msg

        elif fmt == 'GIF':
            # GIF 不处理（可能是动图）
            return None, None, 'skip', 'GIF 格式跳过'

        else:
            return None, None, 'skip', f'不支持的格式: {fmt}'

    except Exception as e:
        return None, None, 'error', f'处理失败 - {e}'


def run(epub_src, output_path=None, jpeg_quality=85, webp_quality=80, png_to_jpg=True):
    """压缩 EPUB 中的图片
    
    Args:
        epub_src: 输入 EPUB 路径
        output_path: 输出目录
        jpeg_quality: JPEG 压缩质量 (1-100)
        webp_quality: WebP 压缩质量 (1-100)
        png_to_jpg: 是否将无透明 PNG 转为 JPG
    """
    try:
        logger.write(f"\n正在压缩图片: {epub_src}")
        logger.write(f"  JPEG 质量: {jpeg_quality}, WebP 质量: {webp_quality}, PNG→JPG: {'是' if png_to_jpg else '否'}")

        if not os.path.exists(epub_src):
            logger.write(f"错误: 文件不存在 {epub_src}")
            return "error"

        epub_dir = os.path.dirname(epub_src)
        epub_name = os.path.basename(epub_src)

        if output_path and os.path.isdir(output_path):
            out_epub = os.path.join(output_path, epub_name.replace('.epub', '_compressed.epub'))
        else:
            out_epub = epub_src.replace('.epub', '_compressed.epub')

        # 图片扩展名集合
        IMG_EXTS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif')

        with zipfile.ZipFile(epub_src, 'r') as zin:
            namelist = zin.namelist()

            # 找到 OPF 文件
            opf_path = None
            for name in namelist:
                if name.lower().endswith('.opf'):
                    opf_path = name
                    break

            if not opf_path:
                logger.write("错误: 找不到 OPF 文件")
                return "error"

            rename_map = {}  # old_arcname -> new_arcname
            processed_count = 0
            skip_count = 0
            total_saved = 0

            with zipfile.ZipFile(out_epub, 'w', zipfile.ZIP_DEFLATED) as zout:
                for arcname in namelist:
                    data = zin.read(arcname)

                    if any(arcname.lower().endswith(ext) for ext in IMG_EXTS):
                        new_data, new_ext, status, msg = process_image(
                            data, arcname,
                            jpeg_quality=jpeg_quality,
                            webp_quality=webp_quality,
                            png_to_jpg=png_to_jpg
                        )

                        if status == 'success' and new_data:
                            processed_count += 1
                            saved = len(data) - len(new_data)
                            total_saved += saved
                            logger.write(f"  {arcname}: {msg}")

                            old_ext = os.path.splitext(arcname)[1].lower()
                            new_ext_dot = f'.{new_ext}'
                            if old_ext != new_ext_dot:
                                new_arcname = os.path.splitext(arcname)[0] + new_ext_dot
                                rename_map[arcname] = new_arcname
                                zout.writestr(new_arcname, new_data)
                            else:
                                zout.writestr(arcname, new_data)
                        else:
                            if status == 'skip':
                                skip_count += 1
                            elif status == 'error':
                                logger.write(f"  {arcname}: {msg}")
                            zout.writestr(arcname, data)
                    else:
                        zout.writestr(arcname, data)

            # 更新引用
            if rename_map:
                logger.write(f"\n更新文件引用: {len(rename_map)} 个文件名变更")
                _update_references(out_epub, rename_map)

        logger.write(f"\n图片压缩完成: 处理 {processed_count} 张, 跳过 {skip_count} 张")
        if total_saved > 0:
            logger.write(f"总计节省: {_size_str(total_saved)}")
        logger.write(f"输出文件: {out_epub}")
        return 0

    except Exception as e:
        logger.write(f"压缩失败: {e}")
        return "error"


def _update_references(epub_path, rename_map):
    """更新 EPUB 中的文件引用"""
    try:
        temp_path = epub_path + '.tmp'

        basename_map = {}
        ext_change_map = {}  # old_basename -> (new_basename, old_ext, new_ext)
        for old_name, new_name in rename_map.items():
            old_bn = os.path.basename(old_name)
            new_bn = os.path.basename(new_name)
            basename_map[old_bn] = new_bn
            old_ext = os.path.splitext(old_bn)[1].lower()
            new_ext = os.path.splitext(new_bn)[1].lower()
            if old_ext != new_ext:
                ext_change_map[old_bn] = (new_bn, old_ext, new_ext)

        with zipfile.ZipFile(epub_path, 'r') as zin:
            with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                for arcname in zin.namelist():
                    data = zin.read(arcname)

                    if arcname in rename_map:
                        continue

                    if arcname.lower().endswith(('.opf', '.xhtml', '.html', '.css', '.ncx')):
                        try:
                            text = data.decode('utf-8')
                            for old_bn, new_bn in basename_map.items():
                                escaped_old = re.escape(old_bn)
                                text = re.sub(
                                    r'(?<=[/"\'])' + escaped_old + r'(?=["\'\s\)>])',
                                    new_bn, text
                                )
                                escaped_old_q = re.escape(quote(old_bn))
                                if escaped_old_q != escaped_old:
                                    text = re.sub(
                                        r'(?<=[/"\'])' + escaped_old_q + r'(?=["\'\s\)>])',
                                        quote(new_bn), text
                                    )

                            # 更新 media-type
                            for old_bn, (new_bn, old_ext, new_ext) in ext_change_map.items():
                                mime_map = {
                                    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                                    '.png': 'image/png', '.webp': 'image/webp',
                                    '.bmp': 'image/bmp', '.gif': 'image/gif'
                                }
                                old_mime = mime_map.get(old_ext, '')
                                new_mime = mime_map.get(new_ext, '')
                                if old_mime and new_mime and old_mime != new_mime:
                                    # href="...new_bn" 附近的 media-type
                                    escaped_new = re.escape(new_bn)
                                    text = re.sub(
                                        rf'media-type="{re.escape(old_mime)}"([^>]*href="[^"]*{escaped_new}")',
                                        f'media-type="{new_mime}"\\1', text
                                    )
                                    text = re.sub(
                                        rf'(href="[^"]*{escaped_new}"[^>]*)media-type="{re.escape(old_mime)}"',
                                        f'\\1media-type="{new_mime}"', text
                                    )

                            data = text.encode('utf-8')
                        except Exception:
                            pass

                    zout.writestr(arcname, data)

        os.replace(temp_path, epub_path)

    except Exception as e:
        logger.write(f"更新引用失败: {e}")
        if os.path.exists(temp_path):
            os.remove(temp_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        print("用法: python img_compress.py <epub文件路径>")
