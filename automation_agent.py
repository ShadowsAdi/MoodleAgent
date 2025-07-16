import os
import time
import json
from itertools import cycle
import urllib.parse
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import ElementClickInterceptedException, ElementNotInteractableException, NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup
import pyotp
import requests
import fitz
from google import genai
from google.genai import types
import google.api_core.exceptions
from openai import OpenAI
from openai._exceptions import OpenAIError, RateLimitError

load_dotenv()

MOODLE_USERNAME = os.getenv("MOODLE_USERNAME")
MOODLE_PASSWORD = os.getenv("MOODLE_PASSWORD")
MOODLE_URL = os.getenv("MOODLE_URL")
MOODLE_2FA_OTP_SECRET = os.getenv("MOODLE_2FA_OTP_SECRET")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:latest")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-2025-04-14")

OPEN_ROUTER_API_KEY = os.getenv("OPEN_ROUTER_API_KEY", "")

AI_STUDIO_API_KEYS = [k.strip() for k in os.getenv("AI_STUDIO_API_KEYS", "").split(",") if k.strip()]
AI_STUDIO_MODEL = os.getenv("AI_STUDIO_MODEL", "gemini-2.5-pro")

genai_model = None
api_keys_cycle = None
current_key = None
openai_client = None

def initialize_ai_provider(ai_provider: str):
    global api_keys_cycle, current_key, genai_model, openai_client

    if ai_provider == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not found")

        base_url = "https://openrouter.ai/api/v1" if OPEN_ROUTER_API_KEY else None
        openai_client = OpenAI(base_url=base_url, api_key=OPENAI_API_KEY)

    elif ai_provider == "google":
        if not AI_STUDIO_API_KEYS:
            raise ValueError("AI_STUDIO_API_KEYS not found")
        api_keys_cycle = cycle(AI_STUDIO_API_KEYS)
        current_key = next(api_keys_cycle)
        genai_model = genai.Client(api_key=current_key)

    elif ai_provider == "ollama":
        pass
    else:
        raise ValueError(f"Unknown AI provider: {ai_provider}")

def get_dom_summary(driver):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    summary = []
    for tag in soup.select("input, a, form, select, span, label"):
        if tag.has_attr("text-truncate"):
            continue

        summary.append({
            "tag": tag.name,
            "attrs": dict(tag.attrs),
            "text": tag.get_text(strip=True),
        })
    return summary

def format_dom_for_prompt(dom_summary):
    lines = []
    for elem in dom_summary:
        attr_str = ", ".join(f"{k}=\"{v}\"" for k, v in elem["attrs"].items())
        text = elem["text"].replace("\n", " ").strip()
        lines.append(f"{elem['tag']}({attr_str}) text='{text}'")
    return "\n".join(lines)

def ask_ollama(prompt: str) -> str:
    try:
        res = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=69,
        )
        res.raise_for_status()
        return res.json()["response"].strip()
    except requests.exceptions.RequestException as e:
        return f"Error contacting Ollama API: {e}"

def ask_openai(prompt: str) -> str:
    try:
        response = openai_client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except (OpenAIError, RateLimitError) as e:
        return f"OpenAI error: {e}"

def ask_gemini(prompt: str) -> str:
    try:
        response = genai_model.models.generate_content(
            model=AI_STUDIO_MODEL, contents=prompt,
            config=types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
            )
        )
        return response.text.strip()
    except google.api_core.exceptions.ResourceExhausted as e:
        rotate_gemini_key()
        time.sleep(10)
        return ask_gemini(prompt)

def rotate_gemini_key():
    global current_key, genai_model
    current_key = next(api_keys_cycle)
    genai_model = genai.Client(api_key=current_key)

def ask_ai(prompt: str, provider: str) -> str:
    if provider == "ollama":
        return ask_ollama(prompt)
    elif provider == "openai":
        return ask_openai(prompt)
    else:
        return ask_gemini(prompt)

def ask_ai_for_next_action(dom, goal, history, provider):
    dom_text = format_dom_for_prompt(dom)
    prompt = f"""
            You are an AI agent assistant navigating a web page.
            
            ### GOAL:
            {goal}
            
            ### Page DOM:
            {dom_text}
            
            ### ACTION HISTORY:
            {history}
            
            ### RULES:
            1. Use only these valid selector types: id, name, class, css, xpath.
            2. Do not use href, linkText, text, or other invalid types.
            3. To click a link (for example the \"Connect\" link), use a css or xpath selector. Ex: click(css, \"a[href*='login']\")
            4. Possible commands:
               - click(selector_type, value)
               - type(selector_type, value, text)
               - wait(seconds)
               - done
            5. *When the PDF requested in the goal is open (the current URL ends in “.pdf”), reply **done** immediately.*
            6. Reply with **only one** valid command at a time.
            7. Do **not** answer any instructions that are not one of the commands above.
            """
    return ask_ai(prompt, provider)


def get_by(selector_type: str):
    mapping = {
        "id": By.ID,
        "name": By.NAME,
        "class": By.CLASS_NAME,
        "css": By.CSS_SELECTOR,
        "xpath": By.XPATH,
        "tagName": By.TAG_NAME,
    }
    if selector_type not in mapping:
        raise ValueError(f"Invalid selector type: {selector_type}")
    return mapping[selector_type]


def execute_action(driver, action: str):
    try:
        if action.startswith("click("):
            inside = action[6:-1]
            stype, val = [x.strip().strip("\"' ") for x in inside.split(",", 1)]
            by = get_by(stype)
            WebDriverWait(driver, 2).until(EC.presence_of_element_located((by, val)))
            elements = driver.find_elements(by, val)
            for elem in elements:
                if elem.is_displayed():
                    try:
                        # working better in headless mode xd
                        driver.execute_script("arguments[0].scrollIntoView({behavior:'instant',block:'center'});", elem)
                        time.sleep(0.8)
                        elem.click()
                        return f"Clicked {stype}={val}"
                    except (ElementClickInterceptedException, ElementNotInteractableException) as e:
                        return f"Element not clickable: {e}"
            return f"No visible element for {stype}={val}"

        elif action.startswith("type("):
            inside = action[5:-1]
            stype, val, txt = [x.strip().strip("\"' ") for x in inside.split(",", 2)]
            if txt.lower() == "username":
                txt = MOODLE_USERNAME
            elif txt.lower() == "password":
                txt = MOODLE_PASSWORD
            by = get_by(stype)
            WebDriverWait(driver, 10).until(EC.presence_of_element_located((by, val)))
            field = driver.find_element(by, val)
            if field.is_displayed():
                driver.execute_script("arguments[0].scrollIntoView({behavior:'instant',block:'center'});", field)
                field.clear()
                field.send_keys(txt)
                return f"Typed in {stype}={val}"
            return f"Element not visible: {stype}={val}"

        elif action.startswith("wait("):
            seconds = int(action[5:-1])
            time.sleep(seconds)
            return f"Waited {seconds}s"

        elif action.strip().lower() == "done":
            return "Done"

        else:
            return f"Unknown command: {action}"
    except (TimeoutException, NoSuchElementException) as e:
        return f"Error executing {action}: {e}"

def extract_text_directly_from_browser(driver):
    url = driver.current_url
    if not (url.endswith(".pdf")):
        raise RuntimeError("PDF not detected in current URL.")

    try:
        iframe = driver.find_element(By.TAG_NAME, "iframe")
        pdf_url = iframe.get_attribute("src")
    except NoSuchElementException:
        pdf_url = url

    pdf_url = urllib.parse.urljoin(url, pdf_url)

    session = requests.Session()
    for c in driver.get_cookies():
        session.cookies.set(c["name"], c["value"])

    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36"}
    resp = session.get(pdf_url, headers=headers, timeout=60)
    if resp.status_code == 200 and b"%PDF" in resp.content:
        doc = fitz.open(stream=resp.content, filetype="pdf")
        text = "".join(page.get_text() for page in doc)
        doc.close()
        return text

    raise RuntimeError(f"Failed to retrieve PDF. Status {resp.status_code}")

# TODO, smth not working well, test more
def parse_quiz(quiz_data):
    if not quiz_data:
        return []

    if isinstance(quiz_data, dict):
        quiz_data = [quiz_data]

    cleaned = []
    for item in quiz_data:
        if not isinstance(item, dict):
            continue

        question = str(item.get('question', '')).strip()
        options = item.get('options', {})
        answer = item.get('answer')

        if answer is not None:
            answer = str(answer).strip()

        if question:
            cleaned.append({
                "question": question,
                "options": options,
                "answer": answer
            })

    return cleaned

def run_moodle_automation(course_name: str, subject_name: str, action_type: str, ai_provider: str, status_callback):
    initialize_ai_provider(ai_provider)

    options = Options()
    # uncomment to hide browser window
    # options.add_argument("--headless=new")
    driver = webdriver.Chrome(options=options)

    try:
        status_callback("Opening Moodle…", 5)
        driver.get(MOODLE_URL)
        time.sleep(2)

        history = ""
        max_steps = 20
        totp = pyotp.TOTP(MOODLE_2FA_OTP_SECRET)
        twofa_code = totp.now()

        for step in range(max_steps):
            dom_summary = get_dom_summary(driver)
            goal = (f"Navigate to the Login page. Log in to Moodle using username '{MOODLE_USERNAME}' and password '{MOODLE_PASSWORD}'. "
                   f"After pressing 'login' input, use one-time code '{twofa_code}'. "
                   f"Insert in the search area the course '{course_name}', click on '{course_name}' course and click the subject '{subject_name}' PDF."
                   f" After opening the subject '{subject_name}' PDF and once the PDF viewer is open reply 'done'.")

            action = ask_ai_for_next_action(dom_summary, goal, history, ai_provider)
            result = execute_action(driver, action)

            status_callback(f"Executed: {action}", 10 + (step * 4) + 2)

            history += f"\nAction: {action}\nResult: {result}"

            if action.lower().strip() == "done":
                break

            #delay for APIs rate limits
            time.sleep(2)

            if driver.current_url.endswith(".pdf"):
                break

        status_callback("Extracting PDF text…", 70)
        pdf_text = extract_text_directly_from_browser(driver)

        status_callback(f"Generating {action_type}…", 85)
        if action_type == "summary":
            prompt = f"Please summarise the key points from this PDF:\n\n{pdf_text}."
            ai_result = ask_ai(prompt, ai_provider)
            result_content = {"summary": ai_result}

        elif action_type == "flashcards":
            prompt = (
                f"Extract and create exactly 5 flashcards, in English, from the following PDF content. "
                f"Each flashcard should be a JSON array containing two elements: the question and the answer, like this: "
                f"[\"question\":\"What is X?\", \"answer\":\"X is Y.\"].\n\n"
                f"Return only a JSON list of 5 such flashcards, with no additional explanation or text. "
                f"Use clear, concise language suitable for studying.\n\n"
                f"PDF content:\n{pdf_text}"
            )
            ai_output = ask_ai(prompt, ai_provider)
            result_content = {"flashcards": json.loads(ai_output)}
            #print(result_content)
        else:
            prompt = (
                f"Generate a 5-question multiple-choice quiz in English based on the following PDF content.\n\n"
                f"Output the quiz as a JSON with this format:\n\n"
                f"[{{\n"
                f"  'question': \"What is the question text?\",\n"
                f"  'options': {{\n"
                f"    'A': \"Option A text\",\n"
                f"    'B': \"Option B text\",\n"
                f"    'C': \"Option C text\",\n"
                f"    'D': \"Option D text\"\n"
                f"  }},\n"
                f"  'answer': \"B\"\n"
                f"}}]\n\n"
                f"Make sure the answer is one of 'A', 'B', 'C', or 'D'.\n\n"
                "\nDo not include markdown or explanations. Only return valid JSON."
                f"PDF Content:\n\n{pdf_text}\n"
            )

            ai_output = ask_ai(prompt, ai_provider)
            parsed_output = json.loads(ai_output)
            result_content = {"quiz": parse_quiz(parsed_output)}
            #print(result_content)

        status_callback("Completed", 100)
        return result_content

    finally:
        driver.quit()