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

### Handover Strategy

1. `HandoverTest.py`: best-elevation
2. `HandoverDis.py`: best-distance
3. `HandoverDisPingPong.py`: best-distance with Ping-Pong
4. `HandoverTest2.py`: elevation
5. force handover
6. `HandoverServiceSimple.py`: service time

### BHO Strategy

1. Elevation
`python3 HandoverForced.py --strategy elevation`

2. Distance
`python3 HandoverForced.py --strategy distance`

3. Servie Time
`python3 HandoverForced.py --strategy time`