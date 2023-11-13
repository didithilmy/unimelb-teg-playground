using System.Collections.Generic;
using UnityEngine;
using EasyRoads3Dv3;
using Michsky.MUIP;
using System;

public class RoadBuilder : MonoBehaviour
{
    public CustomDropdown elementPickerDropdown;
    public Vector3 screenPosition, worldPosition;
    public Vector3 startCoord;
    public Vector3 endCoord;
    public ERRoadNetwork roadNetwork;
    public ERRoadType roadType;
    public Plane plane;

    private bool dragging = false;
    private ERRoad currentRoad;
    private ERConnection currentCrossing;
    private Collider coll;

    enum ConnectionType
    {
        CrossingX,
        CrossingT
    }

    void Start()
    {
        Debug.Log("Please read the comments at the top of the runtime script (/Assets/EasyRoads3D/Scripts/runtimeScript) before using the runtime API!");

        coll = GetComponent<Collider>();
        roadNetwork = new ERRoadNetwork();
        roadType = roadNetwork.GetRoadTypeByName("Default Road");
        roadNetwork.LoadConnections();
    }

    void Update()
    {
        Vector3? coord = GetMouseWorldCoord();
        if (coord != null)
        {
            endCoord = SnapToGrid((Vector3)coord);
            if (dragging)
            {
                if (currentRoad != null)
                {
                    UpdateRoadEndCoord(currentRoad, endCoord);
                }
                else if (currentCrossing != null)
                {
                    UpdateCrossingCoord(currentCrossing, endCoord);
                }
            }
        }
    }

    void OnMouseDown()
    {
        dragging = true;
        Vector3? startCoord = GetMouseWorldCoord();
        if (startCoord != null)
        {
            Vector3 coord = SnapToGrid((Vector3)startCoord);
            switch (elementPickerDropdown.selectedItemIndex)
            {
                case 1:
                    currentRoad = CreateRoad("Road", roadType, coord, 5);
                    break;
                case 2:
                    currentCrossing = CreateCrossing(ConnectionType.CrossingX, coord);
                    break;
                case 3:
                    currentCrossing = CreateCrossing(ConnectionType.CrossingT, coord);
                    break;
            }
        }
    }

    void OnMouseUp()
    {
        dragging = false;
        if (currentRoad != null)
        {
            List<(int, ERConnection)> connections = GetConnectedConnectionsFromRoad(currentRoad);
            foreach ((int markerIndex, ERConnection connection) in connections)
            {
                if (markerIndex == 0)
                {
                    int connectionIndex = connection.FindNearestConnectionIndex(currentRoad.GetMarkerPosition(0));
                    currentRoad.ConnectToStart(connection, connectionIndex);
                }
                else if (markerIndex == 1)
                {
                    int connectionIndex = connection.FindNearestConnectionIndex(currentRoad.GetMarkerPosition(1));
                    currentRoad.ConnectToEnd(connection, connectionIndex);
                }
            }

            HashSet<ERRoad> connectedRoads = GetConnectedRoads(currentRoad);
            foreach (ERRoad connectedRoad in connectedRoads)
            {
                roadNetwork.ConnectRoads(currentRoad, connectedRoad);
            }
            Debug.Log(connectedRoads.Count);
        }
        else if (currentCrossing != null)
        {
            List<(int, ERRoad)> roads = GetConnectedRoadsFromConnection(currentCrossing);
            foreach ((int markerIndex, ERRoad road) in roads)
            {
                if (markerIndex == 0)
                {
                    int connectionIndex = currentCrossing.FindNearestConnectionIndex(road.GetMarkerPosition(0));
                    road.ConnectToStart(currentCrossing, connectionIndex);
                }
                else if (markerIndex == 1)
                {
                    int connectionIndex = currentCrossing.FindNearestConnectionIndex(road.GetMarkerPosition(1));
                    road.ConnectToEnd(currentCrossing, connectionIndex);
                }
            }
        }

        currentRoad = null;
        currentCrossing = null;
    }

    private Vector3? GetMouseWorldCoord()
    {
        Ray ray = Camera.main.ScreenPointToRay(Input.mousePosition);
        if (coll.Raycast(ray, out RaycastHit hit, 1000.0f))
        {
            Vector3 point = ray.GetPoint(hit.distance);
            point.y = 0.05f;
            return point;
        }

        return null;
    }

    private Vector3 SnapToGrid(Vector3 pos)
    {
        float factor = 3f;
        return new Vector3(Mathf.Round(pos.x / factor) * factor,
                             pos.y,
                             Mathf.Round(pos.z / factor) * factor);
    }

    private ERRoad CreateRoad(string name, ERRoadType roadType, Vector3 startCoord, int width = 5, int noOfLanes = 1)
    {
        ERRoad road = roadNetwork.CreateRoad(name, roadType);
        road.SetWidth(width);
        road.AddMarker(startCoord);
        road.AddMarker(startCoord);
        // ERSideWalk sideWalk = roadNetwork.GetSidewalkByName("Concrete");
        // road.SetSidewalk(sideWalk, ERRoadSide.Both, true);
        return road;
    }

    private void UpdateRoadEndCoord(ERRoad road, Vector3 coord)
    {
        road.DeleteMarker(1);
        road.InsertMarker(coord);
    }

    private ERConnection CreateCrossing(ConnectionType connectionType, Vector3 coord)
    {
        String prefabName = "Default X Crossing";
        switch (connectionType)
        {
            case ConnectionType.CrossingT:
                prefabName = "Default T Crossing";
                break;
            case ConnectionType.CrossingX:
                prefabName = "Default X Crossing";
                break;
        }

        ERConnection connectionPrefab = roadNetwork.GetConnectionPrefabByName(prefabName);
        ERConnection connection = roadNetwork.InstantiateConnection(connectionPrefab, "Intersection", coord, Vector3.zero);
        return connection;
    }

    private void UpdateCrossingCoord(ERConnection connection, Vector3 coord)
    {
        connection.gameObject.transform.position = coord;
    }


    private HashSet<ERRoad> GetConnectedRoads(ERRoad currentRoad)
    {
        Vector3 startCoord = currentRoad.GetMarkerPosition(0);
        Vector3 endCoord = currentRoad.GetMarkerPosition(1);
        HashSet<ERRoad> roads = new HashSet<ERRoad>();
        foreach (ERRoad road in roadNetwork.GetRoadObjects())
        {
            if (road == currentRoad) continue;
            Vector3[] markerPositions = road.GetMarkerPositions();
            foreach (Vector3 pos in markerPositions)
            {
                if (pos == startCoord || pos == endCoord)
                {
                    roads.Add(road);
                    break;
                }
            }
        }
        return roads;
    }

    private List<(int, ERConnection)> GetConnectedConnectionsFromRoad(ERRoad currentRoad)
    {
        Dictionary<ERConnection, int> connectionsMap = new Dictionary<ERConnection, int>();
        foreach (ERConnection connection in roadNetwork.GetConnections())
        {
            foreach (Vector3 position in connection.GetConnectionWorldPositions())
            {
                Vector3 snappedPos = SnapToGrid(position);
                // float distThreshold = 3f;
                if (snappedPos == currentRoad.GetMarkerPosition(0))
                {
                    connectionsMap[connection] = 0;
                }
                if (snappedPos == currentRoad.GetMarkerPosition(1))
                {
                    connectionsMap[connection] = 1;
                }
            }
        }

        List<(int, ERConnection)> list = new List<(int, ERConnection)>();
        foreach (ERConnection connection in connectionsMap.Keys)
        {
            list.Add((connectionsMap[connection], connection));
        }
        return list;
    }

    private List<(int, ERRoad)> GetConnectedRoadsFromConnection(ERConnection connection)
    {
        Dictionary<ERRoad, int> roadsMap = new Dictionary<ERRoad, int>();
        foreach (ERRoad road in roadNetwork.GetRoadObjects())
        {
            foreach (Vector3 position in connection.GetConnectionWorldPositions())
            {
                Vector3 snappedPos = SnapToGrid(position);
                // float distThreshold = 3f;
                if (snappedPos == road.GetMarkerPosition(0))
                {
                    roadsMap[road] = 0;
                }
                if (snappedPos == road.GetMarkerPosition(1))
                {
                    roadsMap[road] = 1;
                }
            }
        }

        List<(int, ERRoad)> list = new List<(int, ERRoad)>();
        foreach (ERRoad road in roadsMap.Keys)
        {
            list.Add((roadsMap[road], road));
        }
        return list;
    }
}
