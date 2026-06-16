import os
import re
import sys
import io
import time
import random
import base64
from playwright.sync_api import sync_playwright

# Tu cau hinh encoding va flush immediately cho terminal Windows
sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)
sys.stderr.reconfigure(encoding='utf-8', line_buffering=True)

# --- CAU HINH ---
CHROME_CDP_URL = "http://localhost:9222"
PROMPTS_FILE = "prompts.txt"
OUTPUT_DIR = "outputs"
DELAY_MIN = 5  # Giay nghi toi thieu giua cac anh
DELAY_MAX = 15 # Giay nghi toi da giua cac anh
MAX_WAIT_IMAGE = 240 # Thoi gian cho tao anh toi da (4 phut)

# --- TRINH DON TEN FILE ---
def clean_filename(name):
    # Loai bo ky tu dac biet khong hop le trong Windows
    cleaned = re.sub(r'[\\/:*?"<>|]', '', name)
    # Thay khoang trang bang gach ngang
    cleaned = re.sub(r'\s+', '-', cleaned)
    # Gioi han do dai va loai bo gach ngang o dau/cuoi
    return cleaned[:50].strip('-')

# --- PARSE DONG PROMPT ---
def parse_prompt_line(line, index):
    # Dinh dang [mm:ss]
    match = re.match(r'^\[(\d{2}):(\d{2})\]\s*(.*)$', line)
    if match:
        m, s = match.group(1), match.group(2)
        prompt = match.group(3).strip()
        filename = f"{m}_{s}_{clean_filename(prompt)}"
        return prompt, filename
        
    # Dinh dang [hh:mm:ss]
    match_long = re.match(r'^\[(\d{2}):(\d{2}):(\d{2})\]\s*(.*)$', line)
    if match_long:
        h, m, s = match_long.group(1), match_long.group(2), match_long.group(3)
        prompt = match_long.group(4).strip()
        filename = f"{h}_{m}_{s}_{clean_filename(prompt)}"
        return prompt, filename
        
    # Mac dinh neu khong co timestamp
    prompt = line.strip()
    filename = f"{str(index + 1).zfill(3)}_{clean_filename(prompt)}"
    return prompt, filename

# --- DO O PROMPT TREN GIAO DIEN ---
def find_prompt_input(page):
    selectors = [
        '[data-slate-editor="true"]',
        '[contenteditable="true"][role="textbox"]',
        '[role="textbox"][aria-multiline="true"]',
        'div[role="textbox"]',
        '[contenteditable="true"]',
        '[contenteditable=""]',
        "textarea",
    ]
    for sel in selectors:
        locator = page.locator(sel)
        if locator.count() > 0:
            for i in range(locator.count()):
                el = locator.nth(i)
                if el.is_visible():
                    return el
            return locator.first
    return None

# --- GO PROMPT VAO O (XU LY CA SLATE.JS) ---
def set_prompt_text(page, input_el, text):
    is_content_editable = input_el.evaluate("el => el.isContentEditable")
    if is_content_editable:
        input_el.evaluate("""(el, val) => {
            // Xoa text cu neu co
            try {
                const sel = window.getSelection();
                sel.removeAllRanges();
                const range = document.createRange();
                range.selectNodeContents(el);
                sel.addRange(range);
                el.dispatchEvent(new InputEvent("beforeinput", {
                    inputType: "deleteContentBackward",
                    bubbles: true, cancelable: true, composed: true
                }));
            } catch(e) {}
            
            // Chen text moi
            el.dispatchEvent(new InputEvent("beforeinput", {
                inputType: "insertText",
                data: val,
                bubbles: true, cancelable: true, composed: true
            }));
        }""", text)
    else:
        input_el.fill(text)

# --- KICH HOAT O NHAP LIEU ---
def wake_prompt_box(page):
    input_el = find_prompt_input(page)
    if input_el:
        input_el.click()
        time.sleep(0.2)
        return input_el
        
    # Neu chua moc, thu tim nut arrow_forward va click lech trai 150px
    arrow = page.locator('button:has-text("arrow_forward"), [role="button"]:has-text("arrow_forward")')
    if arrow.count() > 0:
        first_arrow = arrow.first
        if first_arrow.is_visible():
            box = first_arrow.bounding_box()
            if box:
                page.mouse.click(box['x'] - 150, box['y'] + box['height'] / 2)
                time.sleep(0.3)
                return find_prompt_input(page)
                
    return find_prompt_input(page)

# --- QUET ANH DA HOAN THANH ---
def get_completed_images(page):
    return page.evaluate("""() => {
        return Array.from(document.querySelectorAll('img'))
            .filter(img => {
                const src = img.currentSrc || img.src || "";
                if (!/^https?:|^blob:/.test(src)) return false;
                const w = img.naturalWidth || img.width;
                const h = img.naturalHeight || img.height;
                return w >= 256 && h >= 256;
            })
            .map(img => img.currentSrc || img.src);
    }""")

# --- TAI ANH QUA BASE64 DATA URL (GIU NGUYEN SESSION/COOKIES CUA TRINH DUYET) ---
def get_image_data_url(page, src):
    return page.evaluate("""async (src) => {
        const res = await fetch(src);
        const blob = await res.blob();
        return await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = reject;
            reader.readAsDataURL(blob);
        });
    }""", src)

# --- CHUONG TRINH CHINH ---
def main():
    print("=" * 60)
    print(" H2DEV FLOW - BAN LOCAL AUTOMATION SCRIPT")
    print("=" * 60)
    
    if not os.path.exists(PROMPTS_FILE):
        print(f"[ERROR] Khong tim thay file {PROMPTS_FILE}. Vui long tao file nay truoc.")
        return
        
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Doc danh sach prompt
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
        
    if not lines:
        print("[WARNING] File prompts.txt dang trong hoac chi chua ghi chu.")
        return
        
    print(f"[+] Tim thay {len(lines)} prompt trong hang doi.")
    
    with sync_playwright() as p:
        print(f"[+] Dang ket noi voi Chrome qua port 9222...")
        try:
            browser = p.chromium.connect_over_cdp(CHROME_CDP_URL)
        except Exception as e:
            print(f"[ERROR] Khong the ket noi den Chrome: {e}")
            print("Vui long chay file 'run_chrome.bat' truoc va dam bao Chrome dang mo.")
            return
            
        # Tim tab Google Flow
        context = browser.contexts[0]
        flow_page = None
        for page in context.pages:
            if "/tools/flow" in page.url:
                flow_page = page
                break
                
        if not flow_page:
            # Thu lay bat ky trang nao co /fx/ neu khong thay tools/flow
            for page in context.pages:
                if "/fx/" in page.url:
                    flow_page = page
                    break
                    
        if not flow_page:
            print("[ERROR] Khong tim thay tab Google Flow dang mo.")
            print("Vui long mo trang: https://labs.google/fx/tools/flow tren Chrome debug.")
            return
            
        print(f"[OK] Ket noi thanh cong toi tab: '{flow_page.title()}'")
        
        for idx, line in enumerate(lines):
            prompt, file_slug = parse_prompt_line(line, idx)
            dest_file = os.path.join(OUTPUT_DIR, f"{file_slug}.png")
            
            print("-" * 50)
            print(f"[{idx+1}/{len(lines)}] Dang xu ly prompt:")
            print(f" > Content: {prompt[:80]}...")
            print(f" > File se luu: {dest_file}")
            
            # Neu file da ton tai va co dung luong hop le (lon hon 1KB)
            if os.path.exists(dest_file) and os.path.getsize(dest_file) > 1024:
                print(" [i] Anh da ton tai, bo qua de tiet kiem thoi gian.")
                continue
                
            # Danh thuc o nhap prompt
            input_el = wake_prompt_box(flow_page)
            if not input_el:
                print(" [ERROR] Khong tim thay o nhap prompt tren giao dien. Thu lai...")
                continue
                
            # Focus va dien text bang phuong phap truoc-nhap-lieu (beforeinput)
            input_el.click()
            time.sleep(0.1)
            set_prompt_text(flow_page, input_el, prompt)
            time.sleep(0.5)
            
            # Chup danh sach anh nen (baseline)
            baseline = set(get_completed_images(flow_page))
            
            # Gui prompt (nhan Enter)
            flow_page.keyboard.press("Enter")
            print(" [>] Da gui prompt. Dang cho anh moi xu hien...")
            
            # Cho anh moi
            start_time = time.time()
            new_image_src = None
            
            while time.time() - start_time < MAX_WAIT_IMAGE:
                current_imgs = get_completed_images(flow_page)
                new_imgs = [src for src in current_imgs if src not in baseline]
                
                if new_imgs:
                    new_image_src = new_imgs[0]
                    break
                    
                time.sleep(2)
                
            if new_image_src:
                print(" [OK] Da phat hien anh moi. Dang tai...")
                time.sleep(1.5) # Cho anh tai day du
                
                try:
                    # Tai anh bang session cua trinh duyet
                    data_url = get_image_data_url(flow_page, new_image_src)
                    header, encoded = data_url.split(",", 1)
                    data = base64.b64decode(encoded)
                    with open(dest_file, "wb") as f_img:
                        f_img.write(data)
                    print(f" [OK] Luu anh thanh cong.")
                except Exception as e:
                    print(f" [ERROR] Loi khi tai/luu anh: {e}")
            else:
                print(" [ERROR] Qua thoi gian cho tao anh (Timeout). Bo qua...")
                
            # Nghi ngau nhien
            if idx < len(lines) - 1:
                sleep_time = random.uniform(DELAY_MIN, DELAY_MAX)
                print(f" [i] Nghi ngau nhien {sleep_time:.1f} giay truoc prompt tiep theo...")
                time.sleep(sleep_time)
                
        print("=" * 60)
        print(" HOAN THANH TOAN BO HANG DOI PROMPT!")
        print("=" * 60)

if __name__ == "__main__":
    main()
