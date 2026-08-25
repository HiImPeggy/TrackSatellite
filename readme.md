# Handover Strategy with Skyfield

### Create Environment

```
# create and activate a venv
python3 -m venv .venv
source .venv/bin/activate

# install requirements
pip install -r requirements.txt
```

### Run Simulation

```
# 1. generate satellite visibility CSV
python3 SatTrack.py

# 5. serve the workspace and open the viewer
python3 -m http.server 8000
# then open http://localhost:8000/index.html in your browser
```
