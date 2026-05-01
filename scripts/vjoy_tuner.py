import json
import os
import subprocess
import sys
import time
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT_DIR = SCRIPT_DIR.parent
SETTINGS_PATH = SCRIPT_DIR / "vjoy_settings.json"
STOP_SCRIPT = SCRIPT_DIR / "stop-vjoy-bridge.ps1"

DEFAULT_SETTINGS = {
    "x_axis_slew_rate_per_second": 145.0,
    "y_axis_slew_rate_per_second": 145.0,
    "encoder_pulse_seconds": 0.025,
    "encoder_cooldown_seconds": 0.03,
    "encoder_opposite_lockout_seconds": 0.06,
    "serial_port": "COM5",
    "baud": 19200,
    "vjoy_device": 1,
}

NUMERIC_SETTINGS = {
    "x_axis_slew_rate_per_second",
    "y_axis_slew_rate_per_second",
    "encoder_pulse_seconds",
    "encoder_cooldown_seconds",
    "encoder_opposite_lockout_seconds",
}

CONTROLS = [
    (
        "x_axis_slew_rate_per_second",
        "X axis speed",
        20.0,
        10000.0,
        "Higher = faster crosshair movement",
        "{:.0f}",
    ),
    (
        "y_axis_slew_rate_per_second",
        "Y axis speed",
        20.0,
        10000.0,
        "Higher = faster crosshair movement",
        "{:.0f}",
    ),
    (
        "encoder_pulse_seconds",
        "Encoder pulse",
        0.005,
        0.08,
        "How long vJoy button 4/5 is held",
        "{:.3f}",
    ),
    (
        "encoder_cooldown_seconds",
        "Encoder cooldown",
        0.01,
        0.20,
        "Minimum gap between encoder button events",
        "{:.3f}",
    ),
    (
        "encoder_opposite_lockout_seconds",
        "Opposite lockout",
        0.00,
        0.30,
        "Blocks short opposite-direction bounce",
        "{:.3f}",
    ),
]


def load_settings():
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as settings_file:
            loaded = json.load(settings_file)
    except (OSError, json.JSONDecodeError):
        loaded = {}

    settings = DEFAULT_SETTINGS.copy()
    for key, default_value in DEFAULT_SETTINGS.items():
        if key not in NUMERIC_SETTINGS:
            value = loaded.get(key, default_value)
            settings[key] = value if value not in (None, "") else default_value
            continue
        try:
            settings[key] = float(loaded.get(key, default_value))
        except (TypeError, ValueError):
            settings[key] = default_value

    try:
        settings["baud"] = int(settings["baud"])
    except (TypeError, ValueError):
        settings["baud"] = DEFAULT_SETTINGS["baud"]

    try:
        settings["vjoy_device"] = int(settings["vjoy_device"])
    except (TypeError, ValueError):
        settings["vjoy_device"] = DEFAULT_SETTINGS["vjoy_device"]

    return settings


def save_settings(settings):
    SETTINGS_PATH.write_text(
        json.dumps(settings, indent=2) + "\n",
        encoding="utf-8",
    )


class TunerApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("vJoy Input Tuner")
        self.resizable(False, False)
        self.settings = load_settings()
        self.variables = {}
        self.value_labels = {}
        self.port_var = tk.StringVar(value=str(self.settings["serial_port"]))
        self.baud_var = tk.StringVar(value=str(self.settings["baud"]))
        self.device_var = tk.StringVar(value=str(self.settings["vjoy_device"]))
        self.link_axes = tk.BooleanVar(value=True)
        self._syncing_axes = False

        self._build_ui()
        self._refresh_ports(select_saved=True)
        self._save()

    def _build_ui(self):
        frame = ttk.Frame(self, padding=14)
        frame.grid(row=0, column=0, sticky="nsew")

        header = ttk.Label(frame, text="vJoy Input Tuner", font=("Segoe UI", 13, "bold"))
        header.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))

        connection = ttk.LabelFrame(frame, text="Connection", padding=10)
        connection.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 10))

        ttk.Label(connection, text="COM port").grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.port_combo = ttk.Combobox(
            connection,
            textvariable=self.port_var,
            width=24,
            state="normal",
            postcommand=self._refresh_ports,
        )
        self.port_combo.grid(row=0, column=1, sticky="ew")
        self.port_combo.bind("<<ComboboxSelected>>", lambda _event: self._save_connection())
        self.port_combo.bind("<FocusOut>", lambda _event: self._save_connection())

        ttk.Button(connection, text="Refresh", command=self._refresh_ports).grid(
            row=0,
            column=2,
            padx=(8, 0),
        )

        ttk.Label(connection, text="Baud").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=(8, 0))
        baud = ttk.Entry(connection, textvariable=self.baud_var, width=10)
        baud.grid(row=1, column=1, sticky="w", pady=(8, 0))
        baud.bind("<FocusOut>", lambda _event: self._save_connection())

        ttk.Label(connection, text="vJoy ID").grid(row=1, column=1, sticky="e", padx=(0, 64), pady=(8, 0))
        device = ttk.Spinbox(connection, from_=1, to=16, textvariable=self.device_var, width=5)
        device.grid(row=1, column=1, sticky="e", pady=(8, 0))
        device.bind("<FocusOut>", lambda _event: self._save_connection())

        bridge_buttons = ttk.Frame(connection)
        bridge_buttons.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))
        ttk.Button(bridge_buttons, text="Joystick On", command=self._start_bridge).grid(row=0, column=0)
        ttk.Button(bridge_buttons, text="Joystick Off", command=self._stop_bridge).grid(
            row=0,
            column=1,
            padx=8,
        )
        ttk.Button(bridge_buttons, text="Reset Joystick", command=self._reset_joystick).grid(row=0, column=2)

        connection.columnconfigure(1, weight=1)

        link = ttk.Checkbutton(
            frame,
            text="Link X/Y axis speed",
            variable=self.link_axes,
            command=self._sync_y_to_x,
        )
        link.grid(row=2, column=0, columnspan=3, sticky="w", pady=(0, 8))

        for row, (key, label, low, high, hint, fmt) in enumerate(CONTROLS, start=3):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10))

            variable = tk.DoubleVar(value=self.settings[key])
            self.variables[key] = variable

            scale = ttk.Scale(
                frame,
                from_=low,
                to=high,
                variable=variable,
                command=lambda _value, control_key=key: self._on_change(control_key),
                length=260,
            )
            scale.grid(row=row, column=1, sticky="ew", pady=5)

            value_label = ttk.Label(frame, text=fmt.format(self.settings[key]), width=7)
            value_label.grid(row=row, column=2, sticky="e", padx=(10, 0))
            self.value_labels[key] = (value_label, fmt)

            scale.bind("<Enter>", lambda _event, text=hint: self.status.set(text))
            scale.bind("<Leave>", lambda _event: self.status.set("Changes are saved live."))

        buttons = ttk.Frame(frame)
        buttons.grid(row=len(CONTROLS) + 3, column=0, columnspan=3, sticky="ew", pady=(10, 0))

        ttk.Button(buttons, text="Reset Defaults", command=self._reset_defaults).grid(row=0, column=0)
        ttk.Button(buttons, text="Restart Bridge", command=self._restart_bridge).grid(row=0, column=1, padx=8)

        self.status = tk.StringVar(value="Changes are saved live.")
        ttk.Label(frame, textvariable=self.status).grid(
            row=len(CONTROLS) + 4,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(10, 0),
        )

    def _on_change(self, key):
        if key == "x_axis_slew_rate_per_second" and self.link_axes.get() and not self._syncing_axes:
            self._sync_y_to_x()

        for control_key, variable in self.variables.items():
            self.settings[control_key] = float(variable.get())
            label, fmt = self.value_labels[control_key]
            label.configure(text=fmt.format(self.settings[control_key]))
        self._save()

    def _sync_y_to_x(self):
        if not self.link_axes.get():
            return
        self._syncing_axes = True
        self.variables["y_axis_slew_rate_per_second"].set(
            self.variables["x_axis_slew_rate_per_second"].get()
        )
        self._syncing_axes = False
        self._on_change("y_axis_slew_rate_per_second")

    def _save(self):
        self._apply_connection_settings(show_errors=False)
        save_settings(self.settings)
        self.status.set("Changes are saved live.")

    def _save_connection(self):
        if not self._apply_connection_settings(show_errors=True):
            return
        save_settings(self.settings)
        self.status.set(f"Connection saved: {self.settings['serial_port']}.")

    def _apply_connection_settings(self, show_errors):
        port = self._selected_port_name()
        if not port:
            if show_errors:
                messagebox.showerror("COM Port Required", "Choose or type a COM port.")
            return False

        try:
            baud = int(self.baud_var.get())
            device = int(self.device_var.get())
        except ValueError:
            if show_errors:
                messagebox.showerror("Invalid Connection", "Baud and vJoy ID must be numbers.")
            return False

        self.settings["serial_port"] = port
        self.settings["baud"] = baud
        self.settings["vjoy_device"] = device
        return True

    def _refresh_ports(self, select_saved=False):
        current = self.port_var.get().strip()
        ports = []
        if list_ports is not None:
            ports = [
                f"{port.device} - {port.description}"
                for port in list_ports.comports()
            ]

        if not ports:
            ports = [f"COM{number}" for number in range(1, 21)]

        self.port_combo["values"] = ports

        if select_saved:
            saved = str(self.settings["serial_port"])
            matching = next((port for port in ports if port.split(" - ", 1)[0] == saved), None)
            self.port_var.set(matching or saved)
        elif current:
            self.port_var.set(current)

    def _selected_port_name(self):
        return self.port_var.get().split(" - ", 1)[0].strip()

    def _reset_defaults(self):
        for key, value in DEFAULT_SETTINGS.items():
            if key not in self.variables:
                continue
            self.variables[key].set(value)
        for key in NUMERIC_SETTINGS:
            self.settings[key] = DEFAULT_SETTINGS[key]
        self._save()
        self._on_change("x_axis_slew_rate_per_second")

    def _python_executable(self):
        return sys.executable or "python"

    def _start_bridge(self):
        if not self._apply_connection_settings(show_errors=True):
            return

        if not self._stop_bridge(show_status=False):
            return False

        out_log = ROOT_DIR / "vjoy-bridge.out.log"
        err_log = ROOT_DIR / "vjoy-bridge.err.log"
        script = SCRIPT_DIR / "mega_to_vjoy.py"
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

        try:
            with out_log.open("ab") as out, err_log.open("ab") as err:
                process = subprocess.Popen(
                    [
                        self._python_executable(),
                        str(script),
                        "--port",
                        self._selected_port_name(),
                        "--baud",
                        str(self.settings["baud"]),
                        "--device",
                        str(self.settings["vjoy_device"]),
                        "--quiet",
                    ],
                    cwd=ROOT_DIR,
                    stdout=out,
                    stderr=err,
                    creationflags=creationflags,
                    close_fds=os.name != "nt",
                )
        except OSError as error:
            messagebox.showerror("Bridge Start Failed", str(error))
            return False

        time.sleep(0.4)
        if process.poll() is not None:
            error_text = "Bridge exited immediately."
            try:
                recent_error = err_log.read_text(encoding="utf-8", errors="ignore").strip()
            except OSError:
                recent_error = ""
            if recent_error:
                error_text = recent_error.splitlines()[-1]
            messagebox.showerror("Bridge Start Failed", error_text)
            return False

        save_settings(self.settings)
        self.status.set(f"Joystick on: {self._selected_port_name()}.")
        return True

    def _stop_bridge(self, show_status=True):
        try:
            subprocess.run(
                ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(STOP_SCRIPT)],
                cwd=ROOT_DIR,
                check=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.CalledProcessError as error:
            messagebox.showerror("Bridge Stop Failed", str(error))
            return False

        if show_status:
            self.status.set("Joystick off.")
        return True

    def _reset_joystick(self):
        if not self._apply_connection_settings(show_errors=True):
            return

        try:
            import pyvjoy

            joystick = pyvjoy.VJoyDevice(self.settings["vjoy_device"])
            joystick.reset()
        except Exception as error:
            messagebox.showerror("Joystick Reset Failed", str(error))
            return

        self.status.set(f"vJoy device {self.settings['vjoy_device']} reset.")

    def _restart_bridge(self):
        if self._start_bridge():
            self.status.set(f"Bridge restarted on {self._selected_port_name()}.")


if __name__ == "__main__":
    app = TunerApp()
    app.mainloop()
