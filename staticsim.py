import sys
import pandas as pd
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider,
    QPushButton, QTabWidget, QMainWindow, QScrollArea, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer
from matplotlib.backends.backend_qt5agg import (
    FigureCanvasQTAgg as FigureCanvas,
    NavigationToolbar2QT as NavigationToolbar
)
from matplotlib.figure import Figure
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401

# --- Sensor Noise Simulation Functions ---
def simulate_sensor_noise(data, noise_level=0.05):
    noise = np.random.normal(0, noise_level, size=data.shape)
    return data + noise

def simulate_sensor_bias(data, bias=0.1):
    return data + bias

def simulate_sensor_drift(data, drift_rate=0.001, time_step=1):
    drift = drift_rate * np.arange(len(data)) * time_step
    return data + drift

def simulate_sensor_dropout(data, dropout_probability=0.05):
    dropout_mask = np.random.rand(len(data)) < dropout_probability
    data[dropout_mask] = np.nan
    return data

# --- PID Slider Widget ---
class PIDSlider(QWidget):
    def __init__(self, label, init=10, min_val=0, max_val=100):
        super().__init__()
        self.layout = QVBoxLayout()
        self.label_text = label
        self.label = QLabel(f"{label}: {init/10:.1f}")
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(min_val)
        self.slider.setMaximum(max_val)
        self.slider.setValue(init)
        self.slider.valueChanged.connect(self.update_label)
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.slider)
        self.setLayout(self.layout)

    def update_label(self, val):
        self.label.setText(f"{self.label_text}: {val/10:.1f}")

    def get_value(self):
        return self.slider.value() / 10.0

# --- Motor PWM Plotting Tab ---
class PlotTab(QWidget):
    def __init__(self, title="Motor PWMs"):
        super().__init__()
        self.layout = QVBoxLayout()
        self.canvas = FigureCanvas(Figure(figsize=(5, 4)))
        self.ax = self.canvas.figure.add_subplot(111)
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas)
        self.setLayout(self.layout)

    def plot_motor_pwms(self, time, rcThrottle):
        try:
            self.ax.clear()
            self.ax.plot(time, rcThrottle, label="Throttle PWM", color='red')
            self.ax.set_title("Motor PWMs")
            self.ax.set_xlabel("Time (s)")
            self.ax.set_ylabel("PWM (0.0 - 1.0)")
            self.ax.set_ylim(0, 1.1)
            self.ax.legend()
            self.canvas.draw()
        except Exception as e:
            print(f"Error in plot_motor_pwms: {str(e)}")

# --- 3D Trajectory Plotting Tab ---
class Plot3DTab(QWidget):
    def __init__(self, title="3D Trajectory"):
        super().__init__()
        self.layout = QVBoxLayout()
        self.canvas = FigureCanvas(Figure(figsize=(5, 4)))
        self.ax = self.canvas.figure.add_subplot(111, projection='3d')
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.layout.addWidget(self.toolbar)
        self.layout.addWidget(self.canvas)
        self.setLayout(self.layout)

    def plot_trajectory(self, ekf_phi, ekf_theta, rcYaw):
        try:
            self.ax.clear()
            self.ax.plot(ekf_phi, ekf_theta, rcYaw, label="Trajectory", color='blue', marker='o')
            self.ax.set_title("3D Trajectory")
            self.ax.set_xlabel("Phi (Angle in X)")
            self.ax.set_ylabel("Theta (Angle in Y)")
            self.ax.set_zlabel("Yaw (Angle in Z)")
            self.ax.legend()
            self.canvas.draw()
        except Exception as e:
            print(f"Error in plot_trajectory: {str(e)}")

# --- Main GUI Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flight Controller PID GUI")
        self.setGeometry(100, 100, 1200, 700)
        self.main_widget = QWidget()
        self.layout = QHBoxLayout(self.main_widget)

        # --- Left Panel ---
        self.control_scroll = QScrollArea()
        self.control_scroll.setWidgetResizable(True)
        self.control_group = QGroupBox("PID & Throttle Controls")
        self.control_layout = QVBoxLayout()

        self.pid_sliders = {}
        axes = ["Roll", "Pitch", "Yaw", "Altitude"]
        terms = ["P", "I", "D"]
        for axis in axes:
            for term in terms:
                key = f"{axis}_{term}"
                self.pid_sliders[key] = PIDSlider(f"{axis} {term}", init=10)
                self.control_layout.addWidget(self.pid_sliders[key])

        self.throttle_min = PIDSlider("Throttle Min", init=10)
        self.throttle_max = PIDSlider("Throttle Max", init=90)
        self.control_layout.addWidget(self.throttle_min)
        self.control_layout.addWidget(self.throttle_max)

        self.run_button = QPushButton("Run Simulation")
        self.run_button.clicked.connect(self.run_simulation)
        self.control_layout.addWidget(self.run_button)

        self.stop_button = QPushButton("Stop Simulation")
        self.stop_button.clicked.connect(self.stop_simulation)
        self.control_layout.addWidget(self.stop_button)

        self.reset_button = QPushButton("Reset Simulation")
        self.reset_button.clicked.connect(self.reset_simulation)
        self.control_layout.addWidget(self.reset_button)

        self.control_layout.addStretch()
        self.control_group.setLayout(self.control_layout)
        self.control_scroll.setWidget(self.control_group)

        # --- Right Panel ---
        self.tabs = QTabWidget()
        self.motor_tab = PlotTab("Motor PWMs")
        self.traj_tab = Plot3DTab("3D Trajectory")
        self.tabs.addTab(self.motor_tab, "Motor PWMs")
        self.tabs.addTab(self.traj_tab, "3D Trajectory")

        self.layout.addWidget(self.control_scroll, 2)
        self.layout.addWidget(self.tabs, 5)
        self.setCentralWidget(self.main_widget)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plots)

    def run_simulation(self):
        try:
            file_path = r"C:\Users\Aditi\OneDrive\Documents\Desktop\Flight controller\sensors.csv"
            print(f"Attempting to load CSV file: {file_path}")
            data = pd.read_csv(file_path)
            print("CSV Loaded successfully")

            time = data.index.values
            rcThrottle = data['rcThrottle'].values
            rcRoll = data['rcRoll'].values
            rcPitch = data['rcPitch'].values
            rcYaw = data['rcYaw'].values
            ekf_phi = data['ekf.phi'].values
            ekf_theta = data['ekf.theta'].values
            lpfGyrX = data['lpfGyrX'].values
            lpfGyrY = data['lpfGyrY'].values
            lpfGyrZ = data['lpfGyrZ'].values
            lpfAccX = data['lpfAccX'].values
            lpfAccY = data['lpfAccY'].values
            lpfAccZ = data['lpfAccZ'].values

            rcThrottle = simulate_sensor_noise(rcThrottle)
            rcThrottle = simulate_sensor_bias(rcThrottle)
            rcThrottle = simulate_sensor_drift(rcThrottle)
            rcThrottle = simulate_sensor_dropout(rcThrottle)

            print("Data preview:")
            print(data.head())

            self.motor_tab.plot_motor_pwms(time, rcThrottle)
            self.traj_tab.plot_trajectory(ekf_phi, ekf_theta, rcYaw)
            self.timer.start(1000)
        except Exception as e:
            print(f"Error during simulation: {str(e)}")

    def update_plots(self):
        print("Updating plots...")

    def stop_simulation(self):
        print("Simulation stopped.")
        self.timer.stop()

    def reset_simulation(self):
        print("Simulation reset.")
        self.motor_tab.plot_motor_pwms([], [])
        self.traj_tab.plot_trajectory([], [], [])

# --- Run GUI ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
