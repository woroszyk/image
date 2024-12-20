from flask import Flask, render_template, request, jsonify, send_file
import requests
from bs4 import BeautifulSoup
from PIL import Image
import io
import os
from urllib.parse import urljoin, urlparse
import base64
import tempfile
import zipfile
import time
from io import BytesIO
import asyncio
from pyppeteer import launch

app = Flask(__name__)

def get_image_info(img_url):
    try:
        response = requests.get(img_url, timeout=10, verify=False)
        response.raise_for_status()
        
        content_type = response.headers.get('content-type', '').lower()
        if not any(img_type in content_type for img_type in ['image/', 'application/octet-stream']):
            return None
            
        size = len(response.content)
        
        img = Image.open(BytesIO(response.content))
        format = img.format
        width, height = img.size
        
        return {
            'url': img_url,
            'format': format,
            'size': size,
            'width': width,
            'height': height
        }
    except Exception as e:
        print(f"Błąd podczas przetwarzania obrazu {img_url}: {str(e)}")
        return None

async def process_images_async(url):
    print(f"Starting process_images_async for URL: {url}")
    browser = None
    try:
        browser = await launch(
            handleSIGINT=False,
            handleSIGTERM=False,
            handleSIGHUP=False,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--single-process'
            ]
        )
        print("Browser launched successfully")
        
        page = await browser.newPage()
        await page.setViewport({'width': 1920, 'height': 1080})
        print(f"Navigating to URL: {url}")
        await page.goto(url, {'waitUntil': 'networkidle0', 'timeout': 30000})
        print("Page loaded successfully")
        
        # Pobierz wszystkie tagi img
        img_elements = await page.querySelectorAll('img')
        img_urls = []
        print(f"Found {len(img_elements)} img elements")
        
        for img in img_elements:
            try:
                src = await page.evaluate('(element) => element.src', img)
                if src and src.startswith('http'):
                    img_urls.append(src)
            except Exception as e:
                print(f"Error getting image URL: {str(e)}")
                continue
        
        # Pobierz tagi style i background-image
        elements_with_bg = await page.querySelectorAll('*')
        print(f"Checking {len(elements_with_bg)} elements for background images")
        
        for element in elements_with_bg:
            try:
                style = await page.evaluate('''(element) => {
                    const style = window.getComputedStyle(element);
                    return style.backgroundImage;
                }''', element)
                
                if style and style.startswith('url('):
                    url_match = style[4:-1].strip('"\'')
                    if url_match.startswith('http'):
                        img_urls.append(url_match)
            except Exception as e:
                print(f"Error getting background image: {str(e)}")
                continue
    
    except Exception as e:
        print(f"Major error in process_images_async: {str(e)}")
        raise e
    
    finally:
        if browser:
            try:
                await browser.close()
                print("Browser closed successfully")
            except Exception as e:
                print(f"Error closing browser: {str(e)}")
    
    # Usuń duplikaty
    img_urls = list(set(img_urls))
    print(f"Found {len(img_urls)} unique image URLs")
    
    # Pobierz informacje o obrazach
    images_info = []
    for img_url in img_urls:
        info = get_image_info(img_url)
        if info:
            images_info.append(info)
    
    print(f"Successfully processed {len(images_info)} images")
    return images_info

def process_images(url):
    return asyncio.get_event_loop().run_until_complete(process_images_async(url))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    url = request.json.get('url')
    if not url:
        return jsonify({'error': 'URL is required'}), 400
    
    try:
        print(f"Starting analysis for URL: {url}")
        images = process_images(url)
        print(f"Analysis completed successfully with {len(images)} images")
        return jsonify({'images': images})
    except Exception as e:
        print(f"Error in analyze endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/download', methods=['POST'])
def download():
    try:
        selected_images = request.json.get('selectedImages', [])
        if not selected_images:
            return jsonify({'error': 'No images selected'}), 400

        # Utwórz tymczasowy katalog
        with tempfile.TemporaryDirectory() as temp_dir:
            # Utwórz plik ZIP
            zip_path = os.path.join(temp_dir, 'images.zip')
            with zipfile.ZipFile(zip_path, 'w') as zip_file:
                for idx, img_url in enumerate(selected_images):
                    try:
                        # Pobierz obraz
                        response = requests.get(img_url, verify=False)
                        response.raise_for_status()
                        
                        # Określ rozszerzenie pliku
                        content_type = response.headers.get('content-type', '')
                        ext = '.jpg'  # domyślne rozszerzenie
                        if 'png' in content_type.lower():
                            ext = '.png'
                        elif 'gif' in content_type.lower():
                            ext = '.gif'
                        elif 'jpeg' in content_type.lower() or 'jpg' in content_type.lower():
                            ext = '.jpg'
                        
                        # Zapisz obraz do ZIP
                        filename = f'image_{idx + 1}{ext}'
                        zip_file.writestr(filename, response.content)
                        
                    except Exception as e:
                        print(f"Błąd podczas pobierania obrazu {img_url}: {str(e)}")
                        continue

            # Wyślij plik ZIP
            return send_file(
                zip_path,
                mimetype='application/zip',
                as_attachment=True,
                download_name='images.zip'
            )

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
