"""
DEPRECATED — This module is superseded by services/agent_service.py which uses
LangGraph + tool-calling for higher-quality VLM inference. Kept for reference only.

All endpoints now use agent_service.run() instead of extract_issue_data_from_image().
"""
import os
import json
import base64
import requests

def extract_issue_data_from_image(image_bytes: bytes) -> dict:
    """
    Function using local Ollama API to run inference on the image bytes 
    to extract the issue type, severity, and location.
    """
    api_url = os.environ.get("VLM_API_URL", "http://localhost:11434/api/chat")
    model_name = os.environ.get("VLM_MODEL_NAME", "my-custom-model")
    
    # Encode image to base64
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    prompt = (
        "Analyze this image and identify the issue. Extract the following details: "
        "issue_type (e.g., pothole, graffiti, broken_streetlight, fly_tipping), "
        "severity (integer from 1 to 5), "
        "location (string describing the visible location context, if any), "
        "and description (a short description of the issue). "
        "Respond strictly with a JSON object containing these keys."
    )
    
    payload = {
        "model": model_name,
        "messages": [
            {
                "role": "user",
                "content": prompt,
                "images": [base64_image]
            }
        ],
        "stream": False,
        "format": "json"
    }
    
    try:
        response = requests.post(api_url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()
        
        # The response message content should be a JSON string
        content_str = result.get("message", {}).get("content", "{}")
        
        # Strip potential markdown code blocks
        content_str = content_str.strip()
        if content_str.startswith("```json"):
            content_str = content_str[7:]
        if content_str.startswith("```"):
            content_str = content_str[3:]
        if content_str.endswith("```"):
            content_str = content_str[:-3]
        content_str = content_str.strip()
        
        # Parse the JSON string from the model's response
        data = json.loads(content_str)
        
        # Ensure default values are present in case the model misses them
        return {
            "issue_type": data.get("issue_type", "unknown"),
            "severity": data.get("severity", 1),
            "location": data.get("location", "unknown"),
            "description": data.get("description", "No description provided.")
        }
    except Exception as e:
        print(f"Error communicating with VLM: {e}")
        # Fallback to mock data if inference fails
        import random
        issue_types = ["pothole", "graffiti", "broken_streetlight", "fly_tipping"]
        locations = ["Camden", "Westminster", "Islington", "Hackney", "Southwark", "Lambeth"]
        return {
            "issue_type": random.choice(issue_types),
            "severity": random.randint(1, 5),
            "location": random.choice(locations),
            "description": f"Fallback auto-generated mock description. Error: {e}"
        }
