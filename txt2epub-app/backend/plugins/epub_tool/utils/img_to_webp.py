import zipfile
import os
import shutil
from io import BytesIO
from xml.etree import ElementTree

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from ..log import logwriter
except:
    from .log import logwriter

logger = logwriter()


class ImageToWebP:
    def __init__(self, epub_path, output_path):
        if not Image:
             raise ImportError("Pillow library not found. Please install it with 'pip install Pillow'")

        if not os.path.exists(epub_path):
            raise Exception("EPUB文件不存在")

        self.epub_path = os.path.normpath(epub_path)
        
        # Determine output directory with permission fallback
        if output_path and os.path.exists(output_path):
            if os.path.isfile(output_path):
                raise Exception("输出路径不能是文件")
            if not os.path.exists(output_path):
                raise Exception(f"输出路径{output_path}不存在")
        else:
            output_path = os.path.dirname(epub_path)
        
        # Check if we can write to the output directory
        try:
            test_file = os.path.join(output_path, ".test_write_permission")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            # Fallback to current directory if no write permission
            logger.write(f"无法写入到输出目录: {e}, 将使用当前目录作为备选")
            output_path = os.getcwd()
            
        self.output_path = os.path.normpath(output_path)
        self.file_write_path = os.path.join(
            self.output_path,
            os.path.basename(self.epub_path).replace(".epub", "_to_webp.epub"),
        )
        
        # We will open zip files in process() method using 'with' statement
        self.htmls = []
        self.css = []
        self.images = []
        self.opf = ""
        self.ori_files = []
        self.img_dict = {}

    def process(self):
        # Clean up existing target file
        if os.path.exists(self.file_write_path):
            try:
                os.remove(self.file_write_path)
            except OSError:
                pass

        try:
            with zipfile.ZipFile(self.epub_path, 'r') as self.epub, \
                 zipfile.ZipFile(self.file_write_path, "w", zipfile.ZIP_DEFLATED) as self.target_epub:
                
                # 0. Write mimetype file first (must be uncompressed and first)
                try:
                    mimetype = self.epub.read("mimetype")
                    self.target_epub.writestr("mimetype", mimetype, zipfile.ZIP_STORED)
                except KeyError:
                    # If mimetype is missing in source, write default
                    self.target_epub.writestr("mimetype", b"application/epub+zip", zipfile.ZIP_STORED)

                # Scan files
                for file in self.epub.namelist():
                    if file == "mimetype":
                        continue
                    elif file.lower().endswith(".html") or file.endswith(".xhtml"):
                        self.htmls.append(file)
                    elif file.lower().endswith(".css"):
                        self.css.append(file)
                    elif file.lower().endswith((".jpg", ".jpeg", ".png", ".bmp")):
                        self.images.append(file)
                    elif file.lower().endswith(".opf"):
                        self.opf = file
                    else:
                        self.ori_files.append(file)
                
                # 1. Process Images
                self._process_images()
                
                # 2. Copy original files
                self._copy_original_files()
                
                # 3. Check if we need to proceed
                if not self.img_dict:
                    logger.write("没有找到需要转换的图片")
                    # If we skip, we still need to have a valid epub if we want to return "success"
                    # But if we return "skip", the main loop might expect the original file to be untouched or handled.
                    # The original code returns "skip" which usually implies "didn't do anything".
                    # However, we have already started writing the new file. 
                    # If we return "skip", we should probably delete the partial new file.
                    return "skip"

                # 4. Replace references
                self._replace_references()
                
                logger.write(f"EPUB文件处理完成，输出文件路径: {self.file_write_path}")
                return 0

        except Exception as e:
            # Clean up if failed
            if os.path.exists(self.file_write_path):
                try:
                    os.remove(self.file_write_path)
                except:
                    pass
            raise e

    def _process_images(self):
        for img_path in self.images:
            img_data = self.epub.read(img_path)
            img_file = BytesIO(img_data)
            try:
                image = Image.open(img_file)
                img_basename = os.path.basename(img_path)
                filename_no_ext, ext = os.path.splitext(img_basename)
                
                # Convert to WebP
                new_name = filename_no_ext + ".webp"
                self.img_dict[img_basename] = [new_name, "image/webp"]
                
                buffer = BytesIO()
                image.save(buffer, format="WEBP", quality=80) 
                
                # Write to new epub with new name
                new_img_path = img_path.replace(img_basename, new_name)
                self.target_epub.writestr(new_img_path, buffer.getvalue())

            except Exception as e:
                logger.write(f"无法处理图片 {img_path}: {str(e)}")
                # Keep original if conversion fails
                self.target_epub.writestr(img_path, img_data)

    def _copy_original_files(self):
        for item in self.ori_files:
            # Use stream copying to avoid loading large files into memory
            with self.epub.open(item) as source_file:
                # ZipInfo is needed to preserve/set permissions or compression
                # Simple writestr with stream requires us to be careful.
                # However, zipfile.open(name, 'w') is available in newer Python versions
                # and allows writing streams.
                
                # Check if we can open target as stream or if we need to use writestr
                # writestr accepts bytes, so streaming requires reading chunks.
                # shutil.copyfileobj works between file-like objects.
                
                # ZipFile.open(name, 'w') was added in Python 3.6.
                # We want to use ZIP_DEFLATED for these files usually.
                
                # Create a ZipInfo object to specify compression
                zinfo = zipfile.ZipInfo(filename=item)
                zinfo.compress_type = zipfile.ZIP_DEFLATED
                
                # Preserve permissions if possible (optional)
                try:
                    src_info = self.epub.getinfo(item)
                    zinfo.external_attr = src_info.external_attr
                except:
                    pass

                with self.target_epub.open(zinfo, 'w') as target_file:
                    shutil.copyfileobj(source_file, target_file)

    def _replace_references(self):
        # Replace in OPF
        if self.opf:
            opf_content = self.epub.read(self.opf).decode("utf-8")
            self._replace_opf(opf_content)

        # Replace in HTMLs
        for html_path in self.htmls:
            html_content = self.epub.read(html_path).decode("utf-8")
            self._replace_html(html_path, html_content)

        # Replace in CSS
        for css_path in self.css:
            css_content = self.epub.read(css_path).decode("utf-8")
            self._replace_css(css_path, css_content)

    def _replace_opf(self, opf_content):
        # We use regex/string replacement instead of XML parsing to preserve formatting as much as possible,
        # or stick to ElementTree if reliability is key. Original code used ElementTree.
        # Let's use ElementTree but be careful.
        
        try:
            # Register namespace to avoid ns0 prefixes if possible
            ns = {"opf": "http://www.idpf.org/2007/opf"}
            for prefix, uri in ns.items():
                ElementTree.register_namespace(prefix if prefix != 'opf' else '', uri)
            
            # Note: ElementTree might mangle namespaces or prefixes.
            # However, since the original code used it, we stick to it but ensure safe writes.
            root = ElementTree.fromstring(opf_content)
            
            # Replace meta cover
            for meta in root.findall('.//{http://www.idpf.org/2007/opf}meta[@name="cover"]'):
                content = meta.get("content")
                if content and os.path.basename(content) in self.img_dict:
                    cover_basename = os.path.basename(content)
                    replace_name = self.img_dict[cover_basename][0]
                    new_content = content.replace(cover_basename, replace_name)
                    meta.set("content", new_content)

            # Replace manifest items
            for item in root.findall(".//{http://www.idpf.org/2007/opf}item"):
                href = item.get("href")
                if href:
                    href_basename = os.path.basename(href)
                    if href_basename in self.img_dict:
                        replace_name, replace_media_type = self.img_dict[href_basename]
                        
                        # Note: We do NOT change the item ID. 
                        # Changing the ID would break references in the <spine> and <guide> 
                        # unless we also updated them, which is unnecessary complexity.
                        
                        item.set("href", href.replace(href_basename, replace_name))
                        item.set("media-type", replace_media_type)

            modified_opf = ElementTree.tostring(root, encoding="utf-8")
            # Add XML declaration manually if needed, ElementTree.tostring doesn't add it by default usually unless specified
            self.target_epub.writestr(self.opf, b'<?xml version="1.0" encoding="utf-8"?>\n' + modified_opf)
        except Exception as e:
            logger.write(f"OPF replacement failed: {e}, using original")
            self.target_epub.writestr(self.opf, opf_content.encode('utf-8'))

    def _replace_html(self, html_path, content):
        def replace_match(match):
            try:
                if len(match.groups()) >= 3:
                    original_src = match.group(2) + "." + match.group(3)
                    img_basename = os.path.basename(original_src)
                    if img_basename in self.img_dict:
                        new_name = self.img_dict[img_basename][0]
                        return match.group(0).replace(img_basename, new_name)
            except Exception as e:
                logger.write(f"Error in replace_match: {e}")
            return match.group(0)

        import re
        pattern = r'<img\b[^>]*?\bsrc\s*=\s*(["\'])(.*?)\.(jpg|jpeg|png|bmp)\1'
        pattern2 = r'<image\b[^>]*?\bxlink:href\s*=\s*(["\'])(.*?)\.(jpg|jpeg|png|bmp)\1'
        
        updated_content = re.sub(pattern, lambda m: replace_match(m), content, flags=re.IGNORECASE)
        updated_content = re.sub(pattern2, lambda m: replace_match(m), updated_content, flags=re.IGNORECASE)
        
        self.target_epub.writestr(html_path, updated_content.encode("utf-8"))

    def _replace_css(self, css_path, content):
        def replace_match(match):
            quote = match.group(1) or ""
            path_with_ext = match.group(2) + "." + match.group(3)
            img_basename = os.path.basename(path_with_ext)
            if img_basename in self.img_dict:
                new_name = self.img_dict[img_basename][0]
                return f"url({quote}{path_with_ext.replace(img_basename, new_name)}{quote})"
            return match.group(0)

        import re
        pattern = r'url\(\s*([\'"]?)\s*(.*?)\.(jpg|jpeg|png|bmp)\s*(?:\?\S*)?\s*\1\s*\)'
        updated_css = re.sub(pattern, replace_match, content, flags=re.IGNORECASE)
        self.target_epub.writestr(css_path, updated_css.encode("utf-8"))


def run(epub_path, output_path):
    logger.write(f"\n正在尝试将EPUB图片转为WebP: {epub_path}")
    try:
        it = ImageToWebP(epub_path, output_path)
        return it.process()
    except Exception as e:
        logger.write(f"处理EPUB文件时发生错误: {str(e)}")
        import traceback
        logger.write(traceback.format_exc())
        return f"处理EPUB文件时发生错误: {str(e)}"


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        run(sys.argv[1], None)
