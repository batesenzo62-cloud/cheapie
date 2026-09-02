"""
One-off: download the promo/banner images found with unhelpful alt text
(alt="image" or none) so they can be inspected/OCR'd directly, since the
local sandbox's connection to some of these sites is currently blocked.
Not a permanent scraper.
"""
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

urls = [
    ("bbl_homepage_banner.png", "https://blackbullliquorhawera.co.nz/Portals/1/EasyGalleryImages/405/ImageSlider/Thumbs/HomePageBanner134299.png"),
    ("bbl_banner.png", "https://blackbullliquorhawera.co.nz/Portals/1/EasyGalleryImages/405/ImageSlider/BBLbanner.png"),
    ("bbl_bannerclear.png", "https://blackbullliquorhawera.co.nz/Portals/1/skins/black%20bull%20liquor/images/bannerclear.png"),
    ("bbl_winebanner.jpg", "https://blackbullliquorhawera.co.nz/portals/1/winebanner.jpg"),
]

for name, url in urls:
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        print(name, url, r.status_code, len(r.content))
        if r.status_code == 200:
            with open(f"banner_images/{name}", "wb") as f:
                f.write(r.content)
    except Exception as e:
        print(name, "ERROR", e)
