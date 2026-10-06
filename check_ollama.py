"""Check if Ollama is available locally."""
import urllib.request
import json

try:
    req = urllib.request.Request("http://localhost:11434/api/tags")
    with urllib.request.urlopen(req, timeout=3) as resp:
        data = json.loads(resp.read())
        models = data.get("models", [])
        print(f"Ollama running: {len(models)} models")
        for m in models[:5]:
            mdl = m.get("model", "?")
            sz = m.get("size", "?")
            print(f"  {mdl}: {sz}")
except Exception as e:
    print(f"Ollama not available: {type(e).__name__}: {e}")
