cmd: 
for f in ./track-data/deepracer-race-data/raw_data/tracks/npy/*.npy; do echo -e "\n===\n$f\n==="; python3 deepracer_track_converter_v4.py "$f" --fit-room-width 20 --fit-room-height 24 --room-units ft --room-clearance 0 --rotate-to-fit --minimum-track-width 24 --minimum-track-width-units in --inspect-only; done > file.txt


output:
- reInvent2019_wide_ccw.npy
Scale Factor: 88.5% (0.8849)
Fitted Artwork Size: 4.901 m x 7.315 m
Scaled Lane Width: 36.9 in

- reInvent2019_wide_cw.npy
Scale Factor: 88.5% (0.8849)
Fitted Artwork Size: 4.901 m x 7.315 
mScaled Lane Width: 36.9 in

- reInvent2019_wide.npy
Scale Factor: 88.3% (0.8827)
Fitted Artwork Size: 4.896 m x 7.315 m
Scaled Lane Width: 37.1 in

- reInvent2019_wide_mirrored.npy
Scale Factor: 88.3% (0.8827)
Fitted Artwork Size: 4.896 m x 7.315 m
Scaled Lane Width: 37.1 in

- reinvent_base.npy
Scale Factor: 87.7% (0.8773)
Fitted Artwork Size: 4.903 m x 7.315 m
Scaled Lane Width: 26.3 in

- Mexico_track.npy
Scale Factor: 86.4% (0.8635)
Fitted Artwork Size: 5.845 m x 7.315 m
Scaled Lane Width: 28.5 in

- China_track.npy
Scale Factor: 86.1% (0.8610)
Fitted Artwork Size: 6.096 m x 6.875 m
Scaled Lane Width: 30.3 in

- Tokyo_Training_track.npy
Scale Factor: 85.2% (0.8515)
Fitted Artwork Size: 5.887 m x 7.315 m
Scaled Lane Width: 40.3 in

- Virtual_May19_Train_track.npy
Scale Factor: 84.9% (0.8494)
Fitted Artwork Size: 5.020 m x 7.315 m
Scaled Lane Width: 25.4 in

track that are good per Ronald and Manali:
- Mexico_track.npy
- China_track.npy
- Tokyo_Training_track.npy
- Bowtie_track.npy
