@app.get("/", response_class=HTMLResponse)
async def root():
    return FileResponse("frontend/questions.html")