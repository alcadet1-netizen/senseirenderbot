import asyncio
import sys
import os

# Add project root to python path
sys.path.append(os.getcwd())

from src.core.providers import AIProviderFactory
from src.core.config import settings

async def verify_max_tokens_fix():
    print("Verifying AIProviderFactory.generate_text fix...")
    
    # Initialize factory
    factory = AIProviderFactory(settings)
    
    try:
        # Check if generate_text accepts max_tokens argument
        import inspect
        sig = inspect.signature(factory.generate_text)
        if 'max_tokens' in sig.parameters:
            print("SUCCESS: generate_text accepts 'max_tokens' argument.")
        else:
            print("FAILURE: generate_text DOES NOT accept 'max_tokens' argument.")
            
    except Exception as e:
        print(f"FAILURE: Unexpected exception: {e}")

if __name__ == "__main__":
    asyncio.run(verify_max_tokens_fix())
