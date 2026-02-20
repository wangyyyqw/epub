# -*- coding: utf-8 -*-
# 图片压缩工具
# 功能：
# 1. 无透明度的PNG转为JPG
# 2. 有透明度的PNG压缩为PNG-8二值透明

import os
import zipfile
from PIL import Image
import io
import re
from urllib.parse import unquote

try:
    from ..log import logwriter
except:
    from .log import logwriter

logger = logwriter()


def has_transparency(img):
    """检查图片是否有透明度"""
    if img.mode == 'RGBA':
        # 检查alpha通道是否有非255的值
        alpha = img.split()[3]
        if alpha.getextrema()[0] < 255:
            return True
    elif img.mode == 'LA':
        alpha = img.split()[1]
        if alpha.getextrema()[0] < 255:
            return True
    elif img.mode == 'P':
        # 调色板模式，检查是否有透明色
        if 'transparency' in img.info:
            return True
    return False


def convert_to_binary_alpha(img):
    """将图片转换为二值透明PNG-8"""
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # 分离通道
    r, g, b, a = img.split()
    
    # 二值化alpha通道：>128为不透明，<=128为透明
    a = a.point(lambda x: 255 if x > 128 else 0)
    
    # 合并回RGBA
    img = Image.merge('RGBA', (r, g, b, a))
    
    # 创建白色背景并粘贴图片，用于生成调色板
    bg = Image.new('RGB', img.size, (255, 255, 255))
    bg.paste(img, mask=a)
    
    # 量化为255色 (留一个位置给透明色)
    # method=2 (FastOctree)
    p_img = bg.quantize(colors=255, method=2)
    
    # 创建目标P模式图片，初始化为透明色索引 (255)
    trans_index = 255
    out_img = Image.new('P', img.size, color=trans_index)
    
    # 复制调色板
    palette = p_img.getpalette()
    if len(palette) < 768:
        palette += [0] * (768 - len(palette))
    out_img.putpalette(palette)
    
    # 使用alpha作为蒙版，将不透明部分粘贴过去
    out_img.paste(p_img, mask=a)
    
    # 设置透明色索引
    out_img.info['transparency'] = trans_index
    
    return out_img, 'png'


def convert_png_to_jpg(img, quality=85):
    """将PNG转换为JPG"""
    if img.mode in ('RGBA', 'LA', 'P'):
        # 创建白色背景
        background = Image.new('RGB', img.size, (255, 255, 255))
        if img.mode == 'P':
            img = img.convert('RGBA')
        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
        img = background
    elif img.mode != 'RGB':
        img = img.convert('RGB')
    
    return img, 'jpg'


def process_image(img_data, filename):
    """处理单张图片"""
    try:
        img = Image.open(io.BytesIO(img_data))
        original_format = img.format
        
        # 只处理PNG图片
        if original_format != 'PNG':
            return None, None, 'skip'
        
        if has_transparency(img):
            # 有透明度：转为PNG-8二值透明
            new_img, new_ext = convert_to_binary_alpha(img)
            logger.write(f"  {filename}: PNG(透明) -> PNG-8(二值透明)")
        else:
            # 无透明度：转为JPG
            new_img, new_ext = convert_png_to_jpg(img)
            logger.write(f"  {filename}: PNG(无透明) -> JPG")
        
        # 保存到内存
        output = io.BytesIO()
        if new_ext == 'jpg':
            new_img.save(output, format='JPEG', quality=85, optimize=True)
        else:
            new_img.save(output, format='PNG', optimize=True)
        
        return output.getvalue(), new_ext, 'success'
    
    except Exception as e:
        logger.write(f"  {filename}: 处理失败 - {e}")
        return None, None, 'error'


def run(epub_src, output_path=None):
    """压缩EPUB中的图片"""
    try:
        logger.write(f"\n正在压缩图片: {epub_src}")
        
        if not os.path.exists(epub_src):
            logger.write(f"错误: 文件不存在 {epub_src}")
            return "error"
        
        # 确定输出路径
        epub_dir = os.path.dirname(epub_src)
        epub_name = os.path.basename(epub_src)
        
        if output_path and os.path.isdir(output_path):
            out_epub = os.path.join(output_path, epub_name.replace('.epub', '_compressed.epub'))
        else:
            out_epub = epub_src.replace('.epub', '_compressed.epub')
        
        # 读取原始EPUB
        with zipfile.ZipFile(epub_src, 'r') as zin:
            namelist = zin.namelist()
            
            # 找到OPF文件
            opf_path = None
            for name in namelist:
                if name.lower().endswith('.opf'):
                    opf_path = name
                    break
            
            if not opf_path:
                logger.write("错误: 找不到OPF文件")
                return "error"
            
            opf_content = zin.read(opf_path).decode('utf-8')
            opf_dir = os.path.dirname(opf_path)
            
            # 记录需要修改的文件名映射 (旧路径 -> 新路径)
            rename_map = {}  # { old_arcname: new_arcname }
            processed_count = 0
            
            with zipfile.ZipFile(out_epub, 'w', zipfile.ZIP_DEFLATED) as zout:
                for arcname in namelist:
                    data = zin.read(arcname)
                    
                    # 检查是否是PNG图片
                    if arcname.lower().endswith('.png'):
                        new_data, new_ext, status = process_image(data, arcname)
                        
                        if status == 'success' and new_data:
                            processed_count += 1
                            if new_ext == 'jpg':
                                # 修改文件名
                                new_arcname = arcname[:-4] + '.jpg'
                                rename_map[arcname] = new_arcname
                                zout.writestr(new_arcname, new_data)
                            else:
                                # 保持PNG但压缩了
                                zout.writestr(arcname, new_data)
                        else:
                            # 保持原样
                            zout.writestr(arcname, data)
                    else:
                        zout.writestr(arcname, data)
                
                # 如果有PNG转JPG，需要更新OPF和相关文件中的引用
                if rename_map:
                    logger.write(f"更新文件引用: {len(rename_map)} 个文件名变更")
                    
                    # 重新写入修正后的文件
                    # 这需要重新处理EPUB，先关闭再重新打开
            
            # 如果有重命名，需要更新引用
            if rename_map:
                update_references(out_epub, rename_map, opf_path)
        
        logger.write(f"图片压缩完成: 处理了 {processed_count} 张图片")
        logger.write(f"输出文件: {out_epub}")
        return 0
    
    except Exception as e:
        logger.write(f"压缩失败: {e}")
        return "error"


def update_references(epub_path, rename_map, opf_path):
    """更新EPUB中的文件引用，使用精确的正则替换避免误伤"""
    try:
        temp_path = epub_path + '.tmp'
        
        # 预构建精确替换映射：basename -> new_basename
        basename_map = {}
        for old_name, new_name in rename_map.items():
            old_basename = os.path.basename(old_name)
            new_basename = os.path.basename(new_name)
            basename_map[old_basename] = new_basename
        
        with zipfile.ZipFile(epub_path, 'r') as zin:
            with zipfile.ZipFile(temp_path, 'w', zipfile.ZIP_DEFLATED) as zout:
                for arcname in zin.namelist():
                    data = zin.read(arcname)
                    
                    # 跳过已经被重命名的旧文件
                    if arcname in rename_map:
                        continue
                    
                    # 更新文本文件中的引用
                    if arcname.lower().endswith(('.opf', '.xhtml', '.html', '.css', '.ncx')):
                        try:
                            text = data.decode('utf-8')
                            for old_basename, new_basename in basename_map.items():
                                # 使用正则确保只替换属性值中的文件名引用
                                # 匹配 href="...old.png" src="...old.png" url(...old.png) 等
                                escaped_old = re.escape(old_basename)
                                # 替换路径中的文件名（前面是/或引号开头）
                                text = re.sub(
                                    r'(?<=[/"\'])' + escaped_old + r'(?=["\'\s\)>])',
                                    new_basename,
                                    text
                                )
                                # 也替换URL编码的版本
                                from urllib.parse import quote
                                escaped_old_quoted = re.escape(quote(old_basename))
                                text = re.sub(
                                    r'(?<=[/"\'])' + escaped_old_quoted + r'(?=["\'\s\)>])',
                                    quote(new_basename),
                                    text
                                )
                            
                            # 更新media-type
                            text = re.sub(
                                r'media-type="image/png"([^>]*href="[^"]*\.jpg")',
                                r'media-type="image/jpeg"\1',
                                text
                            )
                            text = re.sub(
                                r'(href="[^"]*\.jpg"[^>]*)media-type="image/png"',
                                r'\1media-type="image/jpeg"',
                                text
                            )
                            
                            data = text.encode('utf-8')
                        except:
                            pass
                    
                    zout.writestr(arcname, data)
        
        # 替换原文件
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
