import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D

# === A) PID CONTROLLER ===
class PID:
    def __init__(self, kp, ki, kd, dt):
        self.kp, self.ki, self.kd, self.dt = kp, ki, kd, dt
        self.integral = 0.0
        self.last_error = 0.0

    def update(self, setpoint, measurement):
        error = setpoint - measurement
        self.integral += error * self.dt
        derivative = (error - self.last_error) / self.dt
        self.last_error = error
        return self.kp * error + self.ki * self.integral + self.kd * derivative

# === B) SENSOR FUSION ===
class SensorFusion:
    def __init__(self, dt, alpha=0.98):
        self.dt = dt
        self.alpha = alpha
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        self.alt = 1.0  # start at hover
        self.g = 9.81

    def update(self, gx, gy, gz, ax, ay, az):
        # accel-based tilt
        acc_roll  = np.arctan2(ay, az)
        acc_pitch = np.arctan2(-ax, np.sqrt(ay*ay + az*az))
        # complementary filter
        self.roll  = self.alpha * (self.roll  + gx * self.dt) + (1 - self.alpha) * acc_roll
        self.pitch = self.alpha * (self.pitch + gy * self.dt) + (1 - self.alpha) * acc_pitch
        # yaw integration
        self.yaw   += gz * self.dt
        # altitude integration (vertical accel minus gravity)
        self.alt   += (az - self.g) * self.dt
        return self.roll, self.pitch, self.yaw, self.alt

# === C) FLIGHT CONTROLLER ===
class FlightController:
    def __init__(self, dt):
        rad_per_deg = np.pi / 180.0
        self.dt = dt
        self.RC2ANGLE    = 10 * rad_per_deg
        self.RC2YAWRATE  = 100 * rad_per_deg
        self.TARGET_ALT  = 1.0
        # PWM
        self.PWM_BASE    = 1300
        self.PWM_MIN     = 1000
        self.PWM_MAX     = 1800
        self.PWM_THR_LIM = 600
        # PIDs
        self.pid_r = PID(4.0, 0.5, 0.1, dt)
        self.pid_p = PID(4.0, 0.5, 0.1, dt)
        self.pid_y = PID(1.0, 0.2, 0.05, dt)
        self.pid_a = PID(2.0, 0.4, 0.1, dt)

    def mix(self, rc_thr, rc_r, rc_p, rc_y, roll, pitch, yaw_rate, alt, az):
        # setpoints
        sp_r = rc_r * self.RC2ANGLE
        sp_p = rc_p * self.RC2ANGLE
        sp_y = rc_y * self.RC2YAWRATE
        # PID cmds
        cmd_r = self.pid_r.update(sp_r, roll)
        cmd_p = self.pid_p.update(sp_p, pitch)
        cmd_y = self.pid_y.update(sp_y, yaw_rate)
        cmd_a = self.pid_a.update(self.TARGET_ALT, alt)
        # throttle + alt
        thr_out = np.clip(rc_thr * self.PWM_THR_LIM + cmd_a, 0, self.PWM_THR_LIM)
        # mix
        m0 = self.PWM_BASE + thr_out + cmd_r + cmd_p + cmd_y
        m1 = self.PWM_BASE + thr_out - cmd_r + cmd_p - cmd_y
        m2 = self.PWM_BASE + thr_out - cmd_r - cmd_p + cmd_y
        m3 = self.PWM_BASE + thr_out + cmd_r - cmd_p - cmd_y
        return np.clip([m0, m1, m2, m3], self.PWM_MIN, self.PWM_MAX)

# === Utility: Euler to Rotation Matrix ===
def euler_to_rot(roll, pitch, yaw):
    Rx = np.array([[1, 0, 0], [0, np.cos(roll), -np.sin(roll)], [0, np.sin(roll), np.cos(roll)]])
    Ry = np.array([[np.cos(pitch), 0, np.sin(pitch)], [0, 1, 0], [-np.sin(pitch), 0, np.cos(pitch)]])
    Rz = np.array([[np.cos(yaw), -np.sin(yaw), 0], [np.sin(yaw), np.cos(yaw), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx

# === D) SIMULATOR with PHYSICS-BASED POSITION ===
class Simulator:
    def __init__(self, path):
        self.dt = 0.004
        self.df = pd.read_csv(path)
        self.N = len(self.df)
        # helpers
        self.fusion     = SensorFusion(self.dt)
        self.controller = FlightController(self.dt)
        # state storage
        self.motors = np.zeros((self.N, 4))
        self.roll   = np.zeros(self.N)
        self.pitch  = np.zeros(self.N)
        self.yaw    = np.zeros(self.N)
        self.alt    = np.zeros(self.N)
        self.vel    = np.zeros((self.N, 3))
        self.pos    = np.zeros((self.N, 3))
        # physical params
        self.mass = 1.0  # kg
        self.thrust_coeff = 1e-3  # N per μs above base

    def run(self):
        for i, row in self.df.iterrows():
            # sensors
            rc_thr, rc_r, rc_p, rc_y = row['rcThrottle'], row['rcRoll'], row['rcPitch'], row['rcYaw']
            gx, gy, gz = row['lpfGyrX'], row['lpfGyrY'], row['lpfGyrZ']
            ax, ay, az = row['lpfAccX'], row['lpfAccY'], row['lpfAccZ']
            # fusion
            r, p, y, a = self.fusion.update(gx, gy, gz, ax, ay, az)
            self.roll[i], self.pitch[i], self.yaw[i], self.alt[i] = r, p, y, a
            # control
            self.motors[i] = self.controller.mix(rc_thr, rc_r, rc_p, rc_y, r, p, gz, a, az)
            # physics-based pos
            thrusts = self.thrust_coeff * (self.motors[i] - self.controller.PWM_BASE)
            total_thrust = thrusts.sum()
            # body accel
            acc_body = np.array([0, 0, total_thrust/self.mass - 9.81])
            # world accel
            R = euler_to_rot(r, p, y)
            acc_world = R @ acc_body
            if i > 0:
                self.vel[i] = self.vel[i-1] + acc_world * self.dt
                self.pos[i] = self.pos[i-1] + self.vel[i] * self.dt
        # save
        for j in range(4): self.df[f'motor{j}'] = self.motors[:,j]
        self.df['roll_est'], self.df['pitch_est'], self.df['yaw_est'], self.df['alt_est'] = \
            self.roll, self.pitch, self.yaw, self.alt
        self.df[['velX','velY','velZ']] = self.vel
        self.df[['posX','posY','posZ']] = self.pos

    def plot(self):
        t = np.arange(self.N) * self.dt
        # motor PWMs
        plt.figure(figsize=(8,4))
        for j in range(4): plt.plot(t, self.motors[:,j], label=f'Motor{j}')
        plt.title("Motor PWM Outputs"); plt.xlabel("Time (s)"); plt.legend(); plt.grid(True)
        # attitude/alt
        plt.figure(figsize=(8,4))
        plt.plot(t, self.roll, label='Roll'); plt.plot(t, self.pitch, label='Pitch'); plt.plot(t, self.alt, label='Alt')
        plt.title("Attitude & Altitude"); plt.legend(); plt.grid(True)
        # 3D path
        fig = plt.figure(figsize=(6,6))
        ax = fig.add_subplot(111, projection='3d')
        ax.plot(self.pos[:,0], self.pos[:,1], self.pos[:,2], lw=2)
        ax.set_title("3D Flight Path"); ax.set_xlabel("X"); ax.set_ylabel("Y"); ax.set_zlabel("Z")
        plt.show()

# === E) RUN ===
if __name__ == '__main__':
    sim = Simulator(r"C:/Users/Aditi/OneDrive/Documents/Desktop/Flight controller/sensors.csv")
    sim.run()
    sim.plot()
