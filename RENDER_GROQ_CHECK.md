# How to Verify and Fix Groq API Key in Render

## Issue
The bot is returning a 401 error when calling the Groq API: `❌ Groq error: 401 - {"error":{"message":"Invalid API Key"...}}`

This typically means the `GROQ_API_KEY` environment variable in Render is either:
- Not set
- Set to an incorrect value (placeholder, wrong key, extra whitespace)
- Not updated in the deployed service after being changed

## Steps to Resolve

### 1. Verify the GROQ_API_KEY in Render Dashboard
   - Log in to [Render.com](https://render.com)
   - Select your Sensei bot service
   - Go to the **"Environment"** tab
   - Look for the `GROQ_API_KEY` variable

### 2. Check the Key Value
   - The key should start with `gsk_` (e.g., `gsk_abcdefghijklmnopqrstuvwxyz1234567890`)
   - Ensure there is **no extra whitespace** before or after the key
   - Ensure it is **not** set to a placeholder like `your_groq_key_here` or `sk-or-v1-...`

### 3. If the Key is Incorrect or Missing
   - Update the `GROQ_API_KEY` variable with the correct key
   - **Save Changes**
   - Trigger a **manual deploy** from the "Deploys" tab by clicking "Trigger deploy"
     (This ensures the new environment variable is picked up)

### 4. If the Key Appears Correct
   - Still trigger a **manual deploy** to ensure any cached configuration is refreshed
   - Sometimes Render does not immediately propagate environment variable changes without a redeploy

### 5. Post-Deploy Verification
   - After the deploy completes, check the bot logs for any Groq-related errors
   - Test AI-powered features that use Groq:
     - `/digest` command (in a chat with sufficient messages)
     - `/sensei вопрос <your question>` command
     - Vanga predictions (if enabled)
   - Successful responses indicate the key is now working

## Why This Happens
- Render caches environment variables at deploy time
- Changing the variable in the dashboard does not automatically restart the service
- A manual deploy is required to apply the changes

## Local vs Production
- Your local `.env` file (with `your_groq_key_here`) is for development only
- The deployed bot on Render uses **only** the environment variables set in the Render dashboard
- Never commit real API keys to git - the `.env` file should be in `.gitignore`

## Need Further Help?
If the error persists after verifying the key and redeploying:
1. Double-check the key is valid by testing it directly with Groq's API (if you have access to the key)
2. Ensure there are no other typos in the environment variable name (it must be exactly `GROQ_API_KEY`)
3. Check if the key has been accidentally revoked or regenerated in your Groq account