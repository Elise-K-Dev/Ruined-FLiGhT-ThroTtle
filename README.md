# Throtle DCS vJoy Controller

<img width="3024" height="4032" alt="KakaoTalk_20260502_031447513" src="https://github.com/user-attachments/assets/70a5641b-a3db-403d-9345-926b888f79fd" />


Arduino Mega based controller bridge for DCS. The Mega reads the physical
controls over serial, and `scripts/mega_to_vjoy.py` maps them to vJoy.

## Current Hardware Wiring

### Main Joysticks and Switches

| Control | Arduino Pin | Use |
| --- | --- | --- |
| Throttle joystick X | A1 | vJoy buttons 7/8 |
| Throttle joystick Y | A0 | Incremental throttle value |
| Second joystick X | A2 | vJoy X axis |
| Second joystick Y | A3 | vJoy Y axis |
| Joystick SW1 | D13 | vJoy button 1 |
| Joystick SW2 | D12 | vJoy button 2 |
| Mode toggle | D11 | vJoy button 3 and enables throttle left/right |

### KY-040 Rotary Encoder

| KY-040 Pin | Arduino Pin |
| --- | --- |
| CLK | D2 |
| DT | D3 |
| SW | D10 |
| + | 5V |
| GND | GND |

The encoder uses D2/D3 interrupts. Do not move CLK/DT back to D8/D9 unless the
firmware is changed too.

Optional external pullups:

```text
5V -- 10k -- CLK
5V -- 10k -- DT
```

## vJoy Mapping

| vJoy Control | Source |
| --- | --- |
| X axis | Second joystick X |
| Y axis | Second joystick Y |
| Slider 0 | Incremental throttle |
| Button 1 | SW1 |
| Button 2 | SW2 |
| Button 3 | Mode toggle |
| Button 4 | Encoder direction 1 |
| Button 5 | Encoder direction 2 |
| Button 6 | Encoder push |
| Button 7 | Throttle joystick left |
| Button 8 | Throttle joystick right |

## Daily Use

For normal use, open the tuner and choose the current COM port:

[VJoyTuner.exe](VJoyTuner.exe)

Use `Joystick On`, `Joystick Off`, `Reset Joystick`, and `Restart Bridge` from
that window. The selected COM port, baud rate, and vJoy device ID are saved in
`scripts\vjoy_settings.json`.

You can also start or restart the bridge with these scripts:

```powershell
scripts\stop-vjoy-bridge.ps1
scripts\start-vjoy-bridge.ps1
```

`start-vjoy-bridge.ps1` uses the saved tuner connection settings by default.

Bridge logs are written to:

```text
vjoy-bridge.out.log
vjoy-bridge.err.log
```

## Tuning UI

Open the tuner with:

```powershell
VJoyTuner.exe
```

The tuner edits:

[scripts/vjoy_settings.json](scripts/vjoy_settings.json)

Available controls:

| Setting | Meaning |
| --- | --- |
| X axis speed | vJoy X axis follow speed. High value means near-instant response. |
| Y axis speed | vJoy Y axis follow speed. High value means near-instant response. |
| Encoder pulse | How long buttons 4/5 are held per encoder event. |
| Encoder cooldown | Minimum gap between encoder button events. |
| Opposite lockout | Short block for opposite-direction encoder bounce. |

The bridge reloads this JSON live, so most tuning changes do not need a restart.

## Arduino Firmware

Active firmware:

[JoystickBasic/JoystickBasic.ino](JoystickBasic/JoystickBasic.ino)

Compile:

```powershell
.\.tools\arduino-cli.exe compile --fqbn arduino:avr:mega JoystickBasic
```

Upload:

```powershell
.\.tools\arduino-cli.exe upload -p COM5 --fqbn arduino:avr:mega JoystickBasic
```

If upload fails because COM5 is busy, stop the bridge first:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop-vjoy-bridge.ps1
```

## DCS F-16 Notes

Recommended bindings:

| Hardware | Suggested DCS Use |
| --- | --- |
| Second joystick X/Y | HOTAS Cursor Slew Horizontal/Vertical |
| Encoder directions | Increment/decrement style controls such as HUD/HMCS/MFD brightness, CRS/HDG, range, or similar |
| Encoder push | Cursor enable, reset, or mode action |
| Throttle left/right buttons 7/8 | Mode-gated helper buttons, for example DMS left/right or other HOTAS-style commands |

For TGP use, make the TGP display SOI, then use the same cursor slew/TMS/DMS
controls. TGP and radar share HOTAS controls depending on which display/sensor
is SOI.

## Troubleshooting

### Encoder Does Not Respond

Check that KY-040 is wired:

```text
CLK -> D2
DT  -> D3
SW  -> D10
+   -> 5V
GND -> GND
```

D2/D3 are intentional because they support interrupts on the Mega.

### Upload Cannot Open COM5

Stop the bridge, unplug/replug the Mega, then check:

```powershell
.\.tools\arduino-cli.exe board list
```

If the port changes, upload with the new COM port.

### Axis Feels Delayed

Open the tuner and raise X/Y axis speed. A very high value, such as `10000`,
effectively disables the follow-speed delay.

### Encoder Double Inputs or Reverse Bounce

Use the tuner:

- Increase `Encoder cooldown` to reduce repeated inputs.
- Increase `Opposite lockout` to suppress brief reverse-direction bounce.
- Decrease them if the encoder feels too sluggish.
