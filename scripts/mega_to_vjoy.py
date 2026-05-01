import argparse
import json
from pathlib import Path
import re
import sys
import time

import pyvjoy
import serial


LINE_RE = re.compile(
    r"(?:TX:\s*(-?\d+).*?)?"
    r"THROTTLE:\s*(-?\d+).*?"
    r"X2:\s*(-?\d+).*?"
    r"Y2:\s*(-?\d+).*?"
    r"SW1:\s*(\d+).*?"
    r"SW2:\s*(\d+).*?"
    r"TOGGLE:\s*(\d+).*?"
    r"TLEFT:\s*(\d+).*?"
    r"TRIGHT:\s*(\d+).*?"
    r"ENC:\s*(-?\d+).*?"
    r"ENCSW:\s*(\d+)"
)

VJOY_MIN = 1
VJOY_MAX = 32768
SETTINGS_PATH = Path(__file__).resolve().with_name("vjoy_settings.json")
DEFAULT_SETTINGS = {
    "x_axis_slew_rate_per_second": 145.0,
    "y_axis_slew_rate_per_second": 145.0,
    "encoder_pulse_seconds": 0.025,
    "encoder_cooldown_seconds": 0.03,
    "encoder_opposite_lockout_seconds": 0.06,
}
settings = DEFAULT_SETTINGS.copy()
settings_mtime = None
current_x_axis = 0.0
current_y_axis = 0.0
last_axis_update_time = None
encoder_button_4_until = 0.0
encoder_button_5_until = 0.0
encoder_ignore_until = 0.0
encoder_last_direction = 0
encoder_opposite_lockout_until = 0.0


def clamp(value, low, high):
    return max(low, min(high, value))


def load_settings(force=False):
    global settings, settings_mtime

    try:
        mtime = SETTINGS_PATH.stat().st_mtime
    except FileNotFoundError:
        if force:
            settings = DEFAULT_SETTINGS.copy()
        return

    if not force and settings_mtime == mtime:
        return

    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as settings_file:
            loaded = json.load(settings_file)
    except (OSError, json.JSONDecodeError):
        return

    merged = DEFAULT_SETTINGS.copy()
    for key, default_value in DEFAULT_SETTINGS.items():
        try:
            merged[key] = float(loaded.get(key, default_value))
        except (TypeError, ValueError):
            merged[key] = default_value

    settings = merged
    settings_mtime = mtime


def signed_axis_to_vjoy(value):
    value = clamp(int(value), -100, 100)
    return int((value + 100) * (VJOY_MAX - VJOY_MIN) / 200 + VJOY_MIN)


def slew_signed_axis(current, target, elapsed_seconds, slew_rate):
    target = clamp(float(target), -100.0, 100.0)
    max_delta = max(0.0, float(slew_rate)) * elapsed_seconds
    delta = target - current
    if delta > max_delta:
        return current + max_delta
    if delta < -max_delta:
        return current - max_delta
    return target


def percent_axis_to_vjoy(value):
    value = clamp(int(value), 0, 100)
    return int(value * (VJOY_MAX - VJOY_MIN) / 100 + VJOY_MIN)


def parse_line(line):
    match = LINE_RE.search(line)
    if not match:
        return None

    tx, throttle, x2, y2, sw1, sw2, toggle, tleft, tright, enc, encsw = match.groups()
    return {
        "tx": int(tx) if tx is not None else 0,
        "throttle": int(throttle),
        "x2": int(x2),
        "y2": int(y2),
        "sw1": int(sw1),
        "sw2": int(sw2),
        "toggle": int(toggle),
        "tleft": int(tleft),
        "tright": int(tright),
        "enc": int(enc),
        "encsw": int(encsw),
    }


def apply_to_vjoy(joystick, state):
    global current_x_axis, current_y_axis, last_axis_update_time
    global encoder_button_4_until, encoder_button_5_until, encoder_ignore_until
    global encoder_last_direction, encoder_opposite_lockout_until

    load_settings()

    now = time.monotonic()
    elapsed_seconds = 0.02 if last_axis_update_time is None else now - last_axis_update_time
    last_axis_update_time = now

    current_x_axis = slew_signed_axis(
        current_x_axis,
        -state["x2"],
        elapsed_seconds,
        settings["x_axis_slew_rate_per_second"],
    )
    current_y_axis = slew_signed_axis(
        current_y_axis,
        -state["y2"],
        elapsed_seconds,
        settings["y_axis_slew_rate_per_second"],
    )
    joystick.set_axis(pyvjoy.HID_USAGE_X, signed_axis_to_vjoy(current_x_axis))
    joystick.set_axis(pyvjoy.HID_USAGE_Y, signed_axis_to_vjoy(current_y_axis))
    joystick.set_axis(pyvjoy.HID_USAGE_SL0, percent_axis_to_vjoy(state["throttle"]))

    enc_direction = 1 if state["enc"] > 0 else -1 if state["enc"] < 0 else 0
    if (
        enc_direction != 0
        and now >= encoder_ignore_until
        and not (
            enc_direction != encoder_last_direction
            and now < encoder_opposite_lockout_until
        )
    ):
        if enc_direction > 0:
            encoder_button_4_until = now + settings["encoder_pulse_seconds"]
        else:
            encoder_button_5_until = now + settings["encoder_pulse_seconds"]
        encoder_ignore_until = now + settings["encoder_cooldown_seconds"]
        encoder_last_direction = enc_direction
        encoder_opposite_lockout_until = now + settings["encoder_opposite_lockout_seconds"]

    joystick.set_button(1, 1 if state["sw1"] == 0 else 0)
    joystick.set_button(2, 1 if state["sw2"] == 0 else 0)
    joystick.set_button(3, 1 if state["toggle"] != 0 else 0)
    joystick.set_button(4, 1 if now < encoder_button_4_until else 0)
    joystick.set_button(5, 1 if now < encoder_button_5_until else 0)
    joystick.set_button(6, 1 if state["encsw"] == 0 else 0)
    joystick.set_button(7, 1 if state["tx"] < 0 else 0)
    joystick.set_button(8, 1 if state["tx"] > 0 else 0)


def main():
    parser = argparse.ArgumentParser(description="Bridge Arduino Mega serial output to vJoy.")
    parser.add_argument("--port", default="COM5")
    parser.add_argument("--baud", type=int, default=19200)
    parser.add_argument("--device", type=int, default=1)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()
    load_settings(force=True)

    joystick = pyvjoy.VJoyDevice(args.device)
    joystick.reset()

    if not args.quiet:
        print(f"vJoy device {args.device} opened")
        print(f"Opening {args.port} at {args.baud} baud...")

    with serial.Serial(args.port, args.baud, timeout=1) as ser:
        ser.dtr = False
        ser.rts = False
        last_print = 0.0

        while True:
            raw_line = ser.readline()
            if not raw_line:
                continue

            line = raw_line.decode("utf-8", errors="ignore").strip()
            state = parse_line(line)
            if state is None:
                continue

            apply_to_vjoy(joystick, state)

            now = time.monotonic()
            if not args.quiet and now - last_print >= 0.5:
                last_print = now
                print(
                    "THROTTLE={throttle:3d} X2={x2:4d} Y2={y2:4d} "
                    "Z/TX={tx:4d} "
                    "BTN1/SW1={sw1} BTN2/SW2={sw2} BTN3/TOGGLE={toggle} "
                    "BTN7/TLEFT={tleft} BTN8/TRIGHT={tright} "
                    "ENC={enc} BTN6/ENCSW={encsw}".format(**state)
                )


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
