# 🤖 Quant Bot: The Playful Question Master

Quant Bot is a highly interactive Discord bot that transforms your server into a custom trivia or "Question of the Day" arena. Unlike standard trivia bots, **Quant Bot** allows you to upload your own question sets, making it perfect for niche communities, study groups, or just sharing inside jokes.

## ✨ Features

* **Custom Question Uploads:** Easily bulk-upload your own questions to build a unique server experience.
* **Playful Personality:** Designed to interact with users using a witty, engaging, and lighthearted tone.
* **On-Demand Engagement:** Users can trigger questions whenever they want to spark conversation.
* **Flexible Formatting:** Supports multiple-choice, true/false, or open-ended playful prompts.
* **Render Ready:** Includes a webserver component for 24/7 uptime on hosting platforms like Render.

## 📥 How it Works

1.  **Prepare your Questions:** Create a question bank (e.g., a `.json` or `.txt` file) with your custom content.
2.  **Upload:** Use the bot's upload command to feed the questions into its database.
3.  **Play:** The bot will then pull from this "Quant Bank" to challenge and entertain your members.

## 🛠️ Installation & Setup

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/Rororova/Quant-Bot.git](https://github.com/Rororova/Quant-Bot.git)
    cd Quant-Bot
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Environment Variables:**
    Create a `.env` file in the root directory and add your Discord token:
    ```env
    TOKEN=your_discord_bot_token_here
    ```

4.  **Run the Bot:**
    ```bash
    python run_bot.py
    ```

## 🌐 Hosting on Render

This bot is equipped with a `webserver.py` file to keep it alive on **Render**.
* **Service Type:** Web Service
* **Build Command:** `pip install -r requirements.txt`
* **Start Command:** `python run_bot.py`

## 🎮 Commands


* `/help` - View the playful help menu.

## 🤝 Contributing

Have a feature idea or a fun personality trait to add? Feel free to fork the repo and submit a pull request!

---
*Created by [Rororova](https://github.com/Rororova)*
