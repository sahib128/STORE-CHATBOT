from langchain_ollama import OllamaLLM

DEFAULT_MODEL_NAME = "llama3.1"

def load_default_model():
    """
    Load the default model when the app starts.
    """
    try:
        model = OllamaLLM(model=DEFAULT_MODEL_NAME)
        print(f"✅ Default model '{DEFAULT_MODEL_NAME}' loaded successfully.")
        return model
    except Exception as e:
        print(f"❌ Failed to load default model '{DEFAULT_MODEL_NAME}': {e}")
        raise
