using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using UnityEngine;

public class SocketManager : MonoBehaviour
{
    private TcpListener tcpListener;
    private TcpClient tcpClient;
    private NetworkStream networkStream;
    private byte[] buffer = new byte[1024];

    public float roll, pitch, yaw, throttle;  // Sensor data from Python
    public int port = 5000;  // Port for Socket communication

    void Start()
    {
        StartListening();
    }

    void StartListening()
    {
        tcpListener = new TcpListener(IPAddress.Any, port);
        tcpListener.Start();
        Debug.Log("Listening for connections...");

        // Start listening in a separate thread
        tcpListener.BeginAcceptTcpClient(OnClientConnected, tcpListener);
    }

    void OnClientConnected(IAsyncResult result)
    {
        tcpClient = tcpListener.EndAcceptTcpClient(result);
        networkStream = tcpClient.GetStream();
        Debug.Log("Client connected");

        // Start receiving data
        ReceiveData();
    }

    void ReceiveData()
    {
        networkStream.BeginRead(buffer, 0, buffer.Length, OnDataReceived, null);
    }

    void OnDataReceived(IAsyncResult result)
    {
        int bytesRead = networkStream.EndRead(result);
        if (bytesRead > 0)
        {
            string receivedData = Encoding.UTF8.GetString(buffer, 0, bytesRead);
            ParseData(receivedData);  // Parse the received data into roll, pitch, yaw, throttle
        }

        // Continue receiving data
        ReceiveData();
    }

    void ParseData(string data)
    {
        // Split the received string into individual values
        string[] values = data.Split(',');

        if (values.Length == 4)
        {
            // Parse the roll, pitch, yaw, and throttle values
            float.TryParse(values[0], out roll);
            float.TryParse(values[1], out pitch);
            float.TryParse(values[2], out yaw);
            float.TryParse(values[3], out throttle);
        }
    }

    void OnApplicationQuit()
    {
        if (tcpClient != null)
        {
            tcpClient.Close();
        }

        if (tcpListener != null)
        {
            tcpListener.Stop();
        }
    }
}
