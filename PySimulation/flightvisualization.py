import numpy as np
from vpython import *

# ============================================= 
# Scene Setup 
# ============================================= 
scene = canvas(width=1400, height=800, background=vec(0.5, 0.8, 0.92))
scene.title = "Drone Flight Controller"
scene.forward = vector(-1, -0.3, -1)

# ============================================= 
# Drone Visualization s
# ============================================= 
def create_drone():
    body = box(pos=vector(0,0,0), size=vector(0.4,0.1,0.4), color=color.gray(0.3))
    arms = [
        cylinder(pos=vector(-0.5,0,0), axis=vector(1,0,0), radius=0.02, color=color.gray(0.6)),
        cylinder(pos=vector(0,0,-0.5), axis=vector(0,0,1), radius=0.02, color=color.gray(0.6))
    ]
    rotors = [
        cylinder(pos=vector(-0.5,0.05,0), axis=vector(0,0.1,0), radius=0.15, color=color.red, opacity=0.7),
        cylinder(pos=vector(0.5,0.05,0), axis=vector(0,0.1,0), radius=0.15, color=color.blue, opacity=0.7),
        cylinder(pos=vector(0,0.05,-0.5), axis=vector(0,0.1,0), radius=0.15, color=color.green, opacity=0.7),
        cylinder(pos=vector(0,0.05,0.5), axis=vector(0,0.1,0), radius=0.15, color=color.yellow, opacity=0.7)
    ]
    return compound([body] + arms + rotors)

drone = create_drone()
ground = box(pos=vector(0,-0.1,0), size=vector(20,0.2,20), color=color.green)
trail = curve(color=color.orange, radius=0.02)
console = label(pos=vec(-5, 3, 0), height=18, border=10, text='Initializing...',
                color=color.black, background=color.white, opacity=0.8)

# ============================================= 
# PID Controller for stabilization 
# ============================================= 
class PID:
    def __init__(self, Kp, Ki, Kd):
        self.Kp = Kp
        self.Ki = Ki
        self.Kd = Kd
        self.prev_error = 0
        self.integral = 0

    def update(self, error, dt):
        self.integral += error * dt
        derivative = (error - self.prev_error) / dt
        self.prev_error = error
        return self.Kp * error + self.Ki * self.integral + self.Kd * derivative

# ============================================= 
# Drone Physics & Control System 
# ============================================= 
class EnhancedDronePhysics:
    def __init__(self):
        self.position = vector(0,0,0)  # Start on ground
        self.velocity = vector(0,0,0)
        self.phi = 0.0
        self.theta = 0.0
        self.psi = 0.0
        self.angular_vel = vector(0,0,0)
        self.mass = 1.2
        self.thrust = 0.0
        self.altitude_hold_target = 1.0  # Target altitude for hold
        self.altitude_pid = PID(1.0, 0.1, 0.05)  # PID for altitude hold
        
    def update(self, motors, dt):
        forces = [max(0, min(m, 1000)) * 0.01 for m in motors]
        self.thrust = sum(forces)
        
        # Calculate torques from motor inputs (corrected signs)
        roll_torque = (forces[3] - forces[2])  # Right rotors (1 and 4) vs left rotors (0 and 3)
        pitch_torque = (forces[1] - forces[0])  # Front rotors (0 and 1) vs rear rotors (2 and 3)
        yaw_torque = (forces[0] + forces[2]) - (forces[1] + forces[3])  # CW vs CCW rotors
        
        self.angular_vel.x += roll_torque * dt * 0.1
        self.angular_vel.y += pitch_torque * dt * 0.1
        self.angular_vel.z += yaw_torque * dt * 0.1
        
        self.phi += self.angular_vel.x * dt
        self.theta += self.angular_vel.y * dt
        self.psi += self.angular_vel.z * dt
        
        # Altitude hold PID controller
        altitude_error = self.altitude_hold_target - self.position.y
        altitude_correction = self.altitude_pid.update(altitude_error, dt)
        
        # Rotate thrust vector according to drone orientation
        lift_magnitude = self.thrust + altitude_correction
        lift = rotate(vector(0, lift_magnitude, 0), 
                     angle=self.phi, axis=vector(1,0,0))
        lift = rotate(lift, angle=self.theta, axis=vector(0,0,1))
        
        gravity = vector(0, -9.81 * self.mass, 0)
        acceleration = (lift + gravity) / self.mass
        self.velocity += acceleration * dt
        self.position += self.velocity * dt
        
        # Damping for stabilization
        self.angular_vel *= 0.9
        self.velocity *= 0.97

# Initialize physics and drone object
physics = EnhancedDronePhysics()

# ============================================= 
# Controls 
# ============================================= 
key_state = {'w': False, 's': False, 'a': False, 'd': False, 'q': False, 'e': False, 'r': False, 'f': False}
def keydown(evt): key_state[evt.key] = True
def keyup(evt): key_state[evt.key] = False
scene.bind('keydown', keydown)
scene.bind('keyup', keyup)

def apply_manual_control():
    base_thrust = 650  # Default thrust to maintain stable hover

    # Control adjustments based on key inputs
    roll_adj = 0
    pitch_adj = 0
    yaw_adj = 0
    lift_adj = 0
    
    if key_state['w']: pitch_adj += 20
    if key_state['s']: pitch_adj -= 20
    if key_state['a']: roll_adj -= 20
    if key_state['d']: roll_adj += 20
    if key_state['q']: yaw_adj -= 10
    if key_state['e']: yaw_adj += 10
    if key_state['r']: physics.altitude_hold_target += 0.05  # Increase altitude target
    if key_state['f']: physics.altitude_hold_target = max(0.1, physics.altitude_hold_target - 0.05)  # Decrease altitude target

    # Correct motor mixing (quadcopter X configuration)
    # Motor order: [front-left, front-right, rear-left, rear-right]
    motor1 = base_thrust - pitch_adj + roll_adj + yaw_adj  # Front-left
    motor2 = base_thrust - pitch_adj - roll_adj - yaw_adj  # Front-right
    motor3 = base_thrust + pitch_adj + roll_adj - yaw_adj  # Rear-left
    motor4 = base_thrust + pitch_adj - roll_adj + yaw_adj  # Rear-right
    
    return [motor1, motor2, motor3, motor4]

# ============================================= 
# GUI Buttons (Optional) 
# ============================================= 
def add_control_button(text, key):
    def click(): key_state[key] = True
    def release(): key_state[key] = False
    return button(text=text, bind=click, up=release)

add_control_button("Forward (W)", 'w')
add_control_button("Back (S)", 's')
add_control_button("Left (A)", 'a')
add_control_button("Right (D)", 'd')
add_control_button("Yaw L (Q)", 'q')
add_control_button("Yaw R (E)", 'e')
add_control_button("Up (R)", 'r')
add_control_button("Down (F)", 'f')

# ============================================= 
# Simulation Loop 
# ============================================= 
dt = 0.01
t = 0

while t < 60:
    rate(100)
    motors = apply_manual_control()
    physics.update(motors, dt)
    
    drone.pos = physics.position
    drone.rotate(angle=physics.phi, axis=vector(1,0,0), origin=drone.pos)
    drone.rotate(angle=physics.theta, axis=vector(0,0,1), origin=drone.pos)
    drone.rotate(angle=physics.psi, axis=vector(0,1,0), origin=drone.pos)
    
    trail.append(pos=drone.pos)
    
    console.text = f"""
    FLIGHT TELEMETRY
    ------------------------
    Altitude: {physics.position.y:.2f} m
    Roll: {np.rad2deg(physics.phi):.1f}°
    Pitch: {np.rad2deg(physics.theta):.1f}°
    Yaw: {np.rad2deg(physics.psi):.1f}°
    ------------------------
    Use WASD + QE + R/F to fly
    """
    t += dt

print("Simulation complete.")