# Viiz Data Agent

An agentic data analysis workflow that accepts multiple CSV and Excel files, merges related tables, and generates chart recommendations on the frontend.

## Features

- Upload multiple CSV or Excel files
- Detect table schema and infer relationships
- Merge tables using matching keys such as ids or shared names
- Generate chart suggestions from user prompts
- If no prompt is provided, it can automatically generate useful insights across the merged dataset
- Angular frontend for the user experience
- FastAPI backend for file processing and chart spec generation

## Stack

- Frontend: Angular
- Backend: FastAPI + Pandas + OpenPyXL

## Run locally

1. Install Python dependencies:

   python3 -m pip install -r requirements.txt

2. Install frontend dependencies:

   cd frontend && npm install

3. Start the backend:

   cd /Users/sagar/Projects/Viiz && uvicorn backend.main:app --host 0.0.0.0 --port 8000

4. Start the frontend:

   cd /Users/sagar/Projects/Viiz/frontend && npm start -- --host 0.0.0.0 --port 4200

5. Open:

   http://localhost:4200/

## Notes

- The backend automatically merges rows when tables share logical join keys such as customer_id, order_id, or matching column names.
- If the prompt is empty and the checkbox is enabled, the app tries to generate the most useful aggregate charts from the combined dataset.
- The frontend expects the backend at http://localhost:8000.
