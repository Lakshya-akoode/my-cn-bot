# My CN Bot

## Prerequisites
- Python 3.9+
- Python Virtual Environment

## Setup

1. **Create a virtual environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Environment Variables:**
   - Ensure a `.env` file exists in the root directory.
   - Required variables:
     ```env
     GOOGLE_API_KEY=your_api_key
     ```

## Running the Application

### 1. Start the Backend
Run the following command from the project root:
```bash
cd backend
../venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
The backend will run on `http://localhost:8000`.

### 2. Start the Frontend
Open a new terminal and run:
```bash
python3 -m http.server 3000 --directory frontend
```
The frontend will be available at `http://localhost:3000`.
