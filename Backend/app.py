"""
OutOfBlack - Application entrypoint alias.
Enables running via:
  uvicorn app:app --reload
  python app.py
"""

from main import app

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
