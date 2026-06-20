# AI Study Buddy - AI-Powered Study Assistant

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.8%2B-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License MIT">
  <img src="https://img.shields.io/badge/Status-Active-success.svg" alt="Status Active">
</p>

**AI Study Buddy** is an intelligent study assistant that works as a WeChat (or Telegram) bot. Students simply snap a photo of a problem — the AI recognizes the text, explains it step by step, and generates similar practice questions for reinforcement.

---

## Features

- **📸 Photo-to-Explanation** — Take a picture of any problem (math, physics, chemistry, etc.) and get a full step-by-step breakdown.
- **🧠 Step-by-Step Explanations** — The AI walks you through the solution one logical step at a time, not just the final answer.
- **📝 Similar Problem Generation** — After explaining, the bot generates 3+ similar problems with answers so you can practice what you just learned.
- **❌ Wrong Answer Tracking** — Incorrect responses are logged and can be reviewed later to identify weak areas.
- **📚 Multi-Subject Support** — Works with math, physics, chemistry, biology, economics, and more.
- **🔌 WeChat / Telegram Bot** — Drop-in integration with popular messaging platforms.

---

## Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/ai-study-buddy.git
cd ai-study-buddy
pip install -r requirements.txt
pip install -e .
```

### 2. Configure

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

Edit `.env`:

```ini
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-chat
WECHAT_BOT_TOKEN=your_wechat_bot_token
```

### 3. Run the Bot

```bash
study-buddy
```

Or directly:

```bash
python -m study_buddy
```

---

## Configuration

| Variable | Description | Required |
|---|---|---|
| `DEEPSEEK_API_KEY` | API key for DeepSeek (or OpenAI-compatible service) | ✅ Yes |
| `DEEPSEEK_BASE_URL` | Base URL for the API (default: `https://api.deepseek.com/v1`) | ❌ No |
| `MODEL_NAME` | Model to use (default: `deepseek-chat`) | ❌ No |
| `WECHAT_BOT_TOKEN` | Token for WeChat bot integration | ✅ Yes |
| `DATABASE_PATH` | Path to SQLite database file (default: `study_buddy.db`) | ❌ No |

---

## Usage Examples

### Send a problem photo via WeChat

```
User:   [sends photo of quadratic equation: x² - 5x + 6 = 0]

Bot:    📐 **Analysis:**
        This is a quadratic equation in the form ax² + bx + c = 0.

        📝 **Step 1:** Identify coefficients
        a = 1, b = -5, c = 6

        📝 **Step 2:** Apply the quadratic formula
        x = [-b ± √(b² - 4ac)] / (2a)

        📝 **Step 3:** Substitute values
        x = [5 ± √(25 - 24)] / 2
        x = [5 ± √1] / 2

        📝 **Step 4:** Solve
        x₁ = (5 + 1) / 2 = 3
        x₂ = (5 - 1) / 2 = 2

        ✨ **Answer:** x = 3 or x = 2

        🎯 **Practice Problems:**
        1. x² - 7x + 12 = 0  →  x = 3, x = 4
        2. 2x² + 5x - 3 = 0  →  x = 1/2, x = -3
        3. x² + 6x + 9 = 0   →  x = -3 (double root)
```

### Send a text question

```
User:   Explain the Pythagorean theorem

Bot:    📐 **Pythagorean Theorem:**
        In a right-angled triangle, the square of the hypotenuse equals
        the sum of squares of the other two sides.

        Formula: a² + b² = c²
        ...
```

---

## Project Structure

```
ai-study-buddy/
├── study_buddy/
│   ├── __init__.py          # Package init, version
│   ├── __main__.py          # Entry point
│   ├── bot.py               # WeChat message handler
│   ├── solver.py            # Core AI logic (DeepSeek API)
│   ├── config.py            # Configuration loader
│   └── db.py                # SQLite database layer
├── setup.py                 # Package setup / console entry point
├── requirements.txt         # Python dependencies
├── .gitignore               # Git ignore rules
├── LICENSE                  # MIT License
└── README.md                # This file
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

<p align="center">Built with ❤️ for students everywhere</p>
