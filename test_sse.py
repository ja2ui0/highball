#!/usr/bin/env python3
"""Test SSE formatting"""

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI()

@app.get("/test-sse")
async def test_sse():
    async def event_generator():
        # Test simple HTML
        simple_html = "<div>Simple test</div>"
        yield f"event: test\ndata: {simple_html}\n\n"
        
        # Test complex HTML with newlines
        complex_html = """<div class="alert alert-error" id="test">
    <strong>Test</strong><br>
    <div class="code-container">Multi line content</div>
</div>"""
        # Clean the HTML
        cleaned_html = ' '.join(complex_html.split())
        yield f"event: complex\ndata: {cleaned_html}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8088)