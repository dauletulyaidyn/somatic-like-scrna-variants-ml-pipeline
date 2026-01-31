# Status Web UI

Run the status server (Flask) on port 5556.

Install Flask (manual)
- `pip install flask`

Run
- `python status/app.py --port 5556`

The UI shows:
- Stage statuses
- Events (start/finish/error)
- Configured inputs/outputs per stage (from config/status_config.json)
- File list with sizes and previews
