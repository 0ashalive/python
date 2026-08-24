from fastapi import FastAPI

app = FastAPI()

@app.route("/")
def read_root():
    return {"Status": "FastAPI running on Vercel"}
  
