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

# 2. (optional) convert CSV to CZML with the simpler converter
python3 ConverCsv.py

# 3. run the handover simulation log
python3 HandoverTest.py

# 4. generate handover visualization CZML (runs the HO algorithm & writes output/handover_viz.czml)
python3 HandoverViz.py

# 5. serve the workspace and open the viewer
python3 -m http.server 8000
# then open http://localhost:8000/index.html in your browser
```

### BHO Strategy

```
# Elevation
python3 HandoverForced.py --strategy elevation

# Distance
python3 HandoverForced.py --strategy distance

# Servie Time
python3 HandoverForced.py --strategy time
```

### Handover Strategy

| Name         | File                     | Description                                          | Output File |
|--------------|--------------------------|------------------------------------------------------|-------------|
| Elevation5   | HandoverTest.py          | HO if T-gNB > S-gNB 5°                               | 1.txt       |
| Distance     | HandoverDis.py           | HO if T-gNB > S-gNB 50.0km (satellite to UE)         | 2.txt       |
| PingPong     | HandoverDisPingPong.py   | HO if T-gNB > S-gNB 50.0km and no Ping-Pong in 120s  | 3.txt       |
| Elevation30  | HandoverTest2.py         | HO if T-gNB > S-gNB 30°                              | 4.txt       |
| BHO          | HandoverTest2.py         | HO if S-gNB cannot serve UE                          | 5.txt       |
| Service Time | HandoverServiceSimple.py | HO if T-gNB's serving time > S-gMB's 120s            | 6.txt       |
