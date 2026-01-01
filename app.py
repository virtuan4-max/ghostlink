from flask import Flask, render_template, request, jsonify, session
from groq import Groq
import os
import base64
import json
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- CONFIGURATION ---
# Set your desired backend password here
BACKEND_PASSWORD = "hi"

DEFAULT_MODEL = "llama-3.1-8b-instant" 
VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"  #this is the current vision gorq supported model. Any other vision 3.2 is depracated.
DEFAULT_SYSTEM_PROMPT = "You are GhostLink, a helpful, advanced and minimal AI."
MAX_HISTORY_WINDOW = 4

def encode_image(file):
    return base64.b64encode(file.read()).decode('utf-8')

def trim_history(history, max_messages=MAX_HISTORY_WINDOW):
    if len(history) <= max_messages + 1:
        return history
    return [history[0]] + history[-max_messages:]

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/ask', methods=['POST'])
def ask():
    # 1. PASSWORD CHECK
    user_pass = request.form.get("password")
    if user_pass != BACKEND_PASSWORD:
        return jsonify({"response": "ERROR: Invalid Backend Password."}), 401

    # 2. UPLOADED API KEY CHECK
    user_api_key = request.form.get("api_key")
    if not user_api_key:
        return jsonify({"response": "ERROR: No Groq API Key provided."}), 400

    # Initialize client with the key uploaded from the frontend
    client = Groq(api_key=user_api_key)

    user_query = request.form.get("message", "")
    word_count = len(user_query.split())
    
    if word_count > 1000:
        return jsonify({
            "response": f"Error: Message too long ({word_count} words).",
            "tokens": {"prompt": 0, "completion": 0, "total": 0}
        }), 400

    history_json = request.form.get("history")
    if history_json:
        history = json.loads(history_json)
    else:
        history = [{"role": "system", "content": DEFAULT_SYSTEM_PROMPT}]
    
    sys_prompt = request.form.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
    temp = float(request.form.get("temperature", 0.7))
    selected_model = request.form.get("model", DEFAULT_MODEL)
    
    image_files = []
    for key in request.files:
        if key.startswith("image"):
            image_files.extend(request.files.getlist(key))

    actual_model_to_use = selected_model
    if image_files:
        actual_model_to_use = VISION_MODEL
        content = [{"type": "text", "text": user_query}]
        for img in image_files:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{encode_image(img)}"}
            })
    else:
        content = user_query

    if history and history[0]["role"] == "system":
        history[0]["content"] = sys_prompt
    history = trim_history(history)
    history.append({"role": "user", "content": content})

    try:
        response = client.chat.completions.create(
            model=actual_model_to_use,
            messages=history,
            temperature=temp,
            max_tokens=1024 
        )
        
        bot_text = response.choices[0].message.content
        usage = response.usage
        
        if image_files:
            history[-1]["content"] = f"[Image Analyzed]: {user_query}"

        history.append({"role": "assistant", "content": bot_text})
        updated_history = trim_history(history)

        return jsonify({
            "response": bot_text,
            "tokens": {
                "prompt": usage.prompt_tokens,
                "completion": usage.completion_tokens,
                "total": usage.total_tokens
            },
            "new_history": updated_history 
        })

    except Exception as e:
        return jsonify({"response": f"ERROR: {str(e)}", "tokens": {"prompt": 0, "completion": 0, "total": 0}})

if __name__ == '__main__':
    app.run(debug=True, threaded=True)