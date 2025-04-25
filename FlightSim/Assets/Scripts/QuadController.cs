using UnityEngine;

public class QuadrotorController : MonoBehaviour
{
    private Rigidbody rb;

    void Start()
    {
        rb = GetComponent<Rigidbody>();
    }

    void Update()
    {
        string data = SocketServer.receivedData;

        if (!string.IsNullOrEmpty(data))
        {
            string[] parts = data.Split(',');

            if (parts.Length >= 4)
            {
                try
                {
                    float roll = float.Parse(parts[0]);
                    float pitch = float.Parse(parts[1]);
                    float yaw = float.Parse(parts[2]);
                    float throttle = float.Parse(parts[3]);

                    // Basic movement simulation (can customize physics here)
                    Vector3 movement = new Vector3(pitch, throttle, -roll);
                    rb.AddForce(movement);

                    // Simple yaw rotation
                    rb.AddTorque(Vector3.up * yaw * 0.1f);
                }
                catch (System.Exception e)
                {
                    Debug.LogWarning("Parse error: " + e.Message);
                }
            }
        }
    }
}
