import json
import requests
import ftfy

# Возможно в будущем будет вынесено в настройки
proxies = {
    'http': None,
    'https': None,
}

def tune_llm(api_provider: str, api_url: str, headers: str, workspace: str, tune: str, temperature: float) -> bool:
    if api_provider == "ALLM":
        data = {
            "name": f"{workspace}",
            "openAiTemp": temperature,
            "openAiPrompt": f"{tune}"
        }
        tune_ai = requests.post(f"{api_url}/workspace/{workspace}/update", headers=headers, data=json.dumps(data), proxies=proxies)
        if tune_ai.status_code == 200:
            return True
        else:
            print(f"[FAIL] Tune {workspace}: {tune_ai.status_code}")
            return False
    else:
        return True

def translate_allm(api_url: str, headers: str, workspace: str, thread: str, text: str) -> None:
    create_thread = requests.post(f"{api_url}/workspace/{workspace}/thread/new", headers=headers, data=json.dumps({"userId": 1, "name": f"{thread}", "slug": f"{thread}"}), proxies=proxies)
    if create_thread.status_code == 200:
        request = requests.post(f"{api_url}/workspace/{workspace}/thread/{thread}/chat", headers=headers, data=json.dumps({'mode': 'chat', 'message': f"{text}"}), proxies=proxies)
        request.encoding = 'utf-8'
        if request.status_code == 200:
            response = request.json()['textResponse'].strip()
        else:
            response = f"[TRANSLATIONFAIL]при переводе получен код {request.status_code}"
        requests.delete(f"{api_url}/workspace/{workspace}/thread/{thread}", headers=headers, proxies=proxies)
    else:
        response = f"[TRANSLATIONFAIL]при создании треда получен код {create_thread.status_code}"
    return ftfy.fix_text(response)

def translate_openai(api_url: str, headers: str, system: str, model: str, temperature: float, text: str) -> None:
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": text},
    ]
    data = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    request = requests.post(f"{api_url}/chat/completions", headers=headers, json=data)
    request.encoding = 'utf-8'
    if request.status_code == 200:
        result = request.json()
        if "choices" in result:
            response = result["choices"][0]["message"]["content"].strip()
        else:
            response = f"[TRANSLATIONFAIL]при переводе получен пустой ответ"
    else:
        response = f"[TRANSLATIONFAIL]при переводе получен код {request.status_code}"
    return ftfy.fix_text(response)