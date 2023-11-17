using System.Collections.Generic;
using UnityEngine;
using EasyRoads3Dv3;
using Michsky.MUIP;
using System;
using System.Linq;
using ITS.Utils;
using UnityEngine.EventSystems;
using System.Reflection.Emit;

public class RoadBuilder : MonoBehaviour
{
    public CustomDropdown elementPickerDropdown;
    public ButtonManager startButton, stopButton;
    public Vector3 screenPosition, worldPosition;
    public Vector3 startCoord;
    public Vector3 endCoord;
    public ERRoadNetwork roadNetwork;
    public Plane plane;
    public GameObject itsManager, trafficLightPrefab;
    public bool rightHandDriving = false;

    [SerializeField] public CustomTrafficSpawner.VehicleConfig[] vehicles;

    private bool dragging = false;
    private ERRoad currentRoad;
    private ERConnection currentCrossing;
    private GameObject currentTrafficLight, currentTrafficSpawner;
    private int rotationDegree = 0;
    private Collider coll;
    private TSMainManager tsMainManager;
    private Dictionary<ERRoad, List<TSLaneInfo>> roadLaneMap = new Dictionary<ERRoad, List<TSLaneInfo>>();

    enum ConnectionType
    {
        CrossingX,
        CrossingT
    }

    void Start()
    {
        coll = GetComponent<Collider>();
        roadNetwork = new ERRoadNetwork();
        ERModularBase modularBase = roadNetwork.roadNetwork;
        modularBase.displayLaneData = true; // Required to allow iTS to connect lanes at intersections
        modularBase.rightHandDriving = rightHandDriving ? 1 : 0;
        roadNetwork.LoadConnections();

        tsMainManager = itsManager.GetComponent<TSMainManager>();

        startButton.onClick.AddListener(StartSimulation);
        stopButton.onClick.AddListener(StopSimulation);
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
                    UpdateCrossingCoord(currentCrossing, endCoord, rotationDegree);
                }
                else if (currentTrafficLight != null)
                {
                    UpdateTrafficLightCoord(currentTrafficLight, endCoord, rotationDegree);
                }
                else if (currentTrafficSpawner != null)
                {
                    UpdateTrafficSpawnerRadius(currentTrafficSpawner, endCoord);
                }
            }
        }

        if (Input.GetKeyDown(KeyCode.DownArrow))
        {
            rotationDegree = (rotationDegree + 90) % 360;
        }
        else if (Input.GetKeyDown(KeyCode.UpArrow))
        {
            rotationDegree = (rotationDegree - 90) % 360;
        }
    }

    void OnMouseDown()
    {
        if (EventSystem.current.IsPointerOverGameObject())
        {
            return;
        }

        dragging = true;
        Vector3? startCoord = GetMouseWorldCoord();
        if (startCoord != null)
        {
            Vector3 coord = SnapToGrid((Vector3)startCoord);
            switch (elementPickerDropdown.selectedText.text)
            {
                case "Two-way Road":
                    ERRoadType twoWayRoadType = roadNetwork.GetRoadTypeByName("Primary-TwoLane-TwoWay");
                    currentRoad = CreateRoad("2w2lnRoad", twoWayRoadType, coord, 6f);
                    break;
                case "One-way Road (1 lane)":
                    ERRoadType oneWayRoadType = roadNetwork.GetRoadTypeByName("Primary-OneLane-OneWay");
                    currentRoad = CreateRoad("1w1lnRoad", oneWayRoadType, coord, 4f);
                    break;
                case "One-way Road (2 lanes)":
                    ERRoadType oneWayTwoLanesRoadType = roadNetwork.GetRoadTypeByName("Primary-TwoLane-OneWay");
                    currentRoad = CreateRoad("1w2lnRoad", oneWayTwoLanesRoadType, coord, 6f);
                    break;
                case "X Intersection":
                    rotationDegree = 0;
                    currentCrossing = CreateCrossing(ConnectionType.CrossingX, coord);
                    break;
                case "T Intersection":
                    rotationDegree = 0;
                    currentCrossing = CreateCrossing(ConnectionType.CrossingT, coord);
                    break;
                case "Traffic Light":
                    rotationDegree = 0;
                    currentTrafficLight = CreateTrafficLight(coord);
                    break;
                case "Traffic Spawner":
                    currentTrafficSpawner = CreateTrafficSpawner(coord);
                    break;
            }
        }
    }

    void OnMouseUp()
    {
        dragging = false;

        if (currentRoad != null)
        {
            ProcessNewRoad(currentRoad);
            RecreateITSLanes();
        }
        else if (currentCrossing != null)
        {
            ProcessNewConnection(currentCrossing);
            RecreateITSLanes();
        }

        currentRoad = null;
        currentCrossing = null;
        currentTrafficLight = null;
        currentTrafficSpawner = null;
    }

    void StartSimulation()
    {
        CustomTrafficSpawner[] trafficSpawners = FindObjectsOfType<CustomTrafficSpawner>();
        foreach (CustomTrafficSpawner spawner in trafficSpawners)
        {
            spawner.StartSpawner();
        }
    }

    void StopSimulation()
    {
        CustomTrafficSpawner[] trafficSpawners = FindObjectsOfType<CustomTrafficSpawner>();
        foreach (CustomTrafficSpawner spawner in trafficSpawners)
        {
            spawner.StopSpawner();
            spawner.DestroyAllCars();
        }
    }

    private void ProcessNewRoad(ERRoad currentRoad)
    {
        List<(int, ERConnection)> connections = GetConnectedConnectionsFromRoad(currentRoad);
        foreach ((int markerIndex, ERConnection connection) in connections)
        {
            if (markerIndex == 0)
            {
                int connectionIndex = connection.FindNearestConnectionIndex(currentRoad.GetMarkerPosition(0));
                currentRoad.ConnectToStart(connection, connectionIndex);
                // connection.SetCrosswalk(ERRoadSide.Both, connectionIndex, true);
                // connection.SetSidewalk(ERRoadSide.Both, connectionIndex, true);
            }
            else if (markerIndex == 1)
            {
                int connectionIndex = connection.FindNearestConnectionIndex(currentRoad.GetMarkerPosition(1));
                currentRoad.ConnectToEnd(connection, connectionIndex);
                // connection.SetCrosswalk(ERRoadSide.Both, connectionIndex, true);
                // connection.SetSidewalk(ERRoadSide.Both, connectionIndex, true);
            }
            roadNetwork.Refresh();
            connection.ResetLaneConnectors();
        }

        HashSet<ERRoad> connectedRoads = GetConnectedRoads(currentRoad);
        foreach (ERRoad connectedRoad in connectedRoads)
        {
            roadNetwork.ConnectRoads(currentRoad, connectedRoad);
        }
    }

    private void ProcessNewConnection(ERConnection connection)
    {
        List<(int, ERRoad)> roads = GetConnectedRoadsFromConnection(connection);
        foreach ((int markerIndex, ERRoad road) in roads)
        {
            if (markerIndex == 0)
            {
                int connectionIndex = connection.FindNearestConnectionIndex(road.GetMarkerPosition(0));
                road.ConnectToStart(connection, connectionIndex);
                // connection.SetCrosswalk(ERRoadSide.Both, connectionIndex, true);
                // connection.SetSidewalk(ERRoadSide.Both, connectionIndex, true);
            }
            else if (markerIndex == 1)
            {
                int connectionIndex = connection.FindNearestConnectionIndex(road.GetMarkerPosition(1));
                road.ConnectToEnd(connection, connectionIndex);
                // connection.SetCrosswalk(ERRoadSide.Both, connectionIndex, true);
                // connection.SetSidewalk(ERRoadSide.Both, connectionIndex, true);
            }
        }

        roadNetwork.Refresh();
        connection.ResetLaneConnectors();
    }

    private void RecreateITSLanes()
    {
        tsMainManager.Clear();
        CreateITSLanes(roadNetwork.GetRoadObjects());
        CreateITSConnections(roadNetwork.GetRoadObjects());
        tsMainManager.ProcessJunctions(false, 0f);
    }

    private Vector3? GetMouseWorldCoord()
    {
        Ray ray = Camera.main.ScreenPointToRay(Input.mousePosition);
        if (coll.Raycast(ray, out RaycastHit hit, 1000.0f))
        {
            Vector3 point = ray.GetPoint(hit.distance);
            point.y = 0.0f;
            return point;
        }

        return null;
    }

    private Vector3 SnapToGrid(Vector3 pos)
    {
        float factor = 2f;
        return new Vector3(Mathf.Round(pos.x / factor) * factor,
                             pos.y,
                             Mathf.Round(pos.z / factor) * factor);
    }

    private ERRoad CreateRoad(string name, ERRoadType roadType, Vector3 startCoord, float width = 6f)
    {
        ERRoad road = roadNetwork.CreateRoad(name, roadType);

        Debug.Log(roadType.roadWidth);
        road.SetWidth(roadType.roadWidth);
        road.AddMarker(startCoord);
        road.AddMarker(startCoord);
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

    private void UpdateCrossingCoord(ERConnection connection, Vector3 coord, float planeRotationDegree = 0)
    {
        connection.gameObject.transform.position = coord;
        connection.gameObject.transform.rotation = Quaternion.identity * Quaternion.Euler(0, planeRotationDegree, 0);
    }

    private GameObject CreateTrafficLight(Vector3 coord)
    {
        return Instantiate(trafficLightPrefab, coord, Quaternion.identity);
    }

    private void UpdateTrafficLightCoord(GameObject trafficLight, Vector3 coord, float planeRotationDegree = 0)
    {
        trafficLight.transform.position = coord;
        trafficLight.transform.rotation = Quaternion.identity * Quaternion.Euler(0, planeRotationDegree, 0);
    }

    public void ConnectLaneToTrafficLight(TSTrafficLight trafficLight, TSLaneInfo fromLane, TSLaneInfo toLane)
    {
        int fromLaneIndex = tsMainManager.lanes.FindIndex(fromLane);
        Debug.Log(fromLane.connectors.Length);
        foreach (var connector in fromLane.connectors)
        {
            Debug.Log(connector.NextLane == toLane);
            Debug.Log(toLane);
            if (connector.NextLane == toLane)
            {
                int connectorIndex = fromLane.connectors.FindIndex(connector);
                bool connectionExists = trafficLight.pointsNormalLight.Exists(x => x.lane == fromLaneIndex && x.connector == connectorIndex);
                if (!connectionExists)
                {
                    trafficLight.pointsNormalLight.Add(new TSTrafficLight.TSPointReference()
                    {
                        lane = fromLaneIndex,
                        connector = connectorIndex,
                        point = 0
                    });
                }
            }
        }
    }

    public void DisconnectLaneFromTrafficLight(TSTrafficLight trafficLight, TSLaneInfo fromLane, TSLaneInfo toLane)
    {
        int fromLaneIndex = tsMainManager.lanes.FindIndex(fromLane);
        foreach (var connector in fromLane.connectors)
        {
            if (connector.NextLane == toLane)
            {
                int connectorIndex = fromLane.connectors.FindIndex(connector);
                List<TSTrafficLight.TSPointReference> pointReferences = trafficLight.pointsNormalLight.FindAll(x => x.lane == fromLaneIndex && x.connector == connectorIndex);
                foreach (TSTrafficLight.TSPointReference pointReference in pointReferences)
                {
                    trafficLight.pointsNormalLight.Remove(pointReference);
                }
            }
        }
    }

    public List<TSLaneInfo> GetTrafficLightConnectedLanes(GameObject trafficLight)
    {
        var outList = new List<TSLaneInfo>();
        TSTrafficLight trafficLightScript = trafficLight.GetComponent<TSTrafficLight>();
        foreach (var points in trafficLightScript.pointsNormalLight)
        {
            TSLaneInfo lane = tsMainManager.lanes[points.lane];
            outList.Add(lane);
        }
        return outList;
    }

    public GameObject CreateTrafficSpawner(Vector3 coord, float secondsBetweenSpawn = 1f)
    {
        GameObject trafficSpawnerGameObject = new GameObject("Traffic Spawner");
        trafficSpawnerGameObject.transform.position = coord + new Vector3(0, 0.01f, 0); // Add to prevent clash with the plane
        CustomTrafficSpawner trafficSpawner = trafficSpawnerGameObject.AddComponent<CustomTrafficSpawner>();
        trafficSpawner.vehicles = vehicles;
        trafficSpawner.secondsBetweenCars = secondsBetweenSpawn;

        DrawRadius drawRadius = trafficSpawnerGameObject.AddComponent<DrawRadius>();
        drawRadius.radius = 0.0001f;
        return trafficSpawnerGameObject;
    }

    public void UpdateTrafficSpawnerRadius(GameObject trafficSpawnerGameObject, Vector3 endCoord)
    {
        float radius = (trafficSpawnerGameObject.transform.position - endCoord).magnitude;
        CustomTrafficSpawner trafficSpawner = trafficSpawnerGameObject.GetComponent<CustomTrafficSpawner>();
        trafficSpawner.radius = radius;

        DrawRadius drawRadius = trafficSpawnerGameObject.GetComponent<DrawRadius>();
        drawRadius.radius = radius;

        Debug.Log(radius);
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

    private void CreateITSLanes(ERRoad[] roads, bool reverse = false, float tolerance = 0.4f, int laneWidth = 2)
    {
        roadLaneMap.Clear();
        foreach (ERRoad road in roads)
        {
            roadLaneMap[road] = new List<TSLaneInfo>();
            var laneCount = road.GetLaneCount();
            Debug.Log(laneCount);
            for (int laneIndex = 0; laneIndex < laneCount; laneIndex++)
            {
                var laneData = road.GetLaneData(laneIndex);
                Debug.Log(road.roadScript.laneData.Count);
                Debug.Log(laneData);
                var points = (reverse ? laneData.points.Reverse() : laneData.points).ToArray();
                tsMainManager.AddLane<TSLaneInfo>(points, tolerance);
                TSLaneInfo laneInfo = tsMainManager.lanes.Last();
                laneInfo.laneWidth = laneWidth;
                roadLaneMap[road].Add(laneInfo);
            }
        }
    }

    private void CreateITSConnections(ERRoad[] roads)
    {
        foreach (ERRoad road in roads)
        {
            var laneCount = road.GetLaneCount();
            for (int laneIndex = 0; laneIndex < laneCount; laneIndex++)
            {
                ERConnection firstConnection = road.GetConnectionAtStart(out int firstConnectionIndex);
                if (firstConnection != null) AddITSConnection(firstConnection, firstConnectionIndex, laneIndex);

                ERConnection secondConnection = road.GetConnectionAtEnd(out int secondConnectionIndex);
                if (secondConnection != null) AddITSConnection(secondConnection, secondConnectionIndex, laneIndex);
            }
        }
    }

    private void AddITSConnection(ERConnection connection, int connectionIndex, int laneIndex, bool reverse = false)
    {
        var data = connection.GetLaneData(connectionIndex, laneIndex);
        if (data == null) return;

        foreach (var laneConnector in data)
        {
            Debug.Log(laneConnector);
            var laneFromPoint = reverse ? laneConnector.points.Last() : laneConnector.points.First();
            var laneToPoint = reverse ? laneConnector.points.First() : laneConnector.points.Last();
            var laneFrom = tsMainManager.lanes.FindNearestLastPoint(laneFromPoint);
            var laneTo = tsMainManager.lanes.FindNearestFirstPoint(laneToPoint);
            var points = (reverse ? laneConnector.points.Reverse() : laneConnector.points).ToArray();
            tsMainManager.AddConnector<TSLaneConnector>(laneFrom, laneTo, points);
        }
    }
}
