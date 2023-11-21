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
    public ERRoadNetwork roadNetwork;
    public GameObject itsManager, trafficLightPrefab;
    public bool rightHandDriving = false;

    [SerializeField] public CustomTrafficSpawner.VehicleConfig[] vehicles;

    private TSMainManager tsMainManager;
    private Dictionary<ERRoad, List<TSLaneInfo>> roadLaneMap = new Dictionary<ERRoad, List<TSLaneInfo>>();
    private bool simulationEnabled = false;

    public enum ConnectionType
    {
        CrossingXTwoLane,
        CrossingTTwoLane,
        CrossingXFourLane,
        CrossingTFourLane
    }

    [System.Serializable]
    public class TrafficLightConfig
    {
        public TSTrafficLight.LightType type;
        public int duration;
    }

    void Start()
    {
        roadNetwork = new ERRoadNetwork();
        ERModularBase modularBase = roadNetwork.roadNetwork;
        modularBase.displayLaneData = true; // Required to allow iTS to connect lanes at intersections
        modularBase.rightHandDriving = rightHandDriving ? 1 : 0;
        roadNetwork.LoadConnections();
        tsMainManager = itsManager.GetComponent<TSMainManager>();
    }

    public void StartSimulation()
    {
        simulationEnabled = true;
        CustomTrafficSpawner[] trafficSpawners = FindObjectsOfType<CustomTrafficSpawner>();
        foreach (CustomTrafficSpawner spawner in trafficSpawners)
        {
            spawner.StartSpawner();
        }
    }

    public void StopSimulation()
    {
        simulationEnabled = false;
        CustomTrafficSpawner[] trafficSpawners = FindObjectsOfType<CustomTrafficSpawner>();
        foreach (CustomTrafficSpawner spawner in trafficSpawners)
        {
            spawner.StopSpawner();
            spawner.DestroyAllCars();
        }
    }

    public void ProcessNewRoad(ERRoad currentRoad)
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
            roadNetwork.Refresh();
            connection.ResetLaneConnectors();
        }

        HashSet<ERRoad> connectedRoads = GetConnectedRoads(currentRoad);
        foreach (ERRoad connectedRoad in connectedRoads)
        {
            roadNetwork.ConnectRoads(currentRoad, connectedRoad);
        }
        RecreateITSLanes();
    }

    public void ProcessNewConnection(ERConnection connection)
    {
        List<(int, ERRoad)> roads = GetConnectedRoadsFromConnection(connection);
        foreach ((int markerIndex, ERRoad road) in roads)
        {
            if (markerIndex == 0)
            {
                int connectionIndex = connection.FindNearestConnectionIndex(road.GetMarkerPosition(0));
                road.ConnectToStart(connection, connectionIndex);
            }
            else if (markerIndex == 1)
            {
                int connectionIndex = connection.FindNearestConnectionIndex(road.GetMarkerPosition(1));
                road.ConnectToEnd(connection, connectionIndex);
            }
        }

        roadNetwork.Refresh();
        connection.ResetLaneConnectors();
        RecreateITSLanes();
    }

    public void RecreateITSLanes()
    {
        tsMainManager.Clear();
        CreateITSLanes(roadNetwork.GetRoadObjects());
        CreateITSConnections(roadNetwork.GetRoadObjects());
        tsMainManager.ProcessJunctions(false, 0f);
    }

    public ERRoad CreateRoad(string name, ERRoadType roadType, Vector3 startCoord, float width = 6f)
    {
        ERRoad road = roadNetwork.CreateRoad(name, roadType);
        road.SetWidth(roadType.roadWidth);
        road.AddMarker(startCoord);
        road.AddMarker(startCoord);
        return road;
    }

    public void UpdateRoadEndCoord(ERRoad road, Vector3 coord)
    {
        road.DeleteMarker(1);
        road.InsertMarker(coord);
    }

    public ERConnection CreateCrossing(ConnectionType connectionType, Vector3 coord)
    {
        String prefabName = "X-2Lane";
        switch (connectionType)
        {
            case ConnectionType.CrossingTTwoLane:
                prefabName = "T-2Lane";
                break;
            case ConnectionType.CrossingXTwoLane:
                prefabName = "X-2Lane";
                break;
            case ConnectionType.CrossingTFourLane:
                prefabName = "T-4Lane";
                break;
            case ConnectionType.CrossingXFourLane:
                prefabName = "X-4Lane";
                break;
        }

        ERConnection connectionPrefab = roadNetwork.GetConnectionPrefabByName(prefabName);
        ERConnection connection = roadNetwork.InstantiateConnection(connectionPrefab, "Intersection", coord, Vector3.zero);
        return connection;
    }

    public void UpdateCrossingCoord(ERConnection connection, Vector3 coord, float planeRotationDegree = 0)
    {
        connection.gameObject.transform.position = coord;
        connection.gameObject.transform.rotation = Quaternion.identity * Quaternion.Euler(0, planeRotationDegree, 0);
    }

    public GameObject CreateTrafficLight(Vector3 coord, bool yellowLightsStopTraffic = true)
    {
        GameObject trafficLightObj = Instantiate(trafficLightPrefab, coord, Quaternion.identity);
        TSTrafficLight trafficLight = trafficLightObj.GetComponent<TSTrafficLight>();
        trafficLight.yellowLightsStopTraffic = yellowLightsStopTraffic;
        return trafficLightObj;
    }

    public void UpdateTrafficLightCoord(GameObject trafficLight, Vector3 coord, float planeRotationDegree = 0)
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

    public void SetTrafficLightDurations(TSTrafficLight trafficLight, TrafficLightConfig[] configs)
    {
        trafficLight.lights.Clear();
        foreach (TrafficLightConfig config in configs)
        {
            trafficLight.lights.Add(new TSTrafficLight.TSLight()
            {
                lightType = config.type,
                lightTime = config.duration,
                lightMeshRenderer = trafficLight.gameObject.GetComponentInChildren<MeshRenderer>()
            });
        }
    }

    public GameObject CreateTrafficSpawner(Vector3 coord, float secondsBetweenSpawn = 1f)
    {
        GameObject trafficSpawnerGameObject = new GameObject("Traffic Spawner");
        trafficSpawnerGameObject.transform.position = coord + new Vector3(0, 0.01f, 0); // Add to prevent clash with the plane
        CustomTrafficSpawner trafficSpawner = trafficSpawnerGameObject.AddComponent<CustomTrafficSpawner>();
        trafficSpawner.vehicles = vehicles;
        trafficSpawner.secondsBetweenCars = secondsBetweenSpawn;

        if (simulationEnabled) {
            trafficSpawner.StartSpawner();
        }

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

    public void UpdateTrafficSpawnerInterval(CustomTrafficSpawner spawner, float secondsBetweenCars)
    {
        spawner.secondsBetweenCars = secondsBetweenCars;
    }

    public HashSet<ERRoad> GetConnectedRoads(ERRoad currentRoad)
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

    private List<(int, ERConnection)> GetConnectedConnectionsFromRoad(ERRoad currentRoad, float maxDistance = 3f)
    {
        Dictionary<ERConnection, int> connectionsMap = new Dictionary<ERConnection, int>();
        foreach (ERConnection connection in roadNetwork.GetConnections())
        {
            foreach (Vector3 position in connection.GetConnectionWorldPositions())
            {
                if ((position - currentRoad.GetMarkerPosition(0)).magnitude <= maxDistance)
                {
                    connectionsMap[connection] = 0;
                }
                else if ((position - currentRoad.GetMarkerPosition(1)).magnitude <= maxDistance)
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

    private List<(int, ERRoad)> GetConnectedRoadsFromConnection(ERConnection connection, float maxDistance = 3f)
    {
        Dictionary<ERRoad, int> roadsMap = new Dictionary<ERRoad, int>();
        foreach (ERRoad road in roadNetwork.GetRoadObjects())
        {
            foreach (Vector3 position in connection.GetConnectionWorldPositions())
            {
                // float distThreshold = 3f;
                if ((position - road.GetMarkerPosition(0)).magnitude <= maxDistance)
                {
                    roadsMap[road] = 0;
                }
                if ((position - road.GetMarkerPosition(1)).magnitude <= maxDistance)
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
