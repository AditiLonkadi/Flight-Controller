import sys
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QMainWindow, QScrollArea, QGroupBox, QSlider, QPushButton, QLabel
)
from PyQt5.QtCore import Qt, QTimer

# --- Simulated Sensor Data Generator ---
def generate_sensor_data(num_points=1000):
    time = np.linspace(0, 100, num_points)
    rcThrottle = np.sin(time / 5) * 0.5 + 0.5
    rcRoll = np.cos(time / 10) * 0.3 + 0.5
    rcPitch = np.sin(time / 20) * 0.3 + 0.5
    rcYaw = np.cos(time / 15) * 0.3 + 0.5
    ekf_phi = np.sin(time / 10) * 30
    ekf_theta = np.cos(time / 15) * 30
    ekf_psi = np.sin(time / 20) * 45
    return time, rcThrottle, rcRoll, rcPitch, rcYaw, ekf_phi, ekf_theta, ekf_psi

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

# --- Real-time Plotting Widget ---
class PlotTab(QWidget):
    def __init__(self, title="Motor PWMs"):
        super().__init__()
        self.layout = QVBoxLayout()
        self.canvas = FigureCanvas(Figure(figsize=(10, 5)))
        self.ax1 = self.canvas.figure.add_subplot(121)
        self.ax2 = self.canvas.figure.add_subplot(122, projection='3d')
        self.layout.addWidget(self.canvas)
        self.setLayout(self.layout)

        self.time = []
        self.rcThrottle = []
        self.rcRoll = []
        self.rcPitch = []
        self.rcYaw = []
        self.ekf_phi = []
        self.ekf_theta = []
        self.ekf_psi = []

    def update_plot(self, t, throttle, roll, pitch, yaw, phi, theta, psi):
        self.time.append(t)
        self.rcThrottle.append(throttle)
        self.rcRoll.append(roll)
        self.rcPitch.append(pitch)
        self.rcYaw.append(yaw)
        self.ekf_phi.append(phi)
        self.ekf_theta.append(theta)
        self.ekf_psi.append(psi)

        self.ax1.clear()
        self.ax1.plot(self.time, self.rcThrottle, label="Throttle", color='red')
        self.ax1.plot(self.time, self.rcRoll, label="Roll", color='blue')
        self.ax1.plot(self.time, self.rcPitch, label="Pitch", color='green')
        self.ax1.plot(self.time, self.rcYaw, label="Yaw", color='purple')
        self.ax1.set_xlabel("Time (s)")
        self.ax1.set_ylabel("PWM")
        self.ax1.set_ylim(0, 1.1)
        self.ax1.set_title("Real-Time PWM Signals")
        self.ax1.legend()
        self.ax1.grid(True)

        self.ax2.clear()
        self.ax2.plot(self.ekf_phi, self.ekf_theta, self.ekf_psi, color='black', marker='o', label='Trajectory')
        self.ax2.set_xlabel("Phi (°)")
        self.ax2.set_ylabel("Theta (°)")
        self.ax2.set_zlabel("Psi (°)")
        self.ax2.set_title("3D Orientation (EKF)")
        self.ax2.legend()

        self.canvas.draw()

# --- Main GUI Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Flight Controller - Real-Time Simulation")
        self.setGeometry(100, 100, 1200, 700)

        self.main_widget = QWidget()
        self.layout = QHBoxLayout(self.main_widget)

        self.control_scroll = QScrollArea()
        self.control_scroll.setWidgetResizable(True)
        self.control_group = QGroupBox("Controls")
        self.control_layout = QVBoxLayout()

        self.pid_sliders = {}
        for axis in ["Roll", "Pitch", "Yaw", "Altitude"]:
            for term in ["P", "I", "D"]:
                name = f"{axis}_{term}"
                slider = PIDSlider(name, init=10)
                self.pid_sliders[name] = slider
                self.control_layout.addWidget(slider)

        self.throttle_min = PIDSlider("Throttle Min", init=10)
        self.throttle_max = PIDSlider("Throttle Max", init=90)
        self.control_layout.addWidget(self.throttle_min)
        self.control_layout.addWidget(self.throttle_max)

        self.run_button = QPushButton("Run Simulation")
        self.run_button.clicked.connect(self.run_simulation)
        self.control_layout.addWidget(self.run_button)

        self.control_group.setLayout(self.control_layout)
        self.control_scroll.setWidget(self.control_group)

        self.tabs = QTabWidget()
        self.plot_tab = PlotTab("Motor PWMs")
        self.tabs.addTab(self.plot_tab, "Live Telemetry")

        self.layout.addWidget(self.control_scroll, 2)
        self.layout.addWidget(self.tabs, 5)
        self.setCentralWidget(self.main_widget)

        # Timer for real-time simulation
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_plots)

        # Load data
        self.time, self.rcThrottle, self.rcRoll, self.rcPitch, self.rcYaw, self.ekf_phi, self.ekf_theta, self.ekf_psi = generate_sensor_data()
        self.current_index = 0

    def run_simulation(self):
        self.current_index = 0
        self.plot_tab.time.clear()
        self.plot_tab.rcThrottle.clear()
        self.plot_tab.rcRoll.clear()
        self.plot_tab.rcPitch.clear()
        self.plot_tab.rcYaw.clear()
        self.plot_tab.ekf_phi.clear()
        self.plot_tab.ekf_theta.clear()
        self.plot_tab.ekf_psi.clear()
        self.timer.start(100)  # update every 100 ms

    def update_plots(self):
        if self.current_index >= len(self.time):
            self.timer.stop()
            return

        self.plot_tab.update_plot(
            self.time[self.current_index],
            self.rcThrottle[self.current_index],
            self.rcRoll[self.current_index],
            self.rcPitch[self.current_index],
            self.rcYaw[self.current_index],
            self.ekf_phi[self.current_index],
            self.ekf_theta[self.current_index],
            self.ekf_psi[self.current_index]
        )

        self.current_index += 1

# --- Run the App ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
