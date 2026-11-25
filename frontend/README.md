# AI Organization web app

From the repository root, install the backend packages into the existing virtual environment and install the frontend packages:

```powershell
.\venv\Scripts\python.exe -m pip install -r .\backend\requirements.txt
Set-Location .\frontend
if (-not (Test-Path .env.local)) { Copy-Item .env.example .env.local }
npm install
Set-Location ..
.\start.ps1
```

The local API listens on `127.0.0.1:8000`; Next.js is available at `http://localhost:3000`. To run either service separately, use:

```powershell
.\venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Run the API command from the repository root. In another terminal, run `npm run dev` from `frontend/`.

The web backend copies the existing Chroma data into `backend/data/chroma/` on first start. Web uploads and RAG updates use that copy, leaving the frozen `memory/chroma/` data untouched.
