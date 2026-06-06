from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables at the very beginning
load_dotenv()

from routers import analyse_report, reports

app = FastAPI(title="Zero-Cloud Council Prioritization Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(reports.router)
app.include_router(analyse_report.router)

from fastapi.responses import RedirectResponse

@app.get("/")
def read_root():
    # Redirect to the swagger UI automatically
    return RedirectResponse(url="/docs")

@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "Zero-Cloud Prioritization Engine is running locally."}

if __name__ == "__main__":
    import uvicorn
    import os
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)

