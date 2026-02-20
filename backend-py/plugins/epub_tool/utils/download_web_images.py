# -*- coding: utf-8 -*-
# 网络图片下载工具
# 功能：
# 1. 扫描 EPUB 中的 HTML/XHTML 文件，提取网络图片链接
# 2. 下载网络图片到本地 images 目录
# 3. 替换 HTML 中的网络链接为本地路径
# 4. 更新 OPF manifest

import os
import sys
import zipfile
import re
import hashlib
from urllib.parse import urlparse, unquote
from io import BytesIO

try:
    import requests
except ImportError:
    requests = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

try:
    from ..log import logwriter
except:
    from .log import logwriter

logger = logwriter()


def extract_web_images(html_content):
    """从 HTML 内容中提取所有网络图片 URL"""
    image_urls = []
    
    # 使用正则表达式提取 img 标签中的 src 属性
    # 匹配 http:// 或 https:// 开头的 URL
    img_pattern = r'<img[^>]+src=["\'](https?://[^"\']+)["\']'
    matches = re.findall(img_pattern, html_content, re.IGNORECASE)
    image_urls.extend(matches)
    
    # 如果有 BeautifulSoup，使用它进行更精确的解析
    if BeautifulSoup:
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            for img in soup.find_all('img'):
                src = img.get('src', '')
                if src.startswith('http://') or src.startswith('https://'):
                    if src not in image_urls:
                        image_urls.append(src)
        except Exception as e:
            logger.write(f"  BeautifulSoup 解析失败，使用正则表达式结果: {e}")
    
    return image_urls


def download_image(url, timeout=30):
    """下载单张图片并返回二进制数据"""
    if not requests:
        logger.write("  错误: 需要安装 requests 库")
        return None
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()
        
        # 验证是否为有效图片
        if Image:
            try:
                img = Image.open(BytesIO(response.content))
                img.verify()
            except Exception as e:
                logger.write(f"  图片验证失败 {url}: {e}")
                return None
        
        return response.content
    
    except requests.exceptions.Timeout:
        logger.write(f"  下载超时: {url}")
        return None
    except requests.exceptions.RequestException as e:
        logger.write(f"  下载失败 {url}: {e}")
        return None
    except Exception as e:
        logger.write(f"  未知错误 {url}: {e}")
        return None


def generate_local_filename(url, img_data, existing_filenames=None):
    """根据 URL 和内容生成本地文件名"""
    if existing_filenames is None:
        existing_filenames = set()

    # 尝试从 URL 获取文件名
    parsed_url = urlparse(url)
    path = parsed_url.path
    # 解码 URL 编码的文件名
    filename = unquote(os.path.basename(path))
    
    # 移除 URL 参数和 hash
    filename = filename.split('?')[0].split('#')[0]

    # 如果文件名为空或太短，使用哈希
    if not filename or len(filename) < 3:
        url_hash = hashlib.md5(url.encode('utf-8')).hexdigest()[:12]
        filename = f"web_{url_hash}"
    
    # 规范化扩展名
    base, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    # 验证扩展名是否为常见图片格式
    valid_exts = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
    
    # 检测实际格式
    actual_ext = None
    if Image and img_data:
        try:
            img = Image.open(BytesIO(img_data))
            format_ext = img.format.lower()
            if format_ext == 'jpeg':
                actual_ext = '.jpg'
            else:
                actual_ext = f'.{format_ext}'
        except:
            pass
            
    if ext not in valid_exts:
        # 如果原扩展名无效，使用检测到的扩展名，或者默认 jpg
        ext = actual_ext if actual_ext else '.jpg'
        filename = f"{base}{ext}"
    elif actual_ext and actual_ext != ext and actual_ext != '.jpeg': # jpeg/jpg 视为一致
        # 如果扩展名与实际内容不符，修正扩展名
        # 但有些时候 URL 是 .jpg 但内容是 png，最好还是修正
        if not (ext == '.jpg' and actual_ext == '.jpeg'):
             ext = actual_ext
             filename = f"{base}{ext}"
    
    # 清理文件名中的非法字符
    filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
    
    # 处理重复文件名
    original_base, original_ext = os.path.splitext(filename)
    counter = 1
    while filename in existing_filenames:
        filename = f"{original_base}_{counter}{original_ext}"
        counter += 1
    
    return filename


def update_html_references(html_content, url_mapping):
    """替换 HTML 中的图片链接
    
    Args:
        html_content: HTML 内容
        url_mapping: {原始URL: 本地文件名} 的映射字典
    
    Returns:
        更新后的 HTML 内容
    """
    updated_content = html_content
    
    for original_url, local_filename in url_mapping.items():
        # 替换引号内的完整 URL
        updated_content = updated_content.replace(f'"{original_url}"', f'"../images/{local_filename}"')
        updated_content = updated_content.replace(f"'{original_url}'", f"'../images/{local_filename}'")
        
        # 处理可能的 URL 编码情况
        from urllib.parse import quote
        encoded_url = quote(original_url, safe=':/?#[]@!$&\'()*+,;=')
        if encoded_url != original_url:
            updated_content = updated_content.replace(f'"{encoded_url}"', f'"../images/{local_filename}"')
            updated_content = updated_content.replace(f"'{encoded_url}'", f"'../images/{local_filename}'")
    
    return updated_content


def update_opf_manifest(opf_content, new_images, images_dir_in_opf='images'):
    """更新 OPF manifest，添加新下载的图片
    
    Args:
        opf_content: OPF 文件内容
        new_images: 新图片文件名列表
        images_dir_in_opf: 图片目录在 OPF 中的相对路径
    
    Returns:
        更新后的 OPF 内容
    """
    if not new_images:
        return opf_content
    
    # 查找 manifest 结束标签位置
    manifest_end = opf_content.find('</manifest>')
    if manifest_end == -1:
        logger.write("  警告: 找不到 </manifest> 标签，无法更新 manifest")
        return opf_content
    
    # 生成新的 manifest 项
    new_items = []
    for filename in new_images:
        # 确定 media-type
        ext = os.path.splitext(filename)[1].lower()
        media_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp',
            '.svg': 'image/svg+xml'
        }
        media_type = media_type_map.get(ext, 'image/jpeg')
        
        # 生成唯一的 ID
        item_id = f"img_{os.path.splitext(filename)[0]}"
        href = f"{images_dir_in_opf}/{filename}"
        
        # 创建 manifest item
        item = f'  <item id="{item_id}" href="{href}" media-type="{media_type}"/>\n'
        new_items.append(item)
    
    # 在 </manifest> 前插入新项
    updated_opf = (
        opf_content[:manifest_end] +
        ''.join(new_items) +
        opf_content[manifest_end:]
    )
    
    return updated_opf


def run(epub_path, output_path=None):
    """主函数：下载 EPUB 中的网络图片并替换链接
    
    Args:
        epub_path: 输入的 EPUB 文件路径
        output_path: 输出目录路径（可选）
    
    Returns:
        0: 成功
        其他: 失败
    """
    try:
        sys.stderr.flush()
        logger.write(f"\n正在处理网络图片: {epub_path}")
        
        if not os.path.exists(epub_path):
            logger.write(f"错误: 文件不存在 {epub_path}")
            return 1
        
        # 检查依赖
        if not requests:
            logger.write("错误: 需要安装 requests 库 (pip install requests)")
            return 1
        
        # 确定输出路径
        if output_path and os.path.isdir(output_path):
            out_epub = os.path.join(output_path, os.path.basename(epub_path).replace('.epub', '_downloaded.epub'))
        else:
            out_epub = epub_path.replace('.epub', '_downloaded.epub')
        
        # 临时存储：{网络URL: 本地文件名}
        url_to_local = {}
        # 存储下载的图片数据：{本地文件名: 二进制数据}
        downloaded_images = {}
        
        # 第一遍：读取 EPUB，扫描并下载图片
        with zipfile.ZipFile(epub_path, 'r') as zin:
            namelist = zin.namelist()
            
            # 找到 OPF 文件
            opf_path = None
            for name in namelist:
                if name.lower().endswith('.opf'):
                    opf_path = name
                    break
            
            if not opf_path:
                logger.write("错误: 找不到 OPF 文件")
                return 1
            
            opf_dir = os.path.dirname(opf_path)
            
            logger.write("\n扫描网络图片...")
            total_urls = set()
            
            # 扫描所有 HTML/XHTML 文件
            html_files = [n for n in namelist if n.lower().endswith(('.html', '.xhtml', '.htm'))]
            logger.write(f"共发现 {len(html_files)} 个文本文件，准备扫描...")
            
            for idx, arcname in enumerate(html_files, 1):
                # 每扫描10个文件或最后一个文件时打印进度
                if idx % 10 == 0 or idx == len(html_files):
                    logger.write(f"正在扫描 [{idx}/{len(html_files)}]: {arcname}")
                    
                if True: # 保持原有缩进结构
                    try:
                        content = zin.read(arcname).decode('utf-8', errors='ignore')
                        urls = extract_web_images(content)
                        if urls:
                            logger.write(f"  -> {arcname}: 发现 {len(urls)} 个网络图片")
                            total_urls.update(urls)
                    except Exception as e:
                        logger.write(f"  {arcname}: 扫描失败 - {e}")
            
            if not total_urls:
                logger.write("\n未发现网络图片，无需处理")
                return 0
            
            logger.write(f"\n总计发现 {len(total_urls)} 个唯一的网络图片，开始下载...")
            
            # 下载图片
            success_count = 0
            fail_count = 0
            
            for idx, url in enumerate(total_urls, 1):
                logger.write(f"\n[{idx}/{len(total_urls)}] 下载: {url}")
                img_data = download_image(url)
                
                if img_data:
                    local_filename = generate_local_filename(url, img_data, set(downloaded_images.keys()))
                    url_to_local[url] = local_filename
                    downloaded_images[local_filename] = img_data
                    success_count += 1
                    logger.write(f"  ✓ 成功 -> {local_filename}")
                else:
                    fail_count += 1
                    logger.write(f"  ✗ 失败，将保留原链接")
            
            logger.write(f"\n下载完成: 成功 {success_count} 个, 失败 {fail_count} 个")
            
            if not downloaded_images:
                logger.write("\n没有成功下载任何图片，不生成新文件")
                return 0
        
        # 第二遍：写入新的 EPUB，替换链接并添加图片
        logger.write(f"\n生成新的 EPUB 文件...")
        
        with zipfile.ZipFile(epub_path, 'r') as zin:
            with zipfile.ZipFile(out_epub, 'w', zipfile.ZIP_DEFLATED) as zout:
                namelist = zin.namelist()
                
                # 确定 images 目录路径
                # 通常是 OEBPS/images 或 images
                images_dir = None
                for name in namelist:
                    if 'images/' in name.lower() or 'image/' in name.lower():
                        images_dir = os.path.dirname(name)
                        break
                
                # 如果没有找到，根据 OPF 位置创建
                if not images_dir:
                    if opf_dir:
                        images_dir = os.path.join(opf_dir, 'images')
                    else:
                        images_dir = 'images'
                
                # 确保使用正斜杠
                images_dir = images_dir.replace('\\', '/')
                
                logger.write(f"  图片目录: {images_dir}")
                
                # 复制所有现有文件，并更新 HTML 和 OPF
                for arcname in namelist:
                    data = zin.read(arcname)
                    
                    # 更新 HTML/XHTML 文件中的图片链接
                    if arcname.lower().endswith(('.html', '.xhtml', '.htm')):
                        try:
                            content = data.decode('utf-8', errors='ignore')
                            updated_content = update_html_references(content, url_to_local)
                            data = updated_content.encode('utf-8')
                        except Exception as e:
                            logger.write(f"  警告: 更新 {arcname} 失败 - {e}")
                    
                    # 更新 OPF manifest
                    elif arcname == opf_path:
                        try:
                            content = data.decode('utf-8', errors='ignore')
                            # 计算 images 目录相对于 OPF 的路径
                            if opf_dir:
                                images_rel = os.path.relpath(images_dir, opf_dir).replace('\\', '/')
                            else:
                                images_rel = images_dir
                            updated_content = update_opf_manifest(content, list(downloaded_images.keys()), images_rel)
                            data = updated_content.encode('utf-8')
                        except Exception as e:
                            logger.write(f"  警告: 更新 OPF manifest 失败 - {e}")
                    
                    zout.writestr(arcname, data)
                
                # 添加下载的图片
                logger.write(f"\n添加 {len(downloaded_images)} 个图片到 EPUB...")
                for filename, img_data in downloaded_images.items():
                    img_path = f"{images_dir}/{filename}"
                    zout.writestr(img_path, img_data)
                    logger.write(f"  + {img_path}")
        
        logger.write(f"\n完成! 输出文件: {out_epub}")
        logger.write(f"成功下载并集成 {len(downloaded_images)} 个网络图片")
        return 0
    
    except Exception as e:
        logger.write(f"\n处理失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        run(sys.argv[1])
    else:
        print("用法: python download_web_images.py <epub文件路径>")
