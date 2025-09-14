# MOODLEAGENT  
*Empowering Smarter Learning Through AI*  

![last-commit](https://img.shields.io/github/last-commit/ShadowsAdi/MoodleAgent?style=flat&logo=git&logoColor=white&color=0080ff)  ![repo-top-language](https://img.shields.io/github/languages/top/ShadowsAdi/MoodleAgent?style=flat&color=0080ff)  ![repo-language-count](https://img.shields.io/github/languages/count/ShadowsAdi/MoodleAgent?style=flat&color=0080ff)  

*Built with the tools and technologies:*  
![Flask](https://img.shields.io/badge/Flask-000000.svg?style=flat&logo=Flask&logoColor=white)  ![Selenium](https://img.shields.io/badge/Selenium-43B02A.svg?style=flat&logo=Selenium&logoColor=white)  ![Python](https://img.shields.io/badge/Python-3776AB.svg?style=flat&logo=Python&logoColor=white)  ![OpenAI](https://img.shields.io/badge/OpenAI-412991.svg?style=flat&logo=OpenAI&logoColor=white) ![Ollama](https://img.shields.io/badge/ollama-2F80ED?style=flat&logo=ollama&logoColor=white)  ![Google Gemini](https://img.shields.io/badge/Google%20Gemini-8E75B2.svg?style=flat&logo=Google-Gemini&logoColor=white)  

## Overview  
MoodleAgent is an all-in-one automation tool designed to streamline educational content management within Moodle. It leverages web automation, PDF processing, and AI-driven analysis to facilitate data extraction, document summarizing, and interactive flash-cards.  

**What is MoodleAgent?**  
This project simplifies workflows by integrating multiple tools for web scraping, PDF content extraction, OTP management, and AI interactions.  

The core features include:  
- **🔍 Web & PDF Automation:** Automates navigation and content extraction from Moodle courses, including PDF text processing.  
- **🧠 AI Content Analysis:** Generates summaries, flashcards, and quizzes using multiple AI providers for flexible insights.  
- **🎛️ User Interface:** Provides an intuitive web interface for configuring tasks, monitoring progress, and reviewing results.  
- **🔑 OTP Migration:** Facilitates secure transfer of 2FA secrets, enhancing authentication management.  
- **⚙️ Environment Management:** Ensures all dependencies are installed for scalable, robust functionality across the project.  

---

## Getting Started  

### Prerequisites  
- Python 3.12 
- `pip`  
- Internet access (for Moodle + AI APIs)  
- Appropriate Moodle credentials (user, password; possibly permission to download course resources)  
- API keys / credentials for AI provider(s) you intend to use  

### Installation  

```bash
git clone https://github.com/ShadowsAdi/MoodleAgent.git
cd MoodleAgent
pip install -r requirements.txt
```

### Configuration  

1. Copy `.env.example` to `.env`  
2. Fill in necessary environment variables:  
   - Moodle login credentials (URL, username, password, OTP secret if needed)  
   - AI API key(s)  

### Running the Application  

```bash
python app.py
```

- Access the web UI (default: `http://127.0.0.1:8000`)  
- From UI, configure tasks (e.g. which Moodle course(s), what content to extract), trigger or schedule them.  

---

## Usage 

Here are a few example workflows:

- **Generate flashcards from PDF lectures**:  
  1. Give MoodleAgent the name of course folder.  
  2. It searches for lecture's PDF, extracts text.  
  3. Uses AI to create flashcards automatically or generate a quiz.

- **Summarize a course module**:  
  Extract all lesson pages + PDFs, produce a summary document (or set of summaries per section) to help students review.

- **Backup / migrate 2FA secrets**:  
  Use the OTP secret extractor to export or migrate OTP secrets safely. See [Google Authenticator Exporter](https://github.com/yehudah/google-authenticator-exporter)

---

## MoodleAgent REST API Usage  

The Flask app exposes several REST endpoints that external systems can call to trigger automations, check progress, and retrieve results.  

---

### 🔹 1. Start Automation  
**Endpoint:**  
```
POST /start_automation
```

**Description:**  
Starts a new Moodle automation task (summary, flashcards, or quiz generation).  

**Request Parameters (form-data / x-www-form-urlencoded):**

| Parameter      | Type   | Required | Description |
|----------------|--------|----------|-------------|
| `course_name`  | string | ✅ Yes   | Name of the Moodle course |
| `subject_name` | string | ✅ Yes   | Name of the subject within the course |
| `action_type`  | string | ❌ No    | Task type: `"summary"`, `"flashcards"`, `"quiz"` (default: `"summary"`) |
| `ai_provider`  | string | ❌ No    | AI backend: `"google"` or `"openai"` (default: `"google"`) |

**Example Request (cURL):**
```bash
curl -X POST http://localhost:8000/start_automation   -d "course_name=Computer Science"   -d "subject_name=AI Fundamentals"   -d "action_type=summary"   -d "ai_provider=openai"
```

**Example Response:**
```json
{
  "message": "Started successfully"
}
```

---

### 🔹 2. Get Task Status  
**Endpoint:**  
```
GET /status
```

**Description:**  
Returns the current state of the running (or last) automation task.  

**Example Request:**
```bash
curl http://localhost:8000/status
```

**Example Response:**
```json
{
  "running": true,
  "progress": 35,
  "message": "Extracting PDF content...",
  "result": null,
  "error": null,
  "action_type": "summary"
}
```

---

### 🔹 3. Get Task Result  
**Endpoint:**  
```
GET /result
```

**Description:**  
Fetches the result of the last task.  
- For `summary` → returns HTML rendered summary  
- For `flashcards` or `quiz` → returns JSON content  
- If no result yet, redirects to `/`  

**Example Request:**
```bash
curl http://localhost:8000/result
```

*(Note: This returns rendered HTML — better accessed via browser or embedded in another system.)*

---

### 🔹 4. Reset Task State  
**Endpoint:**  
```
POST /reset
```

**Description:**  
Resets the internal task state (useful for starting fresh).  

**Example Request:**
```bash
curl -X POST http://localhost:8000/reset
```

**Example Response:**
```json
{
  "message": "Data reset successfully"
}
```

---

## Typical Workflow  

1. **Trigger a task** → `POST /start_automation`  
2. **Poll for progress every seconnd** → `GET /status`  
3. **Retrieve result** → `GET /result`  
4. **(Optional) Reset state** → `POST /reset`  

---

## TO DOs

1. **Improve Agent's Memory**  
   - Implement a more persistent memory layer (e.g., vector database or file-based context).  
   - Enable contextual recall across multiple runs.  

2. **Switch to Ollama's Python API**  
   - Replace direct OpenAI calls with Ollama’s Python API.  

3. **Enhance Agentic Capabilities**  
   - Add more tools (web search, file operations, scheduling).  
   - Support flexible tool orchestration (planning + execution).  

4. **Extend REST API**  
   - Add endpoints for managing tasks, retrieving logs, and exporting results (JSON/PDF).  
   - Provide authentication (API keys, JWT, etc).

5. **Deliver a Docker Image**  
   - Create a production-ready Dockerfile.  
   - Publish prebuilt images to Docker Hub.  

6. **Maybe Switching to LangChain**  
   - Compare current architecture with LangChain’s agents & memory.  
   - Prototype a LangChain integration for multi-tool workflows.  

---

